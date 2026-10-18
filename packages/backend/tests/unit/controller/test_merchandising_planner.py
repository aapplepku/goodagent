"""No-key coordination and bounded model evidence do not use hidden simulator demand."""

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError
from scripts.merchandising_decision_fixtures import add_observation, fixture

from open_commerce.controller.merchandising_evidence import merchandising_evidence
from open_commerce.controller.merchandising_planner import plan_merchandising
from open_commerce.controller.model_protocol import (
    PlannerResponse,
    ProposeDecision,
    validated_drafts,
)
from open_commerce.controller.models import ControllerRunRequest
from open_commerce.core.enums import ActionType, GoalStatus
from open_commerce.simulator.merchandising_models import ProductOutcomes


async def test_fresh_profile_waits_without_legacy_warmup_or_acquisition_budget() -> None:
    service, goal, state = fixture()
    assert state.metrics == []
    service.set_goal_status(
        tenant_id=state.tenant_id,
        goal_id=goal.spec.id,
        status=GoalStatus.ACTIVE,
        idempotency_key="activate",
    )
    run = await service.run_goal(
        tenant_id=state.tenant_id,
        goal_id=goal.spec.id,
        request=ControllerRunRequest(),
        idempotency_key="first",
    )
    assert run.intent_drafts == []
    decision = run.summary["merchandising_decision"]
    assert isinstance(decision, dict) and decision["kind"] == "wait"
    assert run.snapshot is not None
    assert run.snapshot.sample_size == 0
    assert run.snapshot.metric_summary["conversion_rate"] is None


def test_search_only_cumulative_counters_without_surface_records_wait() -> None:
    _, goal, state = fixture()
    add_observation(state)
    assert state.merchandising is not None
    goal.spec.allowed_action_types = {ActionType.SET_SEARCH_BOOST, ActionType.NO_OP}
    product = next(p for p in state.products if p.excess_inventory)
    for peer in state.products:
        state.merchandising.product_outcomes[peer.id] = ProductOutcomes(
            search_exposures=1000, orders=30
        )
    state.merchandising.product_outcomes[product.id] = ProductOutcomes(
        search_exposures=100, orders=3
    )
    run_id = uuid4()
    plan = plan_merchandising(goal=goal.spec, state=state, run_id=run_id)
    assert not plan.drafts
    for peer in state.products:
        peer.quality_score = Decimal(0)
        peer.popularity_score = Decimal(1)
    state.seed = 987654
    assert plan_merchandising(goal=goal.spec, state=state, run_id=run_id) == plan


def test_poor_conversion_counters_alone_do_not_establish_price_sensitivity() -> None:
    _, goal, state = fixture()
    assert state.merchandising is not None
    add_observation(state)
    product = state.products[0]
    state.merchandising.product_outcomes[product.id] = ProductOutcomes(search_exposures=400)
    goal.spec.allowed_action_types = {ActionType.SET_VARIANT_PRICE, ActionType.NO_OP}
    plan = plan_merchandising(goal=goal.spec, state=state, run_id=uuid4())
    assert not plan.drafts
    assert plan.decision["predicted_profit_minor"] is None
    goal.spec.allowed_action_types = {ActionType.CREATE_DISCOUNT, ActionType.NO_OP}
    plan = plan_merchandising(goal=goal.spec, state=state, run_id=uuid4())
    assert not plan.drafts
    state.merchandising.constraints.max_effective_discount = Decimal(0)
    assert not plan_merchandising(goal=goal.spec, state=state, run_id=uuid4()).drafts


def test_already_good_store_does_not_require_an_intervention() -> None:
    _, goal, state = fixture()
    assert state.merchandising is not None
    add_observation(state)
    for product in state.products:
        state.merchandising.product_outcomes[product.id] = ProductOutcomes(
            search_exposures=1000, recommendation_exposures=200, clicks=50, orders=30
        )
    assert not plan_merchandising(goal=goal.spec, state=state, run_id=uuid4()).drafts


@pytest.mark.parametrize("view", ["economics", "pricing", "products", "search", "recommendations"])
def test_investigation_is_bounded_scoped_and_allowlisted(view: str) -> None:
    _, _, state = fixture()
    data = merchandising_evidence(state, tenant_id=state.tenant_id, view=view)
    inner = data["data"]
    assert isinstance(inner, dict)
    items = inner["items"]
    assert isinstance(items, list) and len(items) <= 10
    assert all(
        word not in str(data)
        for word in (
            "quality_score",
            "popularity_score",
            "price_sensitivity",
            "customer_segments",
            "seed",
        )
    )
    with pytest.raises(ValueError, match="tenant"):
        merchandising_evidence(state, tenant_id=uuid4(), view=view)
    with pytest.raises(ValueError, match="unknown scoped"):
        merchandising_evidence(state, tenant_id=state.tenant_id, view=view, product_id="unknown")


def test_model_can_propose_finite_rec_controls_not_authoritative_economics() -> None:
    _, goal, state = fixture()
    payload: dict[str, Any] = {
        "decision": {
            "kind": "propose",
            "summary": "Bounded experiment",
            "evidence_refs": ["recorded"],
            "proposals": [
                {
                    "action_type": "set_recommendation_policy",
                    "expected_version": 0,
                    "duration_hours": 48,
                    "controls": {"strategy": "complements"},
                }
            ],
        }
    }
    response = PlannerResponse.model_validate(payload)
    assert isinstance(response.decision, ProposeDecision)
    drafts = validated_drafts(response.decision, goal=goal, state=state, run_id=uuid4())
    assert drafts[0].action_type == ActionType.SET_RECOMMENDATION_POLICY
    assert drafts[0].confidence == 0
    payload["decision"]["proposals"][0]["projected_margin"] = "0.99"
    with pytest.raises(ValidationError):
        PlannerResponse.model_validate(payload)
