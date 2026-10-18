from collections.abc import Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.api.schemas import DependencyStatus
from open_commerce.config import Settings
from open_commerce.search.service import SearchService

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


def readiness_checker() -> ReadinessChecker:
    async def _checker(settings: Settings) -> list[DependencyStatus]:
        _ = settings
        return [DependencyStatus(name="postgres", ok=True, latency_ms=1)]

    return _checker


@pytest.mark.asyncio
async def test_search_api_returns_results_and_debug_trace() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        search_service=SearchService(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            json={"query": "SIM-FOO-0003-1", "top_k": 5, "debug": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["results"][0]["product_id"] == "prod_footwear_0003"
    assert body["trace"]["retrieval"]["fusion"] == "rrf"


@pytest.mark.asyncio
async def test_event_batch_api_requires_idempotency_and_deduplicates() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        search_service=SearchService(),
    )
    payload = {
        "events": [
            {
                "event_id": "evt-1",
                "occurred_at": "2026-09-04T00:00:00Z",
                "session_id": "session-1",
                "type": "product_impression",
                "product_id": "prod_1",
                "position": 1,
                "surface": "search",
            }
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_key = await client.post("/v1/events/batch", json=payload)
        accepted = await client.post(
            "/v1/events/batch",
            headers={"Idempotency-Key": "events-1"},
            json=payload,
        )
        repeated = await client.post(
            "/v1/events/batch",
            headers={"Idempotency-Key": "events-2"},
            json=payload,
        )

    assert missing_key.status_code == 422
    assert accepted.json() == {"accepted": 1, "deduplicated": 0}
    assert repeated.json() == {"accepted": 0, "deduplicated": 1}


@pytest.mark.asyncio
async def test_search_rule_api_cannot_bypass_the_executor() -> None:
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        search_service=SearchService(),
    )
    payload = {
        "query_text": "trail",
        "product_ids": ["prod_footwear_0003"],
        "multiplier": "1.5",
        "starts_at": "2026-09-03T00:00:00Z",
        "ends_at": "2026-09-06T00:00:00Z",
        "reason": "test",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/v1/search/rules",
            headers={"Idempotency-Key": "rule-1"},
            json=payload,
        )
        second = await client.post(
            "/v1/search/rules",
            headers={"Idempotency-Key": "rule-1"},
            json=payload,
        )
        rule_id = "00000000-0000-0000-0000-000000000001"
        deleted = await client.delete(
            f"/v1/search/rules/{rule_id}",
            headers={"Idempotency-Key": "delete-1"},
        )
        listed = await client.get("/v1/search/rules")

    assert first.status_code == 405
    assert second.status_code == 405
    assert deleted.status_code == 404
    assert listed.json()["items"] == []
