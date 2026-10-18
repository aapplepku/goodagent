"""Interpretation preserves explicit values and blocks unsupported meaning."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import ActionType, MetricName
from open_commerce.core.money import Money


@pytest.mark.parametrize(
    ("target", "days", "budget", "daily", "margin", "discount"),
    [
        (321, 17, "1234.56", "12.50", "31", "7.5"),
        (0, 1, "0", "0", "25", "0"),
        (8900, 90, "25000", "100", "45", "3"),
    ],
)
def test_explicit_values_survive_review_and_creation_schema(
    target: int, days: int, budget: str, daily: str, margin: str, discount: str
) -> None:
    result = interpret_goal(
        f"Acquire {target} new customers in {days} days with a ${budget} budget. "
        f"Daily budget ${daily}. CAC <= $19.25; margin >= {margin}%; discount <= {discount}%."
    )
    assert result.status == "ready_for_review", result
    assert result.draft is not None
    draft = GoalCreateRequest.model_validate_json(result.draft.model_dump_json())
    assert draft.target_value == target
    assert draft.horizon_days == days
    assert draft.budget.amount_minor == int(Decimal(budget) * 100)
    assert draft.daily_budget.amount_minor == int(Decimal(daily) * 100)
    by_metric = {item.metric: item.value for item in draft.resolved_constraints()}
    assert by_metric[MetricName.CAC] == Money(amount_minor=1925, currency="USD")
    assert by_metric[MetricName.CONTRIBUTION_MARGIN_RATE] == Decimal(margin) / 100
    assert by_metric[MetricName.DISCOUNT_RATE] == Decimal(discount) / 100
    assert draft.review_hash == draft.configuration_hash


def test_no_discounts_survives_as_both_policy_constraint_and_action_allowlist() -> None:
    result = interpret_goal("Acquire 500 new customers in 20 days; budget: $900. No discounts.")
    assert result.status == "ready_for_review"
    assert result.draft is not None
    assert ActionType.CREATE_DISCOUNT not in result.draft.allowed_action_types
    assert (
        next(
            c.value
            for c in result.draft.resolved_constraints()
            if c.metric == MetricName.DISCOUNT_RATE
        )
        == 0
    )


def test_explicit_allowed_action_families_are_not_restored_to_defaults() -> None:
    result = interpret_goal(
        "Acquire 500 new customers in 20 days; budget: $900. Only search boosts."
    )
    assert result.status == "ready_for_review"
    assert result.draft is not None
    assert result.draft.allowed_action_types == {ActionType.SET_SEARCH_BOOST}


@pytest.mark.parametrize(
    ("text", "metric", "scope", "target"),
    [
        (
            "Clear 230 excess inventory units in 14 days; budget: $600",
            "units_sold",
            "excess_inventory",
            230,
        ),
        (
            "Reach 125 search purchases in 14 days; budget: $600",
            "search_attributed_purchases",
            "store",
            125,
        ),
        (
            "Prioritize contribution profit in 14 days; budget: $600",
            "contribution_profit",
            "store",
            None,
        ),
    ],
)
def test_measurable_objectives(text: str, metric: str, scope: str, target: int | None) -> None:
    result = interpret_goal(text)
    assert result.status == "ready_for_review", result
    assert result.draft is not None
    objective = result.draft.resolved_objective()
    assert objective.metric == metric and objective.scope == scope and objective.target == target


@pytest.mark.parametrize(
    "text",
    [
        "Maximize lifetime value in 30 days with a $100 budget",
        "Acquire 100 new customers in 30 days with a $100 budget. Refund unhappy customers.",
        "Acquire 100 new customers in 30 days with a $100 budget. Only act on Fridays.",
        "Acquire 100 new customers in 0 days with a $100 budget",
        "Acquire 100 new customers in 500 days with a $100 budget",
        "Acquire 100 new customers in 30 days with a $-100 budget",
        "Acquire 100 new customers in 30 days with a $1.001 budget",
        "Acquire 100 new customers in 30 days with a $100 budget. Margin below 25%.",
        "Reach 200 search conversion rate in 30 days with a $100 budget",
    ],
)
def test_unsupported_is_never_an_invented_acquisition_goal(text: str) -> None:
    result = interpret_goal(text)
    assert result.status == "unsupported", result
    assert result.draft is None and result.unsupported_requests


@pytest.mark.parametrize(
    "text",
    [
        "Acquire new customers with a $100 budget",
        "Acquire 100 new customers in 30 days",
        "Acquire 100 new customers in 30 days; budget: $100; budget: $200",
        "Acquire 100 new customers in 30 days; budget: $100. No discounts; discounts <= 10%.",
        "Acquire 100 new customers in 30 days; budget: $100. Margin >= 25%; margin >= 35%.",
    ],
)
def test_ambiguity_has_no_activatable_review_hash(text: str) -> None:
    result = interpret_goal(text)
    assert result.status == "clarification_required", result
    assert result.ambiguities and result.draft is not None
    assert result.draft.review_hash is None


def test_review_hash_rejects_changed_goal_values() -> None:
    result = interpret_goal("Acquire 100 new customers in 30 days with a $100 budget")
    assert result.draft is not None
    payload = result.draft.model_dump(mode="json")
    payload["target_value"] = "200"
    with pytest.raises(ValidationError, match="configuration changed"):
        GoalCreateRequest.model_validate(payload)


def test_unsupported_constraint_is_not_silently_stored_as_enforced() -> None:
    with pytest.raises(ValidationError, match="not enforced or monitored"):
        GoalCreateRequest.model_validate(
            {
                "constraints": [
                    {"metric": "inventory_days_of_supply", "operator": "lte", "value": "30"}
                ]
            }
        )
