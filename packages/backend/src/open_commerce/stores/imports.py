"""Tenant-scoped encrypted catalog review and idempotent indexing confirmation."""

import asyncio
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import catalog_index_status, stage_catalog_upload
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.manager_agent.errors import ManagerDatasetProfileError
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.crypto import decrypt, encrypt
from open_commerce.stores.events import ImportMilestone, record_import_milestone
from open_commerce.stores.import_models import ImportMapping, ImportReview
from open_commerce.stores.import_validation import MAX_UPLOAD, validate_import
from open_commerce.stores.models import StoreError


def review_fingerprint(record: CatalogImportRecord) -> str:
    """Identify persisted review inputs, independent of parser-generated timestamps."""
    return canonical_hash(
        {
            "domain": "catalog-import-review-v1",
            "tenant_id": record.tenant_id,
            "import_id": record.id,
            "upload_sha256": sha256(record.encrypted_data).hexdigest(),
            "mapping": record.mapping,
            "currency": record.currency,
        }
    )


class CatalogImportService:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def upload(self, tenant: UUID, filename: str, data: bytes) -> ImportReview:
        if len(data) > MAX_UPLOAD:
            raise StoreError("Catalog exceeds 20 MiB.", 413)
        try:
            csv_text = data.decode("utf-8-sig")
            profile, _, _ = await asyncio.to_thread(validate_import, csv_text, filename)
        except (UnicodeError, ManagerDatasetProfileError) as exc:
            raise StoreError(
                str(exc) if isinstance(exc, ManagerDatasetProfileError) else "Use UTF-8 CSV."
            ) from exc
        import_id = uuid4()
        record = CatalogImportRecord(
            id=import_id,
            tenant_id=tenant,
            filename=filename[:255],
            encrypted_data=encrypt(
                self.database.settings, data, context=f"import:{tenant}:{import_id}"
            ),
            expires_at=utc_now() + timedelta(hours=24),
            created_at=utc_now(),
            mapping=profile.detected_mappings,
            currency=None,
            status="mapping",
            report={},
        )
        async with self.database.transaction(tenant, write=True) as session:
            session.add(record)
            await record_import_milestone(
                session, tenant, ImportMilestone(kind="products_uploaded", import_id=import_id)
            )
        return await self.review(tenant, import_id)

    async def get(
        self, session: AsyncSession, tenant: UUID, import_id: UUID
    ) -> CatalogImportRecord:
        record = await session.scalar(
            select(CatalogImportRecord).where(
                CatalogImportRecord.tenant_id == tenant,
                CatalogImportRecord.id == import_id,
            )
        )
        if record is None:
            raise StoreError("Import not found.", 404)
        return record

    def data(self, record: CatalogImportRecord) -> str:
        if record.expires_at <= utc_now() or not record.encrypted_data:
            raise StoreError("Upload expired. Upload the CSV again to resume review.", 410)
        return decrypt(
            self.database.settings,
            record.encrypted_data,
            context=f"import:{record.tenant_id}:{record.id}",
        ).decode("utf-8-sig")

    async def review(
        self, tenant: UUID, import_id: UUID, mapping: ImportMapping | None = None
    ) -> ImportReview:
        async with self.database.transaction(tenant, write=mapping is not None) as session:
            record = await self.get(session, tenant, import_id)
            if record.status in {"cancelled", "confirmed"}:
                if mapping is not None:
                    raise StoreError("This import is closed; upload a replacement to edit.", 409)
                report = ImportReview.model_validate(record.report)
                report.status = record.status
                if record.catalog_id:
                    report.indexing = await catalog_index_status(
                        session, tenant_id=tenant, integration_id=record.catalog_id
                    )
                return report
            assignments = mapping or ImportMapping(mapping=record.mapping, currency=record.currency)
            profile, products, errors = await asyncio.to_thread(
                validate_import, self.data(record), record.filename, assignments
            )
            if mapping:
                record.mapping = mapping.mapping
                record.currency = mapping.currency
            report = ImportReview(
                review_fingerprint=review_fingerprint(record),
                sample_data=bool(record.report.get("sample_data")),
                id=record.id,
                filename=record.filename,
                status="mapping" if errors else "review",
                expires_at=record.expires_at,
                columns=profile.columns,
                mapping=assignments.mapping,
                currency=assignments.currency,
                row_count=profile.row_count,
                product_count=len(products),
                errors=errors,
                warnings=profile.warnings[:100],
                products=[p.model_copy(update={"primary_image_url": None}) for p in products[:20]],
            )
            if mapping:
                record.status = report.status
                record.report = report.model_copy(update={"products": []}).model_dump(mode="json")
                if not errors:
                    await record_import_milestone(
                        session,
                        tenant,
                        ImportMilestone(
                            kind="products_reviewed",
                            import_id=import_id,
                            product_count=len(products),
                        ),
                    )
            return report

    async def confirm(
        self, tenant: UUID, import_id: UUID, key: str, *, expected_review_fingerprint: str
    ) -> ImportReview:
        async with self.database.transaction(tenant, write=True) as session:
            receipts = RequestRepository(session, tenant)
            request = {
                "id": str(import_id),
                "expected_review_fingerprint": expected_review_fingerprint,
            }
            cached = await receipts.replay(scope="import:confirm", key=key, request=request)
            if cached:
                return ImportReview.model_validate(cached)
            record = await self.get(session, tenant, import_id)
            if record.status == "confirmed":
                report = ImportReview.model_validate(record.report)
                if (
                    report.review_fingerprint is None
                    or report.review_fingerprint != expected_review_fingerprint
                ):
                    raise StoreError(
                        "This import was already confirmed from another review. "
                        "Review the latest mapping.",
                        409,
                    )
                receipts.remember(scope="import:confirm", key=key, request=request, response=report)
                return report
            if record.status == "cancelled":
                raise StoreError("Import cancelled.", 409)
            data = self.data(record)
            accepted_fingerprint = review_fingerprint(record)
            if expected_review_fingerprint != accepted_fingerprint:
                raise StoreError(
                    "The import review changed. Review the latest mapping before confirming.", 409
                )
            profile, products, errors = await asyncio.to_thread(
                validate_import,
                data,
                record.filename,
                ImportMapping(mapping=record.mapping, currency=record.currency),
            )
            if errors:
                raise StoreError("Correct the row errors and mapping before confirming.", 409)
            for product in products:
                product.attributes["safe_image_pending"] = bool(product.primary_image_url)
            index = await stage_catalog_upload(
                session,
                tenant_id=tenant,
                filename=record.filename,
                source_version=canonical_hash(products),
                products=products,
            )
            record.catalog_id = index.catalog_id
            from open_commerce.persistence.models.integrations import Integration

            integration = await session.scalar(
                select(Integration).where(
                    Integration.tenant_id == tenant, Integration.id == index.catalog_id
                )
            )
            if integration is not None:
                integration.non_secret_config = {
                    **integration.non_secret_config,
                    "sample_data": bool(record.report.get("sample_data")),
                }
            record.status = "confirmed"
            report = ImportReview(
                review_fingerprint=accepted_fingerprint,
                sample_data=bool(record.report.get("sample_data")),
                id=record.id,
                filename=record.filename,
                status="confirmed",
                expires_at=record.expires_at,
                columns=profile.columns,
                mapping=record.mapping,
                currency=record.currency,
                row_count=profile.row_count,
                product_count=len(products),
                warnings=profile.warnings[:100],
                indexing=index,
                catalog_id=index.catalog_id,
            )
            record.encrypted_data = b""
            record.report = report.model_dump(mode="json")
            await record_import_milestone(
                session,
                tenant,
                ImportMilestone(
                    kind="products_confirmed", import_id=import_id, product_count=len(products)
                ),
            )
            receipts.remember(scope="import:confirm", key=key, request=request, response=report)
            return report

    async def cancel(self, tenant: UUID, import_id: UUID) -> ImportReview:
        async with self.database.transaction(tenant, write=True) as session:
            record = await self.get(session, tenant, import_id)
            if record.status == "confirmed":
                raise StoreError(
                    "Already confirmed. Keep the current shared catalog or review its replacement.",
                    409,
                )
            record.encrypted_data = b""
            record.status = "cancelled"
            report = ImportReview(
                id=record.id,
                filename=record.filename,
                status="cancelled",
                expires_at=record.expires_at,
                columns=[],
                mapping={},
                currency=None,
                row_count=0,
            )
            record.report = report.model_dump(mode="json")
            return report

    async def retry(self, tenant: UUID, import_id: UUID) -> ImportReview:
        async with self.database.transaction(tenant, write=True) as session:
            record = await self.get(session, tenant, import_id)
            if not record.catalog_id:
                raise StoreError("Confirm a valid import first.", 409)
            await session.execute(
                update(CatalogIndexJob)
                .where(
                    CatalogIndexJob.tenant_id == tenant,
                    CatalogIndexJob.integration_id == record.catalog_id,
                    CatalogIndexJob.status == "failed",
                )
                .values(status="queued", failures=0, available_at=utc_now(), safe_error=None)
            )
        return await self.review(tenant, import_id)

    async def cleanup(self, tenant: UUID) -> None:
        async with self.database.transaction(tenant, write=True) as session:
            await session.execute(
                update(CatalogImportRecord)
                .where(
                    CatalogImportRecord.tenant_id == tenant,
                    CatalogImportRecord.expires_at <= utc_now(),
                )
                .values(encrypted_data=b"")
            )
