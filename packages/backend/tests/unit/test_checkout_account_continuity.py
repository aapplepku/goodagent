"""Checkout continuity with mocked persistence; receipt-only loss is fault injection."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from sqlalchemy import Select, Table
from sqlalchemy.sql.dml import Delete, Update

from open_commerce.commerce import service as commerce_service
from open_commerce.commerce.errors import (
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePreconditionError,
)
from open_commerce.commerce.models import (
    CheckoutConfirmation,
    CheckoutConfirmRequest,
    CheckoutPreviewRequest,
    PaymentConfirmationRequest,
    PaymentConfirmationResult,
    PaymentProvider,
    TestPaymentMethod,
)
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
    ShopperCartLineRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.commerce import CommerceRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores import shoppers
from open_commerce.stores.shoppers import ShopperAccounts

TENANT, ACCOUNT, GUEST, CART, PAYMENT, VARIANT = [UUID(int=i) for i in range(13101, 13107)]
NOW = datetime(2026, 10, 18, 14, tzinfo=UTC)


@dataclass
class CheckoutHarness:
    database: MagicMock
    session: MagicMock
    repo: MagicMock
    service: DurableCommerceService
    provider: AsyncMock
    audit: AsyncMock
    validate: AsyncMock
    account: ShopperAccountRecord
    cart: ShopperCartRecord
    payment: PaymentAttemptRecord
    hold: InventoryReservationRecord
    receipts: dict[tuple[str, str], IdempotencyRecord]
    orders: list[ShopperOrderRecord]

    async def confirm(
        self, key: str = "same-key", method: TestPaymentMethod = "test_success"
    ) -> CheckoutConfirmation:
        return await self.service.confirm_checkout(
            tenant_id=TENANT,
            account_id=ACCOUNT,
            request=CheckoutConfirmRequest(checkout_id=PAYMENT, payment_method=method),
            idempotency_key=key,
            request_id="synthetic-continuity",
        )

    def snapshot(self) -> object:
        def values(row: Any) -> dict[str, object]:
            return {column.name: getattr(row, column.name) for column in row.__table__.columns}

        return deepcopy(
            (
                [values(row) for row in (self.account, self.cart, self.payment, self.hold)],
                [values(row) for row in self.orders],
                {key: values(row) for key, row in self.receipts.items()},
                self.session.add.call_count,
                self.session.execute.await_count,
                self.session.flush.await_count,
                self.audit.await_count,
            )
        )


@pytest.fixture
def checkout(monkeypatch: pytest.MonkeyPatch) -> CheckoutHarness:
    database = create_autospec(RuntimeDatabase, instance=True)
    session = MagicMock()
    session.scalar, session.execute, session.flush = AsyncMock(), AsyncMock(), AsyncMock()
    database.transaction.return_value.__aenter__.return_value = session
    repo = create_autospec(CommerceRepository, instance=True)
    account = ShopperAccountRecord(id=ACCOUNT, tenant_id=TENANT, status="active", version=1)
    cart = ShopperCartRecord(
        id=CART,
        tenant_id=TENANT,
        account_id=ACCOUNT,
        status="open",
        currency="USD",
        version=4,
        created_at=NOW,
        updated_at=NOW,
    )
    payment = PaymentAttemptRecord(
        id=PAYMENT,
        tenant_id=TENANT,
        account_id=ACCOUNT,
        cart_id=CART,
        cart_version=4,
        provider="local_test",
        provider_reference="synthetic-reference",
        status="requires_confirmation",
        amount_minor=100,
        currency="USD",
        idempotency_key_digest="synthetic-preview",
        rollback_metadata={},
        policy_decision=DurableCommerceService._checkout_policy(
            total_minor=100, preconditions=["synthetic-in-stock"]
        ).model_dump(mode="json"),
        preconditions=[],
        failure_code=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    hold = InventoryReservationRecord(
        id=UUID(int=13110),
        tenant_id=TENANT,
        account_id=ACCOUNT,
        cart_id=CART,
        checkout_id=PAYMENT,
        catalog_variant_id=VARIANT,
        quantity=1,
        status="active",
        expires_at=NOW + timedelta(minutes=15),
        release_reason=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    line = ShopperCartLineRecord(
        id=UUID(int=13111),
        tenant_id=TENANT,
        account_id=ACCOUNT,
        cart_id=CART,
        catalog_variant_id=VARIANT,
        source_product_id="fixture",
        source_variant_id="default",
        title="Synthetic item",
        variant_title="Default",
        quantity=1,
        unit_price_minor=100,
        currency="USD",
        catalog_version=1,
        created_at=NOW,
    )
    receipts: dict[tuple[str, str], IdempotencyRecord] = {}
    orders: list[ShopperOrderRecord] = []

    def read_receipt(statement: Select[Any]) -> IdempotencyRecord | None:
        params = statement.compile().params
        assert params["tenant_id_1"] == TENANT
        return receipts.get((params["scope_1"], params["key_1"]))

    def add(row: IdempotencyRecord | ShopperOrderRecord) -> None:
        if isinstance(row, IdempotencyRecord):
            assert row.tenant_id == TENANT
            receipts[row.scope, row.key] = row
        else:
            orders.append(row)

    async def execute(statement: Update | Delete) -> None:
        params = statement.compile().params
        assert params["tenant_id_1"] == TENANT
        table = statement.table
        assert isinstance(table, Table)
        if isinstance(statement, Update):
            assert table.name == "shopper_accounts" and params["id_1"] == ACCOUNT
            account.version += 1
        elif table.name == "idempotency_records":
            if params["scope_1"] == "shopper:":
                for key in list(receipts):
                    if key[0].startswith("shopper:") and key[0].endswith(str(ACCOUNT)):
                        if key[0] != f"shopper:preferences:{ACCOUNT}":
                            del receipts[key]
            else:
                assert params["scope_1"] == f"activity:configure:{ACCOUNT}"

    async def get_payment(
        *, account_id: UUID, payment_id: UUID, for_update: bool = False
    ) -> PaymentAttemptRecord:
        if account_id != payment.account_id or payment_id != payment.id:
            raise CommerceNotFoundError("Checkout was not found")
        return payment

    async def open_cart(*, account_id: UUID, for_update: bool = False) -> ShopperCartRecord | None:
        return cart if account_id == cart.account_id and cart.status == "open" else None

    async def invalidate(*, cart: ShopperCartRecord, now: datetime) -> None:
        if payment.status == "processing":
            raise CommerceConflictError("Checkout is processing; the cart cannot be changed")
        if hold.status == "active":
            hold.status, hold.release_reason = "released", "cart_changed"
            hold.version += 1
        if payment.status in {"requires_confirmation", "requires_payment_method"}:
            payment.status = "cancelled"
            payment.version += 1

    session.scalar.side_effect, session.add.side_effect = read_receipt, add
    session.execute.side_effect = execute
    repo.payment.side_effect = get_payment
    repo.open_cart.side_effect = open_cart
    repo.cart_by_id.return_value = cart
    repo.cart_lines.return_value = [line]
    repo.reservations_for_checkout.return_value = [hold]
    repo.payment_for_cart_version.return_value = payment
    repo.invalidate_checkout.side_effect = invalidate
    repo.order_for_payment.side_effect = lambda **kwargs: orders[0] if orders else None
    monkeypatch.setattr(commerce_service, "CommerceRepository", lambda *args: repo)
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *args: repo)
    monkeypatch.setattr(commerce_service, "utc_now", lambda: NOW)
    monkeypatch.setattr(shoppers, "utc_now", lambda: NOW)
    provider = AsyncMock(
        return_value=PaymentConfirmationResult(
            status="succeeded", provider_reference="synthetic-reference"
        )
    )
    service = DurableCommerceService(
        database,
        payment_provider=cast(
            PaymentProvider, SimpleNamespace(payment_mode="local_test", confirm=provider)
        ),
    )
    validate = AsyncMock(return_value=([(line, None)], 100, ["synthetic-in-stock"]))
    audit = AsyncMock()
    monkeypatch.setattr(service, "_validate_checkout_lines", validate)
    monkeypatch.setattr(service, "_audit", audit)
    return CheckoutHarness(
        database,
        session,
        repo,
        service,
        provider,
        audit,
        validate,
        account,
        cart,
        payment,
        hold,
        receipts,
        orders,
    )


class ResultGate:
    def __init__(self, checkout: CheckoutHarness) -> None:
        self.checkout = checkout
        self.entered = [asyncio.Event() for _ in range(3)]
        self.release = [asyncio.Event() for _ in range(3)]
        self.requests: list[PaymentConfirmationRequest] = []
        self.tasks: list[asyncio.Task[CheckoutConfirmation]] = []

    async def result(self, request: PaymentConfirmationRequest) -> PaymentConfirmationResult:
        index = len(self.requests)
        self.requests.append(request)
        self.entered[index].set()
        await asyncio.wait_for(self.release[index].wait(), timeout=5)
        decline = request.payment_method == "test_decline"
        return PaymentConfirmationResult(
            status="requires_payment_method" if decline else "succeeded",
            failure_code="test_card_declined" if decline else None,
            provider_reference="synthetic-reference",
        )

    async def start(
        self, key: str = "same-key", method: TestPaymentMethod = "test_success"
    ) -> asyncio.Task[CheckoutConfirmation]:
        index = len(self.requests)
        task = asyncio.create_task(self.checkout.confirm(key, method))
        self.tasks.append(task)
        await asyncio.wait_for(self.entered[index].wait(), timeout=5)
        return task


@asynccontextmanager
async def delayed_results(checkout: CheckoutHarness) -> AsyncIterator[ResultGate]:
    gate = ResultGate(checkout)
    checkout.provider.side_effect = gate.result
    try:
        yield gate
    finally:
        for release in gate.release:
            release.set()
        await asyncio.gather(*gate.tasks, return_exceptions=True)


@pytest.mark.parametrize("choice", ["keep_guest", "keep_account"])
@pytest.mark.parametrize("present", [(True, True), (True, False), (False, True), (False, False)])
async def test_only_transferred_retained_guest_cart_advances_version(
    monkeypatch: pytest.MonkeyPatch, choice: str, present: tuple[bool, bool]
) -> None:
    session = MagicMock(execute=AsyncMock(), flush=AsyncMock())
    guest = ShopperAccountRecord(id=GUEST, is_guest=True, version=2, status="active")
    target = ShopperAccountRecord(id=ACCOUNT, is_guest=False, version=3, status="active")
    carts = {
        GUEST: ShopperCartRecord(id=UUID(int=13120), account_id=GUEST, status="open", version=7),
        ACCOUNT: ShopperCartRecord(id=CART, account_id=ACCOUNT, status="open", version=4),
    }
    repo = MagicMock()
    repo.open_cart = AsyncMock(
        side_effect=lambda **kw: (
            carts[kw["account_id"]] if present[0 if kw["account_id"] == GUEST else 1] else None
        )
    )
    repo.invalidate_checkout = AsyncMock()
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *args: repo)
    monkeypatch.setattr(shoppers, "utc_now", lambda: NOW)

    await ShopperAccounts(MagicMock()).merge_records(session, TENANT, guest, target, choice)

    assert carts[GUEST].version == 7 + int(present[0] and choice == "keep_guest")
    assert carts[ACCOUNT].version == 4
    if present[0] and choice == "keep_guest":
        assert carts[GUEST].updated_at == NOW and carts[GUEST].status == "open"
    if present[0] and choice == "keep_account":
        assert carts[GUEST].status == "abandoned"
    if present[1] and choice == "keep_guest":
        assert carts[ACCOUNT].status == "abandoned"
    assert guest.version == 3 and guest.status == "disabled"
    assert target.version == 3 and target.status == "active"
    tables = {args.args[0].table.name for args in session.execute.call_args_list}
    assert not tables & {"payment_attempts", "inventory_reservations", "shopper_orders"}


async def test_processing_checkout_still_blocks_cart_transfer(checkout: CheckoutHarness) -> None:
    checkout.payment.status = "processing"
    guest = ShopperAccountRecord(id=ACCOUNT, is_guest=True, version=1, status="active")
    target = ShopperAccountRecord(id=GUEST, is_guest=False, version=1, status="active")
    with pytest.raises(CommerceConflictError, match="processing"):
        await ShopperAccounts(checkout.database).merge_records(
            checkout.session, TENANT, guest, target, "keep_guest"
        )
    assert checkout.cart.version == 4 and checkout.cart.status == "open"
    assert guest.version == 1 and guest.status == "active"
    checkout.session.execute.assert_not_called()


@pytest.mark.parametrize(
    "status",
    ["requires_confirmation", "processing", "requires_payment_method", "cancelled", "succeeded"],
)
async def test_preview_rejects_foreign_owned_payment_before_reuse(
    checkout: CheckoutHarness, status: str
) -> None:
    checkout.payment.account_id, checkout.payment.status = GUEST, status
    before = checkout.snapshot()
    with pytest.raises(CommerceConflictError, match="different shopping session") as error:
        await checkout.service.preview_checkout(
            tenant_id=TENANT,
            account_id=ACCOUNT,
            request=CheckoutPreviewRequest(cart_version=4),
            idempotency_key="preview",
            request_id="preview",
        )
    assert str(GUEST) not in str(error.value)
    assert checkout.snapshot() == before
    checkout.validate.assert_not_called()
    checkout.repo.reservations_for_checkout.assert_not_called()


@pytest.mark.parametrize("method", ["test_success", "test_decline"])
@pytest.mark.parametrize("delete_between", [False, True])
async def test_overlapping_result_after_real_deletion_method_is_read_only(
    checkout: CheckoutHarness, method: TestPaymentMethod, delete_between: bool
) -> None:
    """Actual deletion method, mocked SQL storage; unlike receipt-only fault injection."""
    async with delayed_results(checkout) as gate:
        first, duplicate = await gate.start(method=method), await gate.start(method=method)
        gate.release[0].set()
        original = await first
        assert original.status == (
            "succeeded" if method == "test_success" else "requires_payment_method"
        )
        assert len(checkout.receipts) == 1
        if delete_between:
            await ShopperAccounts(checkout.database).delete_data(TENANT, ACCOUNT)
            assert not checkout.receipts and checkout.account.version == 2
            if method == "test_decline":
                assert (
                    checkout.cart.status == "abandoned" and checkout.payment.status == "cancelled"
                )
                with pytest.raises(CommercePreconditionError):
                    await checkout.confirm("new-key")
                assert checkout.provider.await_count == 2
        before = checkout.snapshot()
        cart_reads = checkout.repo.cart_by_id.await_count
        gate.release[1].set()
        late = await duplicate
        expected = "cancelled" if delete_between and method == "test_decline" else original.status
        assert late.status == expected
        assert checkout.snapshot() == before
        assert checkout.repo.cart_by_id.await_count == cart_reads
        assert len(checkout.orders) == int(method == "test_success")
        if delete_between and method == "test_success":
            assert (await checkout.confirm("fresh-retry-key")).status == "succeeded"
            assert checkout.snapshot() == before
            assert checkout.provider.await_count == 2
        state = await checkout.service.checkout_status(
            tenant_id=TENANT, account_id=ACCOUNT, checkout_id=PAYMENT
        )
        assert state is not None and state.status == expected


@pytest.mark.parametrize("change", ["key", "body", "both"])
async def test_receipt_only_loss_fault_cannot_let_old_decline_overwrite_new_attempt(
    checkout: CheckoutHarness, change: str
) -> None:
    """Fault injection, NOT reachable through normal shopping-data deletion."""
    async with delayed_results(checkout) as gate:
        first = await gate.start("old-key", "test_decline")
        duplicate = await gate.start("old-key", "test_decline")
        gate.release[0].set()
        assert (await first).status == "requires_payment_method"
        checkout.receipts.clear()
        key = "old-key" if change == "body" else "new-key"
        method: TestPaymentMethod = "test_decline" if change == "key" else "test_success"
        newer = await gate.start(key, method)
        assert checkout.payment.status == "processing"
        before = checkout.snapshot()
        cart_reads = checkout.repo.cart_by_id.await_count
        gate.release[1].set()
        with pytest.raises(CommerceConflictError, match="attempt changed"):
            await duplicate
        assert checkout.snapshot() == before
        assert checkout.repo.cart_by_id.await_count == cart_reads
        gate.release[2].set()
        assert (await newer).status == (
            "requires_payment_method" if change == "key" else "succeeded"
        )


@pytest.mark.parametrize("state", ["requires_payment_method", "requires_confirmation"])
async def test_missing_receipt_for_settled_or_reset_attempt_cannot_restart_finalization(
    checkout: CheckoutHarness, state: str
) -> None:
    """Synthetic receipt loss; a preview reset is a separate injected state transition."""
    async with delayed_results(checkout) as gate:
        first = await gate.start(method="test_decline")
        duplicate = await gate.start(method="test_decline")
        gate.release[0].set()
        await first
        checkout.receipts.clear()
        checkout.payment.status = state
        before = checkout.snapshot()
        cart_reads = checkout.repo.cart_by_id.await_count
        gate.release[1].set()
        if state == "requires_confirmation":
            with pytest.raises(CommerceConflictError, match="attempt changed"):
                await duplicate
        else:
            result = await duplicate
            assert result.status == state and result.failure_code == "test_card_declined"
        assert checkout.snapshot() == before
        assert checkout.repo.cart_by_id.await_count == cart_reads


async def test_matching_processing_result_still_cancels_expired_hold(
    checkout: CheckoutHarness,
) -> None:
    async with delayed_results(checkout) as gate:
        pending = await gate.start()
        checkout.hold.expires_at = NOW - timedelta(seconds=1)
        gate.release[0].set()
        result = await pending
    assert result.status == checkout.payment.status == "cancelled"
    assert checkout.cart.version == 5 and checkout.hold.status == "released"
    assert not checkout.orders and len(checkout.receipts) == 1
    observed = checkout.payment.rollback_metadata["observed_test_provider_result"]
    assert isinstance(observed, dict) and observed["status"] == "succeeded"


@pytest.mark.parametrize("phase", ["admission", "finalization"])
async def test_missing_processing_body_fingerprint_fails_without_mutation(
    checkout: CheckoutHarness, phase: str
) -> None:
    if phase == "admission":
        checkout.payment.status = "processing"
        checkout.payment.idempotency_key_digest = commerce_service._key_digest("same-key")
        before = checkout.snapshot()
        with pytest.raises(CommerceConflictError, match="original confirmation body"):
            await checkout.confirm()
        assert checkout.snapshot() == before
        checkout.provider.assert_not_called()
    else:
        async with delayed_results(checkout) as gate:
            pending = await gate.start()
            checkout.payment.rollback_metadata = {}
            before = checkout.snapshot()
            gate.release[0].set()
            with pytest.raises(CommerceConflictError, match="attempt changed"):
                await pending
            assert checkout.snapshot() == before


@pytest.mark.parametrize("phase", ["admission", "finalization"])
async def test_succeeded_payment_without_retained_order_does_not_invent_success(
    checkout: CheckoutHarness, phase: str
) -> None:
    if phase == "admission":
        checkout.payment.status = "succeeded"
        before = checkout.snapshot()
        with pytest.raises(CommerceConflictError, match="missing its order"):
            await checkout.confirm()
        assert checkout.snapshot() == before
        checkout.provider.assert_not_called()
    else:
        async with delayed_results(checkout) as gate:
            pending = await gate.start()
            checkout.payment.status = "succeeded"
            before = checkout.snapshot()
            gate.release[0].set()
            with pytest.raises(CommerceConflictError, match="missing its order"):
                await pending
            assert checkout.snapshot() == before
