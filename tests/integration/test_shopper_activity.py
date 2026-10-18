"""Real operational logging, scoped monitoring, retention, and worker-style recovery."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.activity_models import (
    ActivityEventInput,
    ActivityKind,
    ActivityQuery,
    ActivityRuleInput,
)

pytestmark = pytest.mark.integration


async def test_activity_scopes_replays_due_checks_pause_and_retention(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant)
        await database.initialize_tenant(other)
        shopper = DurableShopperAgentService(database, search_service=SearchService())
        accounts = [
            (
                await shopper.register(
                    tenant_id=tenant,
                    request=ShopperRegisterRequest(
                        username=f"activity-{i}",
                        display_name="Synthetic",
                        password="synthetic-test-password",
                    ),
                )
            )[0].account.id
            for i in range(2)
        ]
        activity = ActivityService(database)
        for index, account in enumerate(accounts):
            event = ActivityEventInput(
                kind=ActivityKind.SEARCH, status="ok", duration_ms=50, result_count=index
            )
            for _ in range(2):
                await activity.record(
                    tenant_id=tenant, account_id=account, event=event, key="event"
                )
        mine = await activity.overview(
            tenant_id=tenant, account_id=accounts[0], query=ActivityQuery()
        )
        assert len(mine.events) == 1 and mine.events[0].result_count == 0
        store = await activity.overview(tenant_id=tenant, account_id=None, query=ActivityQuery())
        assert len(store.events) == 2 and store.observed_counts == {"search": 2}
        assert str(accounts[0]) not in store.model_dump_json()
        assert "synthetic-test-password" not in store.model_dump_json()
        assert not (
            await activity.overview(tenant_id=other, account_id=None, query=ActivityQuery())
        ).events
        definition = ActivityRuleInput.model_validate(
            {
                "name": "Empty searches",
                "query": {"kind": "search"},
                "metric": "empty_result_rate",
                "threshold": 25,
                "minimum_samples": 2,
                "interval_minutes": 1,
            }
        )
        rule = await activity.configure(
            tenant_id=tenant, account_id=None, definition=definition, key="rule"
        )
        assert rule.check.state == "alert" and rule.check.value == 50
        assert (
            await activity.configure(
                tenant_id=tenant, account_id=None, definition=definition, key="rule"
            )
            == rule
        )
        personal = await activity.configure(
            tenant_id=tenant, account_id=accounts[0], definition=definition, key="rule"
        )
        assert personal.check.state == "insufficient_data" and personal.id != rule.id
        assert (
            len(
                (
                    await activity.overview(
                        tenant_id=tenant, account_id=None, query=ActivityQuery()
                    )
                ).rules
            )
            == 1
        )
        restarted = ActivityService(database)
        assert await restarted.evaluate_due(tenant, now=utc_now() + timedelta(minutes=2)) == 2
        assert await restarted.evaluate_due(tenant, now=utc_now() + timedelta(minutes=2)) == 0
        paused = await activity.configure(
            tenant_id=tenant,
            account_id=None,
            definition=definition.model_copy(update={"enabled": False}),
            key="pause",
        )
        assert paused.check.state == "paused" and paused.next_check_at is None
        await restarted.evaluate_due(tenant, now=utc_now() + timedelta(days=31))
        assert not (
            await activity.overview(tenant_id=tenant, account_id=None, query=ActivityQuery())
        ).events
    finally:
        await database.close()


async def test_authenticated_shopper_requests_emit_safe_activity_and_reject_foreign_scope(
    integration_settings: Settings,
) -> None:
    tenant = uuid4()
    settings = integration_settings.model_copy(
        update={"local_tenant_id": tenant, "manager_model_provider": "deterministic"}
    )
    database = RuntimeDatabase(settings)
    try:
        await database.initialize_tenant(tenant)
        shopper = DurableShopperAgentService(database, search_service=SearchService())
        app = create_app(
            settings=settings, shopper_agent_service=shopper, search_service=SearchService()
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/v1/shopper/activity")).status_code == 401
            assert (
                await client.post(
                    "/v1/shopper/auth/register",
                    json={
                        "username": "logging-test",
                        "display_name": "Synthetic",
                        "password": "synthetic-test-password",
                    },
                )
            ).status_code == 201
            for _ in range(2):
                response = await client.post(
                    "/v1/shopper/chat",
                    json={"content": "I prefer blue"},
                    headers={"Idempotency-Key": "test-chat"},
                )
                assert response.status_code == 200, response.text
            overview = (await client.get("/v1/shopper/activity")).json()
            assert overview["observed_counts"] == {"chat": 1, "memory_save": 1}
            assert "I prefer blue" not in str(overview)
            with patch.object(
                shopper.agent, "respond", side_effect=ManagerModelUnavailableError("test outage")
            ):
                failed_model = await client.post(
                    "/v1/shopper/chat",
                    json={"content": "Find a gift"},
                    headers={"Idempotency-Key": "failed-model"},
                )
                assert failed_model.status_code == 200
            observed = (await client.get("/v1/shopper/activity")).json()
            assert observed["events"][0]["kind"] == "chat"
            assert observed["events"][0]["status"] == "fallback"
            assert (
                await client.get(f"/v1/shopper/activity?account_id={uuid4()}")
            ).status_code == 422
            forged = await client.post(
                "/v1/shopper/activity/rules",
                json={
                    "name": "My activity",
                    "account_id": str(uuid4()),
                },
                headers={"Idempotency-Key": "forged"},
            )
            assert forged.status_code == 422
            created = await client.post(
                "/v1/shopper/activity/rules",
                json={
                    "name": "My searches",
                    "query": {"kind": "search"},
                },
                headers={"Idempotency-Key": "view"},
            )
            assert created.status_code == 200, created.text
            assert created.json()["check"]["state"] == "log_only"
        await app.state.database.close()
    finally:
        await database.close()
