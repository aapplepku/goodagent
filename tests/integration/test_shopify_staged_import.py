"""Current Shopify CSV review and confirmation against disposable PostgreSQL."""

import base64
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.catalog.shopify_csv import ShopifyProductsExcluded
from open_commerce.config import Settings
from open_commerce.manager_agent.models import (
    ManagerDatasetProfileRequest,
    ManagerThreadCreateRequest,
)
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.catalog import Product, ProductVariant
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.integrations import Integration
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.import_models import ImportMapping
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.models import StoreError
from open_commerce.stores.setup import StoreSetupService

pytestmark = pytest.mark.integration

CSV = (
    b"URL handle,Title,Description,Option1 value,SKU,Price,Status,Published on online store\n"
    b"mug,Mug,<p>Test mug</p>,Red,MUG-R,12.50,active,true\n"
    b"mug,,,Blue,MUG-B,14.00,,\n"
    b"draft,Draft product,,,DRAFT,8,draft,false\n"
)


async def test_shopify_review_confirm_is_scoped_idempotent_and_not_published(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(
        integration_settings.model_copy(
            update={
                "runtime_profile": "self_hosted",
                "manager_model_provider": "deterministic",
                "encryption_key": SecretStr(base64.urlsafe_b64encode(b"s" * 32).decode()),
            }
        )
    )
    try:
        auth = MerchantAuthService(db)
        owner, _ = await auth.oidc_identity("https://shopify-fixture.example", uuid4().hex)
        other, _ = await auth.oidc_identity("https://shopify-fixture.example", uuid4().hex)
        tenant = owner.store.id
        imports = CatalogImportService(db)
        uploaded = await imports.upload(tenant, "shopify-current.csv", CSV)
        assert uploaded.status == "mapping" and uploaded.product_count == 0
        assert "currency" in uploaded.errors[0].message
        assert uploaded.review_fingerprint
        with pytest.raises(StoreError) as incomplete:
            await imports.confirm(
                tenant,
                uploaded.id,
                "confirm-once",
                expected_review_fingerprint=uploaded.review_fingerprint,
            )
        assert incomplete.value.status_code == 409
        reviewed = await imports.review(
            tenant, uploaded.id, ImportMapping(mapping=uploaded.mapping, currency="USD")
        )
        assert reviewed.status == "review" and reviewed.product_count == 1
        assert not reviewed.errors
        assert any("Rows starting at 4" in w for w in reviewed.warnings)
        assert [p.source_product_id for p in reviewed.products] == ["mug"]
        assert [v.price_minor for v in reviewed.products[0].variants] == [1250, 1400]
        assert len(reviewed.products[0].variants) == 2
        resumed = await imports.review(tenant, uploaded.id)
        assert resumed.status == "review" and resumed.product_count == 1
        assert resumed.currency == "USD" and resumed.mapping == reviewed.mapping
        assert resumed.warnings == reviewed.warnings
        assert reviewed.review_fingerprint
        for operation in ("review", "confirm"):
            with pytest.raises(StoreError) as denied:
                if operation == "review":
                    await imports.review(other.store.id, uploaded.id)
                else:
                    await imports.confirm(
                        other.store.id,
                        uploaded.id,
                        "confirm-once",
                        expected_review_fingerprint=reviewed.review_fingerprint,
                    )
            assert denied.value.status_code == 404
        confirmed = await imports.confirm(
            tenant,
            uploaded.id,
            "confirm-once",
            expected_review_fingerprint=reviewed.review_fingerprint,
        )
        assert confirmed == await imports.confirm(
            tenant,
            uploaded.id,
            "confirm-once",
            expected_review_fingerprint=reviewed.review_fingerprint,
        )
        assert confirmed.catalog_id and confirmed.indexing and confirmed.indexing.job_id
        assert confirmed.status == "confirmed" and confirmed.product_count == 1
        assert any("Shopify product excluded" in w for w in confirmed.warnings)
        async with db.transaction(tenant) as session:
            products = list(
                await session.scalars(
                    select(Product).where(
                        Product.tenant_id == tenant, Product.integration_id == confirmed.catalog_id
                    )
                )
            )
            assert [p.source_product_id for p in products] == ["mug"]
            variants = list(
                await session.scalars(
                    select(ProductVariant)
                    .where(
                        ProductVariant.tenant_id == tenant,
                        ProductVariant.product_id == products[0].id,
                    )
                    .order_by(ProductVariant.price_minor)
                )
            )
            assert [v.price_minor for v in variants] == [1250, 1400]
            assert [v.option_values for v in variants] == [{"option1": "Red"}, {"option1": "Blue"}]
            record = await session.scalar(
                select(CatalogImportRecord).where(
                    CatalogImportRecord.tenant_id == tenant, CatalogImportRecord.id == uploaded.id
                )
            )
            assert record is not None and record.encrypted_data == b""
        readiness = await StoreSetupService(db).readiness(tenant)
        assert not readiness.store.sharing_enabled
        assert readiness.store.published_catalog_id is None
    finally:
        await db.close()


async def test_legacy_chat_rejects_all_excluded_catalog_without_queuing(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await db.initialize_tenant(tenant)
        manager = DurableManagerAgentService(db)
        thread = await manager.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title="Catalog import"),
            idempotency_key="create",
        )
        with pytest.raises(ShopifyProductsExcluded):
            await manager.profile_dataset(
                tenant_id=tenant,
                thread_id=thread.thread.id,
                request=ManagerDatasetProfileRequest(
                    dataset_kind="catalog",
                    filename="draft-only.csv",
                    csv_text="URL handle,Title,Price,Status\ndraft,Draft product,8,draft\n",
                    catalog_currency="USD",
                ),
                idempotency_key="excluded-upload",
            )
        async with db.transaction(tenant) as session:
            assert not list(
                await session.scalars(select(Integration).where(Integration.tenant_id == tenant))
            )
            assert not list(
                await session.scalars(
                    select(CatalogIndexJob).where(CatalogIndexJob.tenant_id == tenant)
                )
            )
    finally:
        await db.close()
