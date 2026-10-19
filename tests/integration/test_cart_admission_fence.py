"""Personal-data invalidation wins over already-authenticated cart commands."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Literal, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from open_commerce.api.main import create_app
from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.persistence import activate_catalog, stage_catalog_upload
from open_commerce.commerce.models import Cart, CartItemAddRequest
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.enums import AuditEventType
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.audit import AuditEventRecord
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.shopper_activity import ShopperActivityRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.stores.models import StoreError
from open_commerce.stores.shoppers import ShopperAccounts

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("operation", ["add", "update", "delete"])
@pytest.mark.parametrize("invalidation", ["delete", "cleanup", "elapsed", "preview"])
async def test_invalidated_account_fences_admitted_cart_write(
    integration_settings: Settings,
    operation: Literal["add", "update", "delete"],
    invalidation: Literal["delete", "cleanup", "elapsed", "preview"],
) -> None:
    tenant = uuid4()
    settings = integration_settings.model_copy(
        update={"runtime_profile": "legacy_demo", "local_tenant_id": tenant}
    )
    database = RuntimeDatabase(settings)
    accounts = ShopperAccounts(database)
    try:
        await database.initialize_tenant(tenant)
        now = utc_now()
        async with database.transaction(tenant, write=True) as session:
            staged = await stage_catalog_upload(
                session,
                tenant_id=tenant,
                filename="synthetic-fence.csv",
                source_version=f"sha256:{'d' * 64}",
                products=[
                    CatalogProductInput(
                        source_product_id="cart-fence",
                        title="Synthetic Cart Fence",
                        source_updated_at=now,
                        variants=[
                            CatalogVariantInput(
                                source_variant_id="default",
                                title="Default",
                                price_minor=1234,
                                currency="USD",
                                available=True,
                                inventory_quantity=20,
                            )
                        ],
                    )
                ],
            )
            assert staged.catalog_id is not None
            await activate_catalog(
                session,
                tenant_id=tenant,
                integration_id=staged.catalog_id,
                indexed_count=1,
                completed_at=now,
            )
        auth, token = await accounts.guest(tenant, None)
        assert token is not None
        admitted = auth.account._data_version
        assert admitted is not None
        erases_receipts = invalidation in {"delete", "cleanup"}
        commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
        seeded = await commerce.add_item(
            tenant_id=tenant,
            account_id=auth.account.id,
            request=CartItemAddRequest(product_id="cart-fence"),
            idempotency_key="seed-cart",
            request_id="seed-cart",
        )
        shopper = DurableShopperAgentService(database, search_service=SearchService())
        app = create_app(
            settings=settings, shopper_agent_service=shopper, commerce_service=commerce
        )
        original = cast(Callable[..., Awaitable[Cart]], getattr(commerce, f"{operation}_item"))
        admitted_versions: list[object] = []

        async def invalidate_after_admission(**kwargs: object) -> Cart:
            admitted_versions.append(kwargs.get("account_version"))
            if invalidation in {"cleanup", "elapsed", "preview"}:
                async with database.transaction(tenant, write=True) as session:
                    row = await accounts.account(session, tenant, auth.account.id)
                    if invalidation == "preview":
                        row.preview_catalog_id = staged.catalog_id
                    else:
                        row.expires_at = utc_now() - timedelta(seconds=1)
                if invalidation == "cleanup":
                    await accounts.cleanup(tenant)
            else:
                await accounts.delete_data(tenant, auth.account.id)
            return await original(**kwargs)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                client.cookies.set("open_commerce_shopper_session", token)
                headers = {
                    "Idempotency-Key": (
                        "seed-cart"
                        if not erases_receipts and operation == "add"
                        else "admitted-before-invalidation"
                    ),
                    "X-Shopper-Account-Id": str(auth.account.id),
                }
                with patch.object(commerce, f"{operation}_item", invalidate_after_admission):
                    if operation == "add":
                        response = await client.post(
                            "/v1/shopper/cart/items",
                            json={"product_id": "cart-fence"},
                            headers=headers,
                        )
                    elif operation == "update":
                        response = await client.patch(
                            f"/v1/shopper/cart/items/{seeded.lines[0].id}",
                            json={"quantity": 2},
                            headers=headers,
                        )
                    else:
                        response = await client.delete(
                            f"/v1/shopper/cart/items/{seeded.lines[0].id}", headers=headers
                        )
                assert response.status_code == 401
                assert admitted_versions == [admitted]
                assert isinstance(admitted_versions[0], int)
                current = await commerce.get_cart(tenant_id=tenant, account_id=auth.account.id)
                assert current.item_count == (0 if erases_receipts else seeded.item_count)
                async with database.transaction(tenant) as session:
                    for model in (IdempotencyRecord, ShopperActivityRecord):
                        expected_count = int(
                            (model is IdempotencyRecord and not erases_receipts)
                            or (model is ShopperActivityRecord and invalidation == "preview")
                        )
                        assert (
                            await session.scalar(
                                select(func.count())
                                .select_from(model)
                                .where(model.tenant_id == tenant)
                            )
                            == expected_count
                        )
                    if invalidation == "preview":
                        activity = await session.scalar(
                            select(ShopperActivityRecord).where(
                                ShopperActivityRecord.tenant_id == tenant,
                                ShopperActivityRecord.account_id == auth.account.id,
                            )
                        )
                        assert activity is not None
                        assert activity.status == "error" and activity.is_preview
                        assert activity.kind == "cart_change"
                    assert (
                        await session.scalar(
                            select(func.count())
                            .select_from(AuditEventRecord)
                            .where(
                                AuditEventRecord.tenant_id == tenant,
                                AuditEventRecord.event_type == AuditEventType.CART_UPDATED.value,
                            )
                        )
                        == 1
                    )
                    row = await session.scalar(
                        select(ShopperAccountRecord).where(
                            ShopperAccountRecord.tenant_id == tenant,
                            ShopperAccountRecord.id == auth.account.id,
                        )
                    )
                    assert row is not None
                    if erases_receipts:
                        assert row.version > admitted
                    else:
                        assert row.version == admitted
                if not erases_receipts:
                    # A trusted versionless caller must not bypass expiry/preview on replay.
                    with pytest.raises(StoreError):
                        await commerce.add_item(
                            tenant_id=tenant,
                            account_id=auth.account.id,
                            request=CartItemAddRequest(product_id="cart-fence"),
                            idempotency_key="seed-cart",
                            request_id="versionless-cached-replay",
                        )
                if invalidation == "delete":
                    fresh = await client.post(
                        "/v1/shopper/cart/items",
                        json={"product_id": "cart-fence"},
                        headers={**headers, "Idempotency-Key": "new-explicit-intent"},
                    )
                    assert fresh.status_code == 200
                    assert fresh.json()["item_count"] == 1
        finally:
            await app.state.database.close()
    finally:
        await database.close()
