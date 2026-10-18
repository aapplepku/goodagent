"""Provider-neutral merchandising constraints and exact unit economics."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import Field, field_serializer, model_validator

from open_commerce.core.enums import ActionType
from open_commerce.core.types import StrictDomainModel


class MerchandisingConstraints(StrictDomainModel):
    """Hard action/redemption bounds, not guarantees about realized store outcomes."""

    max_base_price_change: Decimal = Field(default=Decimal("0.10"), ge=0, le=Decimal("0.20"))
    max_cumulative_price_change: Decimal = Field(default=Decimal("0.15"), ge=0, le=Decimal("0.25"))
    max_effective_discount: Decimal = Field(default=Decimal("0.15"), ge=0, le=Decimal("0.30"))
    promotion_cap_minor: int = Field(default=0, ge=0, le=1_000_000)
    minimum_unit_margin: Decimal = Field(default=Decimal("0.25"), ge=0, lt=1)
    minimum_relevance: Decimal = Field(default=Decimal("0.55"), ge=Decimal("0.55"), le=1)
    require_available: Literal[True] = True
    price_cooldown_hours: int = Field(default=72, ge=24, le=720)
    max_duration_hours: int = Field(default=168, ge=24, le=720)
    prohibited_actions: set[ActionType] = Field(
        default_factory=lambda: {ActionType.SET_CAMPAIGN_BUDGET}
    )

    @model_validator(mode="after")
    def forbid_acquisition(self) -> "MerchandisingConstraints":
        if ActionType.SET_CAMPAIGN_BUDGET not in self.prohibited_actions:
            raise ValueError("merchandising cannot enable advertising actions")
        return self

    @field_serializer("prohibited_actions", when_used="json")
    def sorted_prohibitions(self, value: set[ActionType]) -> list[ActionType]:
        return sorted(value, key=lambda action: action.value)


class RecommendationControls(StrictDomainModel):
    """One PDP surface. Complements require explicit pairwise catalog evidence."""

    surface: Literal["product_detail"] = "product_detail"
    strategy: Literal["alternatives", "complements"] = "alternatives"
    excluded_product_ids: list[str] = Field(default_factory=list, max_length=100)
    require_available: Literal[True] = True
    max_per_brand: int = Field(default=2, ge=1, le=4)
    inventory_priority: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("0.15"))
    minimum_relevance: Decimal = Field(default=Decimal("0.55"), ge=Decimal("0.55"), le=1)
    limit: int = Field(default=4, ge=1, le=6)


class UnitEconomics(StrictDomainModel):
    """USD minor units. Net revenue already excludes the offered discount."""

    reference_price_minor: int = Field(gt=0)
    base_price_minor: int = Field(gt=0)
    effective_price_minor: int = Field(ge=0)
    cost_minor: int = Field(ge=0)
    variable_fee_minor: int = Field(ge=0)
    offered_discount_minor: int = Field(ge=0)
    promotion_redemption_value_minor: int = Field(ge=0)
    contribution_profit_minor: int
    unit_margin: Decimal | None
    effective_discount_rate: Decimal


def unit_economics(
    *,
    reference_price_minor: int,
    base_price_minor: int,
    effective_price_minor: int,
    cost_minor: int,
    fee_rate: Decimal,
    promotion_applied: bool,
) -> UnitEconomics:
    """Frozen reference prevents advertised savings inflation after a base-price rise.

    Promotion cap charge is max(0, min(reference, base) - effective) only for a
    redeemed promotion. Base-only markdowns are reported separately, not ad spend.
    This charge is not a causal estimate of incremental profit lost.
    """
    if not (0 <= effective_price_minor <= base_price_minor) or not 0 <= fee_rate <= 1:
        raise ValueError("invalid exact price or fee inputs")
    if reference_price_minor <= 0 or base_price_minor <= 0 or cost_minor < 0:
        raise ValueError("known nonnegative costs and positive prices are required")
    fee = int((effective_price_minor * fee_rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    profit = effective_price_minor - cost_minor - fee
    return UnitEconomics(
        reference_price_minor=reference_price_minor,
        base_price_minor=base_price_minor,
        effective_price_minor=effective_price_minor,
        cost_minor=cost_minor,
        variable_fee_minor=fee,
        offered_discount_minor=base_price_minor - effective_price_minor,
        promotion_redemption_value_minor=max(
            0, min(reference_price_minor, base_price_minor) - effective_price_minor
        )
        if promotion_applied
        else 0,
        contribution_profit_minor=profit,
        unit_margin=Decimal(profit) / effective_price_minor if effective_price_minor else None,
        effective_discount_rate=Decimal(max(0, reference_price_minor - effective_price_minor))
        / reference_price_minor,
    )


class EconomicCandidate(StrictDomainModel):
    """A finite exact offer, never an asserted optimal price or predicted profit."""

    id: str
    product_id: str
    variant_id: str
    base_price_minor: int
    promotion_rate: Decimal
    economics: UnitEconomics
    eligible: bool
    reason_codes: list[str]
    demand_response: Literal["insufficient_evidence"] = "insufficient_evidence"
    predicted_orders: None = None
    predicted_store_profit_minor: None = None
