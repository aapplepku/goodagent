"""Authenticated preference management is separate from permission to recall."""

from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import UUID

import pytest
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.persistence.models.shopper import ShopperMemoryRecord
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.memory_tools import (
    SaveShoppingMemoryInput,
    ShopperMemoryTool,
    ShopperMemoryToolError,
)
from open_commerce.shopper_agent.models import ShopperMessage
from open_commerce.shopper_agent.service import DurableShopperAgentService

TENANT = UUID(int=101)
ACCOUNT = UUID(int=201)
MEMORY = UUID(int=301)
NOW = datetime(2026, 10, 18, tzinfo=UTC)


async def test_disabled_management_list_returns_retained_preference_without_writes() -> None:
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = False
    session.scalars.return_value = [
        ShopperMemoryRecord(
            id=MEMORY,
            tenant_id=TENANT,
            account_id=ACCOUNT,
            content="I prefer reusable cotton bags",
            source_message_id=None,
            created_at=NOW,
        )
    ]
    database = create_autospec(RuntimeDatabase, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    service = object.__new__(DurableShopperAgentService)
    service.database = database

    response = await service.list_memories(tenant_id=TENANT, account_id=ACCOUNT)

    assert [memory.id for memory in response.items] == [MEMORY]
    assert response.items[0].content == "I prefer reusable cotton bags"
    database.transaction.assert_called_once_with(TENANT)
    session.scalar.assert_not_awaited()
    session.add.assert_not_called()
    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


@pytest.mark.parametrize("enabled", [False, None])
async def test_default_recall_stays_closed_without_opt_in(enabled: bool | None) -> None:
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = enabled

    assert await ShopperRepository(session, TENANT).list_memories(account_id=ACCOUNT) == []

    session.scalars.assert_not_awaited()
    params = session.scalar.await_args.args[0].compile().params
    assert params == {"tenant_id_1": TENANT, "id_1": ACCOUNT}


@pytest.mark.parametrize("tenant,account", [(TENANT, ACCOUNT), (UUID(int=102), UUID(int=202))])
@pytest.mark.parametrize("management", [False, True])
async def test_both_lists_preserve_tenant_account_scope_limit_and_chronological_result(
    tenant: UUID, account: UUID, management: bool
) -> None:
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = True
    session.scalars.return_value = [
        ShopperMemoryRecord(
            id=UUID(int=number),
            tenant_id=tenant,
            account_id=account,
            content="Synthetic preference",
            source_message_id=None,
            created_at=NOW,
        )
        for number in (302, 301)
    ]
    repo = ShopperRepository(session, tenant)
    listing = repo.list_memories_for_management if management else repo.list_memories

    result = await listing(account_id=account, limit=2)

    assert [memory.id for memory in result] == [UUID(int=301), UUID(int=302)]
    query = session.scalars.await_args.args[0]
    assert query.compile().params == {"tenant_id_1": tenant, "account_id_1": account, "param_1": 2}
    assert "shopper_memories.created_at DESC, shopper_memories.id DESC" in str(query)
    if management:
        session.scalar.assert_not_awaited()
    else:
        assert session.scalar.await_args.args[0].compile().params == {
            "tenant_id_1": tenant,
            "id_1": account,
        }


async def test_off_on_cycle_retains_management_data_without_allowing_off_recall() -> None:
    session = create_autospec(AsyncSession, instance=True)
    row = ShopperMemoryRecord(
        id=MEMORY,
        tenant_id=TENANT,
        account_id=ACCOUNT,
        content="Synthetic preference",
        source_message_id=None,
        created_at=NOW,
    )
    session.scalars.return_value = [row]
    repo = ShopperRepository(session, TENANT)
    for enabled in (True, False, True):
        session.scalar.return_value = enabled
        managed = await repo.list_memories_for_management(account_id=ACCOUNT)
        recalled = await repo.list_memories(account_id=ACCOUNT)
        assert [memory.id for memory in managed] == [MEMORY]
        assert recalled == (managed if enabled else [])
    session.add.assert_not_called()
    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


async def test_disabled_memory_tool_still_rejects_save_before_receipts_or_writes() -> None:
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = False
    database = create_autospec(RuntimeDatabase, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    message = ShopperMessage(
        id=UUID(int=401),
        conversation_id=UUID(int=501),
        role="user",
        content="I prefer reusable cotton bags",
        created_at=NOW,
    )
    tool = ShopperMemoryTool(
        database, tenant_id=TENANT, account_id=ACCOUNT, current_message=message, history=[]
    )

    with pytest.raises(ShopperMemoryToolError, match="MEMORY_OPTED_OUT"):
        await tool.save(
            SaveShoppingMemoryInput(source_message_id=message.id, preference=message.content)
        )

    database.transaction.assert_called_once_with(TENANT, write=True)
    session.scalar.assert_awaited_once()
    params = session.scalar.await_args.args[0].compile().params
    assert params["tenant_id_1"] == TENANT and params["id_1"] == ACCOUNT
    session.add.assert_not_called()
    session.execute.assert_not_awaited()
    session.flush.assert_not_awaited()


async def test_selective_deletion_remains_available_without_enabling_memory() -> None:
    session = create_autospec(AsyncSession, instance=True)
    row = ShopperMemoryRecord(
        id=MEMORY,
        tenant_id=TENANT,
        account_id=ACCOUNT,
        content="Synthetic preference",
        source_message_id=None,
        created_at=NOW,
    )
    rows = [row]

    async def scalar(query: Select[tuple[object, ...]]) -> object:
        params = query.compile().params
        assert params["tenant_id_1"] == TENANT
        if "account_id_1" in params:
            assert params["account_id_1"] == ACCOUNT and params["id_1"] == MEMORY
            return row
        assert params["id_1"] == ACCOUNT
        return False

    async def execute(statement: object) -> None:
        rows.clear()

    session.scalar.side_effect = scalar
    session.scalars.side_effect = lambda query: list(rows)
    session.execute.side_effect = execute
    repo = ShopperRepository(session, TENANT)
    assert [
        memory.id for memory in await repo.list_memories_for_management(account_id=ACCOUNT)
    ] == [MEMORY]
    assert await repo.list_memories(account_id=ACCOUNT) == []

    await repo.delete_memory(account_id=ACCOUNT, memory_id=MEMORY)

    assert await repo.list_memories_for_management(account_id=ACCOUNT) == []
    assert await repo.list_memories(account_id=ACCOUNT) == []
    deletion = session.execute.await_args.args[0]
    assert deletion.is_delete
    assert deletion.compile().params == {
        "tenant_id_1": TENANT,
        "account_id_1": ACCOUNT,
        "id_1": MEMORY,
    }
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
