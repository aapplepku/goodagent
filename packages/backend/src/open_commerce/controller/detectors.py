"""Read-only deterministic opportunity detectors for simulator state."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from open_commerce.controller.models import (
    EvidenceItem,
    GoalAssessment,
    ObservationSnapshot,
    Opportunity,
)
from open_commerce.core.enums import MetricName, ObjectiveDirection
from open_commerce.core.goals import GoalSpec
from open_commerce.core.types import JsonObject
from open_commerce.simulator.engine import (
    latest_runtime_metric,
    summarize_catalog,
    totals_for_metrics,
)
from open_commerce.simulator.models import DailyMetrics, ProductState, SimulatorState


def build_observation_snapshot(
    *,
    tenant_id: UUID,
    run_id: UUID,
    state: SimulatorState,
) -> ObservationSnapshot:
    """Build a read-only observation snapshot for one controller run."""

    metric = _latest_metric(state)
    totals = totals_for_metrics(state.metrics[-7:], include_history=True)
    catalog = summarize_catalog(state.products)
    sample_size = max(metric.sessions if metric else 0, totals.sessions)
    snapshot_id = uuid5(NAMESPACE_URL, f"{tenant_id}:{run_id}:{state.id}:{state.state_hash}")
    return ObservationSnapshot(
        id=snapshot_id,
        tenant_id=tenant_id,
        run_id=run_id,
        simulator_instance_id=state.id,
        scenario_id=state.scenario_id,
        observed_at=state.current_time,
        state_hash=state.state_hash,
        sample_size=sample_size,
        data_age_minutes={
            "catalog": 0,
            "inventory": 0,
            "orders": 0,
            "campaigns": 0,
            "search": 0,
        },
        catalog_summary=cast(JsonObject, catalog.model_dump(mode="json")),
        metric_summary={
            "sessions": metric.sessions,
            "orders": metric.orders,
            "new_customers": metric.new_customers,
            "conversion_rate": str(metric.conversion_rate),
            "cac_minor": metric.cac_minor,
            "contribution_margin_rate": str(metric.contribution_margin_rate),
            "search_attributed_purchases": metric.search_attributed_purchases,
        }
        if metric
        else {
            "sessions": 0,
            "orders": 0,
            "new_customers": 0,
            "conversion_rate": None,
            "cac_minor": None,
            "contribution_margin_rate": None,
            "search_attributed_purchases": 0,
        },
        campaign_summary=[
            {
                "campaign_id": campaign.id,
                "name": campaign.name,
                "daily_budget_minor": campaign.daily_budget_minor,
                "initial_daily_budget_minor": campaign.initial_daily_budget_minor,
                "active": campaign.active,
                "max_reach": campaign.max_reach,
            }
            for campaign in state.campaigns
        ],
    )


def detect_opportunities(
    snapshot: ObservationSnapshot, state: SimulatorState, goal: GoalSpec, assessment: GoalAssessment
) -> list[Opportunity]:
    """Select hypotheses for the actual objective, not a fixed bundle for every goal."""

    if snapshot.tenant_id != goal.tenant_id or state.tenant_id != goal.tenant_id:
        raise ValueError("Goal and observation tenant mismatch")
    evidence = EvidenceItem(
        source="controller.goal_assessment",
        key="objective",
        value=cast(JsonObject, assessment.model_dump(mode="json")),
    )
    if assessment.feasibility == "infeasible":
        return [
            Opportunity(
                id=_opportunity_id(snapshot.run_id, "guardrail_review"),
                tenant_id=snapshot.tenant_id,
                run_id=snapshot.run_id,
                type="guardrail_review",
                title="Target exceeds the physical inventory bound",
                description="Even selling every remaining unit cannot reach this count target.",
                confidence=Decimal("1"),
                expected_metric=goal.objective.metric,
                evidence=[evidence],
                detected_at=snapshot.observed_at,
            )
        ]
    opportunities: list[Opportunity] = []
    metric = goal.objective.metric
    needs_growth = (
        goal.objective.direction != ObjectiveDirection.MINIMIZE
        and assessment.trajectory in {"at_risk", "no_target", "insufficient_data"}
    )
    if metric == MetricName.NEW_CUSTOMERS and needs_growth:
        opportunities.append(_conversion_opportunity(snapshot))
    if goal.objective.scope == "excess_inventory" and needs_growth:
        excess = _excess_inventory_opportunity(snapshot, state)
        if excess is not None:
            opportunities.append(excess)
    if metric in {
        MetricName.CAC,
        MetricName.CONTRIBUTION_PROFIT,
        MetricName.CONTRIBUTION_MARGIN_RATE,
    } or (metric == MetricName.NEW_CUSTOMERS and not needs_growth):
        if any(campaign.active and campaign.daily_budget_minor > 0 for campaign in state.campaigns):
            opportunities.append(_campaign_efficiency_opportunity(snapshot, state))
    if (
        needs_growth
        and goal.objective.scope == "store"
        and metric not in {MetricName.CAC, MetricName.DISCOUNT_RATE}
    ):
        opportunities.append(_search_exposure_opportunity(snapshot, state))
    for opportunity in opportunities:
        opportunity.evidence.append(evidence)
    return opportunities


def _conversion_opportunity(snapshot: ObservationSnapshot) -> Opportunity:
    return Opportunity(
        id=_opportunity_id(snapshot.run_id, "conversion_gap"),
        tenant_id=snapshot.tenant_id,
        run_id=snapshot.run_id,
        type="conversion_gap",
        title="Improve new-customer conversion",
        description="The recent-rate heuristic does not reach the acquisition target.",
        confidence=Decimal("0.82"),
        expected_metric=MetricName.NEW_CUSTOMERS,
        evidence=[
            EvidenceItem(
                source="simulator.metrics",
                key="conversion_rate",
                value={"value": snapshot.metric_summary["conversion_rate"]},
            ),
            EvidenceItem(
                source="simulator.metrics",
                key="new_customers",
                value={"value": snapshot.metric_summary["new_customers"]},
            ),
        ],
        detected_at=snapshot.observed_at,
    )


def _campaign_efficiency_opportunity(
    snapshot: ObservationSnapshot,
    state: SimulatorState,
) -> Opportunity:
    campaign = max(
        (item for item in state.campaigns if item.active and item.daily_budget_minor > 0),
        key=lambda item: (item.daily_budget_minor, item.id),
    )
    return Opportunity(
        id=_opportunity_id(snapshot.run_id, "campaign_efficiency"),
        tenant_id=snapshot.tenant_id,
        run_id=snapshot.run_id,
        type="campaign_efficiency",
        title="Rebalance acquisition campaign spend",
        description="Test a reversible cost reduction; its effect on demand is uncertain.",
        confidence=Decimal("0.79"),
        expected_metric=MetricName.CAC,
        evidence=[
            EvidenceItem(
                source="simulator.campaigns",
                key=campaign.id,
                value={
                    "daily_budget_minor": campaign.daily_budget_minor,
                    "initial_daily_budget_minor": campaign.initial_daily_budget_minor,
                    "max_reach": campaign.max_reach,
                },
            )
        ],
        detected_at=snapshot.observed_at,
    )


def _search_exposure_opportunity(
    snapshot: ObservationSnapshot,
    state: SimulatorState,
) -> Opportunity:
    category = _most_common_category(state.products)
    return Opportunity(
        id=_opportunity_id(snapshot.run_id, "search_exposure_gap"),
        tenant_id=snapshot.tenant_id,
        run_id=snapshot.run_id,
        type="search_exposure_gap",
        title="Lift relevant search exposure",
        description="Search-attributed purchases can improve with a bounded relevance-gated boost.",
        confidence=Decimal("0.84"),
        expected_metric=MetricName.SEARCH_ATTRIBUTED_PURCHASES,
        evidence=[
            EvidenceItem(
                source="simulator.search",
                key="category",
                value={
                    "category": category,
                    "search_attributed_purchases": snapshot.metric_summary[
                        "search_attributed_purchases"
                    ],
                },
            )
        ],
        detected_at=snapshot.observed_at,
    )


def _excess_inventory_opportunity(
    snapshot: ObservationSnapshot,
    state: SimulatorState,
) -> Opportunity | None:
    excess_products = [
        product
        for product in state.products
        if product.excess_inventory
        and not product.low_stock
        and all(v.available and v.inventory > 5 for v in product.variants)
    ]
    if not excess_products:
        return None
    category = _most_common_category(excess_products)
    return Opportunity(
        id=_opportunity_id(snapshot.run_id, "excess_inventory"),
        tenant_id=snapshot.tenant_id,
        run_id=snapshot.run_id,
        type="excess_inventory",
        title="Move excess inventory without touching low-stock items",
        description="A bounded action can target high-inventory product families only.",
        confidence=Decimal("0.77"),
        expected_metric=MetricName.UNITS_SOLD,
        evidence=[
            EvidenceItem(
                source="simulator.catalog",
                key="excess_inventory",
                value={
                    "category": category,
                    "product_count": len(excess_products),
                    "product_ids": sorted(p.id for p in excess_products if p.category == category),
                },
            )
        ],
        detected_at=snapshot.observed_at,
    )


def _latest_metric(state: SimulatorState) -> DailyMetrics | None:
    latest = latest_runtime_metric(state)
    if latest is not None:
        return latest
    return state.metrics[-1] if state.metrics else None


def _most_common_category(products: list[ProductState]) -> str:
    counts = Counter(product.category for product in products)
    return min(
        (category for category, count in counts.items() if count == max(counts.values())),
        default="apparel",
    )


def _opportunity_id(run_id: UUID, code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{run_id}:opportunity:{code}")
