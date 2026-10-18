"""Compiler safety facts derived from authoritative simulator records."""

from decimal import Decimal

from open_commerce.core.actions import (
    ActionIntent,
    CreateDiscountIntent,
    SetCampaignBudgetIntent,
    SetRecommendationPolicyIntent,
    SetSearchBoostIntent,
    SetVariantPriceIntent,
)
from open_commerce.core.types import JsonObject, canonical_hash
from open_commerce.simulator.demand import effective_price_minor, variable_fee_minor
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.scenarios import get_scenario


def safety_facts(state: SimulatorState, intent: ActionIntent) -> JsonObject:
    """Ignore planner claims about costs, margin, inventory, relevance and deltas."""
    facts = _base_safety_facts(state, intent)
    if state.merchandising is not None:
        facts.update(_merchandising_safety_facts(state, intent))
    return facts


def _base_safety_facts(state: SimulatorState, intent: ActionIntent) -> JsonObject:
    economics = get_scenario(state.scenario_id).economics
    if isinstance(intent, SetCampaignBudgetIntent):
        campaign = next((item for item in state.campaigns if item.id == intent.campaign_id), None)
        if campaign is None:
            raise ValueError("unknown campaign target")
        current = campaign.daily_budget_minor
        delta = abs(intent.new_budget.amount_minor - current)
        return {
            "current_budget_minor": current,
            "new_budget_minor": intent.new_budget.amount_minor,
            "budget_change_rate": str(
                Decimal(delta) / Decimal(current)
                if current
                else Decimal(1)
                if delta
                else Decimal(0)
            ),
        }
    if isinstance(intent, SetVariantPriceIntent):
        variants = {
            variant.id: (product, variant)
            for product in state.products
            for variant in product.variants
        }
        margins = []
        deltas = []
        low_stock = False
        for change in intent.changes:
            match = variants.get(change.variant_id)
            if match is None or match[0].id != change.product_id:
                raise ValueError("unknown price target")
            product, variant = match
            price = change.new_price.amount_minor
            if price <= 0 or change.new_price.currency != variant.currency:
                raise ValueError("invalid target price or currency")
            margins.append(
                Decimal(price - variant.cost_minor - variable_fee_minor(price, economics))
                / Decimal(price)
            )
            deltas.append(Decimal(abs(price - variant.price_minor)) / Decimal(variant.price_minor))
            low_stock |= product.low_stock or variant.inventory <= 5 or not variant.available
        return {
            "known_cost_basis": True,
            "projected_margin_rate": str(min(margins)),
            "max_price_delta_rate": str(max(deltas)),
            "targets_low_stock": low_stock,
        }
    if isinstance(intent, CreateDiscountIntent | SetSearchBoostIntent):
        scope = intent.product_scope
        products = [
            item
            for item in state.products
            if item.id in scope.product_ids
            or (not scope.product_ids and item.category in scope.category_paths)
        ]
        if not products or set(scope.product_ids) - {item.id for item in products}:
            raise ValueError("empty or unknown product scope")
        variants_in_scope = [variant for product in products for variant in product.variants]
        facts: JsonObject = {
            "targets_low_stock": any(product.low_stock for product in products)
            or any(variant.inventory <= 5 or not variant.available for variant in variants_in_scope)
        }
        if isinstance(intent, CreateDiscountIntent):
            margins = []
            for variant in variants_in_scope:
                price = effective_price_minor(
                    variant.price_minor, intent.discount_kind, intent.value
                )
                margin = (
                    Decimal(price - variant.cost_minor - variable_fee_minor(price, economics))
                    / Decimal(price)
                    if price
                    else Decimal(-1)
                )
                margins.append(margin)
            facts.update(
                {
                    "known_cost_basis": True,
                    "projected_margin_rate": str(min(margins)),
                    "discount_percentage": str(intent.value),
                }
            )
        else:
            # v0.1 compiler only supports exact category merchandising queries.
            query = str(intent.query_pattern.get("text", "")).strip().casefold()
            relevance = min(
                Decimal(1) if query == product.category.casefold() else Decimal(0)
                for product in products
            )
            facts.update(
                {"min_relevance_score": str(relevance), "multiplier": str(intent.multiplier)}
            )
        return facts
    return {}


def _merchandising_safety_facts(state: SimulatorState, intent: ActionIntent) -> JsonObject:
    from open_commerce.simulator.merchandising_economics import candidate_economics

    merch = state.merchandising
    assert merch is not None
    errors: list[str] = []
    facts: JsonObject = {"merchandising_constraints_hash": canonical_hash(merch.constraints)}
    margins: list[Decimal] = []
    if isinstance(intent, SetVariantPriceIntent | CreateDiscountIntent):
        for product in state.products:
            for variant in product.variants:
                if isinstance(intent, SetVariantPriceIntent):
                    change = next((c for c in intent.changes if c.variant_id == variant.id), None)
                    if change is None:
                        continue
                    if (intent.current_versions or {}).get(variant.id) != merch.prices[
                        variant.id
                    ].version or change.current_price.amount_minor != variant.price_minor:
                        errors.append("STALE_PRICE_VERSION")
                    base, rate = change.new_price.amount_minor, Decimal(0)
                else:
                    if product.id not in intent.product_scope.product_ids:
                        continue
                    if (
                        intent.discount_kind != "percentage"
                        or intent.customer_scope.new_customers_only
                        or intent.customer_scope.segment != "all"
                    ):
                        errors.append("UNSUPPORTED_MERCHANDISING_PROMOTION")
                    base, rate = variant.price_minor, intent.value
                candidate = candidate_economics(
                    state,
                    tenant_id=state.tenant_id,
                    product_id=product.id,
                    variant_id=variant.id,
                    base_price_minor=base,
                    promotion_rate=rate,
                )
                errors += candidate.reason_codes
                margins.append(
                    candidate.economics.unit_margin
                    if candidate.economics.unit_margin is not None
                    else Decimal(-1)
                )
        if not margins:
            errors.append("EMPTY_SCOPE")
        facts["projected_margin_rate"] = str(min(margins)) if margins else None
        facts["known_cost_basis"] = bool(margins)
        if isinstance(intent, SetVariantPriceIntent):
            window = intent.window
            if (
                window is None
                or window.start_at != state.current_time
                or (window.end_at - window.start_at).total_seconds()
                > merch.constraints.max_duration_hours * 3600
            ):
                errors.append("INVALID_PRICE_WINDOW")
        else:
            if (
                not intent.product_scope.product_ids
                or intent.product_scope.category_paths
                or intent.product_scope.tags
            ):
                errors.append("EXPLICIT_PRODUCT_SCOPE_REQUIRED")
            if (
                intent.starts_at != state.current_time
                or (intent.ends_at - intent.starts_at).total_seconds()
                > merch.constraints.max_duration_hours * 3600
            ):
                errors.append("INVALID_PROMOTION_WINDOW")
            remaining = merch.constraints.promotion_cap_minor - merch.promotion_spent_minor
            if intent.maximum_cost_minor is None or intent.maximum_cost_minor > remaining:
                errors.append("PROMOTION_CAP_EXCEEDED")
    if isinstance(intent, SetRecommendationPolicyIntent):
        if intent.expected_version != merch.recommendation_policy.version:
            errors.append("STALE_RECOMMENDATION_POLICY_VERSION")
        if intent.controls.minimum_relevance < merch.constraints.minimum_relevance:
            errors.append("RECOMMENDATION_RELEVANCE_FLOOR")
        if set(intent.controls.excluded_product_ids) - {p.id for p in state.products}:
            errors.append("UNKNOWN_RECOMMENDATION_EXCLUSION")
        if intent.controls.strategy == "complements" and not merch.compatibility:
            errors.append("NO_EXPLICIT_COMPATIBILITY_EVIDENCE")
        if (
            intent.window.start_at != state.current_time
            or (intent.window.end_at - intent.window.start_at).total_seconds()
            > merch.constraints.max_duration_hours * 3600
        ):
            errors.append("INVALID_RECOMMENDATION_WINDOW")
    facts["merchandising_errors"] = sorted(set(errors))
    return facts
