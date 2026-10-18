"""Allowlisted merchandising observations shared by deterministic and model investigation."""

from typing import Literal
from uuid import UUID

from open_commerce.controller.merchandising_observation import observe_surface, recent_window
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash
from open_commerce.simulator.merchandising_economics import investigate_variant
from open_commerce.simulator.merchandising_models import ProductOutcomes
from open_commerce.simulator.models import SimulatorState

MERCHANDISING_LIMITATIONS = [
    "Synthetic recorded exposures and purchases, not merchant evidence or causal attribution.",
    "Known unit economics are exact; aggregate profit and demand response are not guaranteed.",
    "No identified causal elasticity; candidate predicted orders and profit remain unavailable.",
    "Promotion redemption value is not incremental profit lost; ad and model costs are separate.",
    "No latent preferences, future outcomes, customer attributes or free-form catalog text.",
]

MerchandisingView = Literal[
    "economics", "pricing", "products", "inventory", "outcomes", "search", "recommendations"
]


class MerchandisingEvidenceResponse(StrictDomainModel):
    evidence_ref: str
    observation_version: str
    view: MerchandisingView
    data: JsonObject
    limitations: list[str]


def merchandising_evidence(
    state: SimulatorState,
    *,
    tenant_id: UUID,
    view: str,
    product_id: str | None = None,
    category: str | None = None,
) -> JsonObject:
    if state.tenant_id != tenant_id or state.merchandising is None:
        raise ValueError("tenant-owned merchandising evidence required")
    merch = state.merchandising
    products = [
        p
        for p in sorted(state.products, key=lambda p: p.id)
        if (product_id is None or p.id == product_id)
        and (category is None or p.category == category)
    ]
    if product_id is not None and not products:
        raise ValueError("unknown scoped product ID")
    if category is not None and not products:
        raise ValueError("unknown category")
    selected = products[:5]
    selected_ids = {p.id for p in selected}
    data: JsonObject
    if view in {"economics", "pricing"}:
        data = {
            "items": [
                investigate_variant(
                    state, tenant_id=tenant_id, product_id=p.id, variant_id=v.id
                ).model_dump(mode="json")
                for p in selected
                for v in sorted(p.variants, key=lambda v: v.id)[:2]
            ],
            "selection": "first five scoped product IDs, first two variant IDs per product",
            "matching_product_count": len(products),
        }
    elif view in {"products", "inventory", "outcomes", "search", "recommendations"}:
        data = {
            "items": [
                {
                    "product_id": p.id,
                    "category": p.category,
                    "available_inventory": sum(v.inventory for v in p.variants if v.available),
                    "excess_inventory": p.excess_inventory,
                    "outcomes": merch.product_outcomes.get(p.id, ProductOutcomes()).model_dump(
                        mode="json"
                    ),
                }
                for p in selected
            ],
            "selection": "first five scoped IDs, not ranked by latent demand",
            "matching_product_count": len(products),
            "window": {"start": state.start_at.isoformat(), "end": state.current_time.isoformat()},
        }
        if view in {"search", "recommendations"}:
            surface = "search" if view == "search" else "product_detail"
            batches = [
                batch
                for batch in merch.serving_log.values()
                if batch.surface == surface
                and (
                    product_id is None
                    or product_id in batch.product_ids
                    or product_id == batch.anchor_product_id
                )
            ]
            data["recent_serving"] = [
                batch.model_dump(mode="json", exclude={"order_keys", "query"})
                for batch in sorted(batches, key=lambda b: (b.day, str(b.product_ids)))[-8:]
            ]
            data["matching_serving_batches"] = len(batches)
        if view == "recommendations":
            data["current_policy"] = merch.recommendation_policy.model_dump(
                mode="json", exclude={"command_key"}
            )
            data["explicit_compatibility"] = [
                item.model_dump(mode="json")
                for item in merch.compatibility
                if item.anchor_product_id in selected_ids
            ][:20]
        if view == "search":
            data["active_rules"] = [
                rule.model_dump(mode="json", exclude={"created_by_command"})
                for rule in state.search_boosts
                if rule.active and rule.starts_at <= state.current_time < rule.ends_at
            ][:8]
    else:
        raise ValueError("unsupported merchandising evidence view")
    start, end = recent_window(state)
    data["matched_surface_observations"] = [
        {
            "product_id": product.id,
            "search": observe_surface(
                merch, start=start, end=end, surface="search", product_ids={product.id}
            ).model_dump(mode="json", exclude={"queries"}),
            "product_detail": observe_surface(
                merch, start=start, end=end, surface="product_detail", product_ids={product.id}
            ).model_dump(mode="json", exclude={"queries"}),
        }
        for product in selected
    ]
    payload: JsonObject = {
        "view": view,
        "observation_version": state.state_hash,
        "data": data,
        "limitations": list(MERCHANDISING_LIMITATIONS),
    }
    return {"evidence_ref": canonical_hash(payload), **payload}
