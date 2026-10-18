"""Durable shopper accounts, sessions, conversations, and explicit memory."""

from __future__ import annotations

from datetime import datetime, timedelta
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.persistence import (
    active_catalog_integration,
    catalog_index_status,
    catalog_records,
)
from open_commerce.core.redaction import contains_direct_pii_or_secret
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.agent_tools import CatalogSearchRuntime, CatalogSearchTool
from open_commerce.shopper_agent.auth import (
    hash_password,
    new_session_token,
    session_token_hash,
    verify_password,
)
from open_commerce.shopper_agent.errors import (
    ShopperAccountConflictError,
    ShopperAuthenticationError,
    ShopperUnsafeInputError,
)
from open_commerce.shopper_agent.memory_tools import (
    SaveShoppingMemoryInput,
    ShopperMemoryTool,
    ShopperMemoryToolError,
)
from open_commerce.shopper_agent.model_agent import (
    ShopperAgentOutcome,
    ShopperConversationalAgent,
    explicit_memory,
    memory_only_message,
)
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAgentStep,
    ShopperAuthResponse,
    ShopperChatRequest,
    ShopperChatResponse,
    ShopperConversationDetail,
    ShopperConversationList,
    ShopperDiscoveryResponse,
    ShopperDiscoverySuggestion,
    ShopperLoginRequest,
    ShopperMemory,
    ShopperMemoryDeleteResponse,
    ShopperMemoryList,
    ShopperMessage,
    ShopperRegisterRequest,
)
from open_commerce.stores.shoppers import ShopperAccounts
from open_commerce.stores.usage import ModelQuotaExceeded
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.activity_models import ActivityEventInput, ActivityKind
from open_commerce.telemetry.activity_tools import ActivityTools


class DurableShopperAgentService:
    """Keep shopper identity and memory durable while model calls stay outside transactions."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        search_service: CatalogSearchRuntime,
        model_provider: ManagerModelProvider | None = None,
    ) -> None:
        self.database = database
        search_tool = CatalogSearchTool(search_service)
        settings = database.settings
        self.agent = ShopperConversationalAgent(
            catalog_search=search_tool,
            provider=model_provider,
            max_iterations=settings.manager_model_max_iterations,
            max_tool_calls=settings.manager_model_max_tool_calls,
            max_output_tokens=settings.manager_model_max_output_tokens,
            catalog_reader=CatalogBrowseService(database),
        )

    async def register(
        self, *, tenant_id: UUID, request: ShopperRegisterRequest
    ) -> tuple[ShopperAuthResponse, str]:
        username = request.username.lower()
        password_hash = await hash_password(request.password.get_secret_value())
        now = utc_now()
        raw_token = new_session_token()
        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ShopperRepository(session, tenant_id)
            if await repo.get_account_credentials(username) is not None:
                raise ShopperAccountConflictError("That username is already in use")
            account = await repo.create_account(
                account_id=uuid4(),
                username=username,
                display_name=request.display_name.strip(),
                password_hash=password_hash,
                now=now,
            )
            await self._create_session(repo, account=account, raw_token=raw_token, now=now)
        return ShopperAuthResponse(account=account), raw_token

    async def login(
        self, *, tenant_id: UUID, request: ShopperLoginRequest
    ) -> tuple[ShopperAuthResponse, str]:
        username = request.username.lower()
        async with self.database.transaction(tenant_id) as session:
            stored = await ShopperRepository(session, tenant_id).get_account_credentials(username)
        if stored is None or not await verify_password(
            request.password.get_secret_value(), stored[1]
        ):
            raise ShopperAuthenticationError("Username or password is incorrect")
        account = stored[0]
        raw_token = new_session_token()
        now = utc_now()
        async with self.database.transaction(tenant_id, write=True) as session:
            await self._create_session(
                ShopperRepository(session, tenant_id),
                account=account,
                raw_token=raw_token,
                now=now,
            )
        return ShopperAuthResponse(account=account), raw_token

    async def authenticate(self, *, tenant_id: UUID, raw_token: str) -> ShopperAccount:
        if not raw_token or len(raw_token) > 200:
            raise ShopperAuthenticationError("Sign in to continue")
        async with self.database.transaction(tenant_id) as session:
            account = await ShopperRepository(session, tenant_id).account_for_session(
                token_hash=session_token_hash(raw_token), now=utc_now()
            )
        if account is None:
            raise ShopperAuthenticationError("Your session is invalid or expired")
        return account

    async def logout(self, *, tenant_id: UUID, raw_token: str) -> None:
        if not raw_token:
            return
        async with self.database.transaction(tenant_id, write=True) as session:
            await ShopperRepository(session, tenant_id).revoke_session(
                token_hash=session_token_hash(raw_token), now=utc_now()
            )

    async def list_conversations(
        self, *, tenant_id: UUID, account_id: UUID
    ) -> ShopperConversationList:
        async with self.database.transaction(tenant_id) as session:
            items = await ShopperRepository(session, tenant_id).list_conversations(
                account_id=account_id
            )
        return ShopperConversationList(items=items)

    async def get_conversation(
        self, *, tenant_id: UUID, account_id: UUID, conversation_id: UUID
    ) -> ShopperConversationDetail:
        async with self.database.transaction(tenant_id) as session:
            repo = ShopperRepository(session, tenant_id)
            conversation = await repo.get_conversation(
                account_id=account_id, conversation_id=conversation_id
            )
            messages = await repo.list_messages(
                account_id=account_id, conversation_id=conversation_id
            )
        return ShopperConversationDetail(conversation=conversation, messages=messages)

    async def list_memories(self, *, tenant_id: UUID, account_id: UUID) -> ShopperMemoryList:
        async with self.database.transaction(tenant_id) as session:
            items = await ShopperRepository(session, tenant_id).list_memories_for_management(
                account_id=account_id
            )
        return ShopperMemoryList(items=items)

    async def discovery(self, *, tenant_id: UUID, account_id: UUID) -> ShopperDiscoveryResponse:
        """Build shopper starters only from the manager's active tenant catalog."""

        del account_id  # Authentication is required; discovery itself is tenant-scoped.
        async with self.database.transaction(tenant_id) as session:
            index = await catalog_index_status(session, tenant_id=tenant_id)
            integration = await active_catalog_integration(session, tenant_id=tenant_id)
            records = (
                await catalog_records(session, tenant_id=tenant_id, integration_id=integration.id)
                if integration is not None
                else []
            )

        suggestions: list[ShopperDiscoverySuggestion] = []
        storefront_name = None
        if self.database.settings.runtime_profile != "legacy_demo":
            from open_commerce.persistence.models.identity import Tenant

            async with self.database.transaction(tenant_id) as session:
                storefront_name = await session.scalar(
                    select(Tenant.display_name).where(Tenant.id == tenant_id)
                )
        seen_categories: set[str] = set()
        for product, variants, inventory in records:
            if not variants or not any(
                variant.available and inventory.get(variant.id, 1) > 0 for variant in variants
            ):
                continue
            category = product.category_path[0] if product.category_path else "Catalog"
            category_key = category.casefold()
            if category_key in seen_categories:
                continue
            seen_categories.add(category_key)
            suggestions.append(
                ShopperDiscoverySuggestion(
                    label=f"Explore {category}",
                    query=f"Show me popular {category.lower()} products like {product.title}",
                    category=category,
                    image_url=product.primary_image_url,
                )
            )
            if len(suggestions) == 6:
                break
        return ShopperDiscoveryResponse(
            conversation_mode="basic" if self.agent.provider is None else "model_configured",
            catalog_status="ready" if integration is not None else index.status,
            catalog_name=(
                storefront_name
                or str(integration.non_secret_config.get("filename") or integration.display_name)
                if integration is not None
                else index.filename
            ),
            product_count=len(records),
            suggestions=suggestions,
        )

    async def delete_memory(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        memory_id: UUID,
        idempotency_key: str,
    ) -> ShopperMemoryDeleteResponse:
        request = {"memory_id": str(memory_id), "account_id": str(account_id)}
        scope = f"shopper:memory:delete:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return ShopperMemoryDeleteResponse.model_validate(cached)
            await ShopperRepository(session, tenant_id).delete_memory(
                account_id=account_id, memory_id=memory_id
            )
            response = ShopperMemoryDeleteResponse(memory_id=memory_id, deleted=True)
            receipts.remember(
                scope=scope,
                key=idempotency_key,
                request=request,
                response=response,
            )
            return response

    async def chat(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: ShopperChatRequest,
        idempotency_key: str,
    ) -> ShopperChatResponse:
        if request.expected_account_id is not None and request.expected_account_id != account_id:
            raise ShopperAuthenticationError(
                "Your shopping account changed. Check your session before retrying."
            )

        from open_commerce.stores.usage import model_scope

        with model_scope(self.database, tenant_id, account_id):
            return await self._chat_scoped(
                tenant_id=tenant_id,
                account_id=account_id,
                request=request,
                idempotency_key=idempotency_key,
            )

    async def _chat_scoped(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: ShopperChatRequest,
        idempotency_key: str,
    ) -> ShopperChatResponse:
        if contains_direct_pii_or_secret(request.content):
            raise ShopperUnsafeInputError(
                "Remove contact details, addresses, credentials, or secrets before chatting"
            )
        scope = f"shopper:chat:{account_id}"
        start_scope = f"shopper:chat:start:{account_id}"
        async with self.database.transaction(tenant_id, write=True) as session:
            account_record = await ShopperAccounts(self.database).account(
                session, tenant_id, account_id, account_version=request._account_version
            )
            account_version = account_record.version
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return await self._current_chat_memory(
                    session, tenant_id, account_id, ShopperChatResponse.model_validate(cached)
                )
            repo = ShopperRepository(session, tenant_id)
            started = await receipts.replay(scope=start_scope, key=idempotency_key, request=request)
            if started is not None:
                user_message = ShopperMessage.model_validate(started)
                conversation_id = user_message.conversation_id
            else:
                conversation_id = request.conversation_id or uuid4()
                now = utc_now()
                if request.conversation_id is None:
                    await repo.create_conversation(
                        conversation_id=conversation_id,
                        account_id=account_id,
                        title=_conversation_title(request.content),
                        now=now,
                    )
                else:
                    await repo.get_conversation(
                        account_id=account_id, conversation_id=conversation_id
                    )
                user_message = ShopperMessage(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role="user",
                    content=request.content,
                    created_at=now,
                )
                await repo.add_message(account_id=account_id, message=user_message)
                receipts.remember(
                    scope=start_scope, key=idempotency_key, request=request, response=user_message
                )
            history = [
                item
                for item in await repo.list_messages(
                    account_id=account_id, conversation_id=conversation_id, limit=40
                )
                if item.created_at < user_message.created_at
            ]
            memories = await repo.list_memories(account_id=account_id)
            index = await catalog_index_status(session, tenant_id=tenant_id)
            memory_enabled = account_record.memory_enabled
            temporary_memory = account_record.is_guest

        source: Literal["uploaded_catalog", "simulator_fallback"] = (
            "uploaded_catalog"
            if index.serving_catalog_id is not None or index.status == "ready"
            else "simulator_fallback"
        )
        memory_tool = ShopperMemoryTool(
            self.database,
            tenant_id=tenant_id,
            account_id=account_id,
            current_message=user_message,
            history=history,
        )
        activity = ActivityService(self.database)
        activity_tools = ActivityTools(
            activity,
            tenant_id=tenant_id,
            account_id=account_id,
            turn_key=str(user_message.id),
            account_version=account_version,
        )
        event_number = 0

        async def record_activity(event: ActivityEventInput) -> None:
            nonlocal event_number
            event_number += 1
            await activity.record_best_effort(
                tenant_id=tenant_id,
                account_id=account_id,
                event=event,
                key=f"shopper-tool:{user_message.id}:{event_number}",
                account_version=account_version,
            )

        async def save_memory(arguments: SaveShoppingMemoryInput) -> ShopperMemory:
            started = monotonic()
            try:
                memory = await memory_tool.save(arguments)
            except ShopperMemoryToolError:
                await record_activity(
                    ActivityEventInput(
                        kind=ActivityKind.MEMORY_SAVE,
                        status="error",
                        duration_ms=min(3600000, int((monotonic() - started) * 1000)),
                    )
                )
                raise
            await record_activity(
                ActivityEventInput(
                    kind=ActivityKind.MEMORY_SAVE,
                    status="ok",
                    duration_ms=min(3600000, int((monotonic() - started) * 1000)),
                )
            )
            return memory

        # Only the offline demo uses the legacy explicit-phrase fallback. Hosted intent is
        # selected by the model through the tool, never intercepted by this matcher.
        memory_text = (
            explicit_memory(request.content, history[-12:])
            if self.agent.provider is None and memory_enabled
            else None
        )
        if memory_text is not None and contains_direct_pii_or_secret(memory_text):
            memory_text = None
        if memory_text is not None:
            memory_source = next(
                (
                    item
                    for item in [user_message, *reversed(history[-12:])]
                    if item.role == "user" and memory_text in item.content
                ),
                None,
            )
            if memory_source is not None:
                await save_memory(
                    SaveShoppingMemoryInput(
                        source_message_id=memory_source.id, preference=memory_text
                    )
                )
            else:
                memory_text = None
        model_verified = False
        if memory_text is not None and memory_only_message(request.content):
            outcome = ShopperAgentOutcome(
                content=f'Saved your preference: "{memory_text}". '
                + (
                    "It is temporary for this visit. "
                    if temporary_memory
                    else "I will use it in future chats. "
                )
                + "You can remove it from Shopping memory anytime.",
                products=[],
                steps=[],
            )
        else:
            model_verified = False
            try:
                if (
                    self.database.settings.runtime_profile != "legacy_demo"
                    and self.agent.provider is not None
                ):
                    if not await ShopperAccounts(self.database).admit_turn(
                        tenant_id, account_id, idempotency_key
                    ):
                        raise ModelQuotaExceeded(
                            "Your ten guest AI turns are used. "
                            "Browsing and your cart are still available."
                        )
                outcome = await self.agent.respond(
                    tenant_id=tenant_id,
                    content=request.content,
                    history=history,
                    memories=memories,
                    source=source,
                    current_message_id=user_message.id,
                    save_memory=save_memory if memory_enabled else None,
                    memory_scope="disabled"
                    if not memory_enabled
                    else "temporary"
                    if temporary_memory
                    else "persistent",
                    activity_tools=activity_tools,
                    record_activity=record_activity,
                )
                model_verified = self.agent.provider is not None
            except ManagerModelUnavailableError as exc:
                outcome = ShopperAgentOutcome(
                    content=(
                        "The conversation model is unavailable; automatic preference saving did "
                        "not run. Please try again later. "
                        "Browsing and your cart are still available."
                    ),
                    products=[],
                    steps=[
                        ShopperAgentStep(
                            stage="respond",
                            title="Conversation model unavailable",
                            detail="No recommendations were confirmed. Your message was retained.",
                            status="fallback",
                        )
                    ],
                )
                if isinstance(exc, ModelQuotaExceeded):
                    outcome.content = (
                        str(exc) + " Your message was retained; no recommendations were confirmed."
                    )
                    outcome.steps[0].title = "AI allowance reached"
                if activity_tools.configured:
                    outcome.content = (
                        "Your activity rule was saved, but the conversation model could not finish "
                        "its reply. Check Shopping activity for the saved definition and results."
                    )

        now = utc_now()
        saved = list(memory_tool.saved.values())
        assistant_message = ShopperMessage(
            id=uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content=(
                "Basic mode: AI chat is not connected.\n\n" if self.agent.provider is None else ""
            )
            + outcome.content,
            steps=[
                *outcome.steps[:13],
                *(
                    ShopperAgentStep(
                        stage="remember",
                        title="Saved for this visit"
                        if temporary_memory
                        else "Saved to shopping memory",
                        detail=item.content[:300],
                    )
                    for item in saved
                ),
            ],
            products=outcome.products,
            created_at=now + timedelta(microseconds=1),
        )
        async with self.database.transaction(tenant_id, write=True) as session:
            await ShopperAccounts(self.database).account(
                session, tenant_id, account_id, account_version=account_version
            )
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if cached is not None:
                return await self._current_chat_memory(
                    session, tenant_id, account_id, ShopperChatResponse.model_validate(cached)
                )
            repo = ShopperRepository(session, tenant_id)
            conversation = await repo.touch_conversation(
                account_id=account_id, conversation_id=conversation_id, now=now
            )
            if self.database.settings.runtime_profile != "legacy_demo":
                from open_commerce.catalog.scope import current_catalog
                from open_commerce.persistence.models.store_setup import StoreSetupRecord

                await ShopperAccounts(self.database).account(session, tenant_id, account_id)
                setup = await session.scalar(
                    select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == tenant_id)
                )
                catalog_scope = current_catalog.get()
                if setup is not None and catalog_scope is not None and catalog_scope.preview:
                    facts = dict(setup.readiness)
                    if any(s.stage == "search" and s.status == "completed" for s in outcome.steps):
                        facts["tested_catalog_id"] = str(catalog_scope.catalog_id)
                        facts["search_tested"] = True
                    if model_verified:
                        facts["ai_verified"] = True
                        facts["ai_checked_at"] = now.isoformat()
                    setup.readiness = facts
            response = ShopperChatResponse(
                conversation=conversation,
                user_message=user_message,
                assistant_message=assistant_message,
                memory_created=saved[0] if saved else None,
                memories_saved=saved,
            )
            response = await self._current_chat_memory(session, tenant_id, account_id, response)
            await repo.add_message(account_id=account_id, message=response.assistant_message)
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
        return response

    async def _current_chat_memory(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        account_id: UUID,
        response: ShopperChatResponse,
    ) -> ShopperChatResponse:
        account = await ShopperAccounts(self.database).account(session, tenant_id, account_id)
        previous = response.memories_saved or (
            [response.memory_created] if response.memory_created else []
        )
        repo = ShopperRepository(session, tenant_id)
        current = []
        if account.memory_enabled:
            for item in previous:
                stored = await repo.get_memory(account_id=account_id, memory_id=item.id)
                if stored is not None:
                    current.append(stored)
        if current == previous:
            return response
        # A receipt proves a past save, not permission to restore it after deletion
        # or opt-out. Avoid returning the now-stale model acknowledgement as success.
        message = response.assistant_message.model_copy(
            update={
                "content": "Your shopping memory changed since this turn started. "
                "Deleted or disabled preferences have not been restored. "
                "Send a new message to continue with your current memory settings.",
                "products": [],
                "steps": [
                    step for step in response.assistant_message.steps if step.stage != "remember"
                ],
            }
        )
        return response.model_copy(
            update={
                "assistant_message": message,
                "memory_created": current[0] if current else None,
                "memories_saved": current,
            }
        )

    async def _create_session(
        self,
        repo: ShopperRepository,
        *,
        account: ShopperAccount,
        raw_token: str,
        now: datetime,
    ) -> None:
        await repo.create_session(
            session_id=uuid4(),
            account_id=account.id,
            token_hash=session_token_hash(raw_token),
            expires_at=now + timedelta(days=self.database.settings.shopper_session_days),
            now=now,
        )


def _conversation_title(content: str) -> str:
    words = " ".join(content.split()).split(" ")[:8]
    title = " ".join(words).strip()
    return (title or "Shopping conversation")[:120]
