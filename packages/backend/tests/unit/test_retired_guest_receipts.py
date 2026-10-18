"""Offline SQL contracts for retiring guest response copies without erasing history."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, call, create_autospec
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ClauseElement

from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores import shoppers
from open_commerce.stores.shoppers import ShopperAccounts

TENANT, GUEST, TARGET = UUID(int=14301), UUID(int=14302), UUID(int=14303)
PREFIXES = (
    "shopper:chat:",
    "shopper:chat:start:",
    "shopper:memory:save:",
    "shopper:memory:delete:",
)


@pytest.fixture
def database() -> MagicMock:
    db = create_autospec(RuntimeDatabase, instance=True)
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = None
    session.scalars.return_value = []
    db.transaction.return_value.__aenter__.return_value = session
    return cast(MagicMock, db)


def session_for(database: MagicMock) -> MagicMock:
    return cast(MagicMock, database.transaction.return_value.__aenter__.return_value)


def sql(statement: ClauseElement) -> str:
    return str(
        statement.compile(
            dialect=cast(type[Dialect], postgresql.dialect)(),
            compile_kwargs={"literal_binds": True},
        )
    )


def assert_exact_erasure(statement: ClauseElement) -> None:
    rendered = sql(statement)
    assert "DELETE FROM idempotency_records" in rendered
    assert f"idempotency_records.tenant_id = '{TENANT}'" in rendered
    assert "idempotency_records.scope IN (" in rendered
    assert "LIKE" not in rendered
    compiled = statement.compile()
    assert set(compiled.params) == {"tenant_id_1", "scope_1"}
    assert set(compiled.params["scope_1"]) == {prefix + str(GUEST) for prefix in PREFIXES}
    assert str(TARGET) not in rendered


@pytest.mark.parametrize("choice", ["keep_guest", "keep_account"])
async def test_merge_erases_guest_content_receipts_in_transfer_transaction(
    database: MagicMock, monkeypatch: pytest.MonkeyPatch, choice: str
) -> None:
    commerce = MagicMock(open_cart=AsyncMock(return_value=None))
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *args: commerce)
    guest = ShopperAccountRecord(id=GUEST, is_guest=True, status="active", version=3)
    target = ShopperAccountRecord(id=TARGET, is_guest=False, status="active", version=7)
    session = session_for(database)
    async with database.transaction(TENANT, write=True):
        await ShopperAccounts(database).merge_records(session, TENANT, guest, target, choice)

    statements = [entry.args[0] for entry in session.execute.call_args_list]
    receipt_deletes = [
        stmt for stmt in statements if "DELETE FROM idempotency_records" in sql(stmt)
    ]
    content_deletes = [stmt for stmt in receipt_deletes if "shopper:chat:" in sql(stmt)]
    assert len(content_deletes) == 1, "Retired guest still owns content-bearing response copies"
    assert_exact_erasure(content_deletes[0])
    assert len(receipt_deletes) == 2
    for table in ("shopper_conversations", "shopper_messages", "shopper_memories"):
        transfers = [sql(stmt) for stmt in statements if sql(stmt).startswith(f"UPDATE {table} ")]
        assert len(transfers) == 1
        assert f"account_id='{TARGET}'" in transfers[0]
        assert f"{table}.tenant_id = '{TENANT}'" in transfers[0]
        assert f"{table}.account_id = '{GUEST}'" in transfers[0]
        assert not any(sql(stmt).startswith(f"DELETE FROM {table} ") for stmt in statements)
    assert guest.status == "disabled" and guest.version == 4
    assert target.status == "active" and target.version == 7
    database.transaction.assert_called_once_with(TENANT, write=True)


async def test_cleanup_selects_outstanding_retired_guests_with_correlated_tenant_scope(
    database: MagicMock,
) -> None:
    session = session_for(database)
    session.scalars.side_effect = [[], [GUEST]]
    session.scalar.return_value = GUEST
    await ShopperAccounts(database).cleanup(TENANT)

    selects = [entry.args[0] for entry in session.scalars.call_args_list]
    retired = [stmt for stmt in selects if "'disabled'" in sql(stmt)]
    assert len(retired) == 1, "Cleanup must revisit retired guests with orphaned receipts"
    rendered = sql(retired[0])
    assert "shopper_accounts.is_guest IS true" in rendered
    assert f"shopper_accounts.tenant_id = '{TENANT}'" in rendered
    assert f"idempotency_records.tenant_id = '{TENANT}'" in rendered
    assert "EXISTS (SELECT" in rendered
    assert "FROM idempotency_records \nWHERE" in rendered
    assert "CAST(shopper_accounts.id AS VARCHAR)" in rendered
    for prefix in PREFIXES:
        assert f"'{prefix}' || CAST(shopper_accounts.id AS VARCHAR)" in rendered
    assert "LIKE" not in rendered
    assert "LIMIT 100" in rendered
    assert "ORDER BY shopper_accounts.id" in rendered
    assert "shopper:preferences:" not in rendered
    assert database.transaction.call_args_list[-1] == call(TENANT, write=True)
    session.scalar.assert_awaited_once()
    assert_exact_erasure(session.execute.call_args.args[0])


@pytest.mark.parametrize("eligible", [False, True])
async def test_retired_cleanup_rechecks_identity_after_tenant_write_lock(
    database: MagicMock, eligible: bool
) -> None:
    session = session_for(database)
    entered = False

    async def enter() -> MagicMock:
        nonlocal entered
        entered = True
        return session

    async def check(statement: ClauseElement) -> UUID | None:
        assert entered
        rendered = sql(statement)
        for condition in (
            f"shopper_accounts.tenant_id = '{TENANT}'",
            f"shopper_accounts.id = '{GUEST}'",
            "shopper_accounts.is_guest IS true",
            "shopper_accounts.status = 'disabled'",
        ):
            assert condition in rendered
        return GUEST if eligible else None

    database.transaction.return_value.__aenter__.side_effect = enter
    session.scalar.side_effect = check
    await ShopperAccounts(database)._erase_retired_guest_receipts(TENANT, GUEST)
    database.transaction.assert_called_once_with(TENANT, write=True)
    session.scalar.assert_awaited_once()
    if eligible:
        session.execute.assert_awaited_once()
        assert_exact_erasure(session.execute.call_args.args[0])
    else:
        session.execute.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()


async def test_retired_lookup_failure_never_falls_through_to_erasure(database: MagicMock) -> None:
    session = session_for(database)
    session.scalar.side_effect = RuntimeError("synthetic lookup failure")
    with pytest.raises(RuntimeError, match="synthetic lookup failure"):
        await ShopperAccounts(database)._erase_retired_guest_receipts(TENANT, GUEST)
    session.execute.assert_not_called()


async def test_retired_delete_failure_propagates_to_transaction_rollback(
    database: MagicMock,
) -> None:
    session = session_for(database)
    session.scalar.return_value = GUEST
    session.execute.side_effect = RuntimeError("synthetic delete failure")
    with pytest.raises(RuntimeError, match="synthetic delete failure"):
        await ShopperAccounts(database)._erase_retired_guest_receipts(TENANT, GUEST)
    exit_call = database.transaction.return_value.__aexit__.call_args
    assert exit_call.args[0] is RuntimeError
