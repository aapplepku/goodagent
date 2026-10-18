"""Descriptive monitoring with explicit samples and no causal attribution."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from open_commerce.controller.models import MeasurementSchedule
from open_commerce.simulator.engine import totals_for_metrics
from open_commerce.simulator.models import MetricTotals, SimulatorState


@dataclass(frozen=True)
class WindowAssessment:
    totals: MetricTotals
    enough_data: bool
    reason_codes: list[str]


def assess_window(schedule: MeasurementSchedule, state: SimulatorState) -> WindowAssessment:
    # Daily aggregates cannot attribute the pre-action portion of a partial day.
    metrics = [
        item
        for item in state.metrics
        if not item.is_history
        and schedule.starts_at <= datetime.combine(item.metric_date, time.min, UTC)
        and datetime.combine(item.metric_date, time.min, UTC) + timedelta(days=1)
        <= min(schedule.ends_at, state.current_time)
    ]
    totals = totals_for_metrics(metrics, include_history=False)
    enough = (
        len(metrics) >= schedule.minimum_days
        and totals.sessions >= schedule.minimum_sample
        and (totals.gross_revenue_minor > 0 or totals.ad_spend_minor > 0)
    )
    reasons = []
    if enough:
        if totals.gross_revenue_minor == 0:
            reasons.append("OBSERVED_ZERO_REVENUE_WITH_SPEND")
        elif totals.contribution_margin_rate < schedule.margin_floor:
            reasons.append("OBSERVED_MARGIN_BELOW_FLOOR")
        if schedule.cac_ceiling_minor is not None and totals.ad_spend_minor:
            if totals.new_customers == 0:
                reasons.append("OBSERVED_SPEND_WITHOUT_NEW_CUSTOMERS")
            elif Decimal(totals.ad_spend_minor) / totals.new_customers > schedule.cac_ceiling_minor:
                reasons.append("OBSERVED_CAC_ABOVE_CEILING")
    return WindowAssessment(totals=totals, enough_data=enough, reason_codes=reasons)
