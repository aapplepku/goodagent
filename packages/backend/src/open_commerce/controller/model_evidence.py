"""Allowlisted simulator observations for the read-only model tool boundary."""

from sqlalchemy import select

from open_commerce.controller.merchandising_evidence import (
    MERCHANDISING_LIMITATIONS,
    merchandising_evidence,
)
from open_commerce.controller.model_protocol import InspectTool
from open_commerce.controller.models import ControllerActionRecord, GoalRecord
from open_commerce.controller.objectives import objective_value
from open_commerce.core.types import JsonObject, canonical_hash
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.repositories.budgets import SqlBudgetRepository
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.simulator.models import SimulatorState

SUPPORTED_SOFT_PREFERENCES = {
    "prefer search boosts",
    "prefer lower spend",
    "prefer reversible actions",
    "avoid unnecessary interventions",
    "prefer no discounts",
}

LIMITATIONS = [
    "Synthetic observations only; no future events or hidden demand parameters.",
    "No per-product conversion or per-campaign outcome attribution is recorded.",
    "Inventory deltas are observed cumulative units, not causal action effects.",
    "Aggregate measurement windows may overlap; pending/insufficient is not success.",
    "No calibrated effect estimates; CAC is an uncertain observed outcome.",
    "Free-form catalog titles/descriptions and customer data are deliberately omitted.",
]


def prior_evidence(records: list[ControllerActionRecord]) -> list[JsonObject]:
    result: list[JsonObject] = []
    for record in sorted(records, key=lambda r: (r.created_at, str(r.action.id)))[-8:]:
        action = record.action
        result.append(
            {
                "action_id": str(action.id),
                "run_id": str(action.run_id),
                "action_type": action.intent.type,
                "status": action.status.value,
                "parameters": action.normalized_parameters,
                "receipt_status": record.execution_result.status.value
                if record.execution_result
                else None,
                "measurement": record.measurement.model_dump(mode="json")
                if record.measurement
                else None,
                "outcome": record.outcome.model_dump(mode="json") if record.outcome else None,
            }
        )
    return result


async def budget_evidence(
    repo: ControllerRepository, goal: GoalRecord, state: SimulatorState
) -> list[JsonObject]:
    accounts = await repo.session.scalars(
        select(BudgetAccountRecord)
        .where(
            BudgetAccountRecord.tenant_id == repo.tenant_id,
            BudgetAccountRecord.goal_id == goal.spec.id,
            BudgetAccountRecord.period_start <= state.current_time,
            BudgetAccountRecord.period_end > state.current_time,
        )
        .order_by(BudgetAccountRecord.budget_kind)
    )
    ledger = SqlBudgetRepository(repo.session)
    return [
        {
            "kind": a.budget_kind,
            "allocated_minor": a.allocated_minor,
            "available_minor": await ledger.available_minor(repo.tenant_id, a.id),
            "currency": a.currency,
        }
        for a in accounts
    ]


def overview(
    goal: GoalRecord, state: SimulatorState, budgets: list[JsonObject], prior: list[JsonObject]
) -> JsonObject:
    if goal.spec.tenant_id != state.tenant_id:
        raise ValueError("evidence tenant mismatch")
    value = objective_value(goal.spec.objective, state)
    payload: JsonObject = {
        "goal_revision": goal.revision,
        "soft_preferences": [
            p.lower().strip()
            for p in goal.soft_preferences
            if p.lower().strip() in SUPPORTED_SOFT_PREFERENCES
        ],
        "unsupported_soft_preferences_count": sum(
            p.lower().strip() not in SUPPORTED_SOFT_PREFERENCES for p in goal.soft_preferences
        ),
        "goal": goal.spec.model_dump(
            mode="json",
            include={
                "objective",
                "horizon",
                "constraints",
                "allowed_action_types",
                "autonomy",
                "merchandising",
            },
        ),
        "observation_version": state.state_hash,
        "as_of": state.current_time.isoformat(),
        "virtual_day": state.day,
        "observed_objective_value": str(value) if value is not None else None,
        "business_budgets": budgets,
        "capabilities": ["create_discount", "set_campaign_budget", "set_search_boost"],
        "categories": sorted({p.category for p in state.products}),
        "daily_metrics": [m.model_dump(mode="json") for m in state.metrics[-7:]],
        "prior_interventions": prior,
        "limitations": list(LIMITATIONS),
    }
    if state.merchandising is not None:
        payload["capabilities"] = sorted(a.value for a in goal.spec.allowed_action_types)
        payload["limitations"] = list(MERCHANDISING_LIMITATIONS)
        payload["promotion_ledger"] = {
            "cap_minor": state.merchandising.constraints.promotion_cap_minor,
            "redeemed_value_minor": state.merchandising.promotion_spent_minor,
            "basis": "max(0, min(frozen_reference, base) - effective), redeemed promotions only",
            "ad_spend_minor": 0,
        }
    return {"evidence_ref": canonical_hash(payload), **payload}


def inspect_evidence(
    request: InspectTool, state: SimulatorState, prior: list[JsonObject]
) -> JsonObject:
    if state.merchandising is not None:
        return merchandising_evidence(
            state,
            tenant_id=state.tenant_id,
            view=request.view,
            product_id=request.entity_id,
            category=request.category,
        )
    categories = {p.category for p in state.products}
    if request.category is not None and request.category not in categories:
        raise ValueError("unknown evidence category")
    products = [
        p for p in state.products if request.category is None or p.category == request.category
    ]
    if request.entity_id is not None:
        if request.view in {"products", "inventory"}:
            products = [p for p in products if p.id == request.entity_id]
            if not products:
                raise ValueError("unknown product ID")
        elif request.view != "campaigns":
            raise ValueError("this tool does not accept entity IDs")
    data: JsonObject
    if request.view == "products":
        data = {
            "items": [
                {
                    "id": p.id,
                    "category": p.category,
                    "inventory_units": p.total_inventory,
                    "excess_inventory": p.excess_inventory,
                    "variants": [
                        {
                            "id": v.id,
                            "price_minor": v.price_minor,
                            "cost_minor": v.cost_minor,
                            "inventory": v.inventory,
                            "available": v.available,
                        }
                        for v in p.variants[:5]
                    ],
                }
                for p in sorted(products, key=lambda p: p.id)[:5]
            ],
            "selection": "first 5 IDs, not ranked by hidden quality or demand",
            "matching_count": len(products),
            "conversion_attribution": "unavailable",
        }
    elif request.view == "inventory":
        data = {
            "categories": [
                {
                    "category": category,
                    "inventory_units": sum(
                        p.total_inventory for p in products if p.category == category
                    ),
                    "excess_units": sum(
                        p.total_inventory
                        for p in products
                        if p.category == category and p.excess_inventory
                    ),
                    "observed_inventory_depletion": sum(
                        v.initial_inventory - v.inventory
                        for p in products
                        if p.category == category
                        for v in p.variants
                    ),
                    "low_stock_products": sum(
                        p.low_stock for p in products if p.category == category
                    ),
                }
                for category in sorted({p.category for p in products})
            ]
        }
    elif request.view == "campaigns":
        if request.category is not None:
            raise ValueError("campaigns have no category attribution")
        campaigns = [
            c for c in state.campaigns if request.entity_id is None or c.id == request.entity_id
        ]
        if request.entity_id and not campaigns:
            raise ValueError("unknown campaign ID")
        data = {
            "items": [
                {"id": c.id, "daily_budget_minor": c.daily_budget_minor, "active": c.active}
                for c in sorted(campaigns, key=lambda c: c.id)[:10]
            ],
            "per_campaign_performance": "unavailable",
            "aggregate_paid_spend_minor": [m.ad_spend_minor for m in state.metrics[-7:]],
        }
    elif request.view == "search":
        if request.category is not None:
            raise ValueError("category-level search attribution is unavailable")
        data = {
            "daily_search_purchases": [m.search_attributed_purchases for m in state.metrics[-7:]],
            "query_conversion_attribution": "unavailable",
            "active_rules": [
                b.model_dump(mode="json", exclude={"created_by_command"})
                for b in state.search_boosts
                if b.active
            ][:8],
            "retrieval": "signed-hash vectors and deterministic relevance, not neural retrieval",
        }
    else:
        if request.category is not None:
            raise ValueError("outcomes are aggregate, not category-attributed")
        data = {"prior_interventions": list(prior)}
    payload: JsonObject = {
        "view": request.view,
        "observation_version": state.state_hash,
        "data": data,
        "limitations": list(LIMITATIONS),
    }
    return {"evidence_ref": canonical_hash(payload), **payload}
