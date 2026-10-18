"""Atomic state transitions for the isolated merchandising simulator profile."""

from uuid import UUID

from open_commerce.core.merchandising import MerchandisingConstraints, unit_economics
from open_commerce.core.types import canonical_hash
from open_commerce.simulator.demand import effective_price_minor
from open_commerce.simulator.merchandising_catalog import generate_merchandising_catalog
from open_commerce.simulator.merchandising_economics import scoped_variant
from open_commerce.simulator.merchandising_models import (
    MERCHANDISING_ENGINE_VERSION,
    MerchandisingState,
    PriceRevision,
    ProductOutcomes,
    PromotionRedemption,
)
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.scenarios import get_scenario


def initialize_merchandising(
    state: SimulatorState, *, tenant_id: UUID, constraints: MerchandisingConstraints
) -> None:
    """Only a fresh instance can select this engine; never relabel old observations."""
    if state.tenant_id != tenant_id or state.day or state.command_history or state.merchandising:
        raise ValueError("merchandising requires a fresh tenant-owned simulator")
    state.products, compatibility = generate_merchandising_catalog(state.seed)
    state.merchandising = MerchandisingState(
        constraints=constraints.model_copy(deep=True),
        compatibility=compatibility,
        prices={
            v.id: PriceRevision(reference_price_minor=v.original_price_minor)
            for p in state.products
            for v in p.variants
        },
    )
    state.engine_version = MERCHANDISING_ENGINE_VERSION
    # Generated legacy warmup is not merchandising serving evidence.
    state.metrics = []
    state.events = []
    state.snapshots = []
    state.start_at = state.current_time
    state.ad_spend_limit_minor = 0


def redeem_order(
    state: SimulatorState,
    *,
    tenant_id: UUID,
    order_key: str,
    product_id: str,
    variant_id: str,
    expected_price_version: int,
    discount_id: str | None,
    new_customer: bool = False,
) -> PromotionRedemption:
    """Order, inventory and cap counters mutate together in the caller's transaction.

    Durable callers MUST hold RuntimeDatabase's tenant write lock until save/commit.
    Replays, including declines, preserve the original decision and never spend twice.
    """
    product, variant = scoped_variant(state, tenant_id, product_id, variant_id)
    merch = state.merchandising
    if merch is None or not order_key or len(order_key) > 180:
        raise ValueError("bounded order key and merchandising profile required")
    request_hash = canonical_hash(
        {
            "product_id": product_id,
            "variant_id": variant_id,
            "expected_price_version": expected_price_version,
            "discount_id": discount_id,
            "new_customer": new_customer,
        }
    )
    prior = merch.redemptions.get(order_key)
    if prior is not None:
        if prior.request_hash != request_hash:
            raise ValueError("order idempotency key reused with different request")
        return prior.model_copy(deep=True)
    revision = merch.prices[variant_id]
    discount = next((d for d in state.discounts if d.id == discount_id), None)
    reason = "ELIGIBLE"
    if expected_price_version != revision.version:
        reason = "STALE_PRICE_VERSION"
    elif not variant.available or variant.inventory == 0:
        reason = "UNAVAILABLE"
    elif discount_id is not None and (
        discount is None
        or not discount.applies_to(product, state.current_time)
        or (discount.new_customers_only and not new_customer)
        or variant.price_minor < (discount.minimum_subtotal_minor or 0)
    ):
        reason = "INELIGIBLE_PROMOTION"
    elif discount is not None and (product.low_stock or variant.inventory <= 5):
        reason = "LOW_STOCK_PROMOTION"
    effective = (
        effective_price_minor(variant.price_minor, discount.discount_kind, discount.value)
        if discount
        else variant.price_minor
    )
    economics = unit_economics(
        reference_price_minor=revision.reference_price_minor,
        base_price_minor=variant.price_minor,
        effective_price_minor=effective,
        cost_minor=variant.cost_minor,
        fee_rate=get_scenario(state.scenario_id).economics.payment_fee_rate,
        promotion_applied=discount is not None,
    )
    value = economics.promotion_redemption_value_minor
    if reason == "ELIGIBLE":
        if economics.effective_discount_rate > merch.constraints.max_effective_discount:
            reason = "COMBINED_EFFECTIVE_DISCOUNT_LIMIT"
        elif (
            economics.unit_margin is None
            or economics.unit_margin < merch.constraints.minimum_unit_margin
        ):
            reason = "KNOWN_UNIT_ECONOMICS_FLOOR"
        elif merch.promotion_spent_minor + value > merch.constraints.promotion_cap_minor:
            reason = "PROMOTION_CAP_EXHAUSTED"
        elif (
            discount is not None
            and discount.maximum_cost_minor is not None
            and discount.spent_minor + value > discount.maximum_cost_minor
        ):
            reason = "OFFER_CAP_EXHAUSTED"
    receipt = PromotionRedemption(
        order_key=order_key,
        request_hash=request_hash,
        product_id=product_id,
        variant_id=variant_id,
        discount_id=discount_id,
        occurred_at=state.current_time,
        status="redeemed" if reason == "ELIGIBLE" else "declined",
        reason=reason,
        economics=economics,
    )
    if receipt.status == "redeemed":
        merch.promotion_spent_minor += value
        if discount is not None:
            discount.spent_minor += value
        variant.inventory -= 1
        observed = merch.product_outcomes.setdefault(product_id, ProductOutcomes())
        observed.orders += 1
        observed.units += 1
        observed.net_revenue_minor += effective
        observed.contribution_profit_minor += economics.contribution_profit_minor
        observed.redemption_value_minor += value
    merch.redemptions[order_key] = receipt
    return receipt.model_copy(deep=True)
