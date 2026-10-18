from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.api.schemas import DependencyStatus
from open_commerce.config import Settings

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


def readiness_checker(*statuses: DependencyStatus) -> ReadinessChecker:
    async def _checker(settings: Settings) -> list[DependencyStatus]:
        return list(statuses)

    return _checker


@pytest.mark.asyncio
async def test_liveness_does_not_require_dependencies() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.asyncio
async def test_request_id_is_returned() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live", headers={"x-request-id": "req-test"})

    assert response.headers["x-request-id"] == "req-test"


@pytest.mark.asyncio
async def test_readiness_success() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(
            DependencyStatus(name="postgres", ok=True, latency_ms=1),
            DependencyStatus(name="redis", ok=True, latency_ms=1),
            DependencyStatus(name="qdrant", ok=True, latency_ms=1),
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_failure_reports_dependency_status() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(
            DependencyStatus(name="postgres", ok=True, latency_ms=1),
            DependencyStatus(name="redis", ok=False, latency_ms=1, detail="ConnectionError"),
            DependencyStatus(name="qdrant", ok=True, latency_ms=1),
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["dependencies"][1]["detail"] == "ConnectionError"


@pytest.mark.asyncio
async def test_meta_returns_service_metadata() -> None:
    app = create_app(
        settings=Settings(app_name="Open Commerce Agent", app_version="0.0.1", environment="test"),
        readiness_checker=readiness_checker(
            DependencyStatus(name="postgres", ok=True, latency_ms=1),
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "Open Commerce Agent",
        "version": "0.0.1",
        "environment": "test",
        "status": "ready",
        "dependencies": [{"name": "postgres", "ok": True, "latency_ms": 1.0, "detail": None}],
    }
