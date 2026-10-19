"""Durable cart, test-checkout, order, and observed-inventory orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.commerce.errors import (
    CommerceConflictError,
    CommercePolicyDeniedError,
    CommercePreconditionError,
)
from open_commerce.commerce.models import (
    Cart,
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartLine,
    CartStatus,
    CheckoutConfirmation,
    CheckoutConfirmRequest,
    CheckoutLine,
    CheckoutPreview,
    CheckoutPreviewRequest,
    CheckoutRecovery,
    CommerceInventoryItem,
    CommerceOverview,
    CommercePolicyDecision,
    InventoryState,
    OrderSummary,
    PaymentAttemptSummary,
    PaymentConfirmationRequest,
    PaymentProvider,
    PaymentStatus,
    ReservationStatus,
    ReservationSummary,
    ShopperOrderList,
)
from open_commerce.core.enums import AuditEventType
from open_commerce.core.events import AuditEvent
from open_commerce.core.money import Money
from open_commerce.core.types import ActorRef, utc_now
from open_commerce.persistence.models.catalog import InventorySnapshot
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
    ShopperCartLineRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.repositories.audit import SqlAuditRepository
from open_commerce.persistence.repositories.commerce import CatalogSelection, CommerceRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.shoppers import ShopperAccounts

MAX_CART_LINES = 100
MAX_CART_TOTAL_MINOR = 2_500_000
RESERVATION_MINUTES = 15


class DurableCommerceService:
    """Coordinate explicit shopper writes; no method is exposed as an LLM tool."""

    def __init__(self, database: RuntimeDatabase, *, payment_provider: PaymentProvider) -> None:
        if payment_provider.payment_mode != "local_test":
            raise ValueError("Only no-money local test payments are supported")
        self.database = database
        self.payment_provider = payment_provider

    async def orders(
        self, *, tenant_id: UUID, account_id: UUID, limit: int, offset: int
    ) -> ShopperOrderList:
        if not 1 <= limit <= 50 or offset < 0:
            raise ValueError("Invalid order page")
        async with self.database.transaction(tenant_id) as session:
            rows = await CommerceRepository(session, tenant_id).account_orders(
                account_id=account_id, limit=limit + 1, offset=offset
            )
            return ShopperOrderList(
                items=[self._order(row) for row in rows[:limit]],
                next_offset=offset + limit if len(rows) > limit else None,
            )

    async def get_cart(self, *, tenant_id: UUID, account_id: UUID) -> Cart:
        now = utc_now()
        async with self.database.transaction(tenant_id) as session:
            repo = CommerceRepository(session, tenant_id)
            cart = await repo.open_cart(account_id=account_id)
            return await self._cart(repo, account_id=account_id, cart=cart, now=now)

    async def checkout_status(
        self, *, tenant_id: UUID, account_id: UUID, checkout_id: UUID | None = None
    ) -> CheckoutRecovery | None:
        """Observe persisted state only; never renew holds or invoke a provider."""
        async with self.database.transaction(tenant_id) as session:
            repo = CommerceRepository(session, tenant_id)
            if checkout_id is None:
                checkout_id = await session.scalar(
                    select(PaymentAttemptRecord.id)
                    .where(
                        PaymentAttemptRecord.tenant_id == tenant_id,
                        PaymentAttemptRecord.account_id == account_id,
                        PaymentAttemptRecord.status == "processing",
                    )
                    .order_by(
                        PaymentAttemptRecord.created_at.desc(), PaymentAttemptRecord.id.desc()
                    )
                    .limit(1)
                )
                if checkout_id is None:
                    return None
            payment = await repo.payment(account_id=account_id, payment_id=checkout_id)
            if payment.status == "succeeded":
                return CheckoutRecovery(
                    checkout_id=payment.id,
                    status="succeeded",
                    confirmation=await self._successful_confirmation(repo, payment=payment),
                    message="Demo order confirmed. No real payment was made.",
                )
            cart = await repo.cart_by_id(account_id=account_id, cart_id=payment.cart_id)
            holds = await repo.reservations_for_checkout(
                account_id=account_id, checkout_id=payment.id
            )
            valid = (
                bool(holds)
                and all(hold.status == "active" and hold.expires_at > utc_now() for hold in holds)
                and cart.status == "open"
                and cart.version == payment.cart_version
            )
            if payment.status == "cancelled" or (not valid and payment.status != "processing"):
                return CheckoutRecovery(
                    checkout_id=payment.id,
                    status="cancelled" if payment.status == "cancelled" else "expired",
                    message="This checkout is no longer valid. Review your current cart again.",
                )
            preview = None
            if valid:
                lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
                preview = CheckoutPreview(
                    checkout_id=payment.id,
                    cart_id=cart.id,
                    cart_version=payment.cart_version,
                    status=cast(PaymentStatus, payment.status),
                    lines=[self._checkout_line(line) for line in lines],
                    subtotal=Money(amount_minor=payment.amount_minor, currency=payment.currency),
                    total=Money(amount_minor=payment.amount_minor, currency=payment.currency),
                    reservation_expires_at=min(hold.expires_at for hold in holds),
                    policy=CommercePolicyDecision.model_validate(payment.policy_decision),
                )
            return CheckoutRecovery(
                checkout_id=payment.id,
                status=cast(PaymentStatus, payment.status),
                preview=preview,
                message=(
                    "A checkout on this shopping account is still processing, possibly in "
                    "another tab. Check its status; do not start another payment."
                    if payment.status == "processing"
                    else "Review the saved checkout before explicitly confirming a demo payment."
                ),
            )

    async def add_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CartItemAddRequest,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart:
        now = utc_now()
        scope = f"shopper:cart:add:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            await ShopperAccounts(self.database).account(
                session, tenant_id, account_id, account_version=account_version
            )
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return Cart.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            await repo.expire_reservations(now=now)
            cart = await repo.open_cart(account_id=account_id, for_update=True)
            selection = await repo.catalog_selection(
                source_product_id=request.product_id, source_variant_id=request.variant_id
            )
            self._require_observed_stock(selection)
            if cart is None:
                cart = await repo.create_cart(
                    cart_id=uuid4(),
                    account_id=account_id,
                    currency=selection.variant.currency,
                    now=now,
                )
            else:
                await repo.invalidate_checkout(cart=cart, now=now)
            lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
            existing = await repo.cart_line_for_variant(
                account_id=account_id,
                cart_id=cart.id,
                variant_id=selection.variant.id,
            )
            if existing is None and len(lines) >= MAX_CART_LINES:
                raise CommercePolicyDeniedError("A cart can contain at most 100 distinct items")
            desired_quantity = request.quantity + (existing.quantity if existing else 0)
            if desired_quantity > 20:
                raise CommercePolicyDeniedError("A cart line can contain at most 20 units")
            await self._require_capacity(
                repo,
                selection=selection,
                quantity=desired_quantity,
                now=now,
            )
            if cart.currency != selection.variant.currency:
                raise CommercePolicyDeniedError("A cart cannot mix currencies")
            if existing is None:
                await repo.add_line(
                    line_id=uuid4(),
                    cart=cart,
                    account_id=account_id,
                    selection=selection,
                    quantity=request.quantity,
                    now=now,
                )
            else:
                existing.quantity = desired_quantity
                existing.unit_price_minor = selection.variant.price_minor
                existing.catalog_version = selection.variant.version
                existing.title = selection.product.title
                existing.variant_title = selection.variant.title
                existing.image_url = selection.product.primary_image_url
            self._touch(cart, now)
            response = await self._cart(repo, account_id=account_id, cart=cart, now=now)
            self._require_total_policy(response)
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.CART_UPDATED,
                entity_id=cart.id,
                request_id=request_id,
                payload={
                    "operation": "add_item",
                    "product_id": request.product_id,
                    "quantity": request.quantity,
                    "cart_version": cart.version,
                },
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def update_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        line_id: UUID,
        request: CartItemUpdateRequest,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart:
        now = utc_now()
        receipt_request = {"line_id": str(line_id), "quantity": request.quantity}
        scope = f"shopper:cart:update:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            await ShopperAccounts(self.database).account(
                session, tenant_id, account_id, account_version=account_version
            )
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(
                scope=scope, key=idempotency_key, request=receipt_request
            )
            if cached is not None:
                return Cart.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            await repo.expire_reservations(now=now)
            cart = await self._required_open_cart(repo, account_id=account_id)
            await repo.invalidate_checkout(cart=cart, now=now)
            line = await repo.cart_line(account_id=account_id, cart_id=cart.id, line_id=line_id)
            selection = await repo.current_variant(
                product_id=line.catalog_product_id, variant_id=line.catalog_variant_id
            )
            if selection is None:
                raise CommercePreconditionError("The cart item is no longer available")
            self._require_observed_stock(selection)
            await self._require_capacity(
                repo, selection=selection, quantity=request.quantity, now=now
            )
            line.quantity = request.quantity
            line.unit_price_minor = selection.variant.price_minor
            line.catalog_version = selection.variant.version
            line.title = selection.product.title
            line.variant_title = selection.variant.title
            line.image_url = selection.product.primary_image_url
            self._touch(cart, now)
            response = await self._cart(repo, account_id=account_id, cart=cart, now=now)
            self._require_total_policy(response)
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.CART_UPDATED,
                entity_id=cart.id,
                request_id=request_id,
                payload={
                    "operation": "update_item",
                    "line_id": str(line_id),
                    "quantity": request.quantity,
                    "cart_version": cart.version,
                },
            )
            receipts.remember(
                scope=scope, key=idempotency_key, request=receipt_request, response=response
            )
            return response

    async def delete_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        line_id: UUID,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart:
        now = utc_now()
        receipt_request = {"line_id": str(line_id)}
        scope = f"shopper:cart:delete:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            await ShopperAccounts(self.database).account(
                session, tenant_id, account_id, account_version=account_version
            )
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(
                scope=scope, key=idempotency_key, request=receipt_request
            )
            if cached is not None:
                return Cart.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            await repo.expire_reservations(now=now)
            cart = await self._required_open_cart(repo, account_id=account_id)
            await repo.invalidate_checkout(cart=cart, now=now)
            line = await repo.cart_line(account_id=account_id, cart_id=cart.id, line_id=line_id)
            await repo.delete_line(line)
            self._touch(cart, now)
            response = await self._cart(repo, account_id=account_id, cart=cart, now=now)
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.CART_UPDATED,
                entity_id=cart.id,
                request_id=request_id,
                payload={
                    "operation": "delete_item",
                    "line_id": str(line_id),
                    "cart_version": cart.version,
                },
            )
            receipts.remember(
                scope=scope, key=idempotency_key, request=receipt_request, response=response
            )
            return response

    async def preview_checkout(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CheckoutPreviewRequest,
        idempotency_key: str,
        request_id: str,
    ) -> CheckoutPreview:
        now = utc_now()
        scope = f"shopper:checkout:preview:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return CheckoutPreview.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            await repo.expire_reservations(now=now)
            cart = await self._required_open_cart(repo, account_id=account_id)
            if cart.version != request.cart_version:
                raise CommercePreconditionError("The cart changed; review it before checkout")
            lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
            if not lines:
                raise CommercePreconditionError("Add at least one item before checkout")
            checkout_id = uuid4()
            existing = await repo.payment_for_cart_version(
                cart_id=cart.id, cart_version=cart.version
            )
            if existing is not None:
                if existing.account_id != account_id:
                    raise CommerceConflictError(
                        "Checkout belongs to a different shopping session; review the cart again"
                    )
                if existing.status == "processing":
                    raise CommerceConflictError(
                        "Checkout is processing; check its status before reviewing again"
                    )
                checkout_id = existing.id
            validated, total_minor, preconditions = await self._validate_checkout_lines(
                repo,
                lines=lines,
                currency=cart.currency,
                now=now,
                checkout_id=checkout_id,
            )
            policy = self._checkout_policy(total_minor=total_minor, preconditions=preconditions)
            if not policy.allowed:
                raise CommercePolicyDeniedError(policy.reason)
            expires_at = now + timedelta(minutes=RESERVATION_MINUTES)
            existing_reservations: list[InventoryReservationRecord] = []
            if existing is None:
                payment = PaymentAttemptRecord(
                    id=checkout_id,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    cart_id=cart.id,
                    cart_version=cart.version,
                    provider="local_test",
                    provider_reference=f"local_pi_{checkout_id.hex}",
                    status="requires_confirmation",
                    amount_minor=total_minor,
                    currency=cart.currency,
                    idempotency_key_digest=_key_digest(idempotency_key),
                    policy_decision=policy.model_dump(mode="json"),
                    preconditions=preconditions,
                    rollback_metadata={
                        "before_payment": "release active reservations",
                        "after_success": "no money moved; inventory snapshot remains unchanged",
                    },
                    failure_code=None,
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
                session.add(payment)
            else:
                payment = existing
                current_reservations = await repo.reservations_for_checkout(
                    account_id=account_id, checkout_id=checkout_id
                )
                valid_hold = current_reservations and all(
                    item.status == "active" and item.expires_at > now
                    for item in current_reservations
                )
                if valid_hold:
                    response = self._preview(
                        payment=payment,
                        lines=validated,
                        policy=policy,
                        expires_at=min(item.expires_at for item in current_reservations),
                    )
                    receipts.remember(
                        scope=scope, key=idempotency_key, request=request, response=response
                    )
                    return response
                existing_reservations = current_reservations
                payment.status = "requires_confirmation"
                payment.amount_minor = total_minor
                payment.policy_decision = policy.model_dump(mode="json")
                payment.preconditions = cast(list[object], preconditions)
                payment.failure_code = None
                payment.updated_at = now
                payment.version += 1
            reservations_by_variant = {
                item.catalog_variant_id: item for item in existing_reservations
            }
            for line, _selection in validated:
                reservation = reservations_by_variant.get(line.catalog_variant_id)
                if reservation is not None:
                    reservation.quantity = line.quantity
                    reservation.status = "active"
                    reservation.expires_at = expires_at
                    reservation.release_reason = None
                    reservation.updated_at = now
                    reservation.version += 1
                    continue
                session.add(
                    InventoryReservationRecord(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        account_id=account_id,
                        cart_id=cart.id,
                        checkout_id=checkout_id,
                        cart_line_id=line.id,
                        catalog_product_id=line.catalog_product_id,
                        catalog_variant_id=line.catalog_variant_id,
                        source_product_id=line.source_product_id,
                        source_variant_id=line.source_variant_id,
                        quantity=line.quantity,
                        status="active",
                        expires_at=expires_at,
                        release_reason=None,
                        created_at=now,
                        updated_at=now,
                        version=1,
                    )
                )
            await session.flush()
            response = self._preview(
                payment=payment, lines=validated, policy=policy, expires_at=expires_at
            )
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.CHECKOUT_PREVIEWED,
                entity_id=checkout_id,
                request_id=request_id,
                payload={
                    "cart_id": str(cart.id),
                    "cart_version": cart.version,
                    "amount_minor": total_minor,
                    "currency": cart.currency,
                    "reservation_count": len(lines),
                    "policy_code": policy.code,
                },
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def confirm_checkout(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CheckoutConfirmRequest,
        idempotency_key: str,
        request_id: str,
    ) -> CheckoutConfirmation:
        scope = f"shopper:checkout:confirm:{account_id}"
        key_digest = _key_digest(idempotency_key)
        signature = sha256(request.model_dump_json().encode()).hexdigest()
        now = utc_now()
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return CheckoutConfirmation.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            payment = await repo.payment(
                account_id=account_id, payment_id=request.checkout_id, for_update=True
            )
            if payment.status == "succeeded":
                return await self._successful_confirmation(repo, payment=payment)
            if payment.status == "cancelled":
                raise CommercePreconditionError(
                    "Checkout is no longer active; review the cart again"
                )
            if payment.status == "processing" and payment.idempotency_key_digest != key_digest:
                raise CommerceConflictError("Checkout is already processing")
            if (
                payment.status == "processing"
                and payment.rollback_metadata.get("confirmation_request_hash") != signature
            ):
                raise CommerceConflictError("Retry must use the original confirmation body")
            cart = await repo.cart_by_id(
                account_id=account_id, cart_id=payment.cart_id, for_update=True
            )
            if cart.status != "open" or cart.version != payment.cart_version:
                raise CommercePreconditionError("The cart changed after checkout started")
            reservations = await repo.reservations_for_checkout(
                account_id=account_id, checkout_id=payment.id
            )
            if not reservations or any(
                item.status != "active" or item.expires_at <= now for item in reservations
            ):
                raise CommercePreconditionError("The inventory hold expired; review checkout again")
            if payment.status != "processing":
                lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
                _, total, _ = await self._validate_checkout_lines(
                    repo, lines=lines, currency=payment.currency, now=now, checkout_id=payment.id
                )
                if total != payment.amount_minor:
                    raise CommercePreconditionError("Checkout total changed; review the cart again")
            previous_status = payment.status
            payment.status = "processing"
            payment.rollback_metadata = {
                **payment.rollback_metadata,
                "confirmation_request_hash": signature,
            }
            payment.idempotency_key_digest = key_digest
            payment.failure_code = None
            payment.updated_at = now
            payment.version += 1
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.PAYMENT_STATUS_CHANGED,
                entity_id=payment.id,
                request_id=request_id,
                payload={
                    "from": previous_status,
                    "to": "processing",
                    "provider": "local_test",
                    "amount_minor": payment.amount_minor,
                    "currency": payment.currency,
                    "preconditions_checked": True,
                },
            )

        provider_result = await self.payment_provider.confirm(
            PaymentConfirmationRequest(
                payment_intent_id=request.checkout_id,
                amount=Money(amount_minor=payment.amount_minor, currency=payment.currency),
                payment_method=request.payment_method,
                idempotency_key=idempotency_key,
            )
        )

        completed_at = utc_now()
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return CheckoutConfirmation.model_validate(cached)
            repo = CommerceRepository(session, tenant_id)
            payment = await repo.payment(
                account_id=account_id, payment_id=request.checkout_id, for_update=True
            )
            # A deleted request receipt does not undo a retained checkout outcome.
            if payment.status == "succeeded":
                return await self._successful_confirmation(repo, payment=payment)
            if payment.status == "cancelled":
                return CheckoutConfirmation(
                    checkout_id=payment.id,
                    status="cancelled",
                    failure_code=payment.failure_code,
                    message=(
                        "This demo checkout is no longer active. Review your current cart again."
                    ),
                )
            if (
                payment.idempotency_key_digest != key_digest
                or payment.rollback_metadata.get("confirmation_request_hash") != signature
            ):
                raise CommerceConflictError(
                    "Checkout attempt changed; check its status before retrying"
                )
            if payment.status == "requires_payment_method":
                return CheckoutConfirmation(
                    checkout_id=payment.id,
                    status="requires_payment_method",
                    failure_code=payment.failure_code,
                    message=(
                        "The demo payment was declined. Choose the success test method to retry."
                    ),
                )
            if payment.status != "processing":
                raise CommerceConflictError(
                    "Checkout attempt changed; check its status before retrying"
                )
            cart = await repo.cart_by_id(
                account_id=account_id, cart_id=payment.cart_id, for_update=True
            )
            reservations = await repo.reservations_for_checkout(
                account_id=account_id, checkout_id=payment.id
            )
            # A provider response does not authorize consuming a hold that expired in flight.
            if (
                cart.status != "open"
                or cart.version != payment.cart_version
                or not reservations
                or any(
                    hold.status != "active" or hold.expires_at <= completed_at
                    for hold in reservations
                )
            ):
                payment.status = "cancelled"
                payment.failure_code = "checkout_changed_during_confirmation"
                payment.provider_reference = provider_result.provider_reference
                payment.rollback_metadata = {
                    **payment.rollback_metadata,
                    "observed_test_provider_result": provider_result.model_dump(mode="json"),
                    "reconciled_at": completed_at.isoformat(),
                }
                payment.updated_at = completed_at
                payment.version += 1
                for hold in reservations:
                    if hold.status == "active":
                        hold.status = "released"
                        hold.release_reason = "demo_checkout_cancelled"
                        hold.updated_at = completed_at
                        hold.version += 1
                if cart.status == "open":
                    self._touch(cart, completed_at)
                response = CheckoutConfirmation(
                    checkout_id=payment.id,
                    status="cancelled",
                    failure_code=payment.failure_code,
                    message="The demo checkout expired or changed while confirming. No money "
                    "moved and no order was created. Review your current cart to try again.",
                )
                await self._audit(
                    session,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    event_type=AuditEventType.PAYMENT_STATUS_CHANGED,
                    entity_id=payment.id,
                    request_id=request_id,
                    payload={
                        "from": "processing",
                        "to": "cancelled",
                        "provider_result": provider_result.model_dump(mode="json"),
                        "real_money_moved": False,
                        "reason": payment.failure_code,
                    },
                )
                receipts.remember(
                    scope=scope, key=idempotency_key, request=request, response=response
                )
                return response
            payment.provider_reference = provider_result.provider_reference
            payment.status = provider_result.status
            payment.failure_code = provider_result.failure_code
            payment.updated_at = completed_at
            payment.version += 1
            if provider_result.status == "requires_payment_method":
                response = CheckoutConfirmation(
                    checkout_id=payment.id,
                    status="requires_payment_method",
                    failure_code=provider_result.failure_code,
                    message=(
                        "The demo payment was declined. Choose the success test method to retry."
                    ),
                )
            else:
                order = await repo.order_for_payment(account_id=account_id, payment_id=payment.id)
                if order is None:
                    lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
                    snapshots = [
                        self._checkout_line(line).model_dump(mode="json") for line in lines
                    ]
                    order_id = uuid4()
                    order = ShopperOrderRecord(
                        id=order_id,
                        tenant_id=tenant_id,
                        account_id=account_id,
                        cart_id=cart.id,
                        payment_attempt_id=payment.id,
                        order_number=f"OC-{order_id.hex[:8].upper()}",
                        status="paid",
                        amount_minor=payment.amount_minor,
                        currency=payment.currency,
                        line_snapshots=snapshots,
                        created_at=completed_at,
                    )
                    session.add(order)
                cart.status = "converted"
                cart.updated_at = completed_at
                cart.version += 1
                for reservation in reservations:
                    reservation.status = "consumed"
                    reservation.release_reason = "order_created"
                    reservation.updated_at = completed_at
                    reservation.version += 1
                await session.flush()
                order_summary = self._order(order)
                response = CheckoutConfirmation(
                    checkout_id=payment.id,
                    status="succeeded",
                    order=order_summary,
                    message="Demo payment approved and order created.",
                )
                await self._audit(
                    session,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    event_type=AuditEventType.ORDER_CREATED,
                    entity_id=order.id,
                    request_id=request_id,
                    payload={
                        "order_number": order.order_number,
                        "payment_id": str(payment.id),
                        "amount_minor": order.amount_minor,
                        "currency": order.currency,
                        "inventory_snapshot_mutated": False,
                    },
                )
            await self._audit(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=AuditEventType.PAYMENT_STATUS_CHANGED,
                entity_id=payment.id,
                request_id=request_id,
                payload={
                    "from": "processing",
                    "to": payment.status,
                    "provider": payment.provider,
                    "provider_reference": payment.provider_reference,
                    "failure_code": payment.failure_code,
                    "real_money_moved": False,
                },
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def overview(self, *, tenant_id: UUID) -> CommerceOverview:
        now = utc_now()
        async with self.database.transaction(tenant_id) as session:
            repo = CommerceRepository(session, tenant_id)
            inventory_rows, reservations, orders, payments = await repo.overview_records(now=now)
            variant_ids = [variant.id for _, variant, _ in inventory_rows]
            reserved = await repo.reserved_quantities(variant_ids=variant_ids, now=now)
        inventory = []
        for product, variant, snapshot in inventory_rows:
            observed = snapshot.available_quantity if snapshot is not None else None
            held = reserved.get(variant.id, 0)
            sellable = max(observed - held, 0) if observed is not None else None
            inventory.append(
                CommerceInventoryItem(
                    product_id=product.source_product_id,
                    variant_id=variant.source_variant_id,
                    sku=variant.sku,
                    title=product.title,
                    variant_title=variant.title,
                    image_url=product.primary_image_url,
                    observed_quantity=observed,
                    reserved_quantity=held,
                    sellable_quantity=sellable,
                    state=self._inventory_state(sellable),
                    observed_at=snapshot.observed_at if snapshot else None,
                )
            )
        return CommerceOverview(
            inventory=inventory,
            reservations=[
                ReservationSummary(
                    id=item.id,
                    checkout_id=item.checkout_id,
                    product_id=item.source_product_id,
                    variant_id=item.source_variant_id,
                    quantity=item.quantity,
                    status=cast(
                        ReservationStatus,
                        "expired"
                        if item.status == "active" and item.expires_at <= now
                        else item.status,
                    ),
                    expires_at=item.expires_at,
                )
                for item in reservations
            ],
            orders=[self._order(item) for item in orders],
            payments=[
                PaymentAttemptSummary(
                    id=item.id,
                    provider="local_test",
                    provider_reference=item.provider_reference,
                    status=cast(PaymentStatus, item.status),
                    total=Money(amount_minor=item.amount_minor, currency=item.currency),
                    failure_code=item.failure_code,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in payments
            ],
            generated_at=now,
        )

    async def _cart(
        self,
        repo: CommerceRepository,
        *,
        account_id: UUID,
        cart: ShopperCartRecord | None,
        now: datetime,
    ) -> Cart:
        if cart is None:
            return Cart()
        lines = await repo.cart_lines(account_id=account_id, cart_id=cart.id)
        variant_ids = [line.catalog_variant_id for line in lines]
        reserved = await repo.reserved_quantities(variant_ids=variant_ids, now=now)
        output_lines: list[CartLine] = []
        for line in lines:
            inventory = await repo.latest_inventory(variant_id=line.catalog_variant_id)
            observed = inventory.available_quantity if inventory else None
            held = reserved.get(line.catalog_variant_id, 0)
            output_lines.append(
                CartLine(
                    id=line.id,
                    product_id=line.source_product_id,
                    variant_id=line.source_variant_id,
                    title=line.title,
                    variant_title=line.variant_title,
                    image_url=line.image_url,
                    quantity=line.quantity,
                    unit_price=Money(amount_minor=line.unit_price_minor, currency=line.currency),
                    line_total=Money(
                        amount_minor=line.unit_price_minor * line.quantity,
                        currency=line.currency,
                    ),
                    available_quantity=observed,
                    sellable_quantity=max(observed - held, 0) if observed is not None else None,
                )
            )
        subtotal = sum(item.line_total.amount_minor for item in output_lines)
        updated_at = cast(datetime | None, cart.__dict__.get("updated_at")) or now
        return Cart(
            id=cart.id,
            status=cast(CartStatus, cart.status),
            lines=output_lines,
            subtotal=Money(amount_minor=subtotal, currency=cart.currency),
            total=Money(amount_minor=subtotal, currency=cart.currency),
            item_count=sum(item.quantity for item in output_lines),
            version=cart.version,
            updated_at=updated_at,
        )

    async def _required_open_cart(
        self, repo: CommerceRepository, *, account_id: UUID
    ) -> ShopperCartRecord:
        cart = await repo.open_cart(account_id=account_id, for_update=True)
        if cart is None:
            raise CommercePreconditionError("The cart is empty")
        return cart

    async def _require_capacity(
        self,
        repo: CommerceRepository,
        *,
        selection: CatalogSelection,
        quantity: int,
        now: datetime,
    ) -> None:
        self._require_observed_stock(selection)
        inventory = cast(InventorySnapshot, selection.inventory)
        held = (await repo.reserved_quantities(variant_ids=[selection.variant.id], now=now)).get(
            selection.variant.id, 0
        )
        if quantity > max(inventory.available_quantity - held, 0):
            raise CommercePreconditionError("The requested quantity is not currently available")

    async def _validate_checkout_lines(
        self,
        repo: CommerceRepository,
        *,
        lines: list[ShopperCartLineRecord],
        currency: str,
        now: datetime,
        checkout_id: UUID,
    ) -> tuple[list[tuple[ShopperCartLineRecord, CatalogSelection]], int, list[str]]:
        validated: list[tuple[ShopperCartLineRecord, CatalogSelection]] = []
        preconditions: list[str] = []
        total_minor = 0
        for line in lines:
            selection = await repo.current_variant(
                product_id=line.catalog_product_id, variant_id=line.catalog_variant_id
            )
            if selection is None:
                raise CommercePreconditionError(f"{line.title} is no longer available")
            if (
                selection.variant.version != line.catalog_version
                or selection.variant.price_minor != line.unit_price_minor
            ):
                raise CommercePreconditionError(
                    f"The price for {line.title} changed; refresh the cart before checkout"
                )
            if selection.variant.currency != currency:
                raise CommercePreconditionError("The cart currency no longer matches the catalog")
            self._require_observed_stock(selection)
            inventory = cast(InventorySnapshot, selection.inventory)
            held = (
                await repo.reserved_quantities(
                    variant_ids=[selection.variant.id],
                    now=now,
                    excluding_checkout_id=checkout_id,
                )
            ).get(selection.variant.id, 0)
            if line.quantity > max(inventory.available_quantity - held, 0):
                raise CommercePreconditionError(f"Not enough stock remains for {line.title}")
            total_minor += line.unit_price_minor * line.quantity
            preconditions.extend(
                [
                    f"variant:{line.source_variant_id}:version={line.catalog_version}",
                    f"variant:{line.source_variant_id}:available>={line.quantity}",
                ]
            )
            validated.append((line, selection))
        return validated, total_minor, preconditions

    @staticmethod
    def _require_observed_stock(selection: CatalogSelection) -> None:
        if selection.inventory is None:
            raise CommercePreconditionError("Inventory has not been observed for this item")
        if selection.inventory.available_quantity <= 0:
            raise CommercePreconditionError("This item is out of stock")

    @staticmethod
    def _require_total_policy(cart: Cart) -> None:
        if cart.total.amount_minor > MAX_CART_TOTAL_MINOR:
            raise CommercePolicyDeniedError("The local MVP cart limit is USD 25,000")

    @staticmethod
    def _checkout_policy(*, total_minor: int, preconditions: list[str]) -> CommercePolicyDecision:
        allowed = 0 < total_minor <= MAX_CART_TOTAL_MINOR and bool(preconditions)
        return CommercePolicyDecision(
            allowed=allowed,
            code="LOCAL_TEST_CHECKOUT_ALLOWED" if allowed else "CHECKOUT_POLICY_DENIED",
            reason=(
                "Catalog price and observed inventory preconditions passed."
                if allowed
                else "Checkout must have a positive total within the local MVP limit."
            ),
            preconditions=preconditions,
            rollback_strategy=(
                "Release local reservations; no source inventory or real payment is changed."
            ),
        )

    @staticmethod
    def _preview(
        *,
        payment: PaymentAttemptRecord,
        lines: list[tuple[ShopperCartLineRecord, CatalogSelection]],
        policy: CommercePolicyDecision,
        expires_at: datetime,
    ) -> CheckoutPreview:
        output = [DurableCommerceService._checkout_line(line) for line, _ in lines]
        money = Money(amount_minor=payment.amount_minor, currency=payment.currency)
        return CheckoutPreview(
            checkout_id=payment.id,
            cart_id=payment.cart_id,
            cart_version=payment.cart_version,
            status=cast(PaymentStatus, payment.status),
            lines=output,
            subtotal=money,
            total=money,
            reservation_expires_at=expires_at,
            policy=policy,
        )

    @staticmethod
    def _checkout_line(line: ShopperCartLineRecord) -> CheckoutLine:
        unit = Money(amount_minor=line.unit_price_minor, currency=line.currency)
        return CheckoutLine(
            product_id=line.source_product_id,
            variant_id=line.source_variant_id,
            title=line.title,
            quantity=line.quantity,
            unit_price=unit,
            line_total=Money(
                amount_minor=line.unit_price_minor * line.quantity, currency=line.currency
            ),
        )

    @staticmethod
    def _order(row: ShopperOrderRecord) -> OrderSummary:
        return OrderSummary(
            id=row.id,
            order_number=row.order_number,
            status=cast(Literal["paid", "cancelled"], row.status),
            lines=[CheckoutLine.model_validate(item) for item in row.line_snapshots],
            total=Money(amount_minor=row.amount_minor, currency=row.currency),
            created_at=row.created_at,
        )

    async def _successful_confirmation(
        self, repo: CommerceRepository, *, payment: PaymentAttemptRecord
    ) -> CheckoutConfirmation:
        order = await repo.order_for_payment(account_id=payment.account_id, payment_id=payment.id)
        if order is None:
            raise CommerceConflictError("A successful payment is missing its order record")
        return CheckoutConfirmation(
            checkout_id=payment.id,
            status="succeeded",
            order=self._order(order),
            message="Demo payment already approved; returning the existing order.",
        )

    @staticmethod
    def _inventory_state(sellable: int | None) -> InventoryState:
        if sellable is None:
            return "unknown"
        if sellable == 0:
            return "out"
        if sellable <= 5:
            return "low"
        return "healthy"

    @staticmethod
    def _touch(cart: ShopperCartRecord, now: datetime) -> None:
        cart.updated_at = now
        cart.version += 1

    @staticmethod
    async def _audit(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        account_id: UUID,
        event_type: AuditEventType,
        entity_id: UUID,
        request_id: str,
        payload: dict[str, object],
    ) -> None:
        await SqlAuditRepository(session).append(
            tenant_id,
            AuditEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                actor=ActorRef(type="user", id=str(account_id), roles={"shopper"}),
                event_type=event_type,
                entity_type="shopper_commerce",
                entity_id=entity_id,
                request_id=request_id,
                safe_payload=payload,
                occurred_at=utc_now(),
            ),
        )


def _key_digest(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
