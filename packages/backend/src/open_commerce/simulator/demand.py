"""Inspectable simulator demand and economics formulas."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from open_commerce.simulator.models import CampaignState, CustomerSegment, EconomicParameters


def sigmoid(value: Decimal) -> Decimal:
    """Return a logistic probability for an inspectable Decimal input."""

    numeric = float(value)
    return Decimal(str(1 / (1 + math.exp(-numeric))))


def campaign_sessions(budget_minor: int, max_reach: int, scale_minor: int) -> int:
    """sessions_c(budget) = max_reach_c * (1 - exp(-budget / scale_c))."""

    if budget_minor <= 0:
        return 0
    sessions = max_reach * (1 - math.exp(-budget_minor / scale_minor))
    return max(0, int(round(sessions)))


def campaign_quality(campaign: CampaignState) -> Decimal:
    """conversion_quality_c(budget) = baseline_quality_c - saturation_penalty_c * utilization."""

    utilization = Decimal(campaign.daily_budget_minor) / Decimal(campaign.scale_minor)
    bounded_utilization = min(utilization, Decimal("1"))
    quality = campaign.baseline_quality - campaign.saturation_penalty * bounded_utilization
    return max(Decimal("0"), min(Decimal("1"), quality))


def effective_price_minor(
    price_minor: int, discount_kind: str | None, discount_value: Decimal
) -> int:
    """Return effective unit price after a simulator discount."""

    if discount_kind is None:
        return price_minor
    if discount_kind == "percentage":
        discounted = Decimal(price_minor) * (Decimal("1") - discount_value)
    elif discount_kind == "fixed_amount":
        discounted = Decimal(price_minor) - discount_value
    else:
        raise ValueError(f"unsupported discount kind: {discount_kind}")
    return max(0, int(discounted.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def variable_fee_minor(net_revenue_minor: int, economics: EconomicParameters) -> int:
    """Calculate the variable payment fee in minor units."""

    fee = Decimal(net_revenue_minor) * economics.payment_fee_rate
    return int(fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def unit_contribution_minor(
    *,
    price_minor: int,
    cost_minor: int,
    discount_kind: str | None,
    discount_value: Decimal,
    economics: EconomicParameters,
) -> int:
    """Return contribution before ad spend for one sold unit."""

    effective_price = effective_price_minor(price_minor, discount_kind, discount_value)
    discount_minor = price_minor - effective_price
    fee_minor = variable_fee_minor(effective_price, economics)
    return price_minor - discount_minor - cost_minor - fee_minor


def price_term(
    *,
    effective_price_minor_value: int,
    reference_price_minor: int,
    price_sensitivity: Decimal,
) -> Decimal:
    """Price sensitivity term used in utility; higher price lowers utility."""

    reference = max(reference_price_minor, 1)
    effective = max(effective_price_minor_value, 1)
    return -price_sensitivity * Decimal(str(math.log(effective / reference)))


def utility(
    *,
    relevance: Decimal,
    segment: CustomerSegment,
    product_quality: Decimal,
    effective_price_minor_value: int,
    reference_price_minor: int,
    promotion_lift: Decimal,
    personalization_affinity: Decimal,
    seasonality: Decimal,
    noise: Decimal,
) -> Decimal:
    """Inspectable demand utility for one segment/product exposure."""

    return (
        relevance
        + segment.quality_preference * product_quality
        + price_term(
            effective_price_minor_value=effective_price_minor_value,
            reference_price_minor=reference_price_minor,
            price_sensitivity=segment.price_sensitivity,
        )
        + promotion_lift
        + personalization_affinity
        + seasonality
        + noise
        + segment.base_conversion_adjustment
    )


def click_probability(
    *,
    utility_value: Decimal,
    position: int,
    economics: EconomicParameters,
) -> Decimal:
    """P(click) = sigmoid(click_intercept + utility + position_bias)."""

    position_bias = Decimal("0.58") / Decimal(position)
    return sigmoid(economics.click_intercept + utility_value + position_bias)


def purchase_probability(
    *,
    utility_value: Decimal,
    economics: EconomicParameters,
    availability: Decimal,
    campaign_quality_value: Decimal,
) -> Decimal:
    """P(purchase|click) with trust, availability, campaign quality, and friction."""

    return sigmoid(
        economics.conversion_intercept
        + utility_value
        + economics.trust
        + availability
        + campaign_quality_value
        - economics.shipping_friction
    )
