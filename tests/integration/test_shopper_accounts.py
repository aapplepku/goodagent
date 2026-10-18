"""Real PostgreSQL coverage for shopper accounts, sessions, chat, and memory."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import canonical_hash
from open_commerce.persistence.models.shopper import (
    ShopperAccountRecord,
    ShopperSessionRecord,
)
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.requests import IdempotencyConflictError
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.errors import (
    ShopperAuthenticationError,
    ShopperConversationNotFoundError,
    ShopperMemoryNotFoundError,
)
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome
from open_commerce.shopper_agent.models import (
    ShopperChatRequest,
    ShopperLoginRequest,
    ShopperRegisterRequest,
)
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.stores.shoppers import ShopperAccounts

pytestmark = pytest.mark.integration


async def test_chat_identity_precondition_rejects_other_accounts_and_replays_legacy_receipts(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableShopperAgentService(database, search_service=SearchService())
        account_ids: list[UUID] = []
        for username in ("first-shopper", "second-shopper"):
            registered, token = await service.register(
                tenant_id=tenant_id,
                request=ShopperRegisterRequest(
                    username=username,
                    display_name=username,
                    password="synthetic-precondition-password",
                ),
            )
            authenticated = await service.authenticate(tenant_id=tenant_id, raw_token=token)
            assert authenticated == registered.account
            account_ids.append(authenticated.id)
        first_id, second_id = account_ids
        legacy_payload = {"content": "Find waterproof boots", "conversation_id": None}
        outcome = ShopperAgentOutcome(content="What size do you need?", products=[], steps=[])
        with patch.object(service.agent, "respond", return_value=outcome) as agent:
            first = await service.chat(
                tenant_id=tenant_id,
                account_id=first_id,
                request=ShopperChatRequest.model_validate(legacy_payload),
                idempotency_key="legacy-chat",
            )
            agent.assert_awaited_once()
        history = await service.get_conversation(
            tenant_id=tenant_id, account_id=first_id, conversation_id=first.conversation.id
        )
        receipt_query = (
            select(
                IdempotencyRecord.scope,
                IdempotencyRecord.key,
                IdempotencyRecord.fingerprint,
                IdempotencyRecord.response,
            )
            .where(IdempotencyRecord.tenant_id == tenant_id)
            .order_by(IdempotencyRecord.scope, IdempotencyRecord.key)
        )
        async with database.transaction(tenant_id) as session:
            receipts_before = (await session.execute(receipt_query)).all()
        assert {row.scope for row in receipts_before} == {
            f"shopper:chat:{first_id}",
            f"shopper:chat:start:{first_id}",
        }
        assert all(row.fingerprint == canonical_hash(legacy_payload) for row in receipts_before)

        with (
            patch.object(database, "transaction", wraps=database.transaction) as transaction,
            patch.object(service.agent, "respond") as agent,
        ):
            # Reject both a fresh write under another account and an existing receipt replay.
            for account_id, expected_id in ((second_id, first_id), (first_id, second_id)):
                for conversation_id in (None, first.conversation.id):
                    with pytest.raises(ShopperAuthenticationError) as error:
                        await service.chat(
                            tenant_id=tenant_id,
                            account_id=account_id,
                            request=ShopperChatRequest(
                                content=str(legacy_payload["content"]),
                                conversation_id=conversation_id,
                                expected_account_id=expected_id,
                            ),
                            idempotency_key="legacy-chat",
                        )
                    assert str(account_id) not in str(error.value)
                    assert str(expected_id) not in str(error.value)
            transaction.assert_not_called()
            agent.assert_not_called()

        with patch.object(service.agent, "respond") as agent:
            replay = await service.chat(
                tenant_id=tenant_id,
                account_id=first_id,
                request=ShopperChatRequest(
                    content=str(legacy_payload["content"]), expected_account_id=first_id
                ),
                idempotency_key="legacy-chat",
            )
            assert replay == first
            agent.assert_not_called()
        assert (
            await service.get_conversation(
                tenant_id=tenant_id, account_id=first_id, conversation_id=first.conversation.id
            )
        ) == history
        assert (
            await service.list_conversations(tenant_id=tenant_id, account_id=first_id)
        ).items == [first.conversation]
        assert not (
            await service.list_conversations(tenant_id=tenant_id, account_id=second_id)
        ).items
        for account_id in account_ids:
            assert not (
                await service.list_memories(tenant_id=tenant_id, account_id=account_id)
            ).items
        async with database.transaction(tenant_id) as session:
            assert (await session.execute(receipt_query)).all() == receipts_before
    finally:
        await database.close()


async def test_memory_setting_retries_cannot_undo_later_opt_out(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, other_tenant = uuid4(), uuid4()
    try:
        service = DurableShopperAgentService(database, search_service=SearchService())
        accounts = ShopperAccounts(database)
        ids: list[UUID] = []
        for owner in (tenant, tenant, other_tenant):
            await database.initialize_tenant(owner)
            auth, _ = await service.register(
                tenant_id=owner,
                request=ShopperRegisterRequest(
                    username=f"shopper-{len(ids)}",
                    display_name="Fixture",
                    password="synthetic-setting-password",
                ),
            )
            ids.append(auth.account.id)
        first = await accounts.preferences(tenant, ids[0], True, idempotency_key="lost-on")
        assert first.memory_enabled
        assert not (
            await accounts.preferences(tenant, ids[0], False, idempotency_key="later-off")
        ).memory_enabled
        # A delayed original request or retry returns current state without another write.
        for _ in range(2):
            assert not (
                await accounts.preferences(tenant, ids[0], True, idempotency_key="lost-on")
            ).memory_enabled
        with pytest.raises(IdempotencyConflictError):
            await accounts.preferences(tenant, ids[0], False, idempotency_key="lost-on")
        # Shopping-data deletion must not reopen the old settings operation.
        await accounts.delete_data(tenant, ids[0])
        assert not (
            await accounts.preferences(tenant, ids[0], True, idempotency_key="lost-on")
        ).memory_enabled
        async with database.transaction(tenant) as session:
            receipts = list(
                await session.scalars(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.tenant_id == tenant,
                        IdempotencyRecord.scope == f"shopper:preferences:{ids[0]}",
                    )
                )
            )
        assert len(receipts) == 2
        assert all(set(item.response) == {"enabled"} for item in receipts)
        assert not (
            await accounts.preferences(tenant, ids[1], False, idempotency_key="lost-on")
        ).memory_enabled
        assert not (
            await accounts.preferences(other_tenant, ids[2], False, idempotency_key="lost-on")
        ).memory_enabled
    finally:
        await database.close()


async def test_shopper_identity_memory_and_conversations_are_durable_and_scoped(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    search = SearchService()
    tenant_id, other_tenant = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        await database.initialize_tenant(other_tenant)
        service = DurableShopperAgentService(database, search_service=search)
        registered, token = await service.register(
            tenant_id=tenant_id,
            request=ShopperRegisterRequest(
                username="alex",
                display_name="Alex",
                password="local-demo-password",
            ),
        )
        other_account, _ = await service.register(
            tenant_id=tenant_id,
            request=ShopperRegisterRequest(
                username="sam",
                display_name="Sam",
                password="another-demo-password",
            ),
        )
        await service.register(
            tenant_id=other_tenant,
            request=ShopperRegisterRequest(
                username="alex",
                display_name="Other Alex",
                password="separate-demo-password",
            ),
        )

        authenticated = await service.authenticate(tenant_id=tenant_id, raw_token=token)
        assert authenticated == registered.account
        with pytest.raises(ShopperAuthenticationError):
            await service.authenticate(tenant_id=other_tenant, raw_token=token)
        with pytest.raises(ShopperAuthenticationError):
            await service.login(
                tenant_id=tenant_id,
                request=ShopperLoginRequest(username="alex", password="wrong"),
            )

        first = await service.chat(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            request=ShopperChatRequest(content="running shoes for wet weather"),
            idempotency_key="shopper-first",
        )
        replay = await service.chat(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            request=ShopperChatRequest(content="running shoes for wet weather"),
            idempotency_key="shopper-first",
        )
        assert replay == first
        assert first.assistant_message.products
        mode_notice = "Basic mode: AI chat is not connected.\n\n"
        assert first.assistant_message.content.startswith(mode_notice)

        remembered = await service.chat(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            request=ShopperChatRequest(
                content="Remember that I prefer unsweetened drinks",
                conversation_id=first.conversation.id,
            ),
            idempotency_key="shopper-memory",
        )
        assert remembered.memory_created is not None
        assert remembered.memory_created.content == "I prefer unsweetened drinks"
        assert remembered.assistant_message.content.startswith(mode_notice)
        restored = await service.get_conversation(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            conversation_id=first.conversation.id,
        )
        assert [message.role for message in restored.messages] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert restored.messages[1].content == first.assistant_message.content
        assert restored.messages[3].content == remembered.assistant_message.content
        assert (
            await service.list_memories(tenant_id=tenant_id, account_id=registered.account.id)
        ).items == [remembered.memory_created]
        with pytest.raises(ShopperMemoryNotFoundError):
            await service.delete_memory(
                tenant_id=tenant_id,
                account_id=other_account.account.id,
                memory_id=remembered.memory_created.id,
                idempotency_key="other-shopper-forget",
            )
        deleted = await service.delete_memory(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            memory_id=remembered.memory_created.id,
            idempotency_key="shopper-forget",
        )
        assert deleted.deleted is True
        replayed_delete = await service.delete_memory(
            tenant_id=tenant_id,
            account_id=registered.account.id,
            memory_id=remembered.memory_created.id,
            idempotency_key="shopper-forget",
        )
        assert replayed_delete == deleted
        assert not (
            await service.list_memories(tenant_id=tenant_id, account_id=registered.account.id)
        ).items
        with pytest.raises(ShopperConversationNotFoundError):
            await service.get_conversation(
                tenant_id=tenant_id,
                account_id=other_account.account.id,
                conversation_id=first.conversation.id,
            )

        async with database.transaction(tenant_id) as session:
            account_row = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant_id,
                    ShopperAccountRecord.id == registered.account.id,
                )
            )
            session_row = await session.scalar(
                select(ShopperSessionRecord).where(
                    ShopperSessionRecord.tenant_id == tenant_id,
                    ShopperSessionRecord.account_id == registered.account.id,
                )
            )
            assert account_row is not None
            assert "local-demo-password" not in account_row.password_hash
            assert session_row is not None and session_row.token_hash != token

        await service.logout(tenant_id=tenant_id, raw_token=token)
        with pytest.raises(ShopperAuthenticationError):
            await service.authenticate(tenant_id=tenant_id, raw_token=token)
    finally:
        await database.close()


async def test_natural_preferences_survive_reload_followups_and_reach_only_the_owner(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableShopperAgentService(database, search_service=SearchService())
        account, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="premium", display_name="Premium", password="local-memory-test"
            ),
        )
        other, _ = await service.register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="other", display_name="Other", password="other-memory-test"
            ),
        )
        request = ShopperChatRequest(content="i like premium expensive stuff, keep that in mind")
        with patch.object(service.agent, "respond") as agent:
            saved = await service.chat(
                tenant_id=tenant,
                account_id=account.account.id,
                request=request,
                idempotency_key="natural-memory",
            )
            agent.assert_not_called()
        assert saved.memory_created
        assert saved.memory_created.content == "i like premium expensive stuff"
        assert any(step.stage == "remember" for step in saved.assistant_message.steps)
        restored_service = DurableShopperAgentService(database, search_service=SearchService())
        replay = await restored_service.chat(
            tenant_id=tenant,
            account_id=account.account.id,
            request=request,
            idempotency_key="natural-memory",
        )
        assert replay == saved
        followup = await restored_service.chat(
            tenant_id=tenant,
            account_id=account.account.id,
            request=ShopperChatRequest(
                conversation_id=saved.conversation.id,
                content="save that preference you should automatic save that",
            ),
            idempotency_key="reference-memory",
        )
        assert followup.memory_created == saved.memory_created
        restored = await restored_service.get_conversation(
            tenant_id=tenant,
            account_id=account.account.id,
            conversation_id=saved.conversation.id,
        )
        assert restored.messages[-1].steps[-1].stage == "remember"
        memories = await restored_service.list_memories(
            tenant_id=tenant, account_id=account.account.id
        )
        assert len(memories.items) == 1
        assert not (
            await service.list_memories(
                tenant_id=tenant,
                account_id=other.account.id,
            )
        ).items
        outcome = ShopperAgentOutcome(
            content="What category are you shopping for?", products=[], steps=[]
        )
        with patch.object(restored_service.agent, "respond", return_value=outcome) as agent:
            await restored_service.chat(
                tenant_id=tenant,
                account_id=account.account.id,
                request=ShopperChatRequest(content="Find me a gift"),
                idempotency_key="recall",
            )
            assert agent.call_args.kwargs["memories"] == memories.items
            mixed = await restored_service.chat(
                tenant_id=tenant,
                account_id=account.account.id,
                request=ShopperChatRequest(content="I prefer blue. Find me a gift"),
                idempotency_key="mixed-memory",
            )
            assert mixed.memory_created and mixed.memory_created.content == "I prefer blue"
            assert mixed.assistant_message.content == (
                "Basic mode: AI chat is not connected.\n\n" + outcome.content
            )
            assert any(step.stage == "remember" for step in mixed.assistant_message.steps)
            optout = await restored_service.chat(
                tenant_id=tenant,
                account_id=account.account.id,
                request=ShopperChatRequest(content="I like green, but do not save this"),
                idempotency_key="no-memory",
            )
            assert optout.memory_created is None
            await restored_service.chat(
                tenant_id=tenant,
                account_id=other.account.id,
                request=ShopperChatRequest(content="Find me a gift"),
                idempotency_key="no-recall",
            )
            assert agent.call_args.kwargs["memories"] == []
    finally:
        await database.close()
