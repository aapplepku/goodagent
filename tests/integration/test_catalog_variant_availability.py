"""A sold-out first variant must not hide purchasable alternatives."""

from uuid import UUID, uuid4

import pytest

from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.browse_models import CatalogBrowseQuery
from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.persistence import activate_catalog, stage_catalog_upload
from open_commerce.catalog.scope import CatalogScope, catalog_scope
from open_commerce.commerce.models import CartItemAddRequest, CheckoutPreviewRequest
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.types import JsonObject, canonical_hash, utc_now
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.shopper_agent.product_tools import ProductToolError, ShopperProductTools
from open_commerce.shopper_agent.service import DurableShopperAgentService

pytestmark = pytest.mark.integration


async def test_in_stock_browse_uses_a_purchasable_representative(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await db.initialize_tenant(tenant)
        product = CatalogProductInput(
            source_product_id="mug",
            title="Travel mug",
            source_updated_at=utc_now(),
            variants=[
                CatalogVariantInput(
                    source_variant_id=identity,
                    sku=identity,
                    title=identity,
                    currency="USD",
                    price_minor=price,
                    available=True,
                    inventory_quantity=quantity,
                )
                for identity, price, quantity in [
                    ("a-small", 1500, 0),
                    ("b-large", 1900, 3),
                    ("c-unknown", 2000, None),
                ]
            ],
        )
        async with db.transaction(tenant, write=True) as session:
            staged = await stage_catalog_upload(
                session,
                tenant_id=tenant,
                filename="variants.csv",
                source_version=canonical_hash(product),
                products=[product],
            )
            assert staged.catalog_id
            await activate_catalog(
                session,
                tenant_id=tenant,
                integration_id=staged.catalog_id,
                indexed_count=1,
                completed_at=utc_now(),
            )
        for in_stock in (False, True):
            result = await CatalogBrowseService(db).browse(
                tenant_id=tenant, query=CatalogBrowseQuery(in_stock=in_stock)
            )
            assert result.total == 1
            assert result.items[0].availability == "available"
            assert result.items[0].variant_id == "b-large"
            assert result.items[0].price.amount_minor == 1900
            assert len(result.items[0].variants) == 3
            assert [(v.available, v.availability) for v in result.items[0].variants] == [
                (False, "out_of_stock"),
                (True, "available"),
                (False, "unknown"),
            ]
        tools = ShopperProductTools(tenant_id=tenant, reader=CatalogBrowseService(db))
        await tools.execute("lookup_catalog_products", {"product_ids": ["mug"]})
        args: JsonObject = {
            "items": [
                {"product_id": "mug", "variant_id": "a-small"},
                {"product_id": "mug", "variant_id": "b-large"},
            ]
        }
        comparison = await tools.execute("compare_catalog_prices", args)
        items = comparison["items"]
        assert isinstance(items, list)
        assert [item["available"] for item in items] == [False, True]
        auth, _ = await DurableShopperAgentService(db, search_service=SearchService()).register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="stock-test", display_name="Test", password="synthetic-stock-password"
            ),
        )
        commerce = DurableCommerceService(db, payment_provider=LocalTestPaymentProvider())
        cart = await commerce.add_item(
            tenant_id=tenant,
            account_id=auth.account.id,
            request=CartItemAddRequest(product_id="mug", variant_id="b-large", quantity=3),
            idempotency_key="hold-all",
            request_id="stock-test",
        )
        await commerce.preview_checkout(
            tenant_id=tenant,
            account_id=auth.account.id,
            request=CheckoutPreviewRequest(cart_version=cart.version),
            idempotency_key="hold-all-preview",
            request_id="stock-test",
        )
        held = await tools.execute("compare_catalog_prices", args)
        held_items = held["items"]
        assert isinstance(held_items, list)
        assert [item["available"] for item in held_items] == [False, False]
        assert held_items[1]["availability"] == "out_of_stock"
        assert (
            await CatalogBrowseService(db).browse(
                tenant_id=tenant, query=CatalogBrowseQuery(in_stock=True)
            )
        ).total == 0
    finally:
        await db.close()


async def test_agent_product_evidence_respects_tenant_and_published_catalog(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()

    async def publish(owner: UUID, price: int) -> UUID:
        products = [
            CatalogProductInput(
                source_product_id="same-id",
                title="Travel mug",
                source_updated_at=utc_now(),
                variants=[
                    CatalogVariantInput(
                        source_variant_id="small",
                        sku="small",
                        title="Small",
                        currency="USD",
                        price_minor=price,
                        available=True,
                        inventory_quantity=3,
                    )
                ],
            )
        ]
        async with db.transaction(owner, write=True) as session:
            staged = await stage_catalog_upload(
                session,
                tenant_id=owner,
                filename="private.csv",
                source_version=canonical_hash(products),
                products=products,
            )
            assert staged.catalog_id
            await activate_catalog(
                session,
                tenant_id=owner,
                integration_id=staged.catalog_id,
                indexed_count=1,
                completed_at=utc_now(),
            )
            return staged.catalog_id

    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        old = await publish(tenant, 1500)
        await publish(tenant, 2500)
        foreign = await publish(other, 99999)
        reader = CatalogBrowseService(db)
        tools = ShopperProductTools(tenant_id=tenant, reader=reader)
        with catalog_scope(CatalogScope(tenant_id=tenant, catalog_id=old)):
            await tools.execute("lookup_catalog_products", {"product_ids": ["same-id"]})
            await tools.execute("select_catalog_products", {"product_ids": ["same-id"]})
            assert tools.selected[0].price_minor == 1500
        # A forged catalog ID in a trusted-context fixture cannot expose another tenant.
        with catalog_scope(CatalogScope(tenant_id=tenant, catalog_id=foreign)):
            with pytest.raises(ProductToolError, match="CATALOG_NOT_PUBLISHED"):
                await tools.execute("lookup_catalog_products", {"product_ids": ["same-id"]})
            assert tools.selected == []
        with catalog_scope(CatalogScope(tenant_id=other, catalog_id=foreign)):
            with pytest.raises(ProductToolError, match="PRODUCT_LOOKUP_UNAVAILABLE"):
                await tools.execute("lookup_catalog_products", {"product_ids": ["same-id"]})
        await tools.execute("lookup_catalog_products", {"product_ids": ["same-id"]})
        await tools.execute("select_catalog_products", {"product_ids": ["same-id"]})
        assert tools.selected[0].price_minor == 2500
    finally:
        await db.close()
