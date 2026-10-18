"""Real PostgreSQL cart transfer and overlapping demo checkout finalization."""

import asyncio
from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.persistence import activate_catalog, stage_catalog_upload
from open_commerce.commerce.errors import CommerceNotFoundError
from open_commerce.commerce.models import (
    CartItemAddRequest,
    CheckoutConfirmation,
    CheckoutConfirmRequest,
    CheckoutPreviewRequest,
    PaymentConfirmationRequest,
    PaymentConfirmationResult,
)
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog import InventorySnapshot
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
)
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.shopper_agent.models import ShopperLoginRequest, ShopperRegisterRequest
from open_commerce.stores.shoppers import ShopperAccounts

pytestmark = pytest.mark.integration


@pytest.fixture
async def checkout_store(
    integration_settings: Settings,
) -> AsyncIterator[tuple[RuntimeDatabase, UUID]]:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    try:
        await database.initialize_tenant(tenant)
        async with database.transaction(tenant, write=True) as session:
            index = await stage_catalog_upload(
                session,
                tenant_id=tenant,
                filename="checkout-fixture.csv",
                source_version="sha256:" + "c" * 64,
                products=[
                    CatalogProductInput(
                        source_product_id="fixture-mug",
                        title="Fixture mug",
                        description_text="Synthetic checkout fixture",
                        source_updated_at=utc_now(),
                        variants=[
                            CatalogVariantInput(
                                source_variant_id="default",
                                sku="FIXTURE",
                                title="Default",
                                price_minor=1500,
                                currency="USD",
                                available=True,
                                inventory_quantity=20,
                            )
                        ],
                    )
                ],
            )
            assert index.catalog_id
            await activate_catalog(
                session,
                tenant_id=tenant,
                integration_id=index.catalog_id,
                indexed_count=1,
                completed_at=utc_now(),
            )
        yield database, tenant
    finally:
        await database.close()


@pytest.mark.parametrize("transition", ["login_with_preview", "login_without_preview", "register"])
async def test_retained_guest_cart_can_be_reviewed_and_completed_after_identity_transition(
    checkout_store: tuple[RuntimeDatabase, UUID], transition: str
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    guest, _ = await accounts.guest(tenant, None)
    cart = await commerce.add_item(
        tenant_id=tenant,
        account_id=guest.account.id,
        request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
        idempotency_key="guest-add",
        request_id="guest-add",
    )
    original_checkout: UUID | None = None
    if transition != "login_without_preview":
        preview = await commerce.preview_checkout(
            tenant_id=tenant,
            account_id=guest.account.id,
            request=CheckoutPreviewRequest(cart_version=cart.version),
            idempotency_key="guest-preview",
            request_id="guest-preview",
        )
        original_checkout = preview.checkout_id
    credentials = ShopperRegisterRequest(
        username="returning-shopper", display_name="Fixture", password="synthetic-password"
    )
    if transition == "register":
        registered, _ = await accounts.upgrade(tenant, guest.account.id, credentials)
        target = registered.account.id
    else:
        empty_guest, _ = await accounts.guest(tenant, None)
        registered, _ = await accounts.upgrade(tenant, empty_guest.account.id, credentials)
        logged_in, token = await accounts.login(
            tenant,
            guest.account.id,
            ShopperLoginRequest(username="returning-shopper", password="synthetic-password"),
        )
        assert token and not logged_in.merge_token
        target = registered.account.id
        assert logged_in.account.id == target
    retained = await commerce.get_cart(tenant_id=tenant, account_id=target)
    assert retained.id == cart.id and retained.item_count == cart.item_count
    fresh = await commerce.preview_checkout(
        tenant_id=tenant,
        account_id=target,
        request=CheckoutPreviewRequest(cart_version=retained.version),
        idempotency_key="fresh-preview",
        request_id="fresh-preview",
    )
    if transition == "register":
        assert fresh.checkout_id == original_checkout and retained.version == cart.version
    else:
        assert fresh.checkout_id != original_checkout and retained.version > cart.version
    completed = await commerce.confirm_checkout(
        tenant_id=tenant,
        account_id=target,
        request=CheckoutConfirmRequest(
            checkout_id=fresh.checkout_id, payment_method="test_success"
        ),
        idempotency_key="fresh-confirm",
        request_id="fresh-confirm",
    )
    assert completed.status == "succeeded" and completed.order
    async with database.transaction(tenant) as session:
        payments = list(
            await session.scalars(
                select(PaymentAttemptRecord).where(PaymentAttemptRecord.tenant_id == tenant)
            )
        )
        holds = list(
            await session.scalars(
                select(InventoryReservationRecord).where(
                    InventoryReservationRecord.tenant_id == tenant
                )
            )
        )
        if transition == "login_with_preview":
            old = next(item for item in payments if item.id == original_checkout)
            assert old.account_id == guest.account.id and old.status == "cancelled"
            assert any(
                item.account_id == guest.account.id and item.status == "released" for item in holds
            )
        current = next(item for item in payments if item.id == fresh.checkout_id)
        assert current.account_id == target and current.status == "succeeded"
        quantities = list(
            await session.scalars(
                select(InventorySnapshot.available_quantity).where(
                    InventorySnapshot.tenant_id == tenant
                )
            )
        )
        assert quantities == [20]


class OverlappingPayment(LocalTestPaymentProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.entered = [asyncio.Event(), asyncio.Event()]
        self.release = [asyncio.Event(), asyncio.Event()]

    async def confirm(self, request: PaymentConfirmationRequest) -> PaymentConfirmationResult:
        call = self.calls
        self.calls += 1
        assert call < 2
        result = await super().confirm(request)
        self.entered[call].set()
        await asyncio.wait_for(self.release[call].wait(), timeout=20)
        return result


@pytest.mark.parametrize("delete_between", [False, True])
@pytest.mark.parametrize("method", ["test_success", "test_decline"])
async def test_duplicate_finalization_cannot_regress_paid_order_after_receipt_deletion(
    checkout_store: tuple[RuntimeDatabase, UUID],
    delete_between: bool,
    method: Literal["test_success", "test_decline"],
) -> None:
    database, tenant = checkout_store
    accounts, provider = ShopperAccounts(database), OverlappingPayment()
    commerce = DurableCommerceService(database, payment_provider=provider)
    guest, _ = await accounts.guest(tenant, None)
    registered, _ = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="paid-fixture", display_name="Fixture", password="synthetic-password"
        ),
    )
    account = registered.account.id
    cart = await commerce.add_item(
        tenant_id=tenant,
        account_id=account,
        request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
        idempotency_key="add",
        request_id="add",
    )
    preview = await commerce.preview_checkout(
        tenant_id=tenant,
        account_id=account,
        request=CheckoutPreviewRequest(cart_version=cart.version),
        idempotency_key="preview",
        request_id="preview",
    )
    request = CheckoutConfirmRequest(checkout_id=preview.checkout_id, payment_method=method)

    async def confirm() -> CheckoutConfirmation:
        return await commerce.confirm_checkout(
            tenant_id=tenant,
            account_id=account,
            request=request,
            idempotency_key="same-confirm",
            request_id="same-confirm",
        )

    receipts = (
        select(func.count())
        .select_from(IdempotencyRecord)
        .where(
            IdempotencyRecord.tenant_id == tenant,
            IdempotencyRecord.scope == f"shopper:checkout:confirm:{account}",
        )
    )
    first = asyncio.create_task(confirm())
    second = None
    try:
        await asyncio.wait_for(provider.entered[0].wait(), timeout=10)
        second = asyncio.create_task(confirm())
        await asyncio.wait_for(provider.entered[1].wait(), timeout=10)
        provider.release[0].set()
        committed = await first
        assert committed.status == (
            "succeeded" if method == "test_success" else "requires_payment_method"
        )
        if delete_between:
            await accounts.delete_data(tenant, account)
            async with database.transaction(tenant) as session:
                assert await session.scalar(receipts) == 0
        provider.release[1].set()
        duplicate = await second
        recovery = await commerce.checkout_status(
            tenant_id=tenant, account_id=account, checkout_id=preview.checkout_id
        )
        orders = await commerce.orders(tenant_id=tenant, account_id=account, limit=20, offset=0)
        if method == "test_success":
            assert len(orders.items) == 1 and orders.items[0].status == "paid"
            assert duplicate.status == "succeeded" and duplicate.order == committed.order
            assert recovery and recovery.status == "succeeded"
            observed = await commerce.confirm_checkout(
                tenant_id=tenant,
                account_id=account,
                request=request,
                idempotency_key="observe-retained-success",
                request_id="observe-retained-success",
            )
            assert observed.order == committed.order and provider.calls == 2
        else:
            expected = "cancelled" if delete_between else "requires_payment_method"
            assert orders.items == [] and duplicate.order is None
            assert duplicate.status == expected
            assert recovery and recovery.status == expected
        async with database.transaction(tenant) as session:
            assert await session.scalar(receipts) == (0 if delete_between else 1)
            quantities = list(
                await session.scalars(
                    select(InventorySnapshot.available_quantity).where(
                        InventorySnapshot.tenant_id == tenant
                    )
                )
            )
            assert quantities == [20]
        with pytest.raises(CommerceNotFoundError):
            await commerce.checkout_status(
                tenant_id=tenant, account_id=uuid4(), checkout_id=preview.checkout_id
            )
    finally:
        provider.release[0].set()
        provider.release[1].set()
        tasks = [first] + ([second] if second else [])
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
