"""Real PostgreSQL coverage for durable manager conversations and memory."""

import asyncio
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.manager_agent.errors import (
    ManagerThreadBusyError,
    ManagerThreadInvalidError,
    ManagerThreadNotFoundError,
)
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.manager_agent.models import (
    ManagerDatasetProfileRequest,
    ManagerMessageRequest,
    ManagerReplyThreadCreateRequest,
    ManagerThreadCreateRequest,
    ManagerThreadUpdateRequest,
    ManagerWorkspaceResetRequest,
)
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration


class _BlockingModelSession:
    def __init__(self, provider: "_BlockingModelProvider") -> None:
        self.provider = provider

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        assert tool_results == []
        async with self.provider.entry_lock:
            self.provider.entered += 1
            if self.provider.entered == self.provider.expected_entries:
                self.provider.all_entered.set()
        await self.provider.release.wait()
        return ManagerModelTurn(content="I prepared this topic independently.")


class _BlockingModelProvider:
    provider_name = "test"
    model_id = "blocking-conversation-model"

    def __init__(self, *, expected_entries: int = 2) -> None:
        self.expected_entries = expected_entries
        self.entered = 0
        self.entry_lock = asyncio.Lock()
        self.all_entered = asyncio.Event()
        self.release = asyncio.Event()

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        assert instructions and messages and tools and max_output_tokens > 0
        return _BlockingModelSession(self)


async def test_manager_memory_layers_are_durable_idempotent_and_tenant_scoped(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(
        update={
            "manager_periodic_memory_turns": 2,
            "manager_model_provider": "deterministic",
            "search_embedding_backend": "minilm",
        }
    )
    database = RuntimeDatabase(settings)
    tenant_id, other_tenant = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        await database.initialize_tenant(other_tenant)
        service = DurableManagerAgentService(database)
        created = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(),
            idempotency_key="create-manager-thread",
        )
        replay = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(),
            idempotency_key="create-manager-thread",
        )
        assert replay == created
        profiled = await service.profile_dataset(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="catalog.csv",
                csv_text=(
                    "product_id,title,description,updated_at\n"
                    "p-1,Trail Boot,Waterproof hiking boot,2026-09-01T12:00:00Z\n"
                ),
            ),
            idempotency_key="profile-catalog",
        )
        profile_replay = await service.profile_dataset(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="catalog.csv",
                csv_text=(
                    "product_id,title,description,updated_at\n"
                    "p-1,Trail Boot,Waterproof hiking boot,2026-09-01T12:00:00Z\n"
                ),
            ),
            idempotency_key="profile-catalog",
        )
        assert profile_replay == profiled
        assert profiled.onboarding.catalog is not None
        assert profiled.onboarding.catalog.profile is not None
        assert profiled.onboarding.catalog.profile.row_count == 1

        second_thread = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Another conversation"),
            idempotency_key="create-second-manager-thread",
        )
        assert second_thread.onboarding == profiled.onboarding
        other_thread = await service.create_thread(
            tenant_id=other_tenant,
            request=ManagerThreadCreateRequest(),
            idempotency_key="create-other-manager-thread",
        )
        assert other_thread.onboarding.catalog is None
        first = await service.send_message(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerMessageRequest(
                content="enable semantic search and rank products by popularity"
            ),
            idempotency_key="first-turn",
        )
        first_replay = await service.send_message(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerMessageRequest(
                content="enable semantic search and rank products by popularity"
            ),
            idempotency_key="first-turn",
        )
        assert first_replay == first
        assert first.periodic_memory_created is not None
        assert first.periodic_memory_created.layer == "periodic"
        second = await service.send_message(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerMessageRequest(content="balanced"),
            idempotency_key="second-turn",
        )
        assert second.periodic_memory_created is None
        assert second.thread.working_memory.objective is not None
        assert second.thread.working_memory.objective.status == "ready_for_review"
        remembered = await service.send_message(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            request=ManagerMessageRequest(content="Remember that I prefer concise summaries"),
            idempotency_key="preference-turn",
        )
        long_term = [item for item in remembered.memories if item.layer == "long_term"]
        assert len(long_term) == 1

        restored = await service.get_thread(tenant_id=tenant_id, thread_id=created.thread.id)
        assert len(restored.messages) == 9
        assert [item.role for item in restored.messages] == [
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert {item.layer for item in restored.memories} == {"long_term", "periodic"}
        other_threads = await service.list_threads(tenant_id=other_tenant)
        assert [item.id for item in other_threads.items] == [other_thread.thread.id]
        with pytest.raises(ManagerThreadNotFoundError):
            await service.get_thread(tenant_id=other_tenant, thread_id=created.thread.id)

        cleared = await service.clear_channel_history(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            idempotency_key="clear-manager-history",
        )
        clear_replay = await service.clear_channel_history(
            tenant_id=tenant_id,
            thread_id=created.thread.id,
            idempotency_key="clear-manager-history",
        )
        assert clear_replay == cleared
        assert cleared.deleted_message_count == 9
        assert cleared.deleted_reply_thread_count == 0
        assert len(cleared.detail.messages) == 1
        assert cleared.detail.thread.user_turn_count == 0
        assert cleared.detail.thread.working_memory.current_topic is None
        assert [item.layer for item in cleared.detail.memories] == ["long_term"]
        with pytest.raises(ManagerThreadNotFoundError):
            await service.clear_channel_history(
                tenant_id=other_tenant,
                thread_id=created.thread.id,
                idempotency_key="cross-tenant-clear",
            )

        deleted = await service.delete_memory(
            tenant_id=tenant_id,
            memory_id=long_term[0].id,
            idempotency_key="forget-preference",
        )
        assert deleted.deleted is True
        assert (await service.list_memories(tenant_id=tenant_id, layer="long_term")).items == []
    finally:
        await database.close()


async def test_manager_workspace_reset_is_idempotent_and_retains_catalog(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableManagerAgentService(database)
        await service.bootstrap_workspace(
            tenant_id=tenant_id, idempotency_key="reset-test-bootstrap"
        )
        custom = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Reset test"),
            idempotency_key="reset-test-channel",
        )
        profiled = await service.profile_dataset(
            tenant_id=tenant_id,
            thread_id=custom.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="retained.csv",
                csv_text="product_id,title,image_url\np-1,Retained product,https://example.test/p.jpg\n",
            ),
            idempotency_key="reset-test-catalog",
        )
        await service.send_message(
            tenant_id=tenant_id,
            thread_id=custom.thread.id,
            request=ManagerMessageRequest(content="Remember that I prefer concise updates"),
            idempotency_key="reset-test-memory",
        )

        request = ManagerWorkspaceResetRequest(confirmation="RESET")
        reset = await service.reset_workspace(
            tenant_id=tenant_id,
            request=request,
            idempotency_key="reset-test-workspace",
        )
        replay = await service.reset_workspace(
            tenant_id=tenant_id,
            request=request,
            idempotency_key="reset-test-workspace",
        )

        assert replay == reset
        assert reset.deleted_channel_count == 2
        assert reset.deleted_message_count >= 5
        assert reset.deleted_memory_count == 1
        assert [item.channel_kind for item in reset.workspace.channels] == ["onboarding"]
        assert reset.workspace.onboarding.workspace_status == "in_progress"
        assert reset.workspace.catalog_index.catalog_id == profiled.catalog_index.catalog_id
        assert (await service.list_memories(tenant_id=tenant_id)).items == []
        with pytest.raises(ManagerThreadNotFoundError):
            await service.get_thread(tenant_id=tenant_id, thread_id=custom.thread.id)
    finally:
        await database.close()


async def test_manager_threads_run_in_parallel_and_reject_stale_same_thread_commit(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(
        update={"manager_model_provider": "deterministic", "search_embedding_backend": "minilm"}
    )
    database = RuntimeDatabase(settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        parallel_provider = _BlockingModelProvider()
        service = DurableManagerAgentService(database, model_provider=parallel_provider)
        search_thread = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Search quality"),
            idempotency_key="create-search-thread",
        )
        recommendation_thread = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Recommendations"),
            idempotency_key="create-recommendation-thread",
        )

        search_turn = asyncio.create_task(
            service.send_message(
                tenant_id=tenant_id,
                thread_id=search_thread.thread.id,
                request=ManagerMessageRequest(content="Improve semantic search"),
                idempotency_key="parallel-search-turn",
            )
        )
        recommendation_turn = asyncio.create_task(
            service.send_message(
                tenant_id=tenant_id,
                thread_id=recommendation_thread.thread.id,
                request=ManagerMessageRequest(content="Improve recommendations"),
                idempotency_key="parallel-recommendation-turn",
            )
        )
        await asyncio.wait_for(parallel_provider.all_entered.wait(), timeout=2)
        parallel_provider.release.set()
        replies = await asyncio.gather(search_turn, recommendation_turn)
        assert {reply.thread.id for reply in replies} == {
            search_thread.thread.id,
            recommendation_thread.thread.id,
        }

        conflict_provider = _BlockingModelProvider(expected_entries=1)
        conflict_service = DurableManagerAgentService(database, model_provider=conflict_provider)
        first = asyncio.create_task(
            conflict_service.send_message(
                tenant_id=tenant_id,
                thread_id=search_thread.thread.id,
                request=ManagerMessageRequest(content="Use a balanced popularity signal"),
                idempotency_key="same-thread-first",
            )
        )
        second = asyncio.create_task(
            conflict_service.send_message(
                tenant_id=tenant_id,
                thread_id=search_thread.thread.id,
                request=ManagerMessageRequest(content="Use a strong popularity signal"),
                idempotency_key="same-thread-second",
            )
        )
        await asyncio.wait_for(conflict_provider.all_entered.wait(), timeout=2)
        conflict_provider.release.set()
        outcomes = await asyncio.gather(first, second, return_exceptions=True)

        assert len([item for item in outcomes if isinstance(item, ManagerThreadBusyError)]) == 1
        restored = await service.get_thread(tenant_id=tenant_id, thread_id=search_thread.thread.id)
        assert restored.thread.user_turn_count == 2
        assert len(restored.messages) == 5
    finally:
        await database.close()


async def test_workspace_onboarding_channels_and_reply_threads_are_durable_and_scoped(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(
        update={"manager_model_provider": "deterministic", "search_embedding_backend": "hash"}
    )
    database = RuntimeDatabase(settings)
    tenant_id, other_tenant = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        await database.initialize_tenant(other_tenant)
        service = DurableManagerAgentService(database)

        first = await service.bootstrap_workspace(
            tenant_id=tenant_id, idempotency_key="bootstrap-workspace"
        )
        replay = await service.bootstrap_workspace(
            tenant_id=tenant_id, idempotency_key="bootstrap-workspace"
        )
        assert replay == first
        assert [item.channel_kind for item in first.channels] == ["onboarding"]
        onboarding_channel = first.channels[0]

        answers = [
            "Northstar Goods",
            "Outdoor goods for weekend explorers",
            "Improve product discovery",
            "status,search,analysis",
            "defer",
            "skip",
            "draft_only",
            "confirm",
        ]
        last_reply = None
        for index, answer in enumerate(answers):
            last_reply = await service.send_message(
                tenant_id=tenant_id,
                thread_id=onboarding_channel.id,
                request=ManagerMessageRequest(content=answer),
                idempotency_key=f"onboarding-{index}",
            )

        assert last_reply is not None
        assert last_reply.workspace_changed is True
        assert last_reply.onboarding.workspace_status == "completed"
        assert last_reply.onboarding.limited_mode is True
        assert last_reply.onboarding.catalog is None
        workspace = await service.get_workspace(tenant_id=tenant_id)
        assert [item.channel_kind for item in workspace.channels] == [
            "onboarding",
            "status",
            "search",
            "custom",
        ]
        assert [item.slug for item in workspace.channels] == [
            "onboarding",
            "status",
            "search",
            "analysis",
        ]
        refreshed_bootstrap = await service.bootstrap_workspace(
            tenant_id=tenant_id, idempotency_key="bootstrap-workspace"
        )
        assert refreshed_bootstrap.onboarding.workspace_status == "completed"
        assert refreshed_bootstrap.channels == workspace.channels

        seasonal = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(
                title="Seasonal Launch", description="Plan spring discovery"
            ),
            idempotency_key="create-seasonal-one",
        )
        collision = await service.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Seasonal Launch"),
            idempotency_key="create-seasonal-two",
        )
        assert seasonal.thread.slug == "seasonal-launch"
        assert collision.thread.slug == "seasonal-launch-2"
        renamed = await service.update_thread(
            tenant_id=tenant_id,
            thread_id=seasonal.thread.id,
            request=ManagerThreadUpdateRequest(
                title="Spring Launch", description="Updated purpose", status="archived"
            ),
            idempotency_key="archive-seasonal",
        )
        assert (renamed.thread.slug, renamed.thread.status) == ("spring-launch", "archived")
        restored = await service.update_thread(
            tenant_id=tenant_id,
            thread_id=seasonal.thread.id,
            request=ManagerThreadUpdateRequest(status="active"),
            idempotency_key="restore-seasonal",
        )
        assert restored.thread.status == "active"

        search_channel = next(item for item in workspace.channels if item.channel_kind == "search")
        analysis_channel = next(item for item in workspace.channels if item.slug == "analysis")
        search_detail = await service.get_thread(tenant_id=tenant_id, thread_id=search_channel.id)
        analysis_detail = await service.get_thread(
            tenant_id=tenant_id, thread_id=analysis_channel.id
        )
        root = search_detail.messages[0]
        reply = await service.create_reply_thread(
            tenant_id=tenant_id,
            channel_id=search_channel.id,
            request=ManagerReplyThreadCreateRequest(root_message_id=root.id),
            idempotency_key="create-search-reply",
        )
        reply_replay = await service.create_reply_thread(
            tenant_id=tenant_id,
            channel_id=search_channel.id,
            request=ManagerReplyThreadCreateRequest(root_message_id=root.id),
            idempotency_key="create-search-reply-again",
        )
        assert reply_replay.thread.id == reply.thread.id
        assert reply.root_message == root
        assert reply.thread.parent_thread_id == search_channel.id

        reply_turn = await service.send_message(
            tenant_id=tenant_id,
            thread_id=reply.thread.id,
            request=ManagerMessageRequest(content="Use a balanced popularity signal"),
            idempotency_key="reply-turn",
        )
        assert reply_turn.thread.user_turn_count == 1
        untouched_channel = await service.get_thread(
            tenant_id=tenant_id, thread_id=search_channel.id
        )
        assert untouched_channel.thread.user_turn_count == 0
        restored_reply = await service.get_reply_thread(
            tenant_id=tenant_id,
            channel_id=search_channel.id,
            root_message_id=root.id,
        )
        assert [item.role for item in restored_reply.messages] == ["user", "assistant"]
        counted_root = (
            await service.get_thread(tenant_id=tenant_id, thread_id=search_channel.id)
        ).messages[0]
        assert counted_root.reply_count == 1

        with pytest.raises(ManagerThreadInvalidError):
            await service.create_reply_thread(
                tenant_id=tenant_id,
                channel_id=reply.thread.id,
                request=ManagerReplyThreadCreateRequest(root_message_id=root.id),
                idempotency_key="nested-reply",
            )
        with pytest.raises(ManagerThreadNotFoundError):
            await service.create_reply_thread(
                tenant_id=tenant_id,
                channel_id=search_channel.id,
                request=ManagerReplyThreadCreateRequest(
                    root_message_id=analysis_detail.messages[0].id
                ),
                idempotency_key="wrong-channel-root",
            )
        with pytest.raises(ManagerThreadNotFoundError):
            await service.get_reply_thread(
                tenant_id=other_tenant,
                channel_id=search_channel.id,
                root_message_id=root.id,
            )
        cleared = await service.clear_channel_history(
            tenant_id=tenant_id,
            thread_id=search_channel.id,
            idempotency_key="clear-search-history",
        )
        assert cleared.deleted_message_count == 3
        assert cleared.deleted_reply_thread_count == 1
        assert len(cleared.detail.messages) == 1
        with pytest.raises(ManagerThreadNotFoundError):
            await service.get_reply_thread(
                tenant_id=tenant_id,
                channel_id=search_channel.id,
                root_message_id=root.id,
            )
    finally:
        await database.close()
