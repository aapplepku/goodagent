"""Commit memory before model continuation; isolate accounts and preserve replay semantics."""

import json
import os
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.persistence.models.shopper import ShopperAccountRecord, ShopperMemoryRecord
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.memory_tools import (
    SaveShoppingMemoryInput,
    ShopperMemoryTool,
    ShopperMemoryToolError,
)
from open_commerce.shopper_agent.models import (
    ShopperChatRequest,
    ShopperMessage,
    ShopperRegisterRequest,
)
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.activity_models import ActivityQuery

pytestmark = pytest.mark.integration


class SavingProvider:
    provider_name = "test-model"
    model_id = "scripted-memory"

    def __init__(self, *, fail_after_save: bool = False) -> None:
        self.fail_after_save = fail_after_save
        self.instructions = ""
        self.calls = 0
        self.check_saved: Callable[[], Awaitable[None]] | None = None

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
        self.calls += 1
        assert "save_shopping_memory" in [tool.name for tool in tools]
        current = json.loads(messages[-1].content)
        owner = self

        class Session:
            async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                if not tool_results:
                    return ManagerModelTurn(
                        tool_calls=[
                            ManagerToolCall(
                                call_id="save",
                                name="save_shopping_memory",
                                arguments={
                                    "source_message_id": current["source_message_id"],
                                    "preference": current["content"],
                                },
                            )
                        ]
                    )
                assert tool_results[0].output["ok"] is True
                if owner.check_saved:
                    await owner.check_saved()
                if owner.fail_after_save:
                    raise ManagerModelUnavailableError("synthetic failure after commit")
                return ManagerModelTurn(
                    tool_calls=[
                        ManagerToolCall(
                            call_id="finish",
                            name="complete_shopping_turn",
                            arguments={
                                "kind": "memory",
                                "message": "Saved your organic preference for future chats.",
                                "product_ids": None,
                            },
                        )
                    ]
                )

        return Session()


class RecordingProvider:
    def __init__(self, provider: OpenAIManagerProvider) -> None:
        self.provider = provider
        self.provider_name = provider.provider_name
        self.model_id = provider.model_id
        self.calls: list[dict[str, object]] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        session = self.provider.begin(
            instructions=instructions,
            messages=messages,
            tools=tools,
            max_output_tokens=max_output_tokens,
            require_tool=require_tool,
        )
        calls = self.calls

        class Session:
            async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                calls.extend(result.model_dump(mode="json") for result in tool_results)
                turn = await session.next(tool_results)
                calls.extend(call.model_dump(mode="json") for call in turn.tool_calls)
                return turn

        return Session()


async def test_recording_provider_preserves_required_tool_choice() -> None:
    import httpx
    from pydantic import SecretStr

    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Synthetic response"}],
                    }
                ],
            },
        )

    provider = RecordingProvider(
        OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="offline",
            transport=httpx.MockTransport(respond),
        )
    )
    await provider.begin(
        instructions="Fixture", messages=[], tools=[], max_output_tokens=400, require_tool=True
    ).next([])
    assert requests[0]["tool_choice"] == "required"


async def test_unavailable_model_retains_message_without_unselected_fallback_cards(
    integration_settings: Settings,
) -> None:
    import httpx
    from pydantic import SecretStr

    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        provider = OpenAIManagerProvider(
            api_key=SecretStr("synthetic"),
            model_id="test",
            transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"error": {}})),
        )
        service = DurableShopperAgentService(
            database, search_service=SearchService(), model_provider=provider
        )
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="outage-test", display_name="Test", password="synthetic-outage-password"
            ),
        )
        request = ShopperChatRequest(content="Compare glasses under 30 dollars")
        result = await service.chat(
            tenant_id=tenant, account_id=auth.account.id, request=request, idempotency_key="outage"
        )
        assert result.user_message.content == request.content
        assert not result.assistant_message.products
        assert "model is unavailable" in result.assistant_message.content
        assert "Basic mode:" not in result.assistant_message.content
        assert "Browsing and your cart are still available" in result.assistant_message.content
        assert not result.memories_saved
        assert (
            await service.chat(
                tenant_id=tenant,
                account_id=auth.account.id,
                request=request,
                idempotency_key="outage",
            )
            == result
        )
    finally:
        await database.close()


@pytest.mark.parametrize("fail_after_save", [False, True])
async def test_model_save_is_durable_before_reply_and_replay_does_not_resave(
    integration_settings: Settings,
    fail_after_save: bool,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, other_tenant = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant)
        await database.initialize_tenant(other_tenant)
        provider = SavingProvider(fail_after_save=fail_after_save)
        service = DurableShopperAgentService(
            database,
            search_service=SearchService(),
            model_provider=provider,
        )
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="memory-test",
                display_name="Test",
                password="synthetic-memory-password",
            ),
        )
        account = auth.account.id

        async def check_saved() -> None:
            # A separate transaction can observe the save before the model generates its reply.
            memories = await service.list_memories(tenant_id=tenant, account_id=account)
            assert [item.content for item in memories.items] == ["i am into organic stuffs"]

        provider.check_saved = check_saved
        request = ShopperChatRequest(content="i am into organic stuffs")
        first = await service.chat(
            tenant_id=tenant, account_id=account, request=request, idempotency_key="organic"
        )
        assert len(first.memories_saved) == 1
        assert first.memory_created == first.memories_saved[0]
        assert first.assistant_message.steps[-1].stage == "remember"
        assert "Basic mode:" not in first.assistant_message.content
        replay = await service.chat(
            tenant_id=tenant, account_id=account, request=request, idempotency_key="organic"
        )
        assert replay == first and provider.calls == 1
        restored = DurableShopperAgentService(
            database,
            search_service=SearchService(),
            model_provider=provider,
        )
        second = await restored.chat(
            tenant_id=tenant,
            account_id=account,
            request=request,
            idempotency_key="new-conversation",
        )
        assert second.memory_created == first.memory_created
        assert first.conversation.id != second.conversation.id
        assert "i am into organic stuffs" in provider.instructions
        assert not (
            await restored.list_memories(
                tenant_id=other_tenant,
                account_id=account,
            )
        ).items
        assert not (await restored.list_memories(tenant_id=tenant, account_id=uuid4())).items
        tool = ShopperMemoryTool(
            database,
            tenant_id=tenant,
            account_id=account,
            current_message=first.user_message,
            history=[],
        )
        args = SaveShoppingMemoryInput(
            source_message_id=first.user_message.id, preference=request.content
        )
        assert await tool.save(args) == first.memory_created
        hostile = ShopperMemoryTool(
            database,
            tenant_id=tenant,
            account_id=uuid4(),
            current_message=first.user_message,
            history=[],
        )
        with pytest.raises(ShopperMemoryToolError, match="INVALID_MEMORY_SOURCE"):
            await hostile.save(args)
        await service.delete_memory(
            tenant_id=tenant,
            account_id=account,
            memory_id=first.memories_saved[0].id,
            idempotency_key="delete",
        )
        with pytest.raises(ShopperMemoryToolError, match="MEMORY_PREVIOUSLY_REMOVED"):
            await tool.save(args)
        assert not (await service.list_memories(tenant_id=tenant, account_id=account)).items
    finally:
        await database.close()


@pytest.mark.parametrize("change", ["delete", "disable"])
@pytest.mark.parametrize("during_run", [False, True])
async def test_chat_receipt_does_not_restore_removed_or_disabled_memory(
    integration_settings: Settings, change: str, during_run: bool
) -> None:
    from open_commerce.stores.shoppers import ShopperAccounts

    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        provider = SavingProvider()
        service = DurableShopperAgentService(
            database, search_service=SearchService(), model_provider=provider
        )
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="memory-race", display_name="Test", password="synthetic-race-password"
            ),
        )
        account = auth.account.id

        async def change_memory() -> None:
            if change == "disable":
                await ShopperAccounts(database).preferences(tenant, account, False)
            else:
                saved = await service.list_memories(tenant_id=tenant, account_id=account)
                assert len(saved.items) == 1
                await service.delete_memory(
                    tenant_id=tenant,
                    account_id=account,
                    memory_id=saved.items[0].id,
                    idempotency_key="remove",
                )

        provider.check_saved = change_memory if during_run else None
        request = ShopperChatRequest(content="i am into organic stuffs")
        response = await service.chat(
            tenant_id=tenant, account_id=account, request=request, idempotency_key="one-turn"
        )
        if not during_run:
            assert len(response.memories_saved) == 1
            await change_memory()
        else:
            assert not response.memories_saved
            assert response.memory_created is None
            assert all(step.stage != "remember" for step in response.assistant_message.steps)
        for _ in range(2):
            replay = await service.chat(
                tenant_id=tenant, account_id=account, request=request, idempotency_key="one-turn"
            )
            assert replay.assistant_message.id == response.assistant_message.id
            assert not replay.memories_saved
            assert replay.memory_created is None
            assert all(step.stage != "remember" for step in replay.assistant_message.steps)
            assert "memory changed" in replay.assistant_message.content
        assert provider.calls == 1
        managed = (await service.list_memories(tenant_id=tenant, account_id=account)).items
        assert len(managed) == (1 if change == "disable" else 0)
        async with database.transaction(tenant) as session:
            assert not await ShopperRepository(session, tenant).list_memories(account_id=account)
            remaining = await session.scalar(
                select(func.count())
                .select_from(ShopperMemoryRecord)
                .where(
                    ShopperMemoryRecord.tenant_id == tenant,
                    ShopperMemoryRecord.account_id == account,
                )
            )
        assert remaining == (1 if change == "disable" else 0)
    finally:
        await database.close()


@pytest.mark.parametrize("elapsed_seconds", [0, 1])
async def test_guest_expiry_between_admission_and_save_blocks_persistence(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch, elapsed_seconds: int
) -> None:
    import open_commerce.shopper_agent.memory_tools as memory_module

    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableShopperAgentService(database, search_service=SearchService())
        auth, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="expiry-race", display_name="Test", password="synthetic-expiry-password"
            ),
        )
        account = auth.account.id
        now = utc_now()
        expiry = now + timedelta(minutes=1)
        message = ShopperMessage(
            id=uuid4(),
            conversation_id=uuid4(),
            role="user",
            content="i am into organic stuffs",
            created_at=now,
        )
        async with database.transaction(tenant, write=True) as session:
            row = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant, ShopperAccountRecord.id == account
                )
            )
            assert row is not None
            row.is_guest = True
            row.expires_at = expiry
            repo = ShopperRepository(session, tenant)
            await repo.create_conversation(
                conversation_id=message.conversation_id, account_id=account, title="Test", now=now
            )
            await repo.add_message(account_id=account, message=message)
        monkeypatch.setattr(
            memory_module, "utc_now", lambda: expiry + timedelta(seconds=elapsed_seconds)
        )
        tool = ShopperMemoryTool(
            database, tenant_id=tenant, account_id=account, current_message=message, history=[]
        )
        with pytest.raises(ShopperMemoryToolError, match="INVALID_MEMORY_SOURCE"):
            await tool.save(
                SaveShoppingMemoryInput(source_message_id=message.id, preference=message.content)
            )
        assert not tool.saved
        async with database.transaction(tenant) as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ShopperMemoryRecord)
                    .where(
                        ShopperMemoryRecord.tenant_id == tenant,
                        ShopperMemoryRecord.account_id == account,
                    )
                )
                == 0
            )
    finally:
        await database.close()


@pytest.mark.skipif(
    os.getenv("OPEN_COMMERCE_RUN_LIVE_SHOPPER_MEMORY") != "1",
    reason="opt-in hosted model check; sends synthetic preferences only",
)
async def test_live_model_selects_memory_for_natural_preferences_not_temporary_requests(
    integration_settings: Settings,
) -> None:
    settings = Settings(_env_file=(".env", ".opencommerce/local-runtime.env"))
    assert settings.openai_api_key is not None
    provider = RecordingProvider(
        OpenAIManagerProvider(
            api_key=settings.openai_api_key,
            model_id=settings.manager_model_id,
            timeout_seconds=90,
            max_input_bytes=settings.manager_model_max_input_bytes,
        )
    )
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableShopperAgentService(
            database, search_service=SearchService(), model_provider=provider
        )
        for index, (content, expected) in enumerate(
            [
                ("i am into organic stuffs", True),
                ("Premium is my usual choice when shopping", True),
                ("Find organic coffee for tonight", False),
                ("My friend likes organic food; suggest a gift for them", False),
                ("I like organic products but do not save this", False),
            ]
        ):
            auth, _ = await service.register(
                tenant_id=tenant,
                request=ShopperRegisterRequest(
                    username=f"live-memory-{index}",
                    display_name="Synthetic test",
                    password="synthetic-live-test-password",
                ),
            )
            result = await service.chat(
                tenant_id=tenant,
                account_id=auth.account.id,
                request=ShopperChatRequest(content=content),
                idempotency_key=f"live-{index}",
            )
            assert bool(result.memories_saved) is expected, result.assistant_message.content
            persisted = await service.list_memories(tenant_id=tenant, account_id=auth.account.id)
            assert persisted.items == result.memories_saved
        monitor = await service.chat(
            tenant_id=tenant,
            account_id=auth.account.id,
            request=ShopperChatRequest(
                content=(
                    "Inspect my activity, then create a personal monitor named Empty searches: "
                    "search empty-result rate at or above 25 percent, last 60 minutes, minimum "
                    "5 samples, check every 5 minutes. Enable it. No external notifications."
                )
            ),
            idempotency_key="live-monitor",
        )
        personal = await ActivityService(database).overview(
            tenant_id=tenant, account_id=auth.account.id, query=ActivityQuery()
        )
        assert len(personal.rules) == 1, (monitor.assistant_message.content, provider.calls)
        assert personal.rules[0].definition.metric == "empty_result_rate"
        assert personal.rules[0].definition.threshold == 25
        assert personal.rules[0].definition.interval_minutes == 5
        assert not (
            await ActivityService(database).overview(
                tenant_id=tenant, account_id=None, query=ActivityQuery()
            )
        ).rules
    finally:
        await database.close()
