from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from open_commerce.controller.measurement import assess_window
from open_commerce.controller.models import GoalCreateRequest, MeasurementSchedule
from open_commerce.simulator.engine import advance_state
from open_commerce.simulator.scenarios import get_scenario

from .test_objectives import goal_state


def test_empty_or_short_windows_are_not_reported_as_clear() -> None:
    _, state = goal_state(GoalCreateRequest())
    schedule = MeasurementSchedule(
        action_id=uuid4(),
        starts_at=state.current_time,
        ends_at=state.current_time + timedelta(days=7),
        metric_names=[],
        baseline_ref=state.state_hash,
    )
    assert not assess_window(schedule, state).enough_data
    advance_state(state=state, definition=get_scenario(state.scenario_id), hours=24)
    assessment = assess_window(schedule, state)
    assert assessment.totals.sessions > 500
    assert not assessment.enough_data and assessment.reason_codes == []


def test_sampled_guardrails_use_observed_money_and_margin() -> None:
    _, state = goal_state(GoalCreateRequest())
    schedule = MeasurementSchedule(
        action_id=uuid4(),
        starts_at=state.current_time,
        ends_at=state.current_time + timedelta(days=7),
        metric_names=[],
        baseline_ref=state.state_hash,
        margin_floor=Decimal("0.999"),
        cac_ceiling_minor=1,
    )
    advance_state(state=state, definition=get_scenario(state.scenario_id), hours=48)
    assessment = assess_window(schedule, state)
    assert assessment.enough_data
    assert set(assessment.reason_codes) == {
        "OBSERVED_MARGIN_BELOW_FLOOR",
        "OBSERVED_CAC_ABOVE_CEILING",
    }
    schedule.margin_floor = Decimal("0")
    schedule.cac_ceiling_minor = None
    assert assess_window(schedule, state).reason_codes == []


def test_partial_days_are_not_counted_as_whole_post_action_days() -> None:
    _, state = goal_state(GoalCreateRequest())
    schedule = MeasurementSchedule(
        action_id=uuid4(),
        starts_at=state.current_time + timedelta(hours=12),
        ends_at=state.current_time + timedelta(hours=60),
        metric_names=[],
        baseline_ref=state.state_hash,
    )
    advance_state(state=state, definition=get_scenario(state.scenario_id), hours=72)
    assessment = assess_window(schedule, state)
    runtime = [item for item in state.metrics if not item.is_history]
    assert assessment.totals.sessions == runtime[1].sessions
    assert not assessment.enough_data
