"""Exact unit math is independent of model claims and aggregate forecasts."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import ActionType, MetricName
from open_commerce.core.merchandising import MerchandisingConstraints, unit_economics


def test_net_revenue_does_not_subtract_discount_twice() -> None:
    value = unit_economics(
        reference_price_minor=1000,
        base_price_minor=900,
        effective_price_minor=810,
        cost_minor=500,
        fee_rate=Decimal("0.029"),
        promotion_applied=True,
    )
    assert value.offered_discount_minor == 90
    assert value.variable_fee_minor == 23
    assert value.contribution_profit_minor == 287
    assert value.promotion_redemption_value_minor == 90
    assert value.effective_discount_rate == Decimal("0.19")


def test_raising_base_does_not_inflate_reference_or_cap_charge() -> None:
    value = unit_economics(
        reference_price_minor=1000,
        base_price_minor=1100,
        effective_price_minor=990,
        cost_minor=500,
        fee_rate=Decimal(0),
        promotion_applied=True,
    )
    assert value.offered_discount_minor == 110
    assert value.promotion_redemption_value_minor == 10
    assert value.reference_price_minor == 1000


def test_base_markdown_is_not_promotion_or_ad_spend() -> None:
    value = unit_economics(
        reference_price_minor=1000,
        base_price_minor=900,
        effective_price_minor=900,
        cost_minor=500,
        fee_rate=Decimal(0),
        promotion_applied=False,
    )
    assert value.promotion_redemption_value_minor == 0
    assert value.contribution_profit_minor == 400


def test_profile_cannot_enable_acquisition_and_accepts_no_discounts() -> None:
    with pytest.raises(ValidationError, match="advertising"):
        MerchandisingConstraints(prohibited_actions=set())
    constraints = MerchandisingConstraints(max_effective_discount=Decimal(0))
    assert constraints.promotion_cap_minor == 0


def test_search_only_goal_needs_neither_acquisition_budget_nor_cac() -> None:
    request = GoalCreateRequest(
        merchandising=MerchandisingConstraints(max_effective_discount=Decimal(0)),
        allowed_action_types={ActionType.SET_SEARCH_BOOST, ActionType.NO_OP},
    )
    assert request.budget.amount_minor == request.daily_budget.amount_minor == 0
    assert request.resolved_objective().metric == MetricName.CONTRIBUTION_PROFIT
    assert request.resolved_constraints() == []
    with pytest.raises(ValidationError, match="prohibited"):
        GoalCreateRequest(
            merchandising=MerchandisingConstraints(),
            allowed_action_types={ActionType.SET_CAMPAIGN_BUDGET},
        )


def test_legacy_serialization_omits_absent_profile() -> None:
    assert "merchandising" not in GoalCreateRequest().model_dump(mode="json")
