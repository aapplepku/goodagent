"""Read-only projections for optimistic concurrency and reconciliation."""

from open_commerce.core.actions import (
    ActionIntent,
    CreateDiscountIntent,
    DisableDiscountIntent,
    SetCampaignBudgetIntent,
    SetRecommendationPolicyIntent,
    SetSearchBoostIntent,
    SetVariantPriceIntent,
)
from open_commerce.core.types import JsonObject
from open_commerce.simulator.models import SimulatorCommandRecord, SimulatorState


def target_state(state: SimulatorState, intent: ActionIntent) -> JsonObject:
    """Capture only entities that the compiled intent can affect."""
    if isinstance(intent, SetRecommendationPolicyIntent):
        return (
            {
                "recommendation_policy": state.merchandising.recommendation_policy.model_dump(
                    mode="json"
                ),
                "compatibility": [
                    c.model_dump(mode="json") for c in state.merchandising.compatibility
                ],
            }
            if state.merchandising
            else {"missing_profile": True}
        )
    if isinstance(intent, SetCampaignBudgetIntent):
        campaign = next((item for item in state.campaigns if item.id == intent.campaign_id), None)
        return {"campaign": campaign.model_dump(mode="json") if campaign else None}
    if isinstance(intent, SetVariantPriceIntent):
        ids = {change.variant_id for change in intent.changes}
        return {
            **(
                {
                    "price_revisions": {
                        key: value.model_dump(mode="json")
                        for key, value in state.merchandising.prices.items()
                        if key in ids
                    },
                    "active_promotions": [
                        d.model_dump(
                            mode="json", exclude={"spent_minor", "spend_cap_for_day_minor"}
                        )
                        for d in state.discounts
                        if d.active
                    ],
                }
                if state.merchandising
                else {}
            ),
            "variants": [
                variant.model_dump(mode="json")
                for product in state.products
                for variant in product.variants
                if variant.id in ids
            ],
        }
    if isinstance(intent, DisableDiscountIntent):
        discount = next(
            (item for item in state.discounts if item.id == intent.provider_discount_id), None
        )
        return {"discount": discount.model_dump(mode="json") if discount else None}
    if isinstance(intent, CreateDiscountIntent | SetSearchBoostIntent):
        scope = intent.product_scope
        products = [
            product.model_dump(mode="json")
            for product in state.products
            if product.id in scope.product_ids
            or (not scope.product_ids and product.category in scope.category_paths)
        ]
        if isinstance(intent, CreateDiscountIntent):
            active = [item.model_dump(mode="json") for item in state.discounts if item.active]
        else:
            active = [item.model_dump(mode="json") for item in state.search_boosts if item.active]
        return {"products": products, "active_rules": active}
    return {}


def observed_command_state(state: SimulatorState, record: SimulatorCommandRecord) -> JsonObject:
    """Read the current target, never echo the stored expected result."""
    expected = record.after_state or {}
    if record.action_type == "set_recommendation_policy":
        return (
            {
                "recommendation_policy": state.merchandising.recommendation_policy.model_dump(
                    mode="json"
                )
            }
            if state.merchandising
            else {"missing_profile": True}
        )
    if record.action_type == "rollback":
        source = next(
            (item for item in state.command_history if item.execution_id == record.rollback_of),
            None,
        )
        return observed_command_state(state, source) if source else {"missing_source": True}
    if record.action_type in {"create_discount", "disable_discount"}:
        payload = expected.get("discount")
        target_id = payload.get("id") if isinstance(payload, dict) else None
        target = next((item for item in state.discounts if item.id == target_id), None)
        return {
            "discount": target.model_dump(
                mode="json", exclude={"spent_minor", "spend_cap_for_day_minor"}
            )
            if target
            else None
        }
    if record.action_type == "set_search_boost":
        payload = expected.get("search_boost")
        target_id = payload.get("id") if isinstance(payload, dict) else None
        boost = next((item for item in state.search_boosts if item.id == target_id), None)
        return {"search_boost": boost.model_dump(mode="json") if boost else None}
    if record.action_type == "set_campaign_budget":
        campaign = next(
            (item for item in state.campaigns if item.id == expected.get("campaign_id")), None
        )
        return (
            {"campaign_id": campaign.id, "daily_budget_minor": campaign.daily_budget_minor}
            if campaign
            else {"missing_target": True}
        )
    if record.action_type == "set_variant_price":
        changes = expected.get("changes", [])
        ids = (
            [str(item.get("variant_id")) for item in changes if isinstance(item, dict)]
            if isinstance(changes, list)
            else []
        )
        variants = {
            variant.id: variant for product in state.products for variant in product.variants
        }
        return {
            "changes": [
                {
                    "variant_id": variant_id,
                    "price_minor": variants[variant_id].price_minor,
                    **(
                        {
                            "price_revision": state.merchandising.prices[variant_id].model_dump(
                                mode="json"
                            )
                        }
                        if state.merchandising
                        else {}
                    ),
                }
                if variant_id in variants
                else {"variant_id": variant_id, "missing_target": True}
                for variant_id in ids
            ]
        }
    return {}
