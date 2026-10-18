"""Expiry selection is revalidated before writes; explicit deletion stays separate."""

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock, call, create_autospec
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores import shoppers
from open_commerce.stores.shoppers import ShopperAccounts

TENANT, ACCOUNT = UUID(int=12801), UUID(int=12802)
NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


@pytest.fixture
def database() -> MagicMock:
    database = create_autospec(RuntimeDatabase, instance=True)
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = None
    database.transaction.return_value.__aenter__.return_value = session
    return cast(MagicMock, database)


def session_for(database: MagicMock) -> MagicMock:
    return cast(MagicMock, database.transaction.return_value.__aenter__.return_value)


@pytest.fixture
def commerce_factory(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    commerce = MagicMock()
    commerce.open_cart = AsyncMock(return_value=None)
    commerce.invalidate_checkout = AsyncMock()
    factory = MagicMock(return_value=commerce)
    monkeypatch.setattr(shoppers, "CommerceRepository", factory)
    monkeypatch.setattr(shoppers, "utc_now", lambda: NOW)
    return factory


def assert_no_writes(session: MagicMock, commerce_factory: MagicMock) -> None:
    session.execute.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    commerce_factory.assert_not_called()


async def test_expiry_predicate_uses_current_time_inside_scoped_write_transaction(
    database: MagicMock, commerce_factory: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = session_for(database)
    clock = NOW - timedelta(days=1)
    entered = False

    async def enter() -> MagicMock:
        nonlocal clock, entered
        clock, entered = NOW, True
        return session

    def current_time() -> datetime:
        assert entered, "Expiry must be rechecked after acquiring the tenant write lock"
        return clock

    database.transaction.return_value.__aenter__.side_effect = enter
    monkeypatch.setattr(shoppers, "utc_now", current_time)
    await ShopperAccounts(database).delete_data(TENANT, ACCOUNT, expired=True)

    database.transaction.assert_called_once_with(TENANT, write=True)
    session.scalar.assert_awaited_once()
    query = session.scalar.call_args.args[0]
    compiled = query.compile()
    assert list(query.selected_columns.keys()) == ["id"]
    assert compiled.params == {
        "tenant_id_1": TENANT,
        "id_1": ACCOUNT,
        "status_1": "active",
        "expires_at_1": NOW,
    }
    sql = str(compiled)
    for predicate in (
        "shopper_accounts.tenant_id = :tenant_id_1",
        "shopper_accounts.id = :id_1",
        "shopper_accounts.is_guest IS true",
        "shopper_accounts.status = :status_1",
        "shopper_accounts.expires_at IS NOT NULL",
        "shopper_accounts.expires_at <= :expires_at_1",
    ):
        assert predicate in sql
    assert_no_writes(session, commerce_factory)


async def test_stale_cleanup_selection_is_rechecked_before_any_mutation(
    database: MagicMock, commerce_factory: MagicMock
) -> None:
    session = session_for(database)
    session.scalars.side_effect = [[ACCOUNT], []]
    session.scalar.return_value = None

    await ShopperAccounts(database).cleanup(TENANT)

    assert database.transaction.call_args_list == [
        call(TENANT),
        call(TENANT, write=True),
        call(TENANT),
    ]
    assert session.scalars.await_count == 2
    session.scalar.assert_awaited_once()
    assert_no_writes(session, commerce_factory)


async def test_expiry_lookup_failure_does_not_fall_through_to_deletion(
    database: MagicMock, commerce_factory: MagicMock
) -> None:
    session = session_for(database)
    session.scalar.side_effect = RuntimeError("synthetic lookup failure")

    with pytest.raises(RuntimeError, match="synthetic lookup failure"):
        await ShopperAccounts(database).delete_data(TENANT, ACCOUNT, expired=True)

    assert_no_writes(session, commerce_factory)


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("has_cart", [False, True])
async def test_eligible_retirement_and_explicit_deletion_preserve_existing_effects(
    database: MagicMock, commerce_factory: MagicMock, expired: bool, has_cart: bool
) -> None:
    session = session_for(database)
    session.scalar.return_value = ACCOUNT if expired else None
    cart = MagicMock(status="open") if has_cart else None
    commerce = commerce_factory.return_value
    commerce.open_cart.return_value = cart

    await ShopperAccounts(database).delete_data(TENANT, ACCOUNT, expired=expired)

    database.transaction.assert_called_once_with(TENANT, write=True)
    if expired:
        session.scalar.assert_awaited_once()
        assert session.method_calls[0][0] == "scalar"
    else:
        session.scalar.assert_not_called()
    statements = [args.args[0].compile() for args in session.execute.call_args_list]
    first = statements[0]
    assert "version=(shopper_accounts.version +" in str(first)
    assert {TENANT, ACCOUNT, 1} <= set(first.params.values())
    for table in (
        "activity_checks",
        "shopper_activity",
        "activity_rules",
        "shopper_memories",
        "shopper_messages",
        "shopper_conversations",
    ):
        assert any(f"DELETE FROM {table}" in str(stmt) for stmt in statements)
    receipt_deletes = [
        stmt for stmt in statements if "DELETE FROM idempotency_records" in str(stmt)
    ]
    assert len(receipt_deletes) == 2
    assert f"activity:configure:{ACCOUNT}" in receipt_deletes[0].params.values()
    assert f"shopper:preferences:{ACCOUNT}" in receipt_deletes[1].params.values()
    assert "!=" in str(receipt_deletes[1])
    assert not any("guest:turn:" in str(stmt) for stmt in statements)
    assert not any("DELETE FROM commerce" in str(stmt) for stmt in statements)
    revocations = [stmt for stmt in statements if "UPDATE shopper_sessions" in str(stmt)]
    disablements = [stmt for stmt in statements if stmt.params.get("status") == "disabled"]
    assert len(revocations) == len(disablements) == int(expired)
    commerce.open_cart.assert_awaited_once_with(account_id=ACCOUNT)
    if cart is not None:
        commerce.invalidate_checkout.assert_awaited_once_with(cart=cart, now=NOW)
        assert cart.status == "abandoned"
    else:
        commerce.invalidate_checkout.assert_not_called()


async def test_second_stale_retirement_has_no_additional_side_effects(
    database: MagicMock, commerce_factory: MagicMock
) -> None:
    session = session_for(database)
    session.scalar.side_effect = [ACCOUNT, None]
    accounts = ShopperAccounts(database)

    await accounts.delete_data(TENANT, ACCOUNT, expired=True)
    writes = list(session.execute.call_args_list)
    assert writes
    await accounts.delete_data(TENANT, ACCOUNT, expired=True)

    assert database.transaction.call_args_list == [call(TENANT, write=True)] * 2
    assert session.scalar.await_count == 2
    assert session.execute.call_args_list == writes
    commerce_factory.assert_called_once_with(session, TENANT)
    commerce_factory.return_value.open_cart.assert_awaited_once_with(account_id=ACCOUNT)
