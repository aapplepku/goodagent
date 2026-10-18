from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.api.schemas import DependencyStatus
from open_commerce.config import Settings
from open_commerce.controller.service import ControllerService
from open_commerce.simulator.models import DailyMetrics
from open_commerce.simulator.service import SimulatorService

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


@pytest.mark.parametrize(
    ("text", "metric", "scope", "target", "budget"),
    [
        ("Acquire 0 new customers with a $0 budget", "new_customers", "store", "0", 0),
        (
            "Clear 300 excess inventory units; budget: $50",
            "units_sold",
            "excess_inventory",
            "300",
            5000,
        ),
        (
            "Reach 120 search purchases; budget: $2,000",
            "search_attributed_purchases",
            "store",
            "120",
            200000,
        ),
        (
            "Acquire 100 new customers. CAC $40, budget: $500",
            "new_customers",
            "store",
            "100",
            50000,
        ),
    ],
)
async def test_goal_draft_is_typed_and_preserves_small_explicit_budgets(
    text: str,
    metric: str,
    scope: str,
    target: str,
    budget: int,
) -> None:
    from open_commerce.api.demo import draft_goal
    from open_commerce.api.schemas import GoalDraftRequest

    response = await draft_goal(GoalDraftRequest(text=text))
    assert response.draft is not None
    structured = response.draft.model_dump(mode="json")
    assert structured["objective_metric"] == metric
    assert structured["objective_scope"] == scope
    assert structured["target_value"] == target
    assert structured["budget"]["amount_minor"] == budget
    assert response.status == "clarification_required"
    assert any("horizon" in item for item in response.ambiguities)
    assert response.draft.review_hash is None


def readiness_checker() -> ReadinessChecker:
    async def _checker(settings: Settings) -> list[DependencyStatus]:
        _ = settings
        return [DependencyStatus(name="postgres", ok=True, latency_ms=1)]

    return _checker


@pytest.mark.parametrize("metric", ["units_sold", "revenue"])
async def test_existing_store_metrics_have_definitions_and_series(metric: str) -> None:
    simulator = SimulatorService()
    settings = Settings(environment="test")
    instance = simulator.create_instance(
        tenant_id=settings.local_tenant_id,
        scenario_id="excess_inventory_v1",
        seed=42,
        idempotency_key="metric-series",
    )
    simulator.advance(
        tenant_id=settings.local_tenant_id,
        instance_id=instance.id,
        hours=24,
        idempotency_key="metric-day",
    )
    app = create_app(
        settings=settings,
        readiness_checker=readiness_checker(),
        simulator_service=simulator,
        controller_service=ControllerService(simulator_service=simulator),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/metrics/series", params={"instance_id": str(instance.id), "metric": metric}
        )
        summary = await client.get("/v1/metrics/summary", params={"instance_id": str(instance.id)})
    assert response.status_code == 200, response.text
    definition = next(item for item in summary.json()["definitions"] if item["name"] == metric)
    assert response.json()["definition_version"] == definition["version"]
    stored = simulator.get_full_state(
        tenant_id=settings.local_tenant_id, instance_id=instance.id
    ).metrics[-1]
    expected = stored.units_sold if metric == "units_sold" else stored.gross_revenue_minor
    assert response.json()["items"][0]["value"] == str(expected)
    assert response.json()["completeness_warnings"] == []


@pytest.mark.parametrize("cac", [None, 0, 1234])
async def test_series_distinguishes_unavailable_cac_from_zero(cac: int | None) -> None:
    simulator = SimulatorService()
    settings = Settings(environment="test")
    instance = simulator.create_instance(
        tenant_id=settings.local_tenant_id,
        scenario_id="acquisition_v1",
        seed=42,
        idempotency_key="cac-series",
    )
    state = simulator.get_full_state(tenant_id=settings.local_tenant_id, instance_id=instance.id)
    state.metrics.append(
        DailyMetrics(
            metric_date=date(2026, 1, 1),
            day_index=1,
            sessions=0,
            impressions=0,
            clicks=0,
            carts=0,
            orders=0,
            units_sold=0,
            new_customers=0 if cac is None else 1,
            gross_revenue_minor=0,
            discounts_minor=0,
            cogs_minor=0,
            variable_fees_minor=0,
            ad_spend_minor=cac or 0,
            contribution_profit_minor=-(cac or 0),
            conversion_rate=Decimal(0),
            cac_minor=cac,
            contribution_margin_rate=Decimal(0),
            discount_rate=Decimal(0),
            search_attributed_purchases=0,
            ending_inventory_units=0,
        )
    )
    simulator.store.put(state)
    app = create_app(
        settings=settings,
        readiness_checker=readiness_checker(),
        simulator_service=simulator,
        controller_service=ControllerService(simulator_service=simulator),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/metrics/series", params={"instance_id": str(instance.id), "metric": "cac"}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["value"] == (None if cac is None else str(cac))
    assert bool(body["completeness_warnings"]) is (cac is None)
    assert body["freshness"] == "fresh"


@pytest.mark.asyncio
async def test_release_capabilities_goal_draft_metrics_and_catalog() -> None:
    simulator_service = SimulatorService()
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        simulator_service=simulator_service,
        controller_service=ControllerService(simulator_service=simulator_service),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        capabilities = await client.get("/v1/capabilities")
        draft = await client.post(
            "/v1/goals/draft",
            json={
                "text": (
                    "Acquire 200 new customers in 30 days with a $10,000 budget. "
                    "Keep margin above 25% and discounts under 15%."
                )
            },
        )
        empty_summary = await client.get("/v1/metrics/summary")
        created = await client.post(
            "/v1/simulator/instances",
            headers={"Idempotency-Key": "release-instance"},
            json={"scenario_id": "acquisition_v1", "seed": 42},
        )
        instance_id = created.json()["id"]
        alias_state = await client.get(f"/v1/simulator/instances/{instance_id}")
        await client.post(
            f"/v1/simulator/instances/{instance_id}/advance",
            headers={"Idempotency-Key": "release-advance"},
            json={"hours": 48},
        )
        summary = await client.get(
            "/v1/metrics/summary",
            params={"instance_id": instance_id},
        )
        series = await client.get(
            "/v1/metrics/series",
            params={"instance_id": instance_id, "metric": "new_customers", "limit": 1},
        )
        products = await client.get(
            "/v1/catalog/products",
            params={"instance_id": instance_id, "limit": 2},
        )
        product_id = products.json()["items"][0]["product_id"]
        product = await client.get(
            f"/v1/catalog/products/{product_id}",
            params={"instance_id": instance_id},
        )

    assert capabilities.json()["capabilities"][0]["status"] == "available"
    assert "shopify_shadow" in {item["key"] for item in capabilities.json()["capabilities"]}
    assert draft.json()["draft"]["budget"]["amount_minor"] == 1_000_000
    assert draft.json()["warnings"]
    assert empty_summary.json()["freshness"] == "empty"
    assert created.status_code == 201
    assert alias_state.json()["id"] == instance_id
    assert summary.json()["totals"]["days"] == 2
    assert series.json()["next_cursor"] == "1"
    assert len(products.json()["items"]) == 2
    assert products.json()["next_cursor"] == "2"
    assert "cost_minor" not in product.text
    assert product.json()["variants"]


@pytest.mark.asyncio
async def test_release_error_envelope_interventions_audit_and_sse_resume() -> None:
    simulator_service = SimulatorService()
    controller_service = ControllerService(simulator_service=simulator_service)
    app = create_app(
        settings=Settings(environment="test"),
        readiness_checker=readiness_checker(),
        simulator_service=simulator_service,
        controller_service=controller_service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get(
            "/v1/goals/00000000-0000-0000-0000-000000000000",
            headers={"x-request-id": "req-release"},
        )
        created = await client.post(
            "/v1/goals",
            headers={"Idempotency-Key": "release-goal"},
            json={"seed": 42, "target_value": "10000"},
        )
        goal_id = created.json()["spec"]["id"]
        await client.post(
            f"/v1/goals/{goal_id}/activate",
            headers={"Idempotency-Key": "release-activate"},
        )
        run = await client.post(
            f"/v1/goals/{goal_id}/run",
            headers={"Idempotency-Key": "release-run"},
            json={},
        )
        run_id = run.json()["id"]
        trace = await client.get(f"/v1/runs/{run_id}/trace", params={"limit": 2})
        events = await client.get(
            f"/v1/runs/{run_id}/events",
            headers={"Last-Event-ID": "2"},
        )
        actions = await client.get(
            "/v1/actions",
            params={"run_id": run_id, "status": "awaiting_approval", "limit": 1},
        )
        action = actions.json()["items"][0]
        await client.post(
            f"/v1/actions/{action['action']['id']}/cancel",
            headers={"Idempotency-Key": "release-cancel"},
        )
        interventions = await client.get(
            "/v1/interventions",
            params={"status": "cancelled", "limit": 1},
        )
        audit = await client.get("/v1/audit", params={"event_type": "action_cancelled"})

    body = missing.json()
    assert missing.status_code == 404
    assert missing.headers["x-request-id"] == "req-release"
    assert body["error"]["type"] == "not_found"
    assert body["error"]["request_id"] == "req-release"
    assert trace.json()["next_cursor"] == "2"
    assert "id: 3" in events.text
    assert "id: 1" not in events.text.splitlines()
    assert actions.json()["next_cursor"] == "1"
    assert interventions.json()["items"][0]["status"] == "cancelled"
    assert audit.json()["items"][0]["event_type"] == "action_cancelled"
