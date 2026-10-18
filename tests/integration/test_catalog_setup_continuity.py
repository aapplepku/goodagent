"""Setup actions stay attached to one reviewed import in real PostgreSQL."""

import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.catalog.persistence import activate_catalog
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.import_models import ImportReview
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.models import PublicationRequest
from open_commerce.stores.setup import StoreSetupService
from tests.integration.catalog_browser_fixture import fail_replacement

pytestmark = pytest.mark.integration

CSV_A = (
    b"product_id,title,price,currency,inventory_quantity,updated_at\n"
    b"original,Original mug,10,USD,20,2026-10-01T00:00:00Z\n"
)
CSV_B = CSV_A.replace(b"original,Original mug,10", b"replacement,Replacement bowl,20")


@dataclass
class StoreFixture:
    database: RuntimeDatabase
    tenant: UUID
    imports: CatalogImportService
    setup: StoreSetupService

    async def confirmed(self, name: str, content: bytes, *, ready: bool = True) -> ImportReview:
        review = await self.imports.upload(self.tenant, name, content)
        assert not review.errors
        assert review.review_fingerprint
        result = await self.imports.confirm(
            self.tenant,
            review.id,
            f"confirm-{review.id}",
            expected_review_fingerprint=review.review_fingerprint,
        )
        assert result.catalog_id and result.indexing
        # Persist the actual post-index state. Search/vector execution is separately
        # covered by browser/indexing tests; this fixture exercises SQL selection.
        if ready:
            async with self.database.transaction(self.tenant, write=True) as session:
                await activate_catalog(
                    session,
                    tenant_id=self.tenant,
                    integration_id=result.catalog_id,
                    indexed_count=result.product_count,
                    completed_at=utc_now(),
                )
        return await self.imports.review(self.tenant, review.id)

    async def mark_tested(self, catalog: UUID) -> None:
        async with self.database.transaction(self.tenant, write=True) as session:
            setup = await session.scalar(
                select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == self.tenant)
            )
            assert setup
            setup.readiness = {**setup.readiness, "tested_catalog_id": str(catalog)}

    async def publish(self, catalog: UUID, key: str) -> None:
        await self.mark_tested(catalog)
        await self.setup.share(
            self.tenant,
            PublicationRequest(
                catalog_id=catalog,
                enabled=True,
                acknowledge_demo_checkout=True,
                acknowledge_image_issues=True,
            ),
            key,
        )


@pytest.fixture
async def catalog_store(integration_settings: Settings) -> AsyncIterator[StoreFixture]:
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"c" * 32).decode()),
        }
    )
    database = RuntimeDatabase(settings)
    try:
        owner, _ = await MerchantAuthService(database).oidc_identity(
            "https://catalog-continuity-fixture.invalid", uuid4().hex
        )
        yield StoreFixture(
            database, owner.store.id, CatalogImportService(database), StoreSetupService(database)
        )
    finally:
        await database.close()


async def test_reconfirmed_older_catalog_is_the_preview_and_publication_candidate(
    catalog_store: StoreFixture,
) -> None:
    store = catalog_store
    a = await store.confirmed("original-a.csv", CSV_A)
    assert a.catalog_id
    await store.publish(a.catalog_id, "publish-a")
    b = await store.confirmed("replacement-b.csv", CSV_B)
    assert b.catalog_id and b.catalog_id != a.catalog_id
    await store.mark_tested(b.catalog_id)
    c = await store.confirmed("restore-a.csv", CSV_A, ready=False)
    assert c.catalog_id == a.catalog_id
    readiness = await store.setup.readiness(store.tenant)
    assert readiness.latest_import_id == c.id
    assert readiness.store.published_catalog_id == a.catalog_id
    assert readiness.indexing.catalog_id == c.catalog_id
    assert readiness.indexing.status == "ready"
    assert not readiness.checklist["search_tested"]
    preview = await store.setup.preview(store.tenant, readiness.indexing.catalog_id)
    assert preview.catalog_id == a.catalog_id
    await store.publish(readiness.indexing.catalog_id, "keep-reviewed-a")
    final = await store.setup.readiness(store.tenant)
    assert final.store.published_catalog_id == a.catalog_id
    async with store.database.transaction(store.tenant) as session:
        jobs = list(
            await session.scalars(
                select(CatalogIndexJob).where(CatalogIndexJob.tenant_id == store.tenant)
            )
        )
    assert len(jobs) == 2  # Reuse must not manufacture a newer A job.


@pytest.mark.parametrize("replacement", ["cancelled", "expired"])
async def test_closed_replacement_resumes_failed_import_for_retry(
    catalog_store: StoreFixture, replacement: str
) -> None:
    store = catalog_store
    a = await store.confirmed("published-a.csv", CSV_A)
    assert a.catalog_id
    await store.publish(a.catalog_id, "publish-a")
    b = await store.confirmed("failed-b.csv", CSV_B, ready=False)
    assert b.catalog_id
    async with store.database.transaction(store.tenant, write=True) as session:
        job = await session.scalar(
            select(CatalogIndexJob).where(
                CatalogIndexJob.tenant_id == store.tenant,
                CatalogIndexJob.integration_id == b.catalog_id,
            )
        )
        assert job
        job.status, job.failures = "failed", 3
        job.safe_error = {"code": "synthetic_index_failure"}
    c = await store.imports.upload(store.tenant, "abandoned-c.csv", CSV_A)
    if replacement == "cancelled":
        await store.imports.cancel(store.tenant, c.id)
    else:
        async with store.database.transaction(store.tenant, write=True) as session:
            row = await store.imports.get(session, store.tenant, c.id)
            row.expires_at = utc_now() - timedelta(seconds=1)
        await store.imports.cleanup(store.tenant)
    readiness = await store.setup.readiness(store.tenant)
    assert readiness.latest_import_id == b.id
    assert readiness.indexing.catalog_id == b.catalog_id
    assert readiness.indexing.status == "failed"
    retry = await store.imports.retry(store.tenant, readiness.latest_import_id)
    assert retry.id == b.id and retry.indexing and retry.indexing.status == "queued"
    final = await store.setup.readiness(store.tenant)
    assert final.store.published_catalog_id == a.catalog_id
    assert final.store.sharing_enabled
    async with store.database.transaction(store.tenant) as session:
        closed = await store.imports.get(session, store.tenant, c.id)
        assert closed.catalog_id is None and not closed.encrypted_data
        assert closed.status == ("cancelled" if replacement == "cancelled" else "mapping")


async def test_pending_upload_does_not_borrow_another_catalogs_readiness(
    catalog_store: StoreFixture,
) -> None:
    store = catalog_store
    a = await store.confirmed("published-a.csv", CSV_A)
    assert a.catalog_id
    await store.publish(a.catalog_id, "publish-a")
    pending = await store.imports.upload(store.tenant, "review-b.csv", CSV_B)
    result = await store.setup.readiness(store.tenant)
    assert result.latest_import_id == pending.id
    assert result.indexing.catalog_id is None and result.indexing.status == "not_configured"
    assert not result.checklist["catalog_verified"]
    assert not result.checklist["search_tested"]
    assert not result.checklist["images_reviewed"]
    assert result.store.published_catalog_id == a.catalog_id


async def test_confirmed_import_outlives_staging_deadline_and_excludes_other_stores(
    catalog_store: StoreFixture,
) -> None:
    store = catalog_store
    a = await store.confirmed("retained-a.csv", CSV_A)
    async with store.database.transaction(store.tenant, write=True) as session:
        row = await store.imports.get(session, store.tenant, a.id)
        row.expires_at = utc_now() - timedelta(days=1)
    foreign, _ = await MerchantAuthService(store.database).oidc_identity(
        "https://catalog-continuity-fixture.invalid", uuid4().hex
    )
    await store.imports.upload(foreign.store.id, "foreign.csv", CSV_B)
    await store.imports.cleanup(store.tenant)
    result = await store.setup.readiness(store.tenant)
    assert result.latest_import_id == a.id and result.indexing.catalog_id == a.catalog_id
    assert result.checklist["catalog_verified"]
    async with store.database.transaction(store.tenant) as session:
        retained = await session.scalar(
            select(CatalogImportRecord).where(
                CatalogImportRecord.tenant_id == store.tenant, CatalogImportRecord.id == a.id
            )
        )
        assert retained and retained.status == "confirmed" and not retained.encrypted_data


@pytest.mark.parametrize(
    "state", ["eligible", "published", "foreign", "leased", "running", "missing"]
)
async def test_browser_fault_fixture_only_changes_eligible_unpublished_candidate(
    catalog_store: StoreFixture, state: str
) -> None:
    store = catalog_store
    candidate = await store.confirmed("fixture-only.csv", CSV_A)
    assert candidate.catalog_id
    if state == "published":
        await store.publish(candidate.catalog_id, "fixture-published")
    elif state in {"leased", "running"}:
        async with store.database.transaction(store.tenant, write=True) as session:
            job = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == store.tenant,
                    CatalogIndexJob.integration_id == candidate.catalog_id,
                )
            )
            assert job
            if state == "leased":
                job.lease_token = uuid4()
                job.lease_until = utc_now() + timedelta(minutes=1)
            else:
                job.status = "running"
    if state == "eligible":
        await fail_replacement(store.database, store.tenant, candidate.catalog_id)
        changed = await store.imports.review(store.tenant, candidate.id)
        assert changed.indexing and changed.indexing.status == "failed"
        assert changed.indexing.error_code == "synthetic_browser_retry_fixture"
    else:
        before = await store.imports.review(store.tenant, candidate.id)
        with pytest.raises(RuntimeError, match="idle, confirmed, unpublished"):
            await fail_replacement(
                store.database,
                uuid4() if state == "foreign" else store.tenant,
                uuid4() if state == "missing" else candidate.catalog_id,
            )
        assert await store.imports.review(store.tenant, candidate.id) == before
