from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.api.schemas import DependencyStatus
from open_commerce.config import Settings
from open_commerce.simulator.service import SimulatorService

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


def readiness_checker() -> ReadinessChecker:
    async def _checker(settings: Settings) -> list[DependencyStatus]:
        return [DependencyStatus(name="postgres", ok=True, latency_ms=1)]

    return _checker


@pytest.mark.asyncio
async def test_simulator_api_create_advance_reset_and_baseline() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        simulator_service=SimulatorService(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        scenarios = await client.get("/v1/simulator/scenarios")
        assert scenarios.status_code == 200
        assert {item["id"] for item in scenarios.json()["items"]} == {
            "acquisition_v1",
            "excess_inventory_v1",
            "search_conversion_v1",
        }

        created = await client.post(
            "/v1/simulator/scenarios/acquisition_v1/instances",
            headers={"Idempotency-Key": "create-1"},
            json={"seed": 42},
        )
        assert created.status_code == 201
        body = created.json()
        instance_id = UUID(body["id"])
        initial_hash = body["state_hash"]
        assert body["catalog"]["product_count"] == 1_000

        advanced = await client.post(
            f"/v1/simulator/instances/{instance_id}/advance",
            headers={"Idempotency-Key": "advance-1"},
            json={"hours": 24},
        )
        repeated = await client.post(
            f"/v1/simulator/instances/{instance_id}/advance",
            headers={"Idempotency-Key": "advance-1"},
            json={"hours": 24},
        )
        assert advanced.status_code == 200
        assert repeated.status_code == 200
        assert advanced.json()["day"] == 1
        assert repeated.json()["day"] == 1

        comparison = await client.get(f"/v1/simulator/instances/{instance_id}/compare-baseline")
        assert comparison.status_code == 200
        assert comparison.json()["delta"]["orders"] == 0

        reset = await client.post(
            f"/v1/simulator/instances/{instance_id}/reset",
            headers={"Idempotency-Key": "reset-1"},
            json={"seed": 42},
        )
        assert reset.status_code == 200
        assert reset.json()["state_hash"] == initial_hash


@pytest.mark.asyncio
async def test_simulator_api_requires_idempotency_key_for_mutations() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        simulator_service=SimulatorService(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/simulator/scenarios/acquisition_v1/instances",
            json={"seed": 42},
        )

    assert response.status_code == 422
