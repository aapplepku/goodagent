"""Finite observed-evidence coordinator. Proposals are experiments, not predicted lift."""

from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from open_commerce.controller.models import EvidenceItem, Hypothesis, IntentDraft, Opportunity
from open_commerce.core.enums import ActionType
from open_commerce.core.goals import GoalSpec
from open_commerce.core.types import JsonObject, StrictDomainModel
from open_commerce.simulator.demand import effective_price_minor
from open_commerce.simulator.merchandising_economics import (
    VariantEconomicsReport,
    investigate_variant,
)
from open_commerce.simulator.merchandising_models import ProductOutcomes
from open_commerce.simulator.models import SimulatorState

PLANNER_VERSION = "merchandising-deterministic-v1"


class MerchandisingPlan(StrictDomainModel):
    opportunities: list[Opportunity]
    hypotheses: list[Hypothesis]
    drafts: list[IntentDraft]
    decision: JsonObject


def plan_merchandising(*, goal: GoalSpec, state: SimulatorState, run_id: UUID) -> MerchandisingPlan:
    """One intervention per cycle; authority remains in compiler/policy/executor."""
    merch = state.merchandising
    if goal.tenant_id != state.tenant_id or goal.merchandising is None or merch is None:
        raise ValueError("tenant-owned merchandising goal required")
    allowed = goal.allowed_action_types - goal.merchandising.prohibited_actions
    reports: dict[str, VariantEconomicsReport] = {}
    for product in sorted(state.products, key=lambda p: p.id):
        available = sorted(
            (v for v in product.variants if v.available and v.inventory > 5),
            key=lambda v: (v.price_minor, v.id),
        )
        if available:
            reports[product.id] = investigate_variant(
                state, tenant_id=goal.tenant_id, product_id=product.id, variant_id=available[0].id
            )

    def result(
        reason: str,
        action: ActionType | None = None,
        parameters: JsonObject | None = None,
        evidence: JsonObject | None = None,
    ) -> MerchandisingPlan:
        key = uuid5(NAMESPACE_URL, f"{run_id}:{PLANNER_VERSION}:{reason}")
        hypothesis_id = uuid5(key, "hypothesis")
        decision: JsonObject = {
            "planner_version": PLANNER_VERSION,
            "kind": "propose" if action else "wait",
            "reason": reason,
            "observed_evidence": evidence or {},
            "predicted_profit_minor": None,
            "demand_response": "insufficient_evidence",
            "model_calls": 0,
            "model_cost_minor": 0,
        }
        return MerchandisingPlan(
            opportunities=[
                Opportunity(
                    id=key,
                    tenant_id=goal.tenant_id,
                    run_id=run_id,
                    type="merchandising_investigation",
                    title=reason,
                    description=reason,
                    confidence=Decimal(0),
                    expected_metric=goal.objective.metric,
                    evidence=[
                        EvidenceItem(source=PLANNER_VERSION, key=reason, value=evidence or {})
                    ],
                    detected_at=state.current_time,
                )
            ],
            hypotheses=[
                Hypothesis(
                    id=hypothesis_id,
                    tenant_id=goal.tenant_id,
                    run_id=run_id,
                    opportunity_ids=[key],
                    statement=reason,
                    confidence=Decimal(0),
                    created_at=state.current_time,
                )
            ],
            drafts=[
                IntentDraft(
                    id=uuid5(key, "draft"),
                    tenant_id=goal.tenant_id,
                    run_id=run_id,
                    hypothesis_id=hypothesis_id,
                    opportunity_ids=[key],
                    action_type=action,
                    rationale=reason,
                    parameters=parameters or {},
                    confidence=Decimal(0),
                )
            ]
            if action
            else [],
            decision=decision,
        )

    if ActionType.DISABLE_DISCOUNT in allowed:
        for promotion_report in reports.values():
            if promotion_report.active_promotions and (
                promotion_report.current.unit_margin is None
                or promotion_report.current.unit_margin < merch.constraints.minimum_unit_margin
                or promotion_report.current.effective_discount_rate
                > merch.constraints.max_effective_discount
            ):
                return result(
                    "Stop an active promotion outside current known economics bounds",
                    ActionType.DISABLE_DISCOUNT,
                    {
                        "provider_discount_id": min(
                            promotion_report.active_promotions,
                            key=lambda p: (
                                effective_price_minor(
                                    promotion_report.current.base_price_minor, p.kind, p.value
                                ),
                                p.id,
                            ),
                        ).id
                    },
                    promotion_report.model_dump(mode="json"),
                )
    if goal.horizon.end_at - state.current_time < timedelta(hours=24):
        return result("Insufficient remaining measurement window")
    if sum(metric.sessions for metric in state.metrics) < 200:
        return result("Wait for at least 200 recorded eligible shopping sessions")
    if state.command_history and (
        state.current_time - state.command_history[-1].created_at < timedelta(hours=48)
    ):
        return result("Wait for the prior intervention's two-day measurement window")
    duration = min(48, merch.constraints.max_duration_hours // 24 * 24)
    if ActionType.SET_SEARCH_BOOST in allowed:
        for product in sorted(state.products, key=lambda p: p.id):
            report = reports.get(product.id)
            if report is None or not product.excess_inventory or report.outcomes.orders < 1:
                continue
            peers = [
                merch.product_outcomes.get(p.id, ProductOutcomes()).search_exposures
                for p in state.products
                if p.category == product.category and p.id != product.id
            ]
            if (
                not peers
                or sum(peers) < 200
                or report.outcomes.search_exposures * len(peers) * 2 >= sum(peers)
                or any(
                    product.id in rule.product_ids
                    and rule.active
                    and rule.starts_at <= state.current_time < rule.ends_at
                    for rule in state.search_boosts
                )
            ):
                continue
            return result(
                "Test relevant overstock exposure; "
                "measure displacement and profit, not assumed lift",
                ActionType.SET_SEARCH_BOOST,
                {
                    "product_id": product.id,
                    "category": product.category,
                    "query_text": product.category,
                    "multiplier": "1.10",
                    "duration_hours": duration,
                },
                {
                    "product_id": product.id,
                    "observed": report.outcomes.model_dump(mode="json"),
                    "peer_exposures": peers,
                },
            )
    if (
        ActionType.SET_RECOMMENDATION_POLICY in allowed
        and merch.recommendation_policy.controls.strategy == "alternatives"
        and merch.recommendation_policy.version == 0
    ):
        for pair in merch.compatibility:
            anchor = merch.product_outcomes.get(pair.anchor_product_id, ProductOutcomes())
            complement = reports.get(pair.complement_product_id)
            if (
                anchor.clicks >= 100
                and complement is not None
                and complement.outcomes.orders > 0
                and complement.outcomes.recommendation_exposures < 20
            ):
                return result(
                    "Test explicitly compatible PDP complements; no inferred compatibility",
                    ActionType.SET_RECOMMENDATION_POLICY,
                    {
                        "expected_version": merch.recommendation_policy.version,
                        "controls": {
                            "strategy": "complements",
                            "inventory_priority": "0.05",
                            "minimum_relevance": str(merch.constraints.minimum_relevance),
                        },
                        "duration_hours": duration,
                    },
                    {
                        "compatibility": pair.model_dump(mode="json"),
                        "anchor": anchor.model_dump(mode="json"),
                        "complement": complement.outcomes.model_dump(mode="json"),
                    },
                )
    for report in reports.values():
        observed = report.outcomes
        if observed.search_exposures < 200 or observed.orders * 100 >= observed.search_exposures:
            continue
        if report.active_promotions:
            continue
        candidates = [c for c in report.candidates if c.eligible]
        if ActionType.SET_VARIANT_PRICE in allowed:
            candidate = next(
                (
                    c
                    for c in candidates
                    if c.promotion_rate == 0
                    and c.base_price_minor < report.current.base_price_minor
                ),
                None,
            )
            if candidate is not None:
                return result(
                    "Test a bounded lower base price; "
                    "observed low conversion does not identify elasticity",
                    ActionType.SET_VARIANT_PRICE,
                    {
                        "product_id": report.product_id,
                        "variant_id": report.variant_id,
                        "new_price_minor": candidate.base_price_minor,
                        "expected_version": report.current_version,
                        "duration_hours": duration,
                    },
                    report.model_dump(mode="json"),
                )
        if ActionType.CREATE_DISCOUNT in allowed:
            candidate = next(
                (
                    c
                    for c in candidates
                    if c.promotion_rate > 0
                    and c.base_price_minor == report.current.base_price_minor
                ),
                None,
            )
            if candidate is not None:
                return result(
                    "Test a bounded product promotion; "
                    "measure profit and cap usage, not promised lift",
                    ActionType.CREATE_DISCOUNT,
                    {
                        "product_id": report.product_id,
                        "discount_percentage": str(candidate.promotion_rate),
                        "duration_hours": duration,
                    },
                    report.model_dump(mode="json"),
                )
    return result("No supported evidence-backed intervention; retain current serving and prices")
