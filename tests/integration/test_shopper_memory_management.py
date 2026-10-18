"""Disabled recall does not hide management data or break an explicit deletion replay."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.errors import ShopperMemoryNotFoundError
from open_commerce.shopper_agent.models import ShopperChatRequest, ShopperRegisterRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.stores.shoppers import ShopperAccounts

pytestmark = pytest.mark.integration


class MemoryContextProvider:
    provider_name = "synthetic"
    model_id = "memory-context"

    def __init__(self) -> None:
        self.instructions = ""
        self.tools: list[str] = []
        self.calls = 0

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        self.instructions = instructions
        self.tools = [tool.name for tool in tools]
        owner = self

        class Session:
            async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                owner.calls += 1
                assert not tool_results
                return ManagerModelTurn(
                    tool_calls=[
                        ManagerToolCall(
                            call_id="finish",
                            name="complete_shopping_turn",
                            arguments={
                                "kind": "clarification",
                                "message": "What kind of mug are you looking for?",
                                "product_ids": None,
                            },
                        )
                    ]
                )

        return Session()


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
async def test_model_memory_context_matches_guest_and_registered_opt_out(
    integration_settings: Settings, guest: bool, enabled: bool
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableShopperAgentService(database, search_service=SearchService())
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="context-owner",
                display_name="Synthetic",
                password="synthetic-context-test",
            ),
        )
        account = auth.account.id
        if guest:
            async with database.transaction(tenant, write=True) as session:
                row = await session.scalar(
                    select(ShopperAccountRecord).where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.id == account,
                    )
                )
                assert row is not None
                row.is_guest = True
                row.expires_at = utc_now() + timedelta(hours=24)
        preference = "I prefer reusable cotton bags"
        seeded = await service.chat(
            tenant_id=tenant,
            account_id=account,
            request=ShopperChatRequest(content=preference),
            idempotency_key="context-preference",
        )
        assert len(seeded.memories_saved) == 1
        before = (await service.list_memories(tenant_id=tenant, account_id=account)).items
        await ShopperAccounts(database).preferences(tenant, account, enabled)
        provider = MemoryContextProvider()
        scripted = DurableShopperAgentService(
            database, search_service=SearchService(), model_provider=provider
        )
        answer = await scripted.chat(
            tenant_id=tenant,
            account_id=account,
            request=ShopperChatRequest(content="Help me pick a mug"),
            idempotency_key="context-question",
        )
        assert provider.calls == 1
        assert (preference in provider.instructions) is enabled
        assert ("save_shopping_memory" in provider.tools) is enabled
        assert ("Memory saving and recall are disabled." in provider.instructions) is not enabled
        assert ("Memory is temporary for this guest visit" in provider.instructions) is (
            guest and enabled
        )
        assert not answer.memories_saved and answer.memory_created is None
        assert (await service.list_memories(tenant_id=tenant, account_id=account)).items == before
    finally:
        await database.close()


@pytest.mark.parametrize("guest", [False, True])
async def test_disabled_memory_management_and_replay_are_account_scoped(
    integration_settings: Settings, guest: bool
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, other_tenant = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant)
        await database.initialize_tenant(other_tenant)
        service = DurableShopperAgentService(database, search_service=SearchService())
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="memory-owner", display_name="Synthetic", password="synthetic-memory-test"
            ),
        )
        other, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="memory-other", display_name="Other", password="synthetic-memory-test"
            ),
        )
        account = auth.account.id
        if guest:
            async with database.transaction(tenant) as session:
                row = await session.scalar(
                    select(ShopperAccountRecord).where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.id == account,
                    )
                )
                assert row is not None
                row.is_guest = True
                row.expires_at = utc_now() + timedelta(hours=24)
        for owner in (account, other.account.id):
            result = await service.chat(
                tenant_id=tenant,
                account_id=owner,
                request=ShopperChatRequest(content="I prefer reusable cotton bags"),
                idempotency_key="synthetic-preference",
            )
            assert len(result.memories_saved) == 1
        saved = (await service.list_memories(tenant_id=tenant, account_id=account)).items
        memory_id = saved[0].id
        accounts = ShopperAccounts(database)
        await accounts.preferences(tenant, account, False)
        assert (await service.list_memories(tenant_id=tenant, account_id=account)).items == saved
        assert not (await service.list_memories(tenant_id=other_tenant, account_id=account)).items
        async with database.transaction(tenant) as session:
            assert not await ShopperRepository(session, tenant).list_memories(account_id=account)
        blocked = await service.chat(
            tenant_id=tenant,
            account_id=account,
            request=ShopperChatRequest(content="I prefer blue mugs"),
            idempotency_key="disabled-preference",
        )
        assert not blocked.memories_saved
        assert (await service.list_memories(tenant_id=tenant, account_id=account)).items == saved
        await accounts.preferences(tenant, account, True)
        async with database.transaction(tenant) as session:
            assert (
                await ShopperRepository(session, tenant).list_memories(account_id=account) == saved
            )
        await accounts.preferences(tenant, account, False)
        for scoped_tenant, scoped_account in (
            (other_tenant, account),
            (tenant, other.account.id),
        ):
            with pytest.raises(ShopperMemoryNotFoundError):
                await service.delete_memory(
                    tenant_id=scoped_tenant,
                    account_id=scoped_account,
                    memory_id=memory_id,
                    idempotency_key="foreign-removal",
                )
        outcomes = [
            await service.delete_memory(
                tenant_id=tenant,
                account_id=account,
                memory_id=memory_id,
                idempotency_key="same-removal-key",
            )
            for _ in range(2)
        ]
        assert outcomes[0] == outcomes[1]
        assert outcomes[0].deleted
        assert not (await service.list_memories(tenant_id=tenant, account_id=account)).items
        assert (
            len((await service.list_memories(tenant_id=tenant, account_id=other.account.id)).items)
            == 1
        )
        async with database.transaction(tenant) as session:
            assert (
                await session.scalar(
                    select(ShopperAccountRecord.memory_enabled).where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.id == account,
                    )
                )
                is False
            )
    finally:
        await database.close()
