"""Bounded read-only analytical tools, derived solely from observed catalog state."""

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from open_commerce.core.merchandising import EconomicCandidate, UnitEconomics, unit_economics
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash
from open_commerce.simulator.demand import effective_price_minor
from open_commerce.simulator.merchandising_models import ProductOutcomes
from open_commerce.simulator.models import (
    DiscountState,
    ProductState,
    ProductVariantState,
    SimulatorState,
)
from open_commerce.simulator.scenarios import get_scenario


class PromotionFact(StrictDomainModel):
    id: str
    kind: str
    value: Decimal
    new_customers_only: bool
    minimum_subtotal_minor: int | None
    remaining_offer_cap_minor: int | None


class VariantEconomicsReport(StrictDomainModel):
    tenant_id: UUID
    product_id: str
    variant_id: str
    current_version: int
    available_inventory: int
    current: UnitEconomics
    active_promotions: list[PromotionFact]
    stacking_policy: str = "best_single_eligible_promotion; no additive stacking"
    promotion_remaining_minor: int
    outcomes: ProductOutcomes
    observed_window_start: str
    observed_window_end: str
    prior_interventions: list[str] = Field(max_length=20)
    candidates: list[EconomicCandidate] = Field(max_length=15)
    demand_response_note: str = (
        "Observed conversion is descriptive, not identified causal elasticity. "
        "Demand response is insufficiently evidenced."
    )


def scoped_variant(
    state: SimulatorState, tenant_id: UUID, product_id: str, variant_id: str
) -> tuple[ProductState, ProductVariantState]:
    if state.tenant_id != tenant_id:
        raise ValueError("tenant mismatch")
    product = next((p for p in state.products if p.id == product_id), None)
    if product is None:
        raise ValueError("unknown scoped product")
    variant = next((v for v in product.variants if v.id == variant_id), None)
    if variant is None:
        raise ValueError("unknown scoped variant")
    return product, variant


def applicable_promotions(state: SimulatorState, product: ProductState) -> list[DiscountState]:
    return sorted(
        [d for d in state.discounts if d.applies_to(product, state.current_time)],
        key=lambda d: d.id,
    )


def offer_economics(
    state: SimulatorState,
    product: ProductState,
    variant: ProductVariantState,
    *,
    base_price_minor: int,
    promotion_rate: Decimal = Decimal(0),
) -> UnitEconomics:
    """Worst eligible known offer for bounds; customer conditions never relax safety."""
    if state.merchandising is None:
        raise ValueError("merchandising profile required")
    offers = [effective_price_minor(base_price_minor, "percentage", promotion_rate)]
    offers += [
        effective_price_minor(base_price_minor, d.discount_kind, d.value)
        for d in applicable_promotions(state, product)
    ]
    return unit_economics(
        reference_price_minor=state.merchandising.prices[variant.id].reference_price_minor,
        base_price_minor=base_price_minor,
        effective_price_minor=min(offers),
        cost_minor=variant.cost_minor,
        fee_rate=get_scenario(state.scenario_id).economics.payment_fee_rate,
        promotion_applied=min(offers) < base_price_minor,
    )


def candidate_economics(
    state: SimulatorState,
    *,
    tenant_id: UUID,
    product_id: str,
    variant_id: str,
    base_price_minor: int,
    promotion_rate: Decimal,
) -> EconomicCandidate:
    product, variant = scoped_variant(state, tenant_id, product_id, variant_id)
    merch = state.merchandising
    if merch is None:
        raise ValueError("merchandising profile required")
    if not Decimal(0) <= promotion_rate < Decimal(1):
        raise ValueError("finite fractional promotion rate required")
    economics = offer_economics(
        state, product, variant, base_price_minor=base_price_minor, promotion_rate=promotion_rate
    )
    limits = merch.constraints
    revision = merch.prices[variant.id]
    reasons = []
    delta = abs(base_price_minor - variant.price_minor)
    if Decimal(delta) / variant.price_minor > limits.max_base_price_change:
        reasons.append("BASE_PRICE_CHANGE_LIMIT")
    if (
        Decimal(revision.cumulative_change_minor + delta) / revision.reference_price_minor
        > limits.max_cumulative_price_change
    ):
        reasons.append("CUMULATIVE_PRICE_CHANGE_LIMIT")
    if (
        delta
        and revision.last_changed_at is not None
        and (state.current_time - revision.last_changed_at).total_seconds()
        < limits.price_cooldown_hours * 3600
    ):
        reasons.append("PRICE_COOLDOWN")
    if economics.effective_discount_rate > limits.max_effective_discount:
        reasons.append("COMBINED_EFFECTIVE_DISCOUNT_LIMIT")
    if economics.unit_margin is None or economics.unit_margin < limits.minimum_unit_margin:
        reasons.append("KNOWN_UNIT_ECONOMICS_FLOOR")
    if not variant.available or variant.inventory <= 5 or product.low_stock:
        reasons.append("UNAVAILABLE_OR_LOW_STOCK")
    if promotion_rate and (
        limits.max_effective_discount == 0
        or limits.promotion_cap_minor <= merch.promotion_spent_minor
    ):
        reasons.append("PROMOTIONS_PROHIBITED_OR_CAP_EXHAUSTED")
    return EconomicCandidate(
        id=canonical_hash(
            {
                "variant": variant.id,
                "version": revision.version,
                "base": base_price_minor,
                "promotion": promotion_rate,
            }
        ),
        product_id=product.id,
        variant_id=variant.id,
        base_price_minor=base_price_minor,
        promotion_rate=promotion_rate,
        economics=economics,
        eligible=not reasons,
        reason_codes=reasons,
    )


def investigate_variant(
    state: SimulatorState, *, tenant_id: UUID, product_id: str, variant_id: str
) -> VariantEconomicsReport:
    product, variant = scoped_variant(state, tenant_id, product_id, variant_id)
    merch = state.merchandising
    if merch is None:
        raise ValueError("merchandising profile required")
    step = min(Decimal("0.05"), merch.constraints.max_base_price_change)
    bases = sorted(
        {
            variant.price_minor,
            max(1, int(variant.price_minor * (1 - step))),
            int(variant.price_minor * (1 + step)),
        }
    )
    rates = sorted(
        {
            Decimal(0),
            min(Decimal("0.05"), merch.constraints.max_effective_discount),
            min(Decimal("0.10"), merch.constraints.max_effective_discount),
        }
    )
    return VariantEconomicsReport(
        tenant_id=tenant_id,
        product_id=product.id,
        variant_id=variant.id,
        current_version=merch.prices[variant.id].version,
        available_inventory=variant.inventory if variant.available else 0,
        current=offer_economics(state, product, variant, base_price_minor=variant.price_minor),
        active_promotions=[
            PromotionFact(
                id=d.id,
                kind=d.discount_kind,
                value=d.value,
                new_customers_only=d.new_customers_only,
                minimum_subtotal_minor=d.minimum_subtotal_minor,
                remaining_offer_cap_minor=max(0, d.maximum_cost_minor - d.spent_minor)
                if d.maximum_cost_minor is not None
                else None,
            )
            for d in applicable_promotions(state, product)
        ],
        promotion_remaining_minor=max(
            0, merch.constraints.promotion_cap_minor - merch.promotion_spent_minor
        ),
        outcomes=merch.product_outcomes.get(product.id, ProductOutcomes()).model_copy(deep=True),
        observed_window_start=state.start_at.isoformat(),
        observed_window_end=state.current_time.isoformat(),
        prior_interventions=[
            str(r.execution_id)
            for r in state.command_history
            if intervention_targets(r.before_state, product.id, variant.id)
            or intervention_targets(r.after_state or {}, product.id, variant.id)
        ][-20:],
        candidates=[
            candidate_economics(
                state,
                tenant_id=tenant_id,
                product_id=product.id,
                variant_id=variant.id,
                base_price_minor=base,
                promotion_rate=rate,
            )
            for base in bases
            for rate in rates
        ],
    )


def intervention_targets(payload: JsonObject, product_id: str, variant_id: str) -> bool:
    """Read only the provider receipt's defined scope fields, never substring-match IDs."""
    changes = payload.get("changes")
    if isinstance(changes, list) and any(
        isinstance(change, dict) and change.get("variant_id") == variant_id for change in changes
    ):
        return True
    for key in ("discount", "search_boost"):
        entity = payload.get(key)
        if isinstance(entity, dict) and product_id in entity.get("product_ids", []):
            return True
    return False
