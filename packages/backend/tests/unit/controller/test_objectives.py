"""Objective units, conditional planning, and conservative infeasibility."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.detectors import build_observation_snapshot, detect_opportunities
from open_commerce.controller.models import GoalCreateRequest, GoalRecord
from open_commerce.controller.objectives import assess_goal, objective_value
from open_commerce.controller.planner import DeterministicModelProvider
from open_commerce.controller.service import ControllerService
from open_commerce.core.actions import CreateDiscountIntent, SetSearchBoostIntent
from open_commerce.core.enums import ActionType, MetricName, ObjectiveDirection
from open_commerce.core.goals import ObjectiveSpec
from open_commerce.simulator.engine import advance_state, totals_for_metrics
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.scenarios import get_scenario


def goal_state(request: GoalCreateRequest) -> tuple[GoalRecord, SimulatorState]:
    service = ControllerService()
    tenant = uuid4()
    goal = service.create_goal(tenant_id=tenant, request=request, idempotency_key="objective-test")
    state = service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    return goal, state


@pytest.mark.parametrize(
    ("scenario", "metric", "scope"),
    [
        ("acquisition_v1", "new_customers", "store"),
        ("excess_inventory_v1", "units_sold", "excess_inventory"),
        ("search_conversion_v1", "search_attributed_purchases", "store"),
    ],
)
def test_scenario_defaults_are_measured_objectives(scenario: str, metric: str, scope: str) -> None:
    request = GoalCreateRequest.model_validate({"scenario_id": scenario})
    objective = request.resolved_objective()
    assert objective.metric == metric
    assert objective.scope == scope
    assert objective.target == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"objective_metric": "search_conversion_rate"},
        {"objective_metric": "inventory_days_of_supply"},
        {"objective_metric": "cac", "objective_scope": "excess_inventory"},
        {"objective_metric": "conversion_rate", "target_value": "25"},
        {"target_value": "-1"},
        {"target_value": "NaN"},
    ],
)
def test_unmeasured_or_invalid_goals_are_rejected(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        GoalCreateRequest.model_validate(payload)


def test_progress_uses_cumulative_totals_minor_units_and_undefined_rates() -> None:
    goal, state = goal_state(GoalCreateRequest())
    for metric in (MetricName.CAC, MetricName.CONTRIBUTION_MARGIN_RATE, MetricName.CONVERSION_RATE):
        assert (
            objective_value(ObjectiveSpec(metric=metric, direction=ObjectiveDirection.REACH), state)
            is None
        )
    advance_state(state=state, definition=get_scenario(state.scenario_id), hours=48)
    totals = totals_for_metrics(state.metrics, include_history=False)
    assert objective_value(goal.spec.objective, state) == totals.new_customers
    assert (
        objective_value(
            ObjectiveSpec(metric=MetricName.CAC, direction=ObjectiveDirection.MINIMIZE), state
        )
        == totals.cac_minor
    )
    assert (
        objective_value(
            ObjectiveSpec(metric=MetricName.REVENUE, direction=ObjectiveDirection.REACH), state
        )
        == totals.gross_revenue_minor
    )
    assert (
        objective_value(
            ObjectiveSpec(
                metric=MetricName.CONTRIBUTION_PROFIT, direction=ObjectiveDirection.REACH
            ),
            state,
        )
        == totals.contribution_profit_minor
    )
    assert objective_value(
        ObjectiveSpec(metric=MetricName.DISCOUNT_RATE, direction=ObjectiveDirection.MINIMIZE), state
    ) == (Decimal(totals.discounts_minor) / totals.gross_revenue_minor)


def test_excess_progress_counts_only_original_overstock_depletion() -> None:
    goal, state = goal_state(GoalCreateRequest(scenario_id="excess_inventory_v1"))
    advance_state(state=state, definition=get_scenario(state.scenario_id), hours=48)
    expected = sum(
        v.initial_inventory - v.inventory
        for p in state.products
        if p.excess_inventory
        for v in p.variants
    )
    assert expected > 0
    assert objective_value(goal.spec.objective, state) == expected
    assert expected < totals_for_metrics(state.metrics, include_history=False).units_sold


@pytest.mark.parametrize(
    ("goal_request", "expected_types"),
    [
        (GoalCreateRequest(), {ActionType.SET_CAMPAIGN_BUDGET}),
        (
            GoalCreateRequest(target_value=Decimal("10000")),
            {ActionType.CREATE_DISCOUNT, ActionType.SET_SEARCH_BOOST},
        ),
        (
            GoalCreateRequest(scenario_id="search_conversion_v1", target_value=Decimal("10000")),
            {ActionType.SET_SEARCH_BOOST},
        ),
        (
            GoalCreateRequest(scenario_id="excess_inventory_v1", target_value=Decimal("10000")),
            {ActionType.CREATE_DISCOUNT, ActionType.SET_SEARCH_BOOST},
        ),
        (GoalCreateRequest(target_value=Decimal("999999999")), set()),
    ],
)
def test_plans_depend_on_objective_and_trajectory(
    goal_request: GoalCreateRequest, expected_types: set[ActionType]
) -> None:
    goal, state = goal_state(goal_request)
    assessment = assess_goal(goal.spec, state)
    snapshot = build_observation_snapshot(
        tenant_id=goal.spec.tenant_id, run_id=uuid4(), state=state
    )
    opportunities = detect_opportunities(snapshot, state, goal.spec, assessment)
    planner = DeterministicModelProvider()
    drafts = planner.generate_intent_drafts(
        opportunities=opportunities, hypotheses=planner.generate_hypotheses(opportunities)
    )
    assert {draft.action_type for draft in drafts} == expected_types
    if not expected_types:
        assert assessment.feasibility == "infeasible"
        assert opportunities[0].type == "guardrail_review"
        assert "PHYSICAL_INVENTORY_BOUND" in assessment.reason_codes
    else:
        assert assessment.feasibility == "not_ruled_out"
    assert assessment.forecast_method == "recent_rate_heuristic_not_calibrated"
    for action in ActionCompiler().compile_drafts(goal=goal.spec, state=state, drafts=drafts):
        if goal.spec.objective.scope == "excess_inventory":
            assert isinstance(action.intent, CreateDiscountIntent | SetSearchBoostIntent)
            ids = action.intent.product_scope.product_ids
            assert ids
            assert all(p.excess_inventory for p in state.products if p.id in ids)
            if isinstance(action.intent, CreateDiscountIntent):
                assert not action.intent.customer_scope.new_customers_only


def test_inventory_bound_does_not_mislabel_a_rate_forecast_as_impossible() -> None:
    goal, state = goal_state(
        GoalCreateRequest(objective_metric=MetricName.CAC, target_value=Decimal("1"))
    )
    assessment = assess_goal(goal.spec, state)
    assert assessment.trajectory == "at_risk"
    assert assessment.physical_upper_bound is None
    assert assessment.feasibility == "not_ruled_out"


def test_goal_assessment_rejects_cross_tenant_observation() -> None:
    goal, state = goal_state(GoalCreateRequest())
    state.tenant_id = uuid4()
    with pytest.raises(ValueError, match="tenant mismatch"):
        assess_goal(goal.spec, state)
