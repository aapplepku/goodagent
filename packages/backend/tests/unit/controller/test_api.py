from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.api.schemas import DependencyStatus
from open_commerce.config import Settings
from open_commerce.controller.service import ControllerService
from open_commerce.simulator.service import SimulatorService

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


def readiness_checker() -> ReadinessChecker:
    async def _checker(settings: Settings) -> list[DependencyStatus]:
        _ = settings
        return [DependencyStatus(name="postgres", ok=True, latency_ms=1)]

    return _checker


@pytest.mark.asyncio
async def test_controller_api_goal_run_approval_execution_and_kill_switch() -> None:
    simulator_service = SimulatorService()
    controller_service = ControllerService(simulator_service=simulator_service)
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        simulator_service=simulator_service,
        controller_service=controller_service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_key = await client.post("/v1/goals", json={"seed": 42})
        created = await client.post(
            "/v1/goals",
            headers={"Idempotency-Key": "goal-1"},
            json={"seed": 42, "target_value": "10000"},
        )
        goal_id = created.json()["spec"]["id"]
        inactive_run = await client.post(
            f"/v1/goals/{goal_id}/run",
            headers={"Idempotency-Key": "run-inactive"},
            json={},
        )
        activated = await client.post(
            f"/v1/goals/{goal_id}/activate",
            headers={"Idempotency-Key": "activate-1"},
        )
        run = await client.post(
            f"/v1/goals/{goal_id}/run",
            headers={"Idempotency-Key": "run-1"},
            json={},
        )
        run_id = run.json()["id"]
        trace = await client.get(f"/v1/runs/{run_id}/trace")
        actions = await client.get("/v1/actions", params={"run_id": run_id})
        records = actions.json()["items"]
        boost = next(
            item for item in records if item["action"]["intent"]["type"] == "set_search_boost"
        )
        discount = next(
            item
            for item in records
            if item["action"]["intent"]["type"] == "create_discount"
            and item["action"]["status"] == "awaiting_approval"
        )
        stale_approval = await client.post(
            f"/v1/actions/{discount['action']['id']}/approve",
            headers={"Idempotency-Key": "approve-stale"},
            json={"action_version_hash": "sha256:stale-action"},
        )
        approved = await client.post(
            f"/v1/actions/{discount['action']['id']}/approve",
            headers={"Idempotency-Key": "approve-discount"},
            json={"action_version_hash": discount["action_version_hash"]},
        )
        executed_discount = await client.post(
            f"/v1/actions/{discount['action']['id']}/execute",
            headers={"Idempotency-Key": "execute-discount"},
        )
        kill = await client.post(
            "/v1/kill-switch/enable",
            headers={"Idempotency-Key": "kill-on"},
        )
        blocked = await client.post(
            f"/v1/actions/{boost['action']['id']}/execute",
            headers={"Idempotency-Key": "execute-boost"},
        )

    assert missing_key.status_code == 422
    assert inactive_run.status_code == 409
    assert activated.json()["spec"]["status"] == "active"
    assert run.status_code == 200
    assert trace.json()["items"][0]["node"] == "load_goal_and_policy"
    assert stale_approval.status_code == 409
    assert approved.json()["action"]["status"] == "approved"
    assert executed_discount.json()["action"]["status"] == "succeeded"
    assert kill.json()["enabled"] is True
    assert blocked.status_code == 409
