"""Real PostgreSQL cart, reservation, test-payment, and order lifecycle coverage."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.persistence import activate_catalog, stage_catalog_upload
from open_commerce.commerce.errors import CommerceConflictError, CommerceNotFoundError
from open_commerce.commerce.models import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CheckoutConfirmRequest,
    CheckoutPreviewRequest,
    PaymentConfirmationRequest,
    PaymentConfirmationResult,
)
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.persistence.models.audit import AuditEventRecord
from open_commerce.persistence.models.catalog import InventorySnapshot
from open_commerce.persistence.repositories.commerce import CommerceRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "interruption", ["none", "before_result", "after_result", "concurrent_update", "expired_result"]
)
async def test_cart_checkout_is_idempotent_scoped_and_never_mutates_source_inventory(
    integration_settings: Settings,
    interruption: str,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    now = datetime.now(UTC)
    try:
        await database.initialize_tenant(tenant_id)
        await database.initialize_tenant(other_tenant_id)
        product = CatalogProductInput(
            source_product_id="weeknight-pasta",
            title="Weeknight Pasta Kit",
            description_text="Pasta, sauce, and seasoning for a quick dinner.",
            brand="Northstar",
            category_path=["Pantry"],
            primary_image_url="/abo-images/pasta.jpg",
            source_updated_at=now,
            variants=[
                CatalogVariantInput(
                    source_variant_id="weeknight-pasta-default",
                    sku="PASTA-1",
                    title="Default",
                    price_minor=1899,
                    currency="USD",
                    available=True,
                    inventory_quantity=6,
                )
            ],
        )
        async with database.transaction(tenant_id, write=True) as session:
            staged = await stage_catalog_upload(
                session,
                tenant_id=tenant_id,
                filename="commerce.csv",
                source_version=f"sha256:{'a' * 64}",
                products=[product],
            )
            assert staged.catalog_id is not None
            await activate_catalog(
                session,
                tenant_id=tenant_id,
                integration_id=staged.catalog_id,
                indexed_count=1,
                completed_at=now,
            )
        shopper = DurableShopperAgentService(database, search_service=SearchService())
        account, _ = await shopper.register(
            tenant_id=tenant_id,
            request=ShopperRegisterRequest(
                username=f"buyer-{uuid4().hex[:8]}",
                display_name="Buyer",
                password="local-demo-password",
            ),
        )
        other_account, _ = await shopper.register(
            tenant_id=tenant_id,
            request=ShopperRegisterRequest(
                username=f"other-{uuid4().hex[:8]}",
                display_name="Other buyer",
                password="other-demo-password",
            ),
        )
        service = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
        cart = await service.add_item(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CartItemAddRequest(product_id="weeknight-pasta", quantity=2),
            idempotency_key="add-pasta",
            request_id="request-add",
        )
        replay = await service.add_item(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CartItemAddRequest(product_id="weeknight-pasta", quantity=2),
            idempotency_key="add-pasta",
            request_id="request-add-replay",
        )
        assert replay == cart
        assert cart.item_count == 2
        assert cart.total.amount_minor == 3798
        assert cart.lines[0].sellable_quantity == 6

        cart = await service.update_item(
            tenant_id=tenant_id,
            account_id=account.account.id,
            line_id=cart.lines[0].id,
            request=CartItemUpdateRequest(quantity=3),
            idempotency_key="update-pasta",
            request_id="request-update",
        )
        preview = await service.preview_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutPreviewRequest(cart_version=cart.version),
            idempotency_key="preview-pasta",
            request_id="request-preview",
        )
        assert preview.total.amount_minor == 5697
        assert preview.policy.allowed is True
        assert preview.payment_mode == "local_test"

        with pytest.raises(CommerceNotFoundError):
            await service.confirm_checkout(
                tenant_id=tenant_id,
                account_id=other_account.account.id,
                request=CheckoutConfirmRequest(
                    checkout_id=preview.checkout_id,
                    payment_method="test_success",
                ),
                idempotency_key="cross-account-confirm",
                request_id="request-cross-account",
            )

        declined = await service.confirm_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutConfirmRequest(
                checkout_id=preview.checkout_id,
                payment_method="test_decline",
            ),
            idempotency_key="decline-pasta",
            request_id="request-decline",
        )
        assert declined.status == "requires_payment_method"
        assert declined.order is None

        if interruption in {"concurrent_update", "expired_result"}:
            original_service = service

            class DelayedPayment(LocalTestPaymentProvider):
                async def confirm(
                    self, request: PaymentConfirmationRequest
                ) -> PaymentConfirmationResult:
                    if interruption == "concurrent_update":
                        with pytest.raises(CommerceConflictError, match="processing"):
                            await original_service.update_item(
                                tenant_id=tenant_id,
                                account_id=account.account.id,
                                line_id=cart.lines[0].id,
                                request=CartItemUpdateRequest(quantity=1),
                                idempotency_key="other-tab-update",
                                request_id="other-tab",
                            )
                    else:
                        async with database.transaction(tenant_id, write=True) as session:
                            await CommerceRepository(session, tenant_id).expire_reservations(
                                now=preview.reservation_expires_at + timedelta(seconds=1)
                            )
                    return await LocalTestPaymentProvider().confirm(request)

            service = DurableCommerceService(database, payment_provider=DelayedPayment())
            if interruption == "expired_result":
                cancelled = await service.confirm_checkout(
                    tenant_id=tenant_id,
                    account_id=account.account.id,
                    request=CheckoutConfirmRequest(
                        checkout_id=preview.checkout_id, payment_method="test_success"
                    ),
                    idempotency_key="confirm-pasta",
                    request_id="expired-response",
                )
                assert cancelled.status == "cancelled"
                state = await service.checkout_status(
                    tenant_id=tenant_id,
                    account_id=account.account.id,
                    checkout_id=preview.checkout_id,
                )
                assert state and state.status == "cancelled" and state.preview is None
                async with database.transaction(tenant_id) as session:
                    saved = await CommerceRepository(session, tenant_id).payment(
                        account_id=account.account.id, payment_id=preview.checkout_id
                    )
                    evidence = saved.rollback_metadata["observed_test_provider_result"]
                    assert isinstance(evidence, dict) and evidence["status"] == "succeeded"
                assert not (
                    await service.orders(
                        tenant_id=tenant_id, account_id=account.account.id, limit=10, offset=0
                    )
                ).items
                cart = await service.get_cart(tenant_id=tenant_id, account_id=account.account.id)
                old_checkout = preview.checkout_id
                service = DurableCommerceService(
                    database, payment_provider=LocalTestPaymentProvider()
                )
                preview = await service.preview_checkout(
                    tenant_id=tenant_id,
                    account_id=account.account.id,
                    request=CheckoutPreviewRequest(cart_version=cart.version),
                    idempotency_key="fresh-review",
                    request_id="fresh-review",
                )
                assert preview.checkout_id != old_checkout

        if interruption in {"before_result", "after_result"}:

            class InterruptedPayment(LocalTestPaymentProvider):
                async def confirm(
                    self, request: PaymentConfirmationRequest
                ) -> PaymentConfirmationResult:
                    if interruption == "after_result":
                        await LocalTestPaymentProvider().confirm(request)
                    raise ConnectionError("synthetic interrupted confirmation")

            interrupted = DurableCommerceService(database, payment_provider=InterruptedPayment())
            with pytest.raises(ConnectionError):
                await interrupted.confirm_checkout(
                    tenant_id=tenant_id,
                    account_id=account.account.id,
                    request=CheckoutConfirmRequest(
                        checkout_id=preview.checkout_id, payment_method="test_success"
                    ),
                    idempotency_key="confirm-pasta",
                    request_id="interrupted",
                )
            # Fresh service instance simulates API restart; reads do not execute payment.
            service = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
            state = await service.checkout_status(
                tenant_id=tenant_id, account_id=account.account.id
            )
            assert state and state.status == "processing" and state.preview
            for foreign_tenant, foreign_account in [
                (other_tenant_id, account.account.id),
                (tenant_id, other_account.account.id),
            ]:
                with pytest.raises(CommerceNotFoundError):
                    await service.checkout_status(
                        tenant_id=foreign_tenant,
                        account_id=foreign_account,
                        checkout_id=preview.checkout_id,
                    )
                assert (
                    await service.checkout_status(
                        tenant_id=foreign_tenant, account_id=foreign_account
                    )
                    is None
                )
            for key, method in [
                ("different-key", "test_success"),
                ("confirm-pasta", "test_decline"),
            ]:
                with pytest.raises(CommerceConflictError):
                    await service.confirm_checkout(
                        tenant_id=tenant_id,
                        account_id=account.account.id,
                        request=CheckoutConfirmRequest.model_validate(
                            {"checkout_id": preview.checkout_id, "payment_method": method}
                        ),
                        idempotency_key=key,
                        request_id="wrong-retry",
                    )
            with pytest.raises(CommerceConflictError):
                await service.preview_checkout(
                    tenant_id=tenant_id,
                    account_id=account.account.id,
                    request=CheckoutPreviewRequest(cart_version=cart.version),
                    idempotency_key="new-preview",
                    request_id="new-preview",
                )

        confirmed = await service.confirm_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutConfirmRequest(
                checkout_id=preview.checkout_id,
                payment_method="test_success",
            ),
            idempotency_key="fresh-confirm"
            if interruption == "expired_result"
            else "confirm-pasta",
            request_id="request-confirm",
        )
        confirmed_replay = await service.confirm_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutConfirmRequest(
                checkout_id=preview.checkout_id,
                payment_method="test_success",
            ),
            idempotency_key="fresh-confirm"
            if interruption == "expired_result"
            else "confirm-pasta",
            request_id="request-confirm-replay",
        )
        assert confirmed_replay == confirmed
        assert confirmed.status == "succeeded"
        assert confirmed.order is not None
        restored = await service.checkout_status(
            tenant_id=tenant_id, account_id=account.account.id, checkout_id=preview.checkout_id
        )
        assert restored and restored.confirmation and restored.confirmation.order == confirmed.order
        assert (
            await service.checkout_status(tenant_id=tenant_id, account_id=account.account.id)
            is None
        )
        history = await service.orders(
            tenant_id=tenant_id, account_id=account.account.id, limit=1, offset=0
        )
        assert history.items == [confirmed.order]
        assert history.next_offset is None and history.payment_mode == "local_test"
        assert not (
            await service.orders(
                tenant_id=tenant_id, account_id=other_account.account.id, limit=20, offset=0
            )
        ).items
        assert not (
            await service.orders(
                tenant_id=other_tenant_id, account_id=account.account.id, limit=20, offset=0
            )
        ).items
        assert not (
            await service.orders(
                tenant_id=tenant_id, account_id=account.account.id, limit=1, offset=1
            )
        ).items
        empty_cart = await service.get_cart(tenant_id=tenant_id, account_id=account.account.id)
        assert empty_cart.id is None

        overview = await service.overview(tenant_id=tenant_id)
        assert overview.inventory_writes_enabled is False
        assert overview.inventory[0].observed_quantity == 6
        assert overview.inventory[0].reserved_quantity == 0
        assert len(overview.orders) == 1
        assert [payment.status for payment in overview.payments] == (
            ["succeeded", "cancelled"] if interruption == "expired_result" else ["succeeded"]
        )
        async with database.transaction(tenant_id) as session:
            inventory = await session.scalar(
                select(InventorySnapshot).where(InventorySnapshot.tenant_id == tenant_id)
            )
            audit_types = set(
                await session.scalars(
                    select(AuditEventRecord.event_type).where(
                        AuditEventRecord.tenant_id == tenant_id
                    )
                )
            )
        assert inventory is not None and inventory.available_quantity == 6
        expected_audit = {
            "cart_updated",
            "checkout_previewed",
            "payment_status_changed",
            "order_created",
        }
        assert expected_audit <= audit_types
        assert (await service.overview(tenant_id=other_tenant_id)).orders == []
        second_cart = await service.add_item(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CartItemAddRequest(product_id="weeknight-pasta", quantity=1),
            idempotency_key="second-cart",
            request_id="second-cart",
        )
        second_preview = await service.preview_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutPreviewRequest(cart_version=second_cart.version),
            idempotency_key="second-preview",
            request_id="second-preview",
        )
        second_order = await service.confirm_checkout(
            tenant_id=tenant_id,
            account_id=account.account.id,
            request=CheckoutConfirmRequest(
                checkout_id=second_preview.checkout_id, payment_method="test_success"
            ),
            idempotency_key="second-order",
            request_id="second-order",
        )
        first_page = await service.orders(
            tenant_id=tenant_id, account_id=account.account.id, limit=1, offset=0
        )
        assert first_page.items == [second_order.order] and first_page.next_offset == 1
        last_page = await service.orders(
            tenant_id=tenant_id, account_id=account.account.id, limit=1, offset=1
        )
        assert last_page.items == [confirmed.order] and last_page.next_offset is None
    finally:
        await database.close()
