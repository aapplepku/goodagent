"""Persisted deletion versions fence personal work, without a public version contract."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.api import activity as activity_api
from open_commerce.api import shopper as shopper_api
from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.errors import register_exception_handlers
from open_commerce.catalog.browse_models import CatalogBrowseResponse
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.commerce.models import Cart, CartItemAddRequest
from open_commerce.config import Settings
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.manager_agent.model_provider import ManagerToolCall
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.shopper_activity import ActivityRuleRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent import service as shopper_service
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAgentRuntime,
    ShopperChatRequest,
    ShopperConversation,
)
from open_commerce.stores import shoppers
from open_commerce.stores.models import StoreError
from open_commerce.stores.shoppers import ShopperAccounts
from open_commerce.telemetry.activity import ActivityRuleError, ActivityService
from open_commerce.telemetry.activity_models import (
    ActivityCheck,
    ActivityEventInput,
    ActivityKind,
    ActivityRule,
    ActivityRuleInput,
)
from open_commerce.telemetry.activity_tools import ActivityTools

TENANT = UUID(int=101)
ACCOUNT = UUID(int=201)
VERSION = 3
DEFINITION = ActivityRuleInput(name="Synthetic monitor", threshold=2)
EVENT = ActivityEventInput(kind=ActivityKind.SEARCH, status="ok", duration_ms=1)


@pytest.fixture
def row() -> ShopperAccountRecord:
    return ShopperAccountRecord(
        id=ACCOUNT,
        tenant_id=TENANT,
        username="synthetic",
        display_name="Synthetic",
        password_hash="disabled",
        status="active",
        is_guest=True,
        memory_enabled=True,
        expires_at=None,
        preview_catalog_id=None,
        created_at=utc_now(),
        updated_at=utc_now(),
        version=VERSION,
    )


@pytest.fixture
def database(row: ShopperAccountRecord) -> MagicMock:
    db = create_autospec(RuntimeDatabase, instance=True)
    db.settings = Settings(_env_file=None, runtime_profile="legacy_demo")
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.return_value = row
    session.scalars.return_value = []
    db.transaction.return_value.__aenter__.return_value = session
    return cast(MagicMock, db)


def session_for(database: MagicMock) -> MagicMock:
    return cast(MagicMock, database.transaction.return_value.__aenter__.return_value)


def cached_rule() -> ActivityRule:
    return ActivityRule(
        id=uuid4(),
        definition=DEFINITION,
        check=ActivityCheck(checked_at=utc_now(), state="pending"),
    )


def test_versions_are_private_server_snapshots(row: ShopperAccountRecord) -> None:
    account = ShopperRepository._account(row)
    assert account._data_version == VERSION
    payload = ShopperChatRequest(content="Find a synthetic gift")
    before = canonical_hash(payload)
    payload._account_version = VERSION
    assert canonical_hash(payload) == before
    for model, value, private in (
        (ShopperAccount, account, "_data_version"),
        (ShopperChatRequest, payload, "_account_version"),
    ):
        assert private not in model.model_json_schema()["properties"]
        assert private not in value.model_dump()
        with pytest.raises(ValidationError):
            model.model_validate({**value.model_dump(), private: VERSION})


@pytest.mark.parametrize("operation", ["configure", "record"])
@pytest.mark.parametrize("reason", ["stale", "expired", "missing", "disabled", "tenant", "account"])
async def test_personal_guard_precedes_receipts_and_writes(
    database: MagicMock,
    row: ShopperAccountRecord,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    reason: str,
) -> None:
    session = session_for(database)
    version: int | None = VERSION
    tenant, account = TENANT, ACCOUNT
    if reason == "stale":
        row.version += 1
    elif reason == "expired":
        row.expires_at = utc_now() - timedelta(seconds=1)
        version = None
    else:
        session.scalar.return_value = None
        version = None
        if reason == "tenant":
            tenant = uuid4()
        if reason == "account":
            account = uuid4()
    replay = AsyncMock(return_value=cached_rule().model_dump(mode="json"))
    monkeypatch.setattr(RequestRepository, "replay", replay)
    service = ActivityService(database)
    with pytest.raises(ActivityRuleError) as error:
        if operation == "configure":
            await service.configure(
                tenant_id=tenant,
                account_id=account,
                definition=DEFINITION,
                key="old-receipt",
                account_version=version,
            )
        else:
            await service.record(
                tenant_id=tenant,
                account_id=account,
                event=EVENT,
                key="old-event",
                account_version=version,
            )
    assert str(account) not in str(error.value)
    database.transaction.assert_called_once_with(tenant, write=True)
    query = session.scalar.call_args.args[0]
    assert {tenant, account, "active"} <= set(query.compile().params.values())
    replay.assert_not_called()
    session.add.assert_not_called()
    session.execute.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.parametrize("version", [None, VERSION])
async def test_fresh_personal_config_and_events_keep_existing_receipt_payloads(
    database: MagicMock,
    row: ShopperAccountRecord,
    monkeypatch: pytest.MonkeyPatch,
    version: int | None,
) -> None:
    session = session_for(database)
    session.scalar.side_effect = [row, None, 0, row, False]
    replay = AsyncMock(return_value=None)
    remember = MagicMock()
    monkeypatch.setattr(RequestRepository, "replay", replay)
    monkeypatch.setattr(RequestRepository, "remember", remember)
    service = ActivityService(database)
    result = await service.configure(
        tenant_id=TENANT,
        account_id=ACCOUNT,
        definition=DEFINITION,
        key="new-receipt",
        account_version=version,
    )
    assert result.definition == DEFINITION
    remember.assert_called_once_with(
        scope=f"activity:configure:{ACCOUNT}",
        key="new-receipt",
        request=DEFINITION,
        response=result,
    )
    await service.record(
        tenant_id=TENANT, account_id=ACCOUNT, event=EVENT, key="new-event", account_version=version
    )
    values = session.execute.call_args.args[0].compile().params
    assert values["tenant_id"] == TENANT and values["account_id"] == ACCOUNT
    assert "account_version" not in values


@pytest.mark.parametrize("present", [True, False])
async def test_personal_cached_rule_must_still_exist_in_the_same_scope(
    database: MagicMock, row: ShopperAccountRecord, monkeypatch: pytest.MonkeyPatch, present: bool
) -> None:
    session = session_for(database)
    cached = cached_rule()
    session.scalar.side_effect = [row, cached.id if present else None]
    monkeypatch.setattr(
        RequestRepository, "replay", AsyncMock(return_value=cached.model_dump(mode="json"))
    )
    service = ActivityService(database)
    if present:
        assert (
            await service.configure(
                tenant_id=TENANT,
                account_id=ACCOUNT,
                definition=DEFINITION,
                key="receipt",
                account_version=VERSION,
            )
            == cached
        )
    else:
        with pytest.raises(ActivityRuleError, match="no longer available"):
            await service.configure(
                tenant_id=TENANT,
                account_id=ACCOUNT,
                definition=DEFINITION,
                key="receipt",
                account_version=VERSION,
            )
    query = session.scalar.call_args.args[0]
    assert {TENANT, ACCOUNT, str(ACCOUNT), cached.id} <= set(query.compile().params.values())
    session.add.assert_not_called()
    session.execute.assert_not_called()


async def test_store_wide_replay_has_no_shopper_fence(
    database: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    cached = cached_rule()
    monkeypatch.setattr(
        RequestRepository, "replay", AsyncMock(return_value=cached.model_dump(mode="json"))
    )
    result = await ActivityService(database).configure(
        tenant_id=TENANT, account_id=None, definition=DEFINITION, key="store", account_version=0
    )
    assert result == cached
    session_for(database).scalar.assert_not_called()


async def test_delayed_tool_is_not_verified_and_best_effort_event_is_dropped(
    database: MagicMock, row: ShopperAccountRecord
) -> None:
    tools = ActivityTools(
        ActivityService(database),
        tenant_id=TENANT,
        account_id=ACCOUNT,
        turn_key="old-turn",
        account_version=VERSION,
    )
    row.version += 1
    output = await tools.execute(
        ManagerToolCall(
            name="configure_activity_monitor", call_id="configure", arguments={"name": "Synthetic"}
        )
    )
    assert output["error"] == "ACTIVITY_RULE_BLOCKED"
    assert "verified" not in output and not tools.configured
    await tools.service.record_best_effort(
        tenant_id=TENANT, account_id=ACCOUNT, event=EVENT, key="late", account_version=VERSION
    )
    session_for(database).execute.assert_not_called()
    session_for(database).add.assert_not_called()


@pytest.mark.parametrize("expired", [False, True])
async def test_deletion_increments_version_and_erases_only_personal_activity_receipts(
    database: MagicMock, monkeypatch: pytest.MonkeyPatch, expired: bool
) -> None:
    commerce = MagicMock()
    commerce.open_cart = AsyncMock(return_value=None)
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *args: commerce)
    await ShopperAccounts(database).delete_data(TENANT, ACCOUNT, expired=expired)
    database.transaction.assert_called_once_with(TENANT, write=True)
    statements = [call.args[0] for call in session_for(database).execute.call_args_list]
    first = statements[0].compile()
    assert "version=(shopper_accounts.version +" in str(first)
    assert {TENANT, ACCOUNT, 1} <= set(first.params.values())
    receipt_deletes = [
        stmt.compile() for stmt in statements if "DELETE FROM idempotency_records" in str(stmt)
    ]
    assert len(receipt_deletes) == 2
    assert {TENANT, f"activity:configure:{ACCOUNT}"} <= set(receipt_deletes[0].params.values())
    assert f"shopper:preferences:{ACCOUNT}" in receipt_deletes[1].params.values()
    assert "!=" in str(receipt_deletes[1])
    assert not any("guest:turn:" in str(stmt) for stmt in statements)
    assert not any("DELETE FROM commerce" in str(stmt) for stmt in statements)


async def test_guest_merge_retires_version_and_removes_guest_monitor_receipts(
    database: MagicMock, row: ShopperAccountRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    commerce = MagicMock()
    commerce.open_cart = AsyncMock(return_value=None)
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *args: commerce)
    target = ShopperAccountRecord(id=uuid4(), version=9)
    async with database.transaction(TENANT, write=True) as session:
        await ShopperAccounts(database).merge_records(session, TENANT, row, target, "keep_account")
    assert row.status == "disabled" and row.version == VERSION + 1
    assert target.version == 9
    statements = [call.args[0].compile() for call in session.execute.call_args_list]
    receipts = [stmt for stmt in statements if "DELETE FROM idempotency_records" in str(stmt)]
    assert len(receipts) == 2
    assert {TENANT, f"activity:configure:{ACCOUNT}"} <= set(receipts[0].params.values())
    assert str(target.id) not in receipts[0].params.values()
    assert receipts[1].params == {
        "tenant_id_1": TENANT,
        "scope_1": [
            f"shopper:chat:{ACCOUNT}",
            f"shopper:chat:start:{ACCOUNT}",
            f"shopper:memory:save:{ACCOUNT}",
            f"shopper:memory:delete:{ACCOUNT}",
        ],
    }
    assert "scope IN" in str(receipts[1]) and "LIKE" not in str(receipts[1])


async def test_worker_does_not_write_checks_for_inactive_personal_rules(
    database: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = session_for(database)
    personal = ActivityRuleRecord(id=uuid4(), account_id=ACCOUNT)
    store = ActivityRuleRecord(id=uuid4(), account_id=None)
    session.scalars.return_value = [personal, store]
    session.scalar.return_value = None
    service = ActivityService(database)
    evaluate = AsyncMock()
    monkeypatch.setattr(service, "_evaluate", evaluate)
    assert await service.evaluate_due(TENANT) == 1
    assert evaluate.await_args is not None
    assert evaluate.await_args.args[2] is store


@pytest.mark.parametrize("change", ["deleted", "expired", "merged"])
async def test_started_chat_carries_fence_to_tools_callbacks_and_finalization(
    database: MagicMock, row: ShopperAccountRecord, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    session = session_for(database)
    session.scalar.side_effect = lambda query: row if row.status == "active" else None
    repo = create_autospec(ShopperRepository, instance=True)
    repo.list_messages.return_value = []
    repo.list_memories.return_value = []
    monkeypatch.setattr(shopper_service, "ShopperRepository", lambda *args: repo)
    monkeypatch.setattr(
        shopper_service,
        "catalog_index_status",
        AsyncMock(return_value=CatalogIndexStatus(status="ready")),
    )
    replay = AsyncMock(return_value=None)
    remember = MagicMock()
    monkeypatch.setattr(RequestRepository, "replay", replay)
    monkeypatch.setattr(RequestRepository, "remember", remember)
    service = shopper_service.DurableShopperAgentService(database, search_service=SearchService())
    outputs: list[dict[str, Any]] = []

    async def delayed(**kwargs: Any) -> ShopperAgentOutcome:
        tools = kwargs["activity_tools"]
        assert tools.account_version == VERSION
        if change == "deleted":
            row.version += 1
        elif change == "expired":
            row.expires_at = utc_now() - timedelta(seconds=1)
        else:
            row.status = "disabled"
            row.version += 1
        outputs.append(
            await tools.execute(
                ManagerToolCall(
                    name="configure_activity_monitor",
                    call_id="late",
                    arguments={"name": "Synthetic"},
                )
            )
        )
        await kwargs["record_activity"](EVENT)
        return ShopperAgentOutcome(content="Synthetic", products=[], steps=[])

    monkeypatch.setattr(service.agent, "respond", delayed)
    with pytest.raises(StoreError) as error:
        await service.chat(
            tenant_id=TENANT,
            account_id=ACCOUNT,
            request=ShopperChatRequest(content="Create a synthetic monitor"),
            idempotency_key="turn",
        )
    assert error.value.status_code == 401
    assert outputs[0]["error"] == "ACTIVITY_RULE_BLOCKED"
    assert "verified" not in outputs[0]
    assert replay.await_count == 2  # Only the pre-deletion completed/start chat receipts.
    assert remember.call_count == 1
    repo.touch_conversation.assert_not_called()
    assert repo.add_message.await_count == 1  # The original user message precedes deletion.
    session.add.assert_not_called()
    session.execute.assert_not_called()


async def test_stale_authenticated_chat_cannot_replay_or_start_a_turn(
    database: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    replay = AsyncMock()
    monkeypatch.setattr(RequestRepository, "replay", replay)
    service = shopper_service.DurableShopperAgentService(database, search_service=SearchService())
    respond = AsyncMock()
    monkeypatch.setattr(service.agent, "respond", respond)
    payload = ShopperChatRequest(content="Find a synthetic gift")
    payload._account_version = VERSION - 1
    with pytest.raises(StoreError, match="shopping data changed"):
        await service.chat(
            tenant_id=TENANT, account_id=ACCOUNT, request=payload, idempotency_key="old"
        )
    replay.assert_not_called()
    respond.assert_not_called()
    session_for(database).add.assert_not_called()


async def test_fresh_chat_after_deletion_still_completes(
    database: MagicMock, row: ShopperAccountRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    row.version += 1
    repo = create_autospec(ShopperRepository, instance=True)
    repo.list_messages.return_value = []
    repo.list_memories.return_value = []
    repo.touch_conversation.return_value = ShopperConversation(
        id=uuid4(), title="Synthetic", created_at=utc_now(), updated_at=utc_now(), version=1
    )
    monkeypatch.setattr(shopper_service, "ShopperRepository", lambda *args: repo)
    monkeypatch.setattr(
        shopper_service,
        "catalog_index_status",
        AsyncMock(return_value=CatalogIndexStatus(status="ready")),
    )
    monkeypatch.setattr(RequestRepository, "replay", AsyncMock(return_value=None))
    monkeypatch.setattr(RequestRepository, "remember", MagicMock())
    service = shopper_service.DurableShopperAgentService(database, search_service=SearchService())
    respond = AsyncMock(
        return_value=ShopperAgentOutcome(content="Synthetic", products=[], steps=[])
    )
    monkeypatch.setattr(service.agent, "respond", respond)
    result = await service.chat(
        tenant_id=TENANT,
        account_id=ACCOUNT,
        request=ShopperChatRequest(content="Find a synthetic gift"),
        idempotency_key="fresh",
    )
    assert "Synthetic" in result.assistant_message.content
    assert respond.await_args is not None
    assert respond.await_args.kwargs["activity_tools"].account_version == VERSION + 1
    assert repo.add_message.await_count == 2


async def test_routes_copy_only_the_authenticated_internal_snapshot(
    database: MagicMock, row: ShopperAccountRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = ShopperRepository._account(row)
    app = FastAPI()
    app.state.settings = database.settings
    app.state.database = database
    request = Request({"type": "http", "app": app, "headers": []})
    context = RequestContext(tenant_id=TENANT, actor_id="shopper", roles=set())
    service = create_autospec(ShopperAgentRuntime, instance=True)
    service.authenticate.return_value = account
    assert (
        await shopper_api.get_current_shopper(request, context, service, "synthetic-token")
        is account
    )
    assert request.state.shopper_activity_version == VERSION
    payload = ShopperChatRequest(content="Synthetic gift")
    payload._account_version = 99
    await shopper_api.chat_with_shopper_agent(payload, "turn", context, account, service)
    assert service.chat.await_args.kwargs["request"]._account_version == VERSION
    activity = create_autospec(ActivityService, instance=True)
    await activity_api.shopper_activity_rule(DEFINITION, context, account, "rule", activity)
    assert activity.configure.await_args.kwargs["account_version"] == VERSION
    browser = SimpleNamespace(browse=AsyncMock(return_value=SimpleNamespace(items=[object()])))
    monkeypatch.setattr(shopper_api, "CatalogBrowseService", lambda *args: browser)
    record = AsyncMock()
    monkeypatch.setattr(ActivityService, "record", record)
    await shopper_api.record_product_selection(
        CartItemAddRequest(product_id="synthetic"), request, "selection", context, account
    )
    assert record.await_args is not None
    assert record.await_args.kwargs["account_version"] == VERSION
    record.side_effect = ActivityRuleError("Shopping data changed")
    with pytest.raises(StoreError) as error:
        await shopper_api.record_product_selection(
            CartItemAddRequest(product_id="synthetic"), request, "selection", context, account
        )
    assert error.value.status_code == 401


@pytest.mark.parametrize("deleted", [False, True])
@pytest.mark.parametrize("operation", ["catalog", "cart"])
async def test_real_route_finally_keeps_authenticated_version_after_delayed_work(
    database: MagicMock, row: ShopperAccountRecord, deleted: bool, operation: str
) -> None:
    session = session_for(database)
    session.scalar.side_effect = lambda query: row if "shopper_accounts" in str(query) else False
    service = create_autospec(ShopperAgentRuntime, instance=True)
    service.database = database
    service.authenticate.return_value = ShopperRepository._account(row)
    app = FastAPI()
    app.state.settings = database.settings
    app.state.database = database
    app.state.shopper_agent_service = service
    app.state.commerce_service = MagicMock()
    context = RequestContext(tenant_id=TENANT, actor_id="shopper", roles=set())

    async def context_for_request(request: Request) -> RequestContext:
        request.state.request_id = "deletion-fence-test"
        return context

    app.dependency_overrides[get_request_context] = context_for_request

    async def work(**kwargs: Any) -> Any:
        if deleted:
            row.version += 1
        return (
            Cart()
            if operation == "cart"
            else CatalogBrowseResponse(
                catalog=None,
                indexing=CatalogIndexStatus(),
                categories=[],
                items=[],
                total=0,
                offset=0,
                limit=24,
            )
        )

    app.state.commerce_service.add_item = AsyncMock(side_effect=work)
    app.dependency_overrides[get_catalog_browser] = lambda: SimpleNamespace(browse=work)
    app.include_router(shopper_api.router)
    register_exception_handlers(app)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={shopper_api.SESSION_COOKIE: "synthetic-token"},
    ) as client:
        result = await client.request(
            "POST" if operation == "cart" else "GET",
            "/v1/shopper/cart/items" if operation == "cart" else "/v1/shopper/catalog",
            json={"product_id": "synthetic"} if operation == "cart" else None,
            headers={"Idempotency-Key": "original"},
        )
    assert result.status_code == 200, result.text
    assert session.execute.await_count == (0 if deleted else 2 if operation == "cart" else 1)
