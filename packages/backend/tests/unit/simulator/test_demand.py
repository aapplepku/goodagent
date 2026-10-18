from datetime import UTC, datetime
from decimal import Decimal

from open_commerce.simulator.demand import (
    campaign_quality,
    campaign_sessions,
    unit_contribution_minor,
    utility,
)
from open_commerce.simulator.models import CampaignState, CustomerSegment, EconomicParameters


def _segment(price_sensitivity: Decimal = Decimal("1.0")) -> CustomerSegment:
    return CustomerSegment(
        id="test",
        label="Test",
        share=Decimal("1"),
        price_sensitivity=price_sensitivity,
        quality_preference=Decimal("0.5"),
        discount_elasticity=Decimal("0.5"),
        category_affinities={"apparel": Decimal("1")},
    )


def test_higher_price_lowers_utility_under_fixed_inputs() -> None:
    segment = _segment()
    low_price = utility(
        relevance=Decimal("0.5"),
        segment=segment,
        product_quality=Decimal("0.7"),
        effective_price_minor_value=1_000,
        reference_price_minor=1_000,
        promotion_lift=Decimal("0"),
        personalization_affinity=Decimal("0.2"),
        seasonality=Decimal("0"),
        noise=Decimal("0"),
    )
    high_price = utility(
        relevance=Decimal("0.5"),
        segment=segment,
        product_quality=Decimal("0.7"),
        effective_price_minor_value=1_500,
        reference_price_minor=1_000,
        promotion_lift=Decimal("0"),
        personalization_affinity=Decimal("0.2"),
        seasonality=Decimal("0"),
        noise=Decimal("0"),
    )

    assert high_price < low_price


def test_discount_does_not_increase_unit_contribution() -> None:
    economics = EconomicParameters()
    without_discount = unit_contribution_minor(
        price_minor=10_000,
        cost_minor=4_000,
        discount_kind=None,
        discount_value=Decimal("0"),
        economics=economics,
    )
    with_discount = unit_contribution_minor(
        price_minor=10_000,
        cost_minor=4_000,
        discount_kind="percentage",
        discount_value=Decimal("0.15"),
        economics=economics,
    )

    assert with_discount < without_discount


def test_campaign_spend_has_diminishing_sessions_and_quality_saturation() -> None:
    low = campaign_sessions(budget_minor=10_000, max_reach=1_000, scale_minor=25_000)
    medium = campaign_sessions(budget_minor=20_000, max_reach=1_000, scale_minor=25_000)
    high = campaign_sessions(budget_minor=110_000, max_reach=1_000, scale_minor=25_000)
    very_high = campaign_sessions(budget_minor=120_000, max_reach=1_000, scale_minor=25_000)

    assert medium - low > very_high - high

    base = CampaignState(
        id="c",
        name="Campaign",
        channel_id="paid_search",
        daily_budget_minor=10_000,
        initial_daily_budget_minor=10_000,
        max_reach=1_000,
        scale_minor=25_000,
        baseline_quality=Decimal("0.70"),
        saturation_penalty=Decimal("0.20"),
    )
    saturated = base.model_copy(update={"daily_budget_minor": 60_000})

    assert campaign_quality(saturated) < campaign_quality(base)


def test_economic_parameters_require_aware_start_time_in_dependents() -> None:
    assert datetime(2026, 9, 1, tzinfo=UTC).tzinfo is not None
