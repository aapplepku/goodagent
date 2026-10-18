"""Disposable PostgreSQL regressions for merged and historically retired guests."""

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Literal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import tests.integration.test_checkout_account_continuity as checkout_fixtures
from open_commerce.commerce.models import (
    CartItemAddRequest,
    CheckoutConfirmRequest,
    CheckoutPreviewRequest,
)
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.db import Base
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.shopper_agent.models import (
    ShopperChatRequest,
    ShopperLoginRequest,
    ShopperRegisterRequest,
)
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.stores.shoppers import MergeSelection, ShopperAccounts

pytestmark = pytest.mark.integration
checkout_store = checkout_fixtures.checkout_store

CONTENT = ("shopper:chat:", "shopper:chat:start:", "shopper:memory:save:", "shopper:memory:delete:")
RETAINED = (
    "shopper:preferences:",
    "guest:turn:",
    "shopper:cart:add:",
    "shopper:cart:update:",
    "shopper:cart:delete:",
    "shopper:checkout:preview:",
    "shopper:checkout:confirm:",
    "shopper:chat:future:",
    "shopper:memory:save:future:",
    "other:shopper:chat:",
)
HISTORY = ("shopper_conversations", "shopper_messages", "shopper_memories")
STATE = (
    "shopper_accounts",
    "shopper_sessions",
    *HISTORY,
    "shopper_carts",
    "shopper_cart_lines",
    "inventory_reservations",
    "payment_attempts",
    "shopper_orders",
    "audit_events",
    "shopper_activity",
    "activity_rules",
    "activity_checks",
    "auth_tickets",
    "idempotency_records",
)
Snapshot = dict[str, list[dict[str, object]]]


@pytest.fixture
async def receipt_database(
    integration_settings: Settings,
) -> AsyncIterator[tuple[RuntimeDatabase, UUID]]:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    try:
        await database.initialize_tenant(tenant)
        yield database, tenant
    finally:
        await database.close()


async def snapshot(
    database: RuntimeDatabase,
    tenant: UUID,
    tables: tuple[str, ...] = STATE,
) -> Snapshot:
    result: Snapshot = {}
    async with database.transaction(tenant) as session:
        for name in tables:
            table = Base.metadata.tables[name]
            rows = await session.execute(
                select(table)
                .where(table.c.tenant_id == tenant)
                .order_by(*table.primary_key.columns)
            )
            result[name] = [dict(row) for row in rows.mappings()]
    return result


async def receipts(
    database: RuntimeDatabase, tenant: UUID
) -> dict[tuple[str, str], dict[str, object]]:
    state = await snapshot(database, tenant, ("idempotency_records",))
    return {(str(row["scope"]), str(row["key"])): row for row in state["idempotency_records"]}


def content_scopes(account: UUID) -> set[str]:
    return {prefix + str(account) for prefix in CONTENT}


def seed_receipts(session: AsyncSession, tenant: UUID, account: UUID, *, keys: int = 1) -> None:
    # Several keys per exact scope, plus plausible prefixes that must survive.
    for prefix in (*CONTENT, *RETAINED):
        for key in range(keys):
            session.add(
                IdempotencyRecord(
                    tenant_id=tenant,
                    scope=f"{prefix}{account}",
                    key=f"synthetic-{key}",
                    fingerprint="f" * 64,
                    response={"synthetic": prefix, "account": str(account)},
                )
            )
    session.add(
        IdempotencyRecord(
            tenant_id=tenant,
            scope=f"shopper:chat:{account}:extra",
            key="synthetic",
            fingerprint="f" * 64,
            response={"synthetic": "suffix control"},
        )
    )


def seed_account(
    session: AsyncSession,
    tenant: UUID,
    *,
    account: UUID | None = None,
    status: str = "disabled",
    guest: bool = True,
) -> UUID:
    account = account or uuid4()
    session.add(
        ShopperAccountRecord(
            id=account,
            tenant_id=tenant,
            username=f"g-{account.hex}",
            display_name="Synthetic",
            password_hash="disabled",
            status=status,
            is_guest=guest,
            memory_enabled=False,
            expires_at=utc_now() + timedelta(hours=12) if guest else None,
            version=5,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    return account


async def seed_history(database: RuntimeDatabase, tenant: UUID, account: UUID) -> None:
    service = DurableShopperAgentService(database, search_service=SearchService())
    first = await service.chat(
        tenant_id=tenant,
        account_id=account,
        request=ShopperChatRequest(content="I prefer synthetic red mugs"),
        idempotency_key="red-mugs",
    )
    assert first.memory_created is not None
    second = await service.chat(
        tenant_id=tenant,
        account_id=account,
        request=ShopperChatRequest(content="I prefer synthetic blue bowls"),
        idempotency_key="blue-bowls",
    )
    assert second.memory_created is not None
    await service.delete_memory(
        tenant_id=tenant,
        account_id=account,
        memory_id=second.memory_created.id,
        idempotency_key="remove-blue-bowls",
    )
    assert content_scopes(account) <= {scope for scope, _ in await receipts(database, tenant)}


async def signed_in_target(database: RuntimeDatabase, tenant: UUID) -> UUID:
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    target, _ = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="receipt-target",
            display_name="Synthetic target",
            password="synthetic-receipt-password",
        ),
    )
    return target.account.id


def login_request() -> ShopperLoginRequest:
    return ShopperLoginRequest(username="receipt-target", password="synthetic-receipt-password")


@pytest.mark.parametrize("mode", ["automatic", "keep_guest", "keep_account"])
async def test_login_merge_erases_only_source_receipts_and_preserves_history_until_deletion(
    checkout_store: tuple[RuntimeDatabase, UUID],
    mode: Literal["automatic", "keep_guest", "keep_account"],
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    target = await signed_in_target(database, tenant)
    guest, guest_token = await accounts.guest(tenant, None)
    source = guest.account.id
    await seed_history(database, tenant, source)
    await seed_history(database, tenant, target)
    await accounts.preferences(tenant, target, False, idempotency_key="target-opt-out")
    await accounts.preferences(tenant, source, False, idempotency_key="source-opt-out")
    assert await accounts.admit_turn(tenant, source, "quota")
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    for account in (source, target):
        cart = await commerce.add_item(
            tenant_id=tenant,
            account_id=account,
            request=CartItemAddRequest(product_id="fixture-mug"),
            idempotency_key="completed-cart",
            request_id="completed-cart",
        )
        preview = await commerce.preview_checkout(
            tenant_id=tenant,
            account_id=account,
            request=CheckoutPreviewRequest(cart_version=cart.version),
            idempotency_key="completed-preview",
            request_id="completed-preview",
        )
        confirmed = await commerce.confirm_checkout(
            tenant_id=tenant,
            account_id=account,
            request=CheckoutConfirmRequest(
                checkout_id=preview.checkout_id, payment_method="test_success"
            ),
            idempotency_key="completed-confirm",
            request_id="completed-confirm",
        )
        assert confirmed.status == "succeeded" and confirmed.order is not None
    completed_tables = ("shopper_orders", "payment_attempts", "inventory_reservations")
    completed_before = await snapshot(database, tenant, completed_tables)
    for table, status in zip(completed_tables, ("paid", "succeeded", "consumed"), strict=True):
        rows = completed_before[table]
        assert len(rows) == 2
        assert {row["account_id"] for row in rows} == {source, target}
        assert {row["status"] for row in rows} == {status}

    async def assert_completed_records_unchanged() -> None:
        current = await snapshot(database, tenant, completed_tables)
        for table, previous in completed_before.items():
            ids = {row["id"] for row in previous}
            assert [row for row in current[table] if row["id"] in ids] == previous

    guest_cart = await commerce.add_item(
        tenant_id=tenant,
        account_id=source,
        request=CartItemAddRequest(product_id="fixture-mug"),
        idempotency_key="guest-cart",
        request_id="guest-cart",
    )
    await commerce.preview_checkout(
        tenant_id=tenant,
        account_id=source,
        request=CheckoutPreviewRequest(cart_version=guest_cart.version),
        idempotency_key="guest-preview",
        request_id="guest-preview",
    )
    target_cart = None
    if mode != "automatic":
        target_cart = await commerce.add_item(
            tenant_id=tenant,
            account_id=target,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=2),
            idempotency_key="target-cart",
            request_id="target-cart",
        )
    other, _ = await accounts.guest(tenant, None)
    foreign = uuid4()
    await database.initialize_tenant(foreign)
    async with database.transaction(tenant, write=True) as session:
        seed_receipts(session, tenant, source)
        seed_receipts(session, tenant, other.account.id)
    async with database.transaction(foreign, write=True) as session:
        seed_receipts(session, foreign, source)  # Identical scope strings in another tenant.
    before = await receipts(database, tenant)
    foreign_before = await snapshot(database, foreign)
    history_before = await snapshot(database, tenant, HISTORY)
    audit_before = await snapshot(database, tenant, ("audit_events", "shopper_orders"))
    expected = {key: row for key, row in before.items() if key[0] not in content_scopes(source)}

    result, token = await accounts.login(tenant, source, login_request())
    if mode != "automatic":
        assert result.merge_token and token is None
        assert await receipts(database, tenant) == before
        assert await snapshot(database, tenant, HISTORY) == history_before
        result, token = await accounts.merge(
            tenant,
            source,
            MergeSelection(token=result.merge_token, cart_choice=mode),
        )
    assert result.account.id == target and token and not result.merge_token
    await assert_completed_records_unchanged()
    assert await receipts(database, tenant) == expected
    assert await snapshot(database, foreign) == foreign_before
    history_after = await snapshot(database, tenant, HISTORY)
    for table in HISTORY:
        assert len(history_after[table]) == len(history_before[table])
        for old, current in zip(history_before[table], history_after[table], strict=True):
            expected_row = dict(old)
            if old["account_id"] == source:
                expected_row["account_id"] = target
                if "updated_at" in old:
                    # The existing transfer refreshes the conversation's update timestamp.
                    expected_row["updated_at"] = current["updated_at"]
            assert current == expected_row
    retained_cart = await commerce.get_cart(tenant_id=tenant, account_id=target)
    assert retained_cart.id == (
        target_cart.id if mode == "keep_account" and target_cart else guest_cart.id
    )
    async with database.transaction(tenant) as session:
        source_row = await session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == tenant,
                ShopperAccountRecord.id == source,
            )
        )
        assert source_row and source_row.status == "disabled" and source_row.version == 2
        assert guest_token
        repo = ShopperRepository(session, tenant)
        assert (
            await repo.account_for_session(
                token_hash=session_token_hash(guest_token), now=utc_now()
            )
            is None
        )
        assert not (await accounts.account(session, tenant, target)).memory_enabled
        assert await repo.list_memories(account_id=target) == []
        assert len(await repo.list_memories_for_management(account_id=target)) == 2
    await accounts.cleanup(tenant)
    assert await receipts(database, tenant) == expected
    assert await snapshot(database, tenant, HISTORY) == history_after
    await accounts.delete_data(tenant, target)
    await accounts.cleanup(tenant)
    await assert_completed_records_unchanged()
    assert all(not rows for rows in (await snapshot(database, tenant, HISTORY)).values())
    remaining = await receipts(database, tenant)
    assert not content_scopes(source).intersection(scope for scope, _ in remaining)
    assert not content_scopes(target).intersection(scope for scope, _ in remaining)
    # Explicit deletion retains its existing broad predicate; source commerce stays scoped away.
    for key, value in expected.items():
        if not key[0].endswith(str(target)) or key[0] == f"shopper:preferences:{target}":
            assert remaining[key] == value
    assert await snapshot(database, foreign) == foreign_before
    assert await snapshot(database, tenant, ("audit_events", "shopper_orders")) == audit_before


@pytest.mark.parametrize("mode", ["automatic", "keep_guest", "keep_account"])
async def test_failed_merge_rolls_back_receipts_history_sessions_carts_and_grant(
    checkout_store: tuple[RuntimeDatabase, UUID],
    mode: Literal["automatic", "keep_guest", "keep_account"],
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    target = await signed_in_target(database, tenant)
    guest, _ = await accounts.guest(tenant, None)
    await seed_history(database, tenant, guest.account.id)
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    for account in (guest.account.id, target) if mode != "automatic" else (guest.account.id,):
        await commerce.add_item(
            tenant_id=tenant,
            account_id=account,
            request=CartItemAddRequest(product_id="fixture-mug"),
            idempotency_key="cart",
            request_id="cart",
        )
    grant = None
    if mode != "automatic":
        result, _ = await accounts.login(tenant, guest.account.id, login_request())
        grant = result.merge_token
        assert grant
    before = await snapshot(database, tenant)
    original_erase = accounts._erase_content_receipts

    async def fail_after_delete(session: AsyncSession, owner: UUID, account: UUID) -> None:
        await original_erase(session, owner, account)
        raise RuntimeError("synthetic failure after receipt erasure")

    with patch.object(accounts, "_erase_content_receipts", side_effect=fail_after_delete):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            if grant:
                assert mode != "automatic"
                await accounts.merge(
                    tenant, guest.account.id, MergeSelection(token=grant, cart_choice=mode)
                )
            else:
                await accounts.login(tenant, guest.account.id, login_request())
    assert await snapshot(database, tenant) == before


async def test_registration_keeps_same_identity_history_and_receipts(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    await seed_history(database, tenant, guest.account.id)
    await accounts.preferences(tenant, guest.account.id, False, idempotency_key="opt-out")
    assert await accounts.admit_turn(tenant, guest.account.id, "quota")
    before = await receipts(database, tenant)
    history = await snapshot(database, tenant, HISTORY)
    registered, _ = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="same-identity",
            display_name="Synthetic registration",
            password="synthetic-registration-password",
        ),
    )
    assert registered.account.id == guest.account.id
    await accounts.cleanup(tenant)
    assert await receipts(database, tenant) == before
    assert await snapshot(database, tenant, HISTORY) == history


async def test_expired_guest_keeps_existing_deletion_behavior_and_is_not_swept_twice(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    await seed_history(database, tenant, guest.account.id)
    await accounts.preferences(tenant, guest.account.id, False, idempotency_key="opt-out")
    assert await accounts.admit_turn(tenant, guest.account.id, "quota")
    async with database.transaction(tenant, write=True) as session:
        row = await accounts.account(session, tenant, guest.account.id)
        row.expires_at = utc_now() - timedelta(seconds=1)
    before = await receipts(database, tenant)
    await accounts.cleanup(tenant)
    expected = {
        key: row for key, row in before.items() if key[0] not in content_scopes(guest.account.id)
    }
    assert await receipts(database, tenant) == expected
    assert all(not rows for rows in (await snapshot(database, tenant, HISTORY)).values())
    retired = await snapshot(database, tenant)
    assert retired["shopper_accounts"][0]["version"] == 2
    assert retired["shopper_accounts"][0]["status"] == "disabled"
    await accounts.cleanup(tenant)
    assert await snapshot(database, tenant) == retired


async def test_historical_cleanup_repairs_only_disabled_guests_with_exact_local_receipts(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    foreign = uuid4()
    await database.initialize_tenant(foreign)
    accounts = ShopperAccounts(database)
    target = await signed_in_target(database, tenant)
    await seed_history(database, tenant, target)
    async with database.transaction(tenant, write=True) as session:
        retired = seed_account(session, tenant)
        active = seed_account(session, tenant, status="active")
        registered = seed_account(session, tenant, guest=False)
        foreign_only = seed_account(session, tenant)
        for account in (retired, active, registered, target):
            seed_receipts(session, tenant, account, keys=3)
        # Retained scopes alone must not cause a historical candidate.
        session.add(
            IdempotencyRecord(
                tenant_id=tenant,
                scope=f"guest:turn:{foreign_only}",
                key="quota",
                fingerprint="f" * 64,
                response={"allowed": True},
            )
        )
    async with database.transaction(foreign, write=True) as session:
        foreign_account = seed_account(session, foreign)
        for account in (retired, foreign_only, foreign_account):
            seed_receipts(session, foreign, account)
    before, foreign_before = await snapshot(database, tenant), await snapshot(database, foreign)
    seen: list[UUID] = []
    erase = accounts._erase_retired_guest_receipts

    async def record(owner: UUID, account: UUID) -> None:
        seen.append(account)
        await erase(owner, account)

    with patch.object(accounts, "_erase_retired_guest_receipts", side_effect=record):
        await accounts.cleanup(tenant)
        await accounts.cleanup(tenant)
    assert seen == [retired]
    expected = {
        **before,
        "idempotency_records": [
            row
            for row in before["idempotency_records"]
            if row["scope"] not in content_scopes(retired)
        ],
    }
    assert await snapshot(database, tenant) == expected
    assert await snapshot(database, foreign) == foreign_before


@pytest.mark.parametrize("change", ["active", "registered", "foreign", "cleared"])
async def test_historical_selection_is_rechecked_inside_write_transaction(
    receipt_database: tuple[RuntimeDatabase, UUID],
    change: str,
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    async with database.transaction(tenant, write=True) as session:
        account = seed_account(session, tenant)
        seed_receipts(session, tenant, account)
    foreign = uuid4()
    await database.initialize_tenant(foreign)
    erase = accounts._erase_retired_guest_receipts
    expected: Snapshot = {}

    async def change_before_lock(owner: UUID, selected: UUID) -> None:
        nonlocal expected
        assert owner == tenant and selected == account
        async with database.transaction(tenant, write=True) as session:
            row = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant,
                    ShopperAccountRecord.id == account,
                )
            )
            assert row
            if change == "active":
                row.status = "active"
            elif change == "registered":
                row.is_guest = False
                row.expires_at = None
            elif change == "cleared":
                await accounts._erase_content_receipts(session, tenant, account)
        expected = await snapshot(database, tenant)
        await erase(foreign if change == "foreign" else owner, selected)

    with patch.object(accounts, "_erase_retired_guest_receipts", side_effect=change_before_lock):
        await accounts.cleanup(tenant)
    assert expected and await snapshot(database, tenant) == expected


async def test_historical_failure_rolls_back_and_retry_erases_only_receipts(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    async with database.transaction(tenant, write=True) as session:
        account = seed_account(session, tenant)
        seed_receipts(session, tenant, account)
    before = await snapshot(database, tenant)
    erase = accounts._erase_content_receipts

    async def fail_after_delete(session: AsyncSession, owner: UUID, selected: UUID) -> None:
        await erase(session, owner, selected)
        raise RuntimeError("synthetic sweep failure")

    with patch.object(accounts, "_erase_content_receipts", side_effect=fail_after_delete):
        with pytest.raises(RuntimeError, match="synthetic sweep failure"):
            await accounts.cleanup(tenant)
    assert await snapshot(database, tenant) == before
    await accounts.cleanup(tenant)
    expected = {
        **before,
        "idempotency_records": [
            row
            for row in before["idempotency_records"]
            if row["scope"] not in content_scopes(account)
        ],
    }
    assert await snapshot(database, tenant) == expected


async def test_more_than_100_retired_guests_progress_past_cleared_and_foreign_only_accounts(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    foreign = uuid4()
    await database.initialize_tenant(foreign)
    # Ascending, globally unique fixture UUIDs guarantee clean rows precede dirty rows.
    base = uuid4().int & ~0xFFFF
    clean = [UUID(int=base + index) for index in range(1, 111)]
    dirty = [UUID(int=base + index) for index in range(111, 216)]
    async with database.transaction(tenant, write=True) as session:
        for account in (*clean, *dirty):
            seed_account(session, tenant, account=account)
            seed_receipts(session, tenant, account)
        await session.flush()
        for account in clean:
            await accounts._erase_content_receipts(session, tenant, account)
    async with database.transaction(foreign, write=True) as session:
        for account in clean:
            seed_receipts(session, foreign, account)
    before = await snapshot(database, tenant)
    foreign_before = await snapshot(database, foreign)
    selected: list[UUID] = []
    erase = accounts._erase_retired_guest_receipts

    async def record(owner: UUID, account: UUID) -> None:
        selected.append(account)
        await erase(owner, account)

    with patch.object(accounts, "_erase_retired_guest_receipts", side_effect=record):
        await accounts.cleanup(tenant)
        assert selected == dirty[:100]
        scopes = {scope for scope, _ in await receipts(database, tenant)}
        assert not set().union(*(content_scopes(account) for account in dirty[:100])) & scopes
        assert set().union(*(content_scopes(account) for account in dirty[100:])) <= scopes
        await accounts.cleanup(tenant)
        assert selected == dirty
        await accounts.cleanup(tenant)
        assert selected == dirty
    removed = set().union(*(content_scopes(account) for account in dirty))
    expected = {
        **before,
        "idempotency_records": [
            row for row in before["idempotency_records"] if row["scope"] not in removed
        ],
    }
    assert await snapshot(database, tenant) == expected
    assert await snapshot(database, foreign) == foreign_before


async def test_duplicate_historical_selections_are_idempotent(
    receipt_database: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = receipt_database
    accounts = ShopperAccounts(database)
    async with database.transaction(tenant, write=True) as session:
        account = seed_account(session, tenant)
        seed_receipts(session, tenant, account)
    before = await snapshot(database, tenant)
    selected = 0
    both_selected = asyncio.Event()
    erase = accounts._erase_retired_guest_receipts

    async def gate(owner: UUID, candidate: UUID) -> None:
        nonlocal selected
        assert candidate == account
        selected += 1
        if selected == 2:
            both_selected.set()
        await asyncio.wait_for(both_selected.wait(), timeout=10)
        await erase(owner, candidate)

    with patch.object(accounts, "_erase_retired_guest_receipts", side_effect=gate):
        await asyncio.wait_for(
            asyncio.gather(accounts.cleanup(tenant), accounts.cleanup(tenant)), 15
        )
    assert selected == 2
    expected = {
        **before,
        "idempotency_records": [
            row
            for row in before["idempotency_records"]
            if row["scope"] not in content_scopes(account)
        ],
    }
    assert await snapshot(database, tenant) == expected
