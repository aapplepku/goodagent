"""Real API/SQL confirmation must bind to the owner's displayed import review."""

import base64
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog import ProductVariant
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.import_models import ImportMapping
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.setup import StoreSetupService

pytestmark = pytest.mark.integration

CSV = b"product_id,title,retail,cost,updated_at\none,Synthetic product,100,1,2026-10-01T00:00:00Z\n"
MAPPING = {
    "product_id": "product_id",
    "title": "title",
    "price": "retail",
    "updated_at": "updated_at",
}


@pytest.fixture
def review_settings(integration_settings: Settings) -> Settings:
    return integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "manager_model_provider": "deterministic",
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"r" * 32).decode()),
        }
    )


async def import_state(db: RuntimeDatabase, tenant: UUID, import_id: UUID) -> tuple[object, ...]:
    async with db.transaction(tenant) as session:
        row = await CatalogImportService(db).get(session, tenant, import_id)
        jobs = await session.scalar(
            select(func.count(CatalogIndexJob.id)).where(
                CatalogIndexJob.tenant_id == tenant,
            )
        )
        return row.encrypted_data, dict(row.mapping), row.currency, row.status, row.catalog_id, jobs


async def test_other_tabs_mapping_cannot_be_confirmed_by_stale_review(
    review_settings: Settings,
) -> None:
    db = RuntimeDatabase(review_settings)
    app = create_app(review_settings)
    try:
        owner, token = await MerchantAuthService(db).oidc_identity(
            "https://import-review-fixture.invalid",
            uuid4().hex,
        )
        tenant = owner.store.id
        imports = CatalogImportService(db)
        upload = await imports.upload(tenant, "review.csv", CSV)
        a = await imports.review(tenant, upload.id, ImportMapping(mapping=MAPPING, currency="USD"))
        b = await imports.review(
            tenant,
            upload.id,
            ImportMapping(
                mapping={**MAPPING, "price": "cost"},
                currency="EUR",
            ),
        )
        assert a.products[0].variants[0].price_minor == 10000
        assert a.currency == "USD"
        assert b.products[0].variants[0].price_minor == 100 and b.currency == "EUR"
        before = await import_state(db, tenant, upload.id)
        headers = {"X-Merchant-Owner-Id": str(owner.user_id), "X-Merchant-Store-Id": str(tenant)}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("open_commerce_merchant_session", token)
            reviewed_token = a.review_fingerprint
            assert reviewed_token is not None
            for invalid_body in ({}, {"expected_review_fingerprint": "invalid"}):
                invalid = await client.post(
                    f"/v1/merchant/imports/{upload.id}/confirm",
                    json=invalid_body,
                    headers={**headers, "Idempotency-Key": "invalid"},
                )
                assert invalid.status_code == 422, invalid.text
                assert await import_state(db, tenant, upload.id) == before
            rejected = await client.post(
                f"/v1/merchant/imports/{upload.id}/confirm",
                json={"expected_review_fingerprint": reviewed_token},
                headers={**headers, "Idempotency-Key": "stale"},
            )
            assert rejected.status_code == 409, rejected.text
            assert await import_state(db, tenant, upload.id) == before
            assert before[0] and before[4] is None and before[5] == 0
            fresh = await client.get(f"/v1/merchant/imports/{upload.id}", headers=headers)
            assert fresh.status_code == 200
            fresh_token = fresh.json()["review_fingerprint"]
            assert isinstance(fresh_token, str) and len(fresh_token) == 71
            assert fresh_token != reviewed_token
            reread = await client.get(f"/v1/merchant/imports/{upload.id}", headers=headers)
            assert reread.json()["review_fingerprint"] == fresh_token
            confirmed = await client.post(
                f"/v1/merchant/imports/{upload.id}/confirm",
                json={"expected_review_fingerprint": fresh_token},
                headers={**headers, "Idempotency-Key": "fresh"},
            )
            assert confirmed.status_code == 200, confirmed.text
            replay = await client.post(
                f"/v1/merchant/imports/{upload.id}/confirm",
                json={"expected_review_fingerprint": fresh_token},
                headers={**headers, "Idempotency-Key": "fresh"},
            )
            assert replay.status_code == 200 and replay.json() == confirmed.json()
            different_key = await client.post(
                f"/v1/merchant/imports/{upload.id}/confirm",
                json={"expected_review_fingerprint": fresh_token},
                headers={**headers, "Idempotency-Key": "duplicate-click"},
            )
            assert different_key.status_code == 200
            assert different_key.json() == confirmed.json()
            for key in ("fresh", "new-stale-intent"):
                changed_intent = await client.post(
                    f"/v1/merchant/imports/{upload.id}/confirm",
                    json={"expected_review_fingerprint": reviewed_token},
                    headers={**headers, "Idempotency-Key": key},
                )
                assert changed_intent.status_code == 409, changed_intent.text
        after = await import_state(db, tenant, upload.id)
        assert after[0] == b"" and after[5] == 1
        async with db.transaction(tenant) as session:
            variants = list(
                await session.scalars(
                    select(ProductVariant).where(
                        ProductVariant.tenant_id == tenant,
                    )
                )
            )
            assert [(variant.price_minor, variant.currency) for variant in variants] == [
                (100, "EUR")
            ]
        readiness = await StoreSetupService(db).readiness(tenant)
        assert not readiness.store.sharing_enabled and readiness.store.published_catalog_id is None
    finally:
        await app.state.search_service.close()
        await app.state.database.close()
        await db.close()


@pytest.mark.parametrize("closed", ["cancelled", "expired"])
async def test_review_token_cannot_confirm_cancelled_or_expired_upload(
    review_settings: Settings,
    closed: str,
) -> None:
    db = RuntimeDatabase(review_settings)
    app = create_app(review_settings)
    try:
        owner, token = await MerchantAuthService(db).oidc_identity(
            "https://import-review-fixture.invalid",
            uuid4().hex,
        )
        tenant = owner.store.id
        imports = CatalogImportService(db)
        upload = await imports.upload(tenant, "review.csv", CSV)
        reviewed = await imports.review(
            tenant,
            upload.id,
            ImportMapping(mapping=MAPPING, currency="USD"),
        )
        if closed == "cancelled":
            await imports.cancel(tenant, upload.id)
        else:
            async with db.transaction(tenant, write=True) as session:
                record = await imports.get(session, tenant, upload.id)
                record.expires_at = utc_now() - timedelta(seconds=1)
        before = await import_state(db, tenant, upload.id)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("open_commerce_merchant_session", token)
            response = await client.post(
                f"/v1/merchant/imports/{upload.id}/confirm",
                json={"expected_review_fingerprint": reviewed.review_fingerprint},
                headers={
                    "X-Merchant-Owner-Id": str(owner.user_id),
                    "X-Merchant-Store-Id": str(tenant),
                    "Idempotency-Key": "closed-upload",
                },
            )
            assert response.status_code == (409 if closed == "cancelled" else 410), response.text
        assert await import_state(db, tenant, upload.id) == before
        assert before[4] is None and before[5] == 0
    finally:
        await app.state.search_service.close()
        await app.state.database.close()
        await db.close()


async def test_review_is_scoped_to_exact_store_and_import(review_settings: Settings) -> None:
    db = RuntimeDatabase(review_settings)
    app = create_app(review_settings)
    try:
        auth = MerchantAuthService(db)
        owner, token = await auth.oidc_identity(
            "https://import-review-fixture.invalid", uuid4().hex
        )
        foreign, _ = await auth.oidc_identity("https://import-review-fixture.invalid", uuid4().hex)
        imports = CatalogImportService(db)
        reviews = []
        for tenant in (owner.store.id, owner.store.id, foreign.store.id):
            upload = await imports.upload(tenant, "review.csv", CSV)
            reviews.append(
                await imports.review(
                    tenant,
                    upload.id,
                    ImportMapping(mapping=MAPPING, currency="USD"),
                )
            )
        own, other_import, other_store = reviews
        assert len({review.review_fingerprint for review in reviews}) == 3
        before = await import_state(db, owner.store.id, own.id)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("open_commerce_merchant_session", token)
            headers = {
                "X-Merchant-Owner-Id": str(owner.user_id),
                "X-Merchant-Store-Id": str(owner.store.id),
                "Idempotency-Key": "different-import",
            }
            for invalid in (other_import, other_store):
                response = await client.post(
                    f"/v1/merchant/imports/{own.id}/confirm",
                    json={"expected_review_fingerprint": invalid.review_fingerprint},
                    headers=headers,
                )
                assert response.status_code == 409, response.text
            response = await client.post(
                f"/v1/merchant/imports/{other_store.id}/confirm",
                json={"expected_review_fingerprint": other_store.review_fingerprint},
                headers=headers,
            )
            assert response.status_code == 404, response.text
        assert await import_state(db, owner.store.id, own.id) == before
        assert before[4] is None and before[5] == 0
    finally:
        await app.state.search_service.close()
        await app.state.database.close()
        await db.close()
