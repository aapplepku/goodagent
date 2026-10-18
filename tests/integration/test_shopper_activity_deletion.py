"""Deletion wins over delayed personal tools and request instrumentation."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.api.main import create_app
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
from open_commerce.persistence.models.shopper_activity import (
    ActivityCheckRecord,
    ActivityRuleRecord,
    ShopperActivityRecord,
)
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome
from open_commerce.shopper_agent.models import ShopperLoginRequest, ShopperRegisterRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.stores.shoppers import ShopperAccounts
from open_commerce.telemetry.activity import ActivityRuleError, ActivityService
from open_commerce.telemetry.activity_models import (
    ActivityEventInput,
    ActivityKind,
    ActivityRuleInput,
)

pytestmark = pytest.mark.integration


class DelayedMonitorProvider:
    """Synthetic model boundary, retaining the real agent loop and tools."""

    provider_name = "test-model"
    model_id = "delayed-personal-monitor"

    def __init__(self, erase: Callable[[], Awaitable[None]]) -> None:
        self.erase = erase
        self.results: list[ManagerToolResult] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        assert "configure_activity_monitor" in {tool.name for tool in tools}
        owner = self

        class Session:
            async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                if not tool_results:
                    await owner.erase()
                    return ManagerModelTurn(
                        tool_calls=[
                            ManagerToolCall(
                                call_id="delayed-monitor",
                                name="configure_activity_monitor",
                                arguments={"name": "Delayed personal monitor", "threshold": 2},
                            )
                        ]
                    )
                owner.results.extend(tool_results)
                return ManagerModelTurn(
                    tool_calls=[
                        ManagerToolCall(
                            call_id="done",
                            name="complete_shopping_turn",
                            arguments={
                                "kind": "blocked" if tool_results[0].is_error else "activity",
                                "message": "The earlier operation was interrupted.",
                                "product_ids": None,
                            },
                        )
                    ]
                )

        return Session()


async def _assert_no_personal_activity(database: RuntimeDatabase, tenant: UUID) -> None:
    async with database.transaction(tenant) as session:
        for model in (ActivityRuleRecord, ActivityCheckRecord, ShopperActivityRecord):
            assert (
                await session.scalar(
                    select(func.count()).select_from(model).where(model.tenant_id == tenant)
                )
                == 0
            )


async def _erase(database: RuntimeDatabase, tenant: UUID, account: UUID, *, expire: bool) -> None:
    accounts = ShopperAccounts(database)
    if expire:
        async with database.transaction(tenant, write=True) as session:
            row = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant, ShopperAccountRecord.id == account
                )
            )
            assert row is not None and row.is_guest
            row.expires_at = utc_now() - timedelta(seconds=1)
        await accounts.cleanup(tenant)
    else:
        await accounts.delete_data(tenant, account)
    await _assert_no_personal_activity(database, tenant)


@pytest.mark.parametrize("expire", [False, True])
async def test_delayed_model_monitor_cannot_repopulate_deleted_data(
    integration_settings: Settings, expire: bool
) -> None:
    tenant = uuid4()
    settings = integration_settings.model_copy(
        update={"runtime_profile": "legacy_demo", "local_tenant_id": tenant}
    )
    database = RuntimeDatabase(settings)
    try:
        await database.initialize_tenant(tenant)
        auth, token = await ShopperAccounts(database).guest(tenant, None)
        assert token is not None

        async def erase() -> None:
            await _erase(database, tenant, auth.account.id, expire=expire)

        provider = DelayedMonitorProvider(erase)
        shopper = DurableShopperAgentService(
            database, search_service=SearchService(), model_provider=provider
        )
        app = create_app(settings=settings, shopper_agent_service=shopper)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                client.cookies.set("open_commerce_shopper_session", token)
                response = await client.post(
                    "/v1/shopper/chat",
                    json={"content": "Please create a personal empty search monitor"},
                    headers={
                        "Idempotency-Key": "delayed-monitor-turn",
                        "X-Shopper-Account-Id": str(auth.account.id),
                    },
                )
                assert response.status_code in {401, 404}
                assert provider.results
                assert provider.results[0].is_error
                assert not provider.results[0].output.get("verified")
                await _assert_no_personal_activity(database, tenant)
        finally:
            await app.state.database.close()
    finally:
        await database.close()


@pytest.mark.parametrize("expire", [False, True])
async def test_delayed_tool_and_route_telemetry_stay_erased(
    integration_settings: Settings, expire: bool
) -> None:
    tenant = uuid4()
    settings = integration_settings.model_copy(
        update={"runtime_profile": "legacy_demo", "local_tenant_id": tenant}
    )
    database = RuntimeDatabase(settings)
    try:
        await database.initialize_tenant(tenant)
        auth, token = await ShopperAccounts(database).guest(tenant, None)
        assert token is not None
        shopper = DurableShopperAgentService(database, search_service=SearchService())
        app = create_app(settings=settings, shopper_agent_service=shopper)

        async def delayed_response(**kwargs: object) -> ShopperAgentOutcome:
            await _erase(database, tenant, auth.account.id, expire=expire)
            record = cast(
                Callable[[ActivityEventInput], Awaitable[None]], kwargs["record_activity"]
            )
            await record(
                ActivityEventInput(
                    kind=ActivityKind.SEARCH, status="ok", duration_ms=1, result_count=0
                )
            )
            return ShopperAgentOutcome(content="Fixture finished", products=[], steps=[])

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                client.cookies.set("open_commerce_shopper_session", token)
                with patch.object(shopper.agent, "respond", side_effect=delayed_response):
                    response = await client.post(
                        "/v1/shopper/chat",
                        json={"content": "Find a gift"},
                        headers={"Idempotency-Key": "delayed-activity-turn"},
                    )
                assert response.status_code in {401, 404}
                await _assert_no_personal_activity(database, tenant)
        finally:
            await app.state.database.close()
    finally:
        await database.close()


async def test_deletion_removes_personal_receipts_but_preserves_opt_out_and_guest_quota(
    integration_settings: Settings,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    try:
        await database.initialize_tenant(tenant)
        accounts, activity = ShopperAccounts(database), ActivityService(database)
        auth, _ = await accounts.guest(tenant, None)
        account, version = auth.account.id, auth.account._data_version
        assert version is not None
        definition = ActivityRuleInput(name="My personal search monitor", threshold=2)
        before = await activity.configure(
            tenant_id=tenant,
            account_id=account,
            definition=definition,
            key="monitor",
            account_version=version,
        )
        await accounts.preferences(tenant, account, True, idempotency_key="initial-on")
        await accounts.preferences(tenant, account, False, idempotency_key="later-off")
        for number in range(10):
            assert await accounts.admit_turn(tenant, account, f"turn-{number}")
        await accounts.delete_data(tenant, account)
        await _assert_no_personal_activity(database, tenant)
        async with database.transaction(tenant) as session:
            scopes = list(
                await session.scalars(
                    select(IdempotencyRecord.scope).where(IdempotencyRecord.tenant_id == tenant)
                )
            )
            current = await accounts.account(session, tenant, account)
            assert current.version == version + 1
        assert f"activity:configure:{account}" not in scopes
        assert scopes.count(f"shopper:preferences:{account}") == 2
        assert scopes.count(f"guest:turn:{account}") == 10
        assert not await accounts.admit_turn(tenant, account, "eleventh-turn")
        assert await accounts.admit_turn(tenant, account, "turn-0")
        assert not (
            await accounts.preferences(tenant, account, True, idempotency_key="initial-on")
        ).memory_enabled
        with pytest.raises(ActivityRuleError):
            await activity.configure(
                tenant_id=tenant,
                account_id=account,
                definition=definition,
                key="monitor",
                account_version=version,
            )
        fresh = await activity.configure(
            tenant_id=tenant,
            account_id=account,
            definition=definition,
            key="monitor",
            account_version=version + 1,
        )
        assert fresh.id != before.id
        assert (
            await activity.configure(
                tenant_id=tenant,
                account_id=account,
                definition=definition,
                key="monitor",
                account_version=version + 1,
            )
            == fresh
        )
        await activity.record(
            tenant_id=tenant,
            account_id=account,
            event=ActivityEventInput(kind=ActivityKind.SEARCH, status="ok", duration_ms=1),
            key="fresh-event",
            account_version=version + 1,
        )
        # Tenant-wide operator rules do not inherit a shopper's deletion fence.
        operator = await activity.configure(
            tenant_id=tenant,
            account_id=None,
            definition=definition,
            key="operator",
        )
        assert operator.id != fresh.id
    finally:
        await database.close()


async def test_merged_guest_cannot_recreate_personal_activity(
    integration_settings: Settings,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    try:
        await database.initialize_tenant(tenant)
        accounts, activity = ShopperAccounts(database), ActivityService(database)
        target, _ = await DurableShopperAgentService(
            database, search_service=SearchService()
        ).register(
            tenant_id=tenant,
            request=ShopperRegisterRequest(
                username="saved-shopper",
                display_name="Saved shopper",
                password="synthetic-merge-password",
            ),
        )
        guest, _ = await accounts.guest(tenant, None)
        definition = ActivityRuleInput(name="Temporary guest monitor", threshold=2)
        await activity.configure(
            tenant_id=tenant,
            account_id=guest.account.id,
            definition=definition,
            key="guest-rule",
            account_version=guest.account._data_version,
        )
        merged, _ = await accounts.login(
            tenant,
            guest.account.id,
            ShopperLoginRequest(username="saved-shopper", password="synthetic-merge-password"),
        )
        assert merged.account.id == target.account.id
        for version in (None, guest.account._data_version):
            with pytest.raises(ActivityRuleError):
                await activity.configure(
                    tenant_id=tenant,
                    account_id=guest.account.id,
                    definition=definition,
                    key="guest-rule",
                    account_version=version,
                )
        await _assert_no_personal_activity(database, tenant)
        async with database.transaction(tenant) as session:
            assert not await session.scalar(
                select(IdempotencyRecord.key).where(
                    IdempotencyRecord.tenant_id == tenant,
                    IdempotencyRecord.scope == f"activity:configure:{guest.account.id}",
                )
            )
    finally:
        await database.close()


@pytest.mark.parametrize("deletion_first", [False, True])
async def test_deletion_and_personal_activity_are_transactionally_ordered(
    integration_settings: Settings,
    deletion_first: bool,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    entered, release = asyncio.Event(), asyncio.Event()
    pending: list[asyncio.Task[None]] = []
    try:
        await database.initialize_tenant(tenant)
        accounts, activity = ShopperAccounts(database), ActivityService(database)
        auth, _ = await accounts.guest(tenant, None)
        account, version = auth.account.id, auth.account._data_version
        original_account, original_erase = activity._account, accounts.erase_activity

        async def account_gate(
            session: AsyncSession,
            tenant_id: UUID,
            account_id: UUID,
            account_version: int | None,
        ) -> ShopperAccountRecord:
            row = await original_account(session, tenant_id, account_id, account_version)
            if not deletion_first:
                entered.set()
                await asyncio.wait_for(release.wait(), timeout=10)
            return row

        async def erase_gate(session: AsyncSession, tenant: UUID, account: UUID) -> None:
            await original_erase(session, tenant, account)
            if deletion_first:
                entered.set()
                await asyncio.wait_for(release.wait(), timeout=10)

        async def record() -> None:
            await activity.record(
                tenant_id=tenant,
                account_id=account,
                event=ActivityEventInput(kind=ActivityKind.SEARCH, status="ok", duration_ms=1),
                key="ordered-event",
                account_version=version,
            )

        with (
            patch.object(activity, "_account", side_effect=account_gate),
            patch.object(accounts, "erase_activity", side_effect=erase_gate),
        ):
            first = asyncio.create_task(
                accounts.delete_data(tenant, account) if deletion_first else record()
            )
            pending.append(first)
            await asyncio.wait_for(entered.wait(), timeout=10)
            second = asyncio.create_task(
                record() if deletion_first else accounts.delete_data(tenant, account)
            )
            pending.append(second)
            release.set()
            await asyncio.wait_for(first, timeout=10)
            if deletion_first:
                with pytest.raises(ActivityRuleError):
                    await asyncio.wait_for(second, timeout=10)
            else:
                await asyncio.wait_for(second, timeout=10)
        await _assert_no_personal_activity(database, tenant)
    finally:
        release.set()
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await database.close()
