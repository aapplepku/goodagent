"""Publication and private previews require an exact, verified store catalog."""

import json
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.catalog.persistence import catalog_index_status
from open_commerce.core.types import StrictDomainModel, utc_now
from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.models.store_setup import (
    AuthTicketRecord,
    SetupEventRecord,
    StoreSetupRecord,
)
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.stores.auth import store_profile
from open_commerce.stores.models import (
    PreviewResponse,
    PublicationRequest,
    StoreError,
    StoreProfile,
    StoreProfileUpdate,
)


class StoreImageIssue(StrictDomainModel):
    product_id: str
    title: str
    next_action: str = "Replace this product's image URL in a new catalog upload."


class StoreReadiness(StrictDomainModel):
    store: StoreProfile
    indexing: CatalogIndexStatus
    image_failures: int
    image_issues: list[StoreImageIssue] = Field(default_factory=list)
    image_issues_truncated: bool = False
    latest_import_id: UUID | None
    checklist: dict[str, bool]


async def store_records(session: AsyncSession, tenant_id: UUID) -> tuple[Tenant, StoreSetupRecord]:
    row = (
        await session.execute(
            select(Tenant, StoreSetupRecord).join(StoreSetupRecord).where(Tenant.id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise StoreError("Store setup not found.", 404)
    return row[0], row[1]


async def verified_catalog(session: AsyncSession, tenant: UUID, catalog: UUID) -> None:
    source = await session.scalar(
        select(CatalogImportRecord.id)
        .where(
            CatalogImportRecord.tenant_id == tenant,
            CatalogImportRecord.catalog_id == catalog,
            CatalogImportRecord.status == "confirmed",
        )
        .limit(1)
    )
    if source is None:
        raise StoreError("Review this catalog through store setup before sharing it.", 409)
    job = await session.scalar(
        select(CatalogIndexJob).where(
            CatalogIndexJob.tenant_id == tenant,
            CatalogIndexJob.integration_id == catalog,
            CatalogIndexJob.status == "ready",
        )
    )
    if job is None or job.product_count <= 0 or job.indexed_product_count != job.product_count:
        raise StoreError(
            "Wait for this catalog version to finish verification before previewing or sharing.",
            409,
        )


class StoreSetupService:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def readiness(self, tenant: UUID) -> StoreReadiness:
        async with self.database.transaction(tenant) as session:
            owner, setup = await store_records(session, tenant)
            latest = await session.scalar(
                select(CatalogImportRecord)
                .where(
                    CatalogImportRecord.tenant_id == tenant,
                    or_(
                        CatalogImportRecord.status == "confirmed",
                        CatalogImportRecord.status.in_(["mapping", "review"])
                        & (CatalogImportRecord.expires_at > utc_now()),
                    ),
                )
                .order_by(CatalogImportRecord.created_at.desc(), CatalogImportRecord.id.desc())
                .limit(1)
            )
            index = CatalogIndexStatus()
            if latest is not None:
                if latest.status == "confirmed" and latest.catalog_id is not None:
                    candidate = await catalog_index_status(
                        session, tenant_id=tenant, integration_id=latest.catalog_id
                    )
                    if candidate.catalog_id == latest.catalog_id:
                        index = candidate
            elif (
                await session.scalar(
                    select(CatalogImportRecord.id)
                    .where(CatalogImportRecord.tenant_id == tenant)
                    .limit(1)
                )
                is None
            ):
                # Direct legacy catalogs have no reviewed-import history to resume.
                index = await catalog_index_status(session, tenant_id=tenant)
            has_catalog = index.catalog_id is not None
            failures = 0
            issues: list[Product] = []
            if has_catalog:
                failures = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(Product)
                        .where(
                            Product.tenant_id == tenant,
                            Product.integration_id == index.catalog_id,
                            Product.attributes["image_failed"].as_boolean().is_(True),
                        )
                    )
                    or 0
                )
                issues = list(
                    await session.scalars(
                        select(Product)
                        .where(
                            Product.tenant_id == tenant,
                            Product.integration_id == index.catalog_id,
                            Product.attributes["image_failed"].as_boolean().is_(True),
                        )
                        .order_by(Product.source_product_id)
                        .limit(100)
                    )
                )
            same = setup.readiness.get("catalog_id") == str(index.catalog_id)
            return StoreReadiness(
                store=store_profile(owner, setup),
                indexing=index,
                image_failures=failures,
                image_issues=[
                    StoreImageIssue(product_id=p.source_product_id, title=p.title[:240])
                    for p in issues
                ],
                image_issues_truncated=failures > len(issues),
                latest_import_id=latest.id if latest is not None else None,
                checklist={
                    "catalog_verified": has_catalog
                    and index.status == "ready"
                    and index.product_count > 0
                    and index.indexed_product_count == index.product_count,
                    "images_reviewed": has_catalog
                    and (
                        failures == 0 or (same and setup.readiness.get("images_reviewed") is True)
                    ),
                    "search_tested": has_catalog
                    and setup.readiness.get("tested_catalog_id") == str(index.catalog_id),
                    "ai_verified": setup.readiness.get("ai_verified") is True,
                    "demo_checkout_acknowledged": setup.readiness.get("checkout_acknowledged")
                    is True,
                    "sharing_enabled": setup.sharing_enabled,
                },
            )

    async def profile(self, tenant: UUID, payload: StoreProfileUpdate) -> StoreProfile:
        async with self.database.transaction(tenant, write=True) as session:
            owner, setup = await store_records(session, tenant)
            owner.display_name = payload.name.strip()
            owner.default_currency = payload.currency
            setup.description = payload.description
            setup.goal = payload.goal
            return store_profile(owner, setup)

    async def preview(self, tenant: UUID, catalog: UUID) -> PreviewResponse:
        async with self.database.transaction(tenant, write=True) as session:
            owner, _ = await store_records(session, tenant)
            await verified_catalog(session, tenant, catalog)
            token = secrets.token_urlsafe(32)
            expires = utc_now() + timedelta(minutes=30)
            session.add(
                SetupEventRecord(
                    id=uuid4(),
                    tenant_id=tenant,
                    kind="preview_created",
                    event_key=f"preview:{uuid4()}",
                    details={"catalog_id": str(catalog)},
                    occurred_at=utc_now(),
                )
            )
            session.add(
                AuthTicketRecord(
                    token_hash=session_token_hash(token),
                    purpose="shopper_preview",
                    tenant_id=tenant,
                    payload=json.dumps({"catalog_id": str(catalog)}).encode(),
                    expires_at=expires,
                    created_at=utc_now(),
                )
            )
            return PreviewResponse(
                token=token, store_slug=owner.slug, catalog_id=catalog, expires_at=expires
            )

    async def share(self, tenant: UUID, payload: PublicationRequest, key: str) -> StoreProfile:
        async with self.database.transaction(tenant, write=True) as session:
            receipts = RequestRepository(session, tenant)
            cached = await receipts.replay(scope="store:publish", key=key, request=payload)
            if cached:
                return StoreProfile.model_validate(cached)
            owner, setup = await store_records(session, tenant)
            previous = setup.published_catalog_id
            if payload.enabled:
                await verified_catalog(session, tenant, payload.catalog_id)
                if not payload.acknowledge_demo_checkout or not payload.acknowledge_image_issues:
                    raise StoreError(
                        "Acknowledge image review and demo-only checkout before sharing.", 409
                    )
                if setup.readiness.get("tested_catalog_id") != str(payload.catalog_id):
                    raise StoreError(
                        "Test shopper search in this version's private preview before sharing.", 409
                    )
                setup.published_catalog_id = payload.catalog_id
                from open_commerce.persistence.models.integrations import Integration

                integration = await session.scalar(
                    select(Integration).where(
                        Integration.tenant_id == tenant, Integration.id == payload.catalog_id
                    )
                )
                setup.sample_data = bool(
                    integration and integration.non_secret_config.get("sample_data")
                )
                setup.readiness = {
                    **setup.readiness,
                    "catalog_id": str(payload.catalog_id),
                    "images_reviewed": True,
                    "search_tested": True,
                    "checkout_acknowledged": True,
                }
            setup.sharing_enabled = payload.enabled
            session.add(
                SetupEventRecord(
                    id=uuid4(),
                    tenant_id=tenant,
                    kind="sharing_enabled" if payload.enabled else "sharing_disabled",
                    event_key=f"publish:{key}",
                    occurred_at=utc_now(),
                    details={
                        "catalog_id": str(payload.catalog_id),
                        "previous_catalog_id": str(previous) if previous else None,
                        "policy": "owner_explicit_approval",
                        "rollback": "disable sharing or republish the prior verified version",
                    },
                )
            )
            result = store_profile(owner, setup)
            receipts.remember(scope="store:publish", key=key, request=payload, response=result)
            return result
