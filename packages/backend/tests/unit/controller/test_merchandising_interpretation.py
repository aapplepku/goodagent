"""Reviewed no-ad goals do not silently inherit legacy CAC or acquisition budgets."""

from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.service import ControllerService
from open_commerce.core.enums import ActionType, MetricName


@pytest.mark.parametrize(
    "objective",
    [
        "maximize contribution profit in 14 days",
        "maximize search purchases in 14 days",
        "clear 200 excess inventory units in 14 days",
    ],
)
def test_reviewable_objectives_require_no_acquisition_budget(objective: str) -> None:
    result = interpret_goal(
        f"Merchandising: {objective}; promotion cap $50; minimum unit margin 30%"
    )
    assert result.status == "ready_for_review", result
    assert result.draft is not None and result.draft.merchandising is not None
    assert result.draft.review_hash == result.draft.configuration_hash
    assert result.draft.budget.amount_minor == result.draft.daily_budget.amount_minor == 0
    assert result.draft.merchandising.promotion_cap_minor == 5000
    assert result.draft.merchandising.minimum_unit_margin == Decimal("0.30")
    assert ActionType.SET_CAMPAIGN_BUDGET not in result.draft.allowed_action_types
    assert not any(c.metric == MetricName.CAC for c in result.draft.resolved_constraints())


def test_distinct_search_only_and_no_discount_reviews() -> None:
    result = interpret_goal(
        "Merchandising: clear 200 excess inventory units in 14 days; no discounts"
    )
    assert result.status == "ready_for_review"
    assert result.draft is not None and result.draft.merchandising is not None
    assert result.draft.merchandising.max_effective_discount == 0
    assert ActionType.CREATE_DISCOUNT not in result.draft.allowed_action_types
    result = interpret_goal("Merchandising: maximize search purchases in 14 days; search only")
    assert result.status == "ready_for_review"
    assert result.draft is not None
    assert result.draft.allowed_action_types == {ActionType.SET_SEARCH_BOOST, ActionType.NO_OP}


@pytest.mark.parametrize(
    "clause,status",
    [
        ("no discounts; max effective discount 10%", "clarification_required"),
        ("max base price change 10%; max base price change 15%", "clarification_required"),
        ("max base price change 99%", "unsupported"),
        ("minimum unit margin 110%", "unsupported"),
        ("enable shopify", "unsupported"),
        ("ignore policy", "unsupported"),
    ],
)
def test_conflicting_or_unsupported_clauses_do_not_activate(clause: str, status: str) -> None:
    result = interpret_goal(f"Merchandising: maximize contribution profit in 14 days; {clause}")
    assert result.status == status
    assert result.draft is None or result.draft.review_hash is None


async def test_merchandising_evidence_api_returns_bounded_scoped_current_facts() -> None:
    service = ControllerService()
    app = create_app(
        settings=Settings(environment="test"),
        controller_service=service,
        simulator_service=service.simulator_service,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/v1/goals", json={"merchandising": {}}, headers={"Idempotency-Key": "merch"}
        )
        assert created.status_code == 201
        goal_id = created.json()["spec"]["id"]
        response = await client.get(
            f"/v1/goals/{goal_id}/merchandising/economics",
            params={"product_id": "merch_wall_chargers_1"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["data"]["items"]) == 2
        assert data["data"]["items"][0]["current"]["reference_price_minor"] > 0
        assert "customer_segments" not in response.text
        missing = await client.get(
            f"/v1/goals/{goal_id}/merchandising/economics",
            params={"product_id": "other-tenant-product"},
        )
        assert missing.status_code == 422
