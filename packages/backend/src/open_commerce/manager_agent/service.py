"""Durable Slack-style manager workspace with bounded agent memory."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from open_commerce.catalog.csv_import import normalize_catalog_csv
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.catalog.persistence import catalog_index_status, stage_catalog_upload
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.agent import ManagerReActAgent
from open_commerce.manager_agent.data_onboarding import (
    attach_profile,
    onboarding_question,
    profile_csv,
)
from open_commerce.manager_agent.errors import (
    ManagerModelUnavailableError,
    ManagerThreadBusyError,
    ManagerThreadInvalidError,
    ManagerThreadNotFoundError,
)
from open_commerce.manager_agent.model_agent import ModelBackedManagerAgent
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.manager_agent.models import (
    AgentStep,
    ManagerAgentCapabilities,
    ManagerAgentOutcome,
    ManagerAgentReply,
    ManagerChannelClearResponse,
    ManagerChannelKind,
    ManagerDataOnboarding,
    ManagerDatasetProfileReply,
    ManagerDatasetProfileRequest,
    ManagerMemory,
    ManagerMemoryDeleteResponse,
    ManagerMemoryListResponse,
    ManagerMessage,
    ManagerMessageRequest,
    ManagerReplyThreadCreateRequest,
    ManagerRuntimeStatus,
    ManagerThread,
    ManagerThreadCreateRequest,
    ManagerThreadDetail,
    ManagerThreadListResponse,
    ManagerThreadUpdateRequest,
    ManagerWorkingMemory,
    ManagerWorkspaceResetRequest,
    ManagerWorkspaceResetResponse,
    ManagerWorkspaceResponse,
    MemoryLayer,
    StarterAgent,
)
from open_commerce.manager_agent.runs import (
    ManagerRunService,
    PersistentRunJournal,
    active_run,
    append_event,
)
from open_commerce.manager_agent.tools import (
    ManagerStatusProbe,
    ManagerToolRuntime,
    channel_allows,
    extract_search_test,
    extract_status_refresh,
    format_runtime_status,
    format_search_observation,
    is_status_question,
)
from open_commerce.manager_agent.workspace_onboarding import (
    advance_interview,
    apply_profile_progress,
    choose_model_prompt,
    onboarding_welcome,
    set_current_prompt,
    start_interview,
)
from open_commerce.manager_agent.workspace_tools import WorkspaceTools
from open_commerce.persistence.repositories.manager_agent import ManagerAgentRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.agent_tools import (
    CatalogSearchRuntime,
    CatalogSearchTool,
    CatalogSearchToolError,
)

ONBOARDING_CHANNEL: tuple[ManagerChannelKind, str, str, int, str] = (
    "onboarding",
    "onboarding",
    "Onboarding",
    0,
    "Business context, data readiness, goals, guardrails, and working preferences.",
)

STARTER_AGENT_CHANNELS: dict[StarterAgent, tuple[ManagerChannelKind, str, str, int, str]] = {
    "general": (
        "custom",
        "general-commerce",
        "General commerce",
        5,
        "An open-ended operator copilot for store questions, planning, and coordination.",
    ),
    "status": (
        "status",
        "status",
        "Status",
        10,
        "Monitor runtime services, catalog indexing, shopper surfaces, and agent availability.",
    ),
    "search": (
        "search",
        "search",
        "Search",
        20,
        "Plan retrieval, ranking signals, query quality, and search evaluation.",
    ),
    "recommendations": (
        "recommendations",
        "recommendations",
        "Recommendations",
        30,
        "Shape recommendation surfaces, objectives, constraints, and measurement.",
    ),
    "buy_again": (
        "buy_again",
        "buy-it-again",
        "Buy it again",
        40,
        "Explore repeat-purchase strategy without activating personalization or writes.",
    ),
    "analysis": (
        "custom",
        "analysis",
        "Analysis",
        50,
        "Investigate commerce questions, compare evidence, and prepare decision briefs.",
    ),
}

LEGACY_STARTER_AGENTS: tuple[StarterAgent, ...] = (
    "status",
    "search",
    "recommendations",
    "buy_again",
)

_CHANNEL_INTROS: dict[ManagerChannelKind, str] = {
    "status": (
        "This channel tracks live runtime and shopper-surface health. The status panel refreshes "
        "automatically, and you can ask me what is green, degraded, down, or blocking search."
    ),
    "search": (
        "This channel is for shopper search. Tell me what you want shoppers to find or how "
        "results should rank. Catalog CSV uploads are indexed in the background and become "
        "searchable here once verified. Ranking changes remain review drafts until an activation "
        "tool is added."
    ),
    "recommendations": (
        "This channel is for recommendation strategy across product, home, and cart surfaces. "
        "I can clarify the objective and prepare a bounded model brief, but I will not claim a "
        "model was trained, measured, or activated."
    ),
    "buy_again": (
        "This channel is for buy-it-again strategy. We can reason about eligibility, cadence, "
        "ranking, and success measures without using personal data or enabling live commerce."
    ),
    "custom": (
        "This is a focused strategy channel. Describe the outcome you want, and I will ask one "
        "material question at a time before preparing a reviewable draft."
    ),
    "onboarding": "",
}

_STARTER_AGENT_INTROS: dict[StarterAgent, str] = {
    "general": (
        "I am your general commerce agent. Bring me an operating question, an idea, or a messy "
        "problem and I will help shape the next useful step. I can coordinate the read-only "
        "tools that are available here; store changes still require the existing policy gates."
    ),
    "status": _CHANNEL_INTROS["status"],
    "search": _CHANNEL_INTROS["search"],
    "recommendations": _CHANNEL_INTROS["recommendations"],
    "buy_again": _CHANNEL_INTROS["buy_again"],
    "analysis": (
        "I am your analysis agent. Ask a commerce question or share a decision you are weighing. "
        "I will separate known facts, assumptions, and the evidence still needed without "
        "pretending a simulated result is a live business outcome."
    ),
}


class DurableManagerAgentService:
    """Persist each branch atomically without holding a lock during model latency."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        model_provider: ManagerModelProvider | None = None,
        search_service: CatalogSearchRuntime | None = None,
        status_probe: ManagerStatusProbe | None = None,
    ) -> None:
        self.database = database
        self.model_provider = model_provider
        self.capabilities = _capabilities(database.settings, model_provider)
        self.tool_runtime = ManagerToolRuntime(
            workspace=WorkspaceTools(database),
            catalog_search=CatalogSearchTool(search_service),
            status_probe=status_probe,
        )
        self.agent = ManagerReActAgent(self.capabilities)
        self.model_agent = (
            ModelBackedManagerAgent(
                provider=model_provider,
                capabilities=self.capabilities,
                max_iterations=database.settings.manager_model_max_iterations,
                max_tool_calls=database.settings.manager_model_max_tool_calls,
                max_output_tokens=database.settings.manager_model_max_output_tokens,
                tool_runtime=self.tool_runtime,
            )
            if model_provider is not None
            else None
        )

    async def bootstrap_workspace(
        self, *, tenant_id: UUID, idempotency_key: str
    ) -> ManagerWorkspaceResponse:
        """Start the interview and idempotently create eligible default channels."""

        request = {"workspace": "manager"}
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            prior_receipt = await receipts.replay(
                scope="manager:workspace:bootstrap", key=idempotency_key, request=request
            )
            repo = ManagerAgentRepository(session, tenant_id)
            now = utc_now()
            stored_onboarding = await repo.get_onboarding()
            onboarding = start_interview(stored_onboarding)
            if self.database.settings.runtime_profile != "legacy_demo":
                index = await catalog_index_status(session, tenant_id=tenant_id)
                onboarding.workspace_status = "completed"
                onboarding.current_prompt = None
                onboarding.completed_at = onboarding.completed_at or now
                onboarding.limited_mode = index.serving_catalog_id is None
                onboarding.catalog_decision = "defer" if onboarding.limited_mode else "provide"
            if onboarding != stored_onboarding:
                onboarding = await repo.save_onboarding(onboarding, now=now)
            await self._ensure_default_channels(
                repo,
                tenant_id=tenant_id,
                onboarding=onboarding,
                include_strategy=onboarding.workspace_status == "completed",
                now=now,
            )
            response = ManagerWorkspaceResponse(
                channels=await repo.list_threads(),
                onboarding=onboarding,
                capabilities=self.capabilities,
                catalog_index=await catalog_index_status(session, tenant_id=tenant_id),
            )
            if prior_receipt is None:
                receipts.remember(
                    scope="manager:workspace:bootstrap",
                    key=idempotency_key,
                    request=request,
                    response=response,
                )
            return response

    async def get_workspace(self, *, tenant_id: UUID) -> ManagerWorkspaceResponse:
        async with self.database.transaction(tenant_id) as session:
            repo = ManagerAgentRepository(session, tenant_id)
            return ManagerWorkspaceResponse(
                channels=await repo.list_threads(),
                onboarding=await repo.get_onboarding(),
                capabilities=self.capabilities,
                catalog_index=await catalog_index_status(session, tenant_id=tenant_id),
            )

    async def reset_workspace(
        self,
        *,
        tenant_id: UUID,
        request: ManagerWorkspaceResetRequest,
        idempotency_key: str,
    ) -> ManagerWorkspaceResetResponse:
        """Reset manager conversations and memory without deleting catalog or shopper state."""

        scope = "manager:workspace:reset"
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerWorkspaceResetResponse.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            channel_count, message_count, memory_count = await repo.reset_workspace()
            now = utc_now()
            onboarding = start_interview(ManagerDataOnboarding(tenant_id=tenant_id))
            onboarding = await repo.save_onboarding(onboarding, now=now)
            await self._ensure_default_channels(
                repo,
                tenant_id=tenant_id,
                onboarding=onboarding,
                include_strategy=False,
                now=now,
            )
            workspace = ManagerWorkspaceResponse(
                channels=await repo.list_threads(),
                onboarding=onboarding,
                capabilities=self.capabilities,
                catalog_index=await catalog_index_status(session, tenant_id=tenant_id),
            )
            response = ManagerWorkspaceResetResponse(
                workspace=workspace,
                deleted_channel_count=channel_count,
                deleted_message_count=message_count,
                deleted_memory_count=memory_count,
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def get_runtime_status(self, *, tenant_id: UUID) -> ManagerRuntimeStatus:
        async with self.database.transaction(tenant_id) as session:
            index_status = await catalog_index_status(session, tenant_id=tenant_id)
        snapshot = await self.tool_runtime.status(
            catalog_index=index_status, capabilities=self.capabilities, tenant_id=tenant_id
        )
        return snapshot

    async def create_thread(
        self,
        *,
        tenant_id: UUID,
        request: ManagerThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(
                scope="manager:thread:create", key=idempotency_key, request=request
            )
            if cached is not None:
                return ManagerThreadDetail.model_validate(cached)
            now = utc_now()
            repo = ManagerAgentRepository(session, tenant_id)
            slug = await _available_slug(repo, request.title)
            thread = await repo.create_thread(
                thread_id=uuid4(),
                title=request.title,
                description=request.description or _CHANNEL_INTROS["custom"],
                slug=slug,
                position=await repo.next_channel_position(),
                now=now,
            )
            onboarding = await repo.get_onboarding()
            welcome = _message(
                tenant_id=tenant_id,
                thread_id=thread.id,
                role="assistant",
                content=_custom_agent_intro(thread),
                now=now,
            )
            await repo.add_message(welcome)
            response = ManagerThreadDetail(
                thread=thread,
                messages=[welcome],
                memories=[],
                capabilities=self.capabilities,
                onboarding=onboarding,
            )
            receipts.remember(
                scope="manager:thread:create",
                key=idempotency_key,
                request=request,
                response=response,
            )
            return response

    async def list_threads(self, *, tenant_id: UUID) -> ManagerThreadListResponse:
        async with self.database.transaction(tenant_id) as session:
            return ManagerThreadListResponse(
                items=await ManagerAgentRepository(session, tenant_id).list_threads()
            )

    async def update_thread(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerThreadUpdateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        scope = f"manager:thread:{thread_id}:update"
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerThreadDetail.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            current = await repo.get_thread(thread_id)
            if current.thread_type != "channel":
                raise ManagerThreadInvalidError("Reply threads cannot be renamed or archived")
            if current.channel_kind == "onboarding" and request.status == "archived":
                raise ManagerThreadInvalidError("The onboarding channel cannot be archived")
            slug = None
            if request.title is not None and request.title != current.title:
                candidate = _slugify(request.title)
                occupied = await repo.get_channel_by_slug(candidate)
                slug = candidate if occupied is None or occupied.id == current.id else None
                if slug is None:
                    raise ManagerThreadInvalidError("A channel with that name already exists")
            await repo.update_thread_metadata(
                thread_id=thread_id,
                title=request.title,
                description=request.description,
                status=request.status,
                slug=slug,
                now=utc_now(),
            )
            response = await self._thread_detail(repo, thread_id)
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def clear_channel_history(
        self, *, tenant_id: UUID, thread_id: UUID, idempotency_key: str
    ) -> ManagerChannelClearResponse:
        scope = f"manager:thread:{thread_id}:clear-history"
        request = {"thread_id": str(thread_id)}
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerChannelClearResponse.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            thread = await repo.get_thread(thread_id)
            if thread.thread_type != "channel":
                raise ManagerThreadInvalidError("Only agent channels can be cleared")
            onboarding = await repo.get_onboarding()
            now = utc_now()
            deleted_messages, deleted_replies = await repo.clear_channel_history(
                thread_id=thread_id, now=now
            )
            refreshed = await repo.get_thread(thread_id)
            await repo.add_message(
                _message(
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                    role="assistant",
                    content=_fresh_agent_intro(refreshed, onboarding),
                    now=now + timedelta(microseconds=1),
                )
            )
            response = ManagerChannelClearResponse(
                detail=await self._thread_detail(repo, thread_id),
                deleted_message_count=deleted_messages,
                deleted_reply_thread_count=deleted_replies,
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def create_reply_thread(
        self,
        *,
        tenant_id: UUID,
        channel_id: UUID,
        request: ManagerReplyThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        scope = f"manager:thread:{channel_id}:reply:{request.root_message_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerThreadDetail.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            channel = await repo.get_thread(channel_id)
            if channel.thread_type != "channel":
                raise ManagerThreadInvalidError("Nested reply threads are not supported")
            root = await repo.get_message(thread_id=channel_id, message_id=request.root_message_id)
            existing = await repo.get_reply_thread(
                parent_thread_id=channel_id, root_message_id=root.id
            )
            if existing is None:
                existing = await repo.create_thread(
                    thread_id=uuid4(),
                    title=_reply_title(root.content),
                    thread_type="reply",
                    channel_kind=None,
                    slug=None,
                    description=f"Reply thread in #{channel.slug}",
                    position=0,
                    parent_thread_id=channel_id,
                    root_message_id=root.id,
                    now=utc_now(),
                )
            response = await self._thread_detail(repo, existing.id)
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def get_reply_thread(
        self, *, tenant_id: UUID, channel_id: UUID, root_message_id: UUID
    ) -> ManagerThreadDetail:
        async with self.database.transaction(tenant_id) as session:
            repo = ManagerAgentRepository(session, tenant_id)
            channel = await repo.get_thread(channel_id)
            if channel.thread_type != "channel":
                raise ManagerThreadInvalidError("Nested reply threads are not supported")
            await repo.get_message(thread_id=channel_id, message_id=root_message_id)
            reply = await repo.get_reply_thread(
                parent_thread_id=channel_id, root_message_id=root_message_id
            )
            if reply is None:
                raise ManagerThreadNotFoundError("Reply thread was not found")
            return await self._thread_detail(repo, reply.id)

    async def get_thread(self, *, tenant_id: UUID, thread_id: UUID) -> ManagerThreadDetail:
        async with self.database.transaction(tenant_id) as session:
            return await self._thread_detail(ManagerAgentRepository(session, tenant_id), thread_id)

    async def send_message(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
    ) -> ManagerAgentReply:
        return await ManagerRunService(self.database).compatibility_reply(
            tenant_id=tenant_id,
            thread_id=thread_id,
            request=request,
            idempotency_key=idempotency_key,
            service=self,
        )

    async def _execute_message(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
        journal: PersistentRunJournal,
        persisted_user_id: UUID,
    ) -> ManagerAgentReply:
        from open_commerce.stores.usage import model_scope

        with model_scope(self.database, tenant_id):
            return await self._execute_scoped_message(
                tenant_id=tenant_id,
                thread_id=thread_id,
                request=request,
                idempotency_key=idempotency_key,
                journal=journal,
                persisted_user_id=persisted_user_id,
            )

    async def _execute_scoped_message(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
        journal: PersistentRunJournal,
        persisted_user_id: UUID,
    ) -> ManagerAgentReply:
        scope = f"manager:thread:{thread_id}:message"
        async with self.database.transaction(tenant_id) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerAgentReply.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            thread = await repo.get_thread(thread_id)
            history = await repo.list_messages(thread_id, limit=24)
            history = [message for message in history if message.id != persisted_user_id]
            memories = await repo.list_memories(thread_id=thread_id)
            onboarding = await repo.get_onboarding()
            index_status = await catalog_index_status(session, tenant_id=tenant_id)
            root = (
                await repo.get_message(
                    thread_id=thread.parent_thread_id,
                    message_id=thread.root_message_id,
                )
                if thread.thread_type == "reply"
                and thread.parent_thread_id is not None
                and thread.root_message_id is not None
                else None
            )
            focus_thread = (
                await repo.get_thread(thread.parent_thread_id)
                if thread.thread_type == "reply" and thread.parent_thread_id is not None
                else thread
            )

        is_interview = (
            thread.thread_type == "channel"
            and thread.channel_kind == "onboarding"
            and onboarding.workspace_status != "completed"
        )
        if is_interview:
            outcome = await self._onboarding_outcome(
                onboarding=onboarding,
                request=request,
                working=thread.working_memory,
            )
        else:
            agent_history = ([root] if root is not None else []) + history[-12:]
            status_refresh = extract_status_refresh(request.content)
            if self.model_agent is None and status_refresh is not None:
                updated_onboarding = onboarding.model_copy(
                    update={"status_refresh_minutes": status_refresh.minutes}
                )
                outcome = ManagerAgentOutcome(
                    content=(
                        "Automatic status checks are off. You can still refresh the panel manually."
                        if status_refresh.minutes == 0
                        else "I set the status panel to check every "
                        f"{status_refresh.minutes} minutes."
                    ),
                    working_memory=thread.working_memory.model_copy(
                        update={"current_topic": "Runtime status", "open_question": None}
                    ),
                    steps=[
                        AgentStep(
                            stage="act",
                            title="Update status cadence",
                            detail=(
                                "Disabled automatic polling; manual refresh remains available."
                                if status_refresh.minutes == 0
                                else "Saved a tenant workspace polling interval of "
                                f"{status_refresh.minutes} minutes."
                            ),
                            tool="configure_status_refresh",
                        )
                    ],
                    onboarding=updated_onboarding,
                )
            elif self.model_agent is not None:
                outcome = await self.model_agent.respond(
                    tenant_id=tenant_id,
                    content=request.content,
                    working=thread.working_memory,
                    memories=memories,
                    recent_messages=agent_history,
                    onboarding=onboarding,
                    catalog_index=index_status,
                    channel=focus_thread,
                    journal=journal,
                )
            else:
                tool_outcome = await self._deterministic_tool_outcome(
                    tenant_id=tenant_id,
                    content=request.content,
                    thread=focus_thread,
                    working=thread.working_memory,
                    catalog_index=index_status,
                )
                if tool_outcome is None:
                    outcome = self.agent.respond(
                        content=request.content,
                        working=thread.working_memory,
                        long_term_memories=[item for item in memories if item.layer == "long_term"],
                        recent_messages=agent_history,
                        onboarding=onboarding,
                        catalog_index=index_status,
                    )
                else:
                    outcome = tool_outcome

        async with self.database.transaction(tenant_id, write=True) as session:
            run = await journal.checked_row(session)
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerAgentReply.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            current_thread = await repo.get_thread(thread_id)
            if (
                current_thread.user_turn_count != thread.user_turn_count
                or current_thread.version != thread.version
            ):
                raise ManagerThreadBusyError(
                    "This conversation advanced while the agent was working. Retry your message."
                )
            current_onboarding = await repo.get_onboarding()
            onboarding_changed = outcome.onboarding is not None and outcome.onboarding != onboarding
            if onboarding_changed and current_onboarding != onboarding:
                raise ManagerThreadBusyError(
                    "Workspace onboarding changed in another conversation. Review it and retry."
                )
            now = utc_now()
            assistant_at = now + timedelta(microseconds=1)
            user_message = await repo.get_message(thread_id=thread_id, message_id=persisted_user_id)
            assistant_message = _message(
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="assistant",
                content=outcome.content,
                now=assistant_at,
                steps=outcome.steps,
            )
            await repo.add_message(assistant_message)
            saved_onboarding = current_onboarding
            workspace_changed = False
            if onboarding_changed and outcome.onboarding is not None:
                saved_onboarding = await repo.save_onboarding(outcome.onboarding, now=now)
                workspace_changed = (
                    onboarding.workspace_status != "completed"
                    and saved_onboarding.workspace_status == "completed"
                )
                if workspace_changed:
                    await self._ensure_default_channels(
                        repo,
                        tenant_id=tenant_id,
                        onboarding=saved_onboarding,
                        include_strategy=True,
                        now=assistant_at,
                    )
            if outcome.explicit_preference is not None:
                memory = _preference_memory(
                    tenant_id=tenant_id,
                    content=outcome.explicit_preference,
                    source_message_id=user_message.id,
                    now=now,
                )
                await repo.add_memory(memory, source_message_id=user_message.id)
            turn_count = thread.user_turn_count + 1
            updated = await repo.update_thread(
                thread_id=thread_id,
                working_memory=outcome.working_memory,
                user_turn_count=turn_count,
                title=_thread_title(thread, request.content),
                now=assistant_at,
            )
            periodic = None
            interval = self.database.settings.manager_periodic_memory_turns
            if not is_interview and turn_count % interval == 0:
                periodic = _periodic_memory(
                    tenant_id=tenant_id,
                    thread=updated,
                    messages=[*history, user_message, assistant_message][-interval * 2 :],
                    now=now,
                    interval=interval,
                )
                await repo.add_memory(periodic, source_message_id=assistant_message.id)
            response = ManagerAgentReply(
                thread=updated,
                user_message=user_message,
                assistant_message=assistant_message,
                memories=await repo.list_memories(thread_id=thread_id),
                periodic_memory_created=periodic,
                capabilities=self.capabilities,
                onboarding=saved_onboarding,
                workspace_changed=workspace_changed,
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            limited = bool(outcome.steps and outcome.steps[-1].title == "Stop bounded run")
            run.status = "failed" if limited else "completed"
            run.error_code = "RUN_LIMIT_REACHED" if limited else None
            run.assistant_message_id = assistant_message.id
            run.result = response.model_dump(mode="json")
            run.lease_token = None
            run.lease_until = None
            await append_event(
                session,
                run,
                "failed" if limited else "completed",
                "Needs continuation" if limited else "Reply ready",
                outcome.content if limited else "Completed the conversation turn.",
            )
            return response

    async def _deterministic_tool_outcome(
        self,
        *,
        tenant_id: UUID,
        content: str,
        thread: ManagerThread,
        working: ManagerWorkingMemory,
        catalog_index: CatalogIndexStatus,
    ) -> ManagerAgentOutcome | None:
        search_request = extract_search_test(content)
        if search_request is not None and channel_allows(thread, "search"):
            try:
                observation = await self.tool_runtime.test_search(
                    tenant_id=tenant_id,
                    arguments=search_request,
                    catalog_index=catalog_index,
                )
            except CatalogSearchToolError as exc:
                return ManagerAgentOutcome(
                    content=(
                        "I could not run that catalog search right now. "
                        f"The search service reported {exc.code}."
                    ),
                    working_memory=working.model_copy(
                        update={"current_topic": "Search test", "open_question": None}
                    ),
                    steps=[
                        AgentStep(
                            stage="act",
                            title="Run tenant catalog search",
                            detail=f"The read-only search stopped with {exc.code}.",
                            status="needs_input",
                            tool="test_catalog_search",
                        )
                    ],
                )
            reply = format_search_observation(observation)
            return ManagerAgentOutcome(
                content=reply,
                working_memory=working.model_copy(
                    update={"current_topic": "Search test", "open_question": None}
                ),
                steps=[
                    AgentStep(
                        stage="recall",
                        title="Load channel function",
                        detail=f"Used #{thread.slug} as the search-testing context.",
                    ),
                    AgentStep(
                        stage="act",
                        title="Run tenant catalog search",
                        detail=f"Executed bounded {search_request.mode} retrieval.",
                        tool="test_catalog_search",
                    ),
                    AgentStep(
                        stage="observe",
                        title="Inspect ranked results",
                        detail=(
                            f"Observed {observation.get('result_count', 0)} eligible products; "
                            "no ranking state changed."
                        ),
                        tool="test_catalog_search",
                    ),
                    AgentStep(
                        stage="respond",
                        title="Report search test",
                        detail="Returned current catalog results with prices and scores.",
                    ),
                ],
            )
        if is_status_question(content) and channel_allows(thread, "status"):
            status = await self.tool_runtime.status(
                catalog_index=catalog_index, capabilities=self.capabilities, tenant_id=tenant_id
            )
            return ManagerAgentOutcome(
                content=format_runtime_status(status),
                working_memory=working.model_copy(
                    update={"current_topic": "Runtime status", "open_question": None}
                ),
                steps=[
                    AgentStep(
                        stage="act",
                        title="Probe runtime services",
                        detail="Ran independent read-only dependency and surface probes.",
                        tool="inspect_service_status",
                    ),
                    AgentStep(
                        stage="observe",
                        title="Compile service status",
                        detail="Mapped current observations to green, degraded, down, or unknown.",
                        tool="inspect_service_status",
                    ),
                    AgentStep(
                        stage="respond",
                        title="Report current status",
                        detail="Returned the same status snapshot used by the channel panel.",
                    ),
                ],
            )
        return None

    async def profile_dataset(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerDatasetProfileRequest,
        idempotency_key: str,
    ) -> ManagerDatasetProfileReply:
        """Profile one bounded CSV and attach only its structural metadata."""

        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            scope = f"manager:thread:{thread_id}:dataset-profile"
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ManagerDatasetProfileReply.model_validate(cached)
            repo = ManagerAgentRepository(session, tenant_id)
            thread = await repo.get_thread(thread_id)
            profile = profile_csv(
                dataset_kind=request.dataset_kind,
                filename=request.filename,
                csv_text=request.csv_text,
            )
            now = profile.profiled_at
            assistant_at = now + timedelta(microseconds=1)
            onboarding = attach_profile(await repo.get_onboarding(), profile)
            index_status = CatalogIndexStatus()
            engagement_count = 0
            if request.dataset_kind == "engagement" and not profile.missing_required:
                from open_commerce.ranking.service import import_engagement

                engagement = await import_engagement(session, tenant_id, request.csv_text)
                engagement_count = engagement.event_count
            if request.dataset_kind == "catalog":
                onboarding.catalog_decision = "provide"
                if not profile.missing_required:
                    from open_commerce.catalog.shopify_csv import shopify_csv

                    products = shopify_csv(request.csv_text, request.catalog_currency)
                    source_version = profile.content_sha256
                    if products is None:
                        products = normalize_catalog_csv(csv_text=request.csv_text, profile=profile)
                    else:
                        from open_commerce.core.types import canonical_hash

                        source_version = canonical_hash(
                            {
                                "csv": profile.content_sha256,
                                "currency": request.catalog_currency,
                            }
                        )
                    index_status = await stage_catalog_upload(
                        session,
                        tenant_id=tenant_id,
                        filename=profile.filename,
                        source_version=source_version,
                        products=products,
                    )
                    onboarding.limited_mode = False
            if not profile.missing_required and onboarding.workspace_status != "not_started":
                onboarding = apply_profile_progress(onboarding, request.dataset_kind)
            onboarding = await repo.save_onboarding(onboarding, now=now)
            user_message = _message(
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="user",
                content=f"Attached {request.dataset_kind} CSV: {profile.filename}",
                now=now,
            )
            missing = profile.missing_required
            status: Literal["completed", "needs_input"]
            if missing:
                content = (
                    f"I profiled {profile.filename}: {profile.row_count} rows and "
                    f"{len(profile.columns)} columns. I could not map {', '.join(missing)}. "
                    "Please upload a revised CSV or name a Markdown mapping document. "
                    "No catalog rows were retained."
                )
                status = "needs_input"
            elif request.dataset_kind == "catalog":
                next_question = (
                    onboarding.current_prompt.question
                    if onboarding.current_prompt is not None
                    else onboarding_question(onboarding)
                )
                follow_up = next_question or (
                    "I will show the catalog as ready when the count matches."
                )
                content = (
                    f"I validated {profile.filename} and queued {index_status.product_count} "
                    "products for search indexing. I retained only normalized catalog fields, "
                    "not the uploaded CSV. You can keep chatting in any channel while the "
                    f"index builds. {follow_up}"
                )
                status = "needs_input" if next_question else "completed"
            else:
                next_question = (
                    onboarding.current_prompt.question
                    if onboarding.current_prompt is not None
                    else onboarding_question(onboarding)
                )
                content = (
                    f"I validated {profile.filename}: {profile.row_count} rows and "
                    f"{len(profile.columns)} columns, with {len(profile.detected_mappings)} "
                    f"canonical fields detected. Retained {engagement_count} deduplicated "
                    "events for local ranking; raw CSV, queries and visitor IDs were discarded. "
                    f"{next_question or 'The data onboarding draft is ready for review.'}"
                )
                status = "needs_input" if next_question else "completed"
            assistant_message = _message(
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="assistant",
                content=content,
                steps=[
                    AgentStep(
                        stage="act",
                        title=(
                            "Stage catalog index"
                            if request.dataset_kind == "catalog" and not missing
                            else "Profile attached CSV"
                        ),
                        detail=(
                            "Persisted bounded normalized product fields and queued a durable "
                            "index job."
                            if request.dataset_kind == "catalog" and not missing
                            else "Parsed bounded CSV structure without retaining raw rows."
                        ),
                        status="completed",
                        tool=(
                            "catalog.stage_index"
                            if request.dataset_kind == "catalog" and not missing
                            else "data.profile_csv"
                        ),
                    ),
                    AgentStep(
                        stage="observe",
                        title="Update data onboarding",
                        detail=(
                            "Saved tenant-scoped source metadata; catalog activation waits for a "
                            "verified index build."
                            if request.dataset_kind == "catalog" and not missing
                            else "Saved tenant-scoped source metadata; no connector, schedule, "
                            "index, or model was activated."
                        ),
                        status=status,
                        tool="data.profile_csv",
                    ),
                ],
                now=assistant_at,
            )
            await repo.add_message(user_message)
            await repo.add_message(assistant_message)
            open_question = (
                onboarding.current_prompt.question
                if onboarding.current_prompt is not None
                else onboarding_question(onboarding)
            )
            updated = await repo.update_thread(
                thread_id=thread_id,
                working_memory=thread.working_memory.model_copy(
                    update={"current_topic": "Data onboarding", "open_question": open_question}
                ),
                user_turn_count=thread.user_turn_count + 1,
                title=_thread_title(thread, f"Onboard {request.dataset_kind} data"),
                now=assistant_at,
            )
            response = ManagerDatasetProfileReply(
                thread=updated,
                user_message=user_message,
                assistant_message=assistant_message,
                memories=await repo.list_memories(thread_id=thread_id),
                capabilities=self.capabilities,
                onboarding=onboarding,
                profile=profile,
                catalog_index=index_status,
            )
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def list_memories(
        self, *, tenant_id: UUID, layer: MemoryLayer | None = None
    ) -> ManagerMemoryListResponse:
        async with self.database.transaction(tenant_id) as session:
            return ManagerMemoryListResponse(
                items=await ManagerAgentRepository(session, tenant_id).list_memories(layer=layer)
            )

    async def delete_memory(
        self, *, tenant_id: UUID, memory_id: UUID, idempotency_key: str
    ) -> ManagerMemoryDeleteResponse:
        request = {"memory_id": str(memory_id)}
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(
                scope="manager:memory:delete", key=idempotency_key, request=request
            )
            if cached is not None:
                return ManagerMemoryDeleteResponse.model_validate(cached)
            response = await ManagerAgentRepository(session, tenant_id).delete_long_term_memory(
                memory_id
            )
            receipts.remember(
                scope="manager:memory:delete",
                key=idempotency_key,
                request=request,
                response=response,
            )
            return response

    async def _thread_detail(
        self, repo: ManagerAgentRepository, thread_id: UUID
    ) -> ManagerThreadDetail:
        thread = await repo.get_thread(thread_id)
        root = None
        if (
            thread.thread_type == "reply"
            and thread.parent_thread_id is not None
            and thread.root_message_id is not None
        ):
            root = await repo.get_message(
                thread_id=thread.parent_thread_id,
                message_id=thread.root_message_id,
            )
        return ManagerThreadDetail(
            thread=thread,
            messages=await repo.list_messages(thread_id),
            memories=await repo.list_memories(thread_id=thread_id),
            capabilities=self.capabilities,
            onboarding=await repo.get_onboarding(),
            root_message=root,
            active_run=await active_run(repo.session, repo.tenant_id, thread_id),
        )

    async def _onboarding_outcome(
        self,
        *,
        onboarding: ManagerDataOnboarding,
        request: ManagerMessageRequest,
        working: ManagerWorkingMemory,
    ) -> ManagerAgentOutcome:
        advance = advance_interview(onboarding, request.content)
        content = advance.fallback_content
        steps = [
            AgentStep(
                stage="understand",
                title="Validate onboarding answer",
                detail=(
                    "Mapped the answer to the active typed onboarding field."
                    if advance.accepted
                    else "Kept the active question because the answer was not safely mapped."
                ),
                status="completed" if advance.accepted else "needs_input",
            )
        ]
        updated = advance.onboarding
        current = onboarding.current_prompt
        if (
            advance.accepted
            and not advance.completed
            and current is not None
            and self.model_provider is not None
        ):
            try:
                selected = await choose_model_prompt(
                    provider=self.model_provider,
                    onboarding=updated,
                    completed_field=current.field,
                    max_output_tokens=self.database.settings.manager_model_max_output_tokens,
                )
            except ManagerModelUnavailableError:
                selected = None
            if selected is not None:
                prompt, model_content = selected
                updated = set_current_prompt(updated, prompt.field)
                content = model_content
                steps.append(
                    AgentStep(
                        stage="act",
                        title="Choose next interview prompt",
                        detail=(
                            "Accepted one model-selected field from the finite eligible registry."
                        ),
                        tool="onboarding.choose_question",
                    )
                )
            else:
                steps.append(
                    AgentStep(
                        stage="act",
                        title="Use deterministic onboarding",
                        detail="Continued with the next eligible registry prompt.",
                        status="simulated",
                        tool="onboarding.choose_question",
                    )
                )
        steps.append(
            AgentStep(
                stage="respond",
                title="Continue onboarding",
                detail=(
                    "Completed the interview and unlocked the workspace."
                    if advance.completed
                    else "Asked one validated question without exposing hidden reasoning."
                ),
            )
        )
        open_question = updated.current_prompt.question if updated.current_prompt else None
        return ManagerAgentOutcome(
            content=content,
            working_memory=working.model_copy(
                update={"current_topic": "Workspace onboarding", "open_question": open_question}
            ),
            steps=steps,
            onboarding=updated,
        )

    async def _ensure_default_channels(
        self,
        repo: ManagerAgentRepository,
        *,
        tenant_id: UUID,
        onboarding: ManagerDataOnboarding,
        include_strategy: bool,
        now: datetime,
    ) -> None:
        specs = [ONBOARDING_CHANNEL]
        if include_strategy:
            selected = onboarding.workspace_profile.starter_agents or list(LEGACY_STARTER_AGENTS)
            specs.extend(STARTER_AGENT_CHANNELS[item] for item in selected)
        for kind, slug, title, position, description in specs:
            if await repo.get_channel_by_slug(slug) is not None:
                continue
            thread = await repo.create_thread(
                thread_id=uuid5(NAMESPACE_URL, f"{tenant_id}:manager-channel:{slug}"),
                title=title,
                channel_kind=kind,
                slug=slug,
                description=description,
                position=position,
                now=now,
            )
            if kind == "onboarding":
                intro = onboarding_welcome(onboarding)
            else:
                selected_agent = next(
                    agent for agent, spec in STARTER_AGENT_CHANNELS.items() if spec[1] == slug
                )
                intro = _STARTER_AGENT_INTROS[selected_agent]
            await repo.add_message(
                _message(
                    tenant_id=tenant_id,
                    thread_id=thread.id,
                    role="assistant",
                    content=intro,
                    now=now,
                )
            )


def _custom_agent_intro(thread: ManagerThread) -> str:
    purpose = thread.description or _CHANNEL_INTROS["custom"]
    return (
        f"I am the {thread.title} agent. My focus is: {purpose} "
        "Tell me what you are working through, and I will use the safe context and tools "
        "available to this workspace."
    )


def _fresh_agent_intro(thread: ManagerThread, onboarding: ManagerDataOnboarding) -> str:
    if thread.channel_kind == "onboarding":
        return onboarding_welcome(onboarding)
    for agent, spec in STARTER_AGENT_CHANNELS.items():
        if spec[1] == thread.slug:
            return f"History cleared. {_STARTER_AGENT_INTROS[agent]}"
    if thread.channel_kind in _CHANNEL_INTROS and thread.channel_kind != "custom":
        return f"History cleared. {_CHANNEL_INTROS[thread.channel_kind]}"
    return f"History cleared. {_custom_agent_intro(thread)}"


def _capabilities(
    settings: Settings, model_provider: ManagerModelProvider | None
) -> ManagerAgentCapabilities:
    model_fields = (
        {
            "conversation_provider": model_provider.provider_name,
            "conversation_model": model_provider.model_id,
            "model_backed": True,
        }
        if model_provider is not None
        else {}
    )
    if settings.search_embedding_backend == "minilm":
        return ManagerAgentCapabilities(
            semantic_backend="all-MiniLM-L6-v2 (pinned local)",
            learned_semantics=True,
            **model_fields,
        )
    return ManagerAgentCapabilities(
        semantic_backend="signed-hash test baseline", learned_semantics=False, **model_fields
    )


async def _available_slug(repo: ManagerAgentRepository, title: str) -> str:
    base = _slugify(title)
    candidate = base
    suffix = 2
    while await repo.get_channel_by_slug(candidate) is not None:
        tail = f"-{suffix}"
        candidate = f"{base[: 120 - len(tail)]}{tail}"
        suffix += 1
    return candidate


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (slug or "channel")[:120].rstrip("-")


def _reply_title(content: str) -> str:
    cleaned = " ".join(content.split())
    return f"Thread: {cleaned[:72]}" if len(cleaned) <= 72 else f"Thread: {cleaned[:69]}..."


def _thread_title(thread: ManagerThread, content: str) -> str:
    if thread.thread_type != "channel" or thread.channel_kind != "custom":
        return thread.title
    if thread.user_turn_count > 0 or thread.title != "Discovery strategy":
        return thread.title
    cleaned = " ".join(content.split())
    return cleaned[:77] + "..." if len(cleaned) > 80 else cleaned


def _message(
    *,
    tenant_id: UUID,
    thread_id: UUID,
    role: Literal["user", "assistant"],
    content: str,
    now: datetime,
    steps: list[AgentStep] | None = None,
) -> ManagerMessage:
    return ManagerMessage(
        id=uuid4(),
        tenant_id=tenant_id,
        thread_id=thread_id,
        role=role,
        content=content,
        steps=steps or [],
        created_at=now,
    )


def _preference_memory(
    *, tenant_id: UUID, content: str, source_message_id: UUID, now: datetime
) -> ManagerMemory:
    _ = source_message_id
    normalized = " ".join(content.lower().split())
    title = content[:57] + "..." if len(content) > 60 else content
    return ManagerMemory(
        id=uuid5(NAMESPACE_URL, f"{tenant_id}:manager-preference:{normalized}"),
        tenant_id=tenant_id,
        layer="long_term",
        title=title,
        content=content,
        source="explicit_manager",
        created_at=now,
    )


def _periodic_memory(
    *,
    tenant_id: UUID,
    thread: ManagerThread,
    messages: list[ManagerMessage],
    now: datetime,
    interval: int,
) -> ManagerMemory:
    user_messages = [item for item in messages if item.role == "user"]
    start = user_messages[0].created_at if user_messages else now
    objective = thread.working_memory.objective
    objective_text = (
        f"Discovery objective is {objective.status}: surface={objective.surface}, "
        f"retrieval={objective.retrieval_mode}, signals={','.join(objective.ranking_signals)}."
        if objective
        else "No typed discovery objective is ready."
    )
    latest = user_messages[-1].content if user_messages else "No manager request recorded."
    content = (
        f"Turns {thread.user_turn_count - interval + 1}-{thread.user_turn_count}. "
        f"{objective_text} Latest manager request: {latest[:500]}"
    )
    return ManagerMemory(
        id=uuid5(
            NAMESPACE_URL,
            f"{tenant_id}:manager-period:{thread.id}:{thread.user_turn_count}",
        ),
        tenant_id=tenant_id,
        thread_id=thread.id,
        layer="periodic",
        title=f"Conversation checkpoint {thread.user_turn_count // interval}",
        content=content,
        source="periodic_summary",
        period_start=start,
        period_end=now,
        created_at=now,
    )
