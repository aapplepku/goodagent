"""Read-only, unit-correct goal progress and conservative simulator feasibility."""

from decimal import Decimal
from typing import Literal

from open_commerce.controller.models import GoalAssessment
from open_commerce.core.enums import MetricName, ObjectiveDirection
from open_commerce.core.goals import GoalSpec, ObjectiveSpec
from open_commerce.simulator.engine import totals_for_metrics
from open_commerce.simulator.models import MetricTotals, SimulatorState

COUNT_METRICS = {
    MetricName.NEW_CUSTOMERS,
    MetricName.UNITS_SOLD,
    MetricName.SEARCH_ATTRIBUTED_PURCHASES,
}
SUPPORTED_OBJECTIVES = COUNT_METRICS | {
    MetricName.CAC,
    MetricName.REVENUE,
    MetricName.CONTRIBUTION_PROFIT,
    MetricName.CONTRIBUTION_MARGIN_RATE,
    MetricName.CONVERSION_RATE,
    MetricName.DISCOUNT_RATE,
}


def objective_value(objective: ObjectiveSpec, state: SimulatorState) -> Decimal | None:
    """No observations means undefined rates, not a misleading zero CAC/margin."""

    if objective.scope == "excess_inventory":
        return Decimal(
            sum(
                variant.initial_inventory - variant.inventory
                for product in state.products
                if product.excess_inventory
                for variant in product.variants
            )
        )
    return _total_value(objective.metric, totals_for_metrics(state.metrics, include_history=False))


def _total_value(metric: MetricName, totals: MetricTotals) -> Decimal | None:
    values: dict[MetricName, int | Decimal | None] = {
        MetricName.NEW_CUSTOMERS: totals.new_customers,
        MetricName.UNITS_SOLD: totals.units_sold,
        MetricName.SEARCH_ATTRIBUTED_PURCHASES: totals.search_attributed_purchases,
        MetricName.CAC: totals.cac_minor,
        MetricName.REVENUE: totals.gross_revenue_minor,
        MetricName.CONTRIBUTION_PROFIT: totals.contribution_profit_minor,
        MetricName.CONTRIBUTION_MARGIN_RATE: totals.contribution_margin_rate
        if totals.gross_revenue_minor
        else None,
        MetricName.CONVERSION_RATE: totals.conversion_rate if totals.sessions else None,
        MetricName.DISCOUNT_RATE: Decimal(totals.discounts_minor)
        / Decimal(totals.gross_revenue_minor)
        if totals.gross_revenue_minor
        else None,
    }
    if metric not in values:
        raise ValueError("The simulator does not measure this objective")
    value = values[metric]
    return Decimal(value) if value is not None else None


def assess_goal(goal: GoalSpec, state: SimulatorState) -> GoalAssessment:
    """Rule out impossible count targets without pretending expected demand is a bound."""

    if goal.tenant_id != state.tenant_id:
        raise ValueError("Goal and observation tenant mismatch")
    objective = goal.objective
    current = objective_value(objective, state)
    remaining_inventory = sum(
        product.total_inventory
        for product in state.products
        if objective.scope == "store" or product.excess_inventory
    )
    upper = (
        Decimal(remaining_inventory) + (current or Decimal("0"))
        if objective.metric in COUNT_METRICS
        else None
    )
    remaining_days = max(
        Decimal("0"),
        Decimal(str((goal.horizon.end_at - state.current_time).total_seconds())) / 86400,
    )
    observed = [metric for metric in state.metrics if not metric.is_history]
    recent = observed[-7:] or state.metrics[-7:]
    recent_totals = totals_for_metrics(recent, include_history=True)
    estimate = _total_value(objective.metric, recent_totals)
    projected: Decimal | None
    if objective.metric in COUNT_METRICS:
        if objective.scope == "excess_inventory" and state.day:
            rate = (current or Decimal("0")) / state.day
        else:
            rate = (estimate or Decimal("0")) / max(1, len(recent))
            if objective.scope == "excess_inventory":
                total_initial = sum(v.initial_inventory for p in state.products for v in p.variants)
                excess_initial = sum(
                    v.initial_inventory
                    for p in state.products
                    if p.excess_inventory
                    for v in p.variants
                )
                rate *= Decimal(excess_initial) / max(1, total_initial)
        projected = min(upper or Decimal("0"), (current or Decimal("0")) + rate * remaining_days)
    elif objective.metric in {MetricName.REVENUE, MetricName.CONTRIBUTION_PROFIT}:
        projected = (current or Decimal("0")) + (estimate or Decimal("0")) / max(
            1, len(recent)
        ) * remaining_days
    else:
        projected = estimate
    target = objective.target
    infeasible = (
        objective.direction != ObjectiveDirection.MINIMIZE
        and target is not None
        and upper is not None
        and target > upper
    )
    reason_codes = ["PHYSICAL_INVENTORY_BOUND"] if infeasible else []
    if not observed:
        reason_codes.append("HISTORICAL_PRIOR_NOT_CURRENT_OUTCOME")
    trajectory: Literal["achieved", "on_track", "at_risk", "no_target", "insufficient_data"]
    if target is None:
        trajectory = "no_target"
    elif current is not None and _meets(current, target, objective.direction):
        trajectory = "achieved"
    elif projected is None:
        trajectory = "insufficient_data"
    else:
        trajectory = "on_track" if _meets(projected, target, objective.direction) else "at_risk"
    return GoalAssessment(
        metric=objective.metric,
        scope=objective.scope,
        current_value=current,
        target_value=target,
        projected_value=projected,
        physical_upper_bound=upper,
        feasibility="infeasible" if infeasible else "not_ruled_out",
        trajectory=trajectory,
        reason_codes=reason_codes,
    )


def _meets(value: Decimal, target: Decimal, direction: ObjectiveDirection) -> bool:
    return value <= target if direction == ObjectiveDirection.MINIMIZE else value >= target
