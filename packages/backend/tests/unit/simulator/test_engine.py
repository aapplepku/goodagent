from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from open_commerce.simulator.engine import (
    advance_state,
    compare_to_baseline,
    create_initial_state,
    reset_state,
    subtract_totals,
    totals_for_metrics,
)
from open_commerce.simulator.models import ENGINE_VERSION
from open_commerce.simulator.scenarios import get_scenario

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_seeded_catalog_and_run_are_deterministic() -> None:
    definition = get_scenario("acquisition_v1")
    left = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    right = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)

    assert len(left.products) == 1_000
    assert left.state_hash == right.state_hash

    advance_state(state=left, definition=definition, hours=30 * 24)
    advance_state(state=right, definition=definition, hours=30 * 24)

    assert left.state_hash == right.state_hash


def test_different_seeds_produce_different_worlds() -> None:
    definition = get_scenario("acquisition_v1")
    left = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    right = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=43)

    assert left.state_hash != right.state_hash


def test_thirty_day_run_has_no_negative_inventory_and_valid_accounting() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)

    advance_state(state=state, definition=definition, hours=30 * 24)

    assert state.day == 30
    assert len(state.snapshots) == 31
    assert all(variant.inventory >= 0 for product in state.products for variant in product.variants)
    runtime_metrics = [metric for metric in state.metrics if not metric.is_history]
    assert len(runtime_metrics) == 30
    for metric in runtime_metrics:
        assert metric.contribution_profit_minor == (
            metric.gross_revenue_minor
            - metric.discounts_minor
            - metric.cogs_minor
            - metric.variable_fees_minor
            - metric.ad_spend_minor
        )


def test_baseline_comparison_matches_no_intervention_run() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    advance_state(state=state, definition=definition, hours=7 * 24)

    comparison = compare_to_baseline(state=state, definition=definition)

    assert comparison.current == comparison.baseline
    assert comparison.delta.orders == 0


def test_reset_reproduces_initial_world_for_same_seed() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    initial_hash = state.state_hash

    advance_state(state=state, definition=definition, hours=24)
    reset = reset_state(state=state, definition=definition)

    assert reset.state_hash == initial_hash
    assert reset.current_time == definition.start_at


def test_run_until_advances_crossed_days_only() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)

    advance_state(state=state, definition=definition, hours=36)

    assert state.day == 1
    assert state.current_time == definition.start_at + timedelta(hours=36)
    assert totals_for_metrics(state.metrics, include_history=False).days == 1


def test_baseline_uses_the_same_total_and_daily_limits() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    state.total_spend_limit_minor = 5000
    state.daily_spend_limit_minor = 2000
    advance_state(state=state, definition=definition, hours=96)
    comparison = compare_to_baseline(state=state, definition=definition)
    assert comparison.current == comparison.baseline
    assert comparison.baseline.ad_spend_minor == 5000
    assert comparison.delta.contribution_margin_rate == 0


def test_rate_deltas_are_differences_not_ratios_of_differences() -> None:
    empty = totals_for_metrics([], include_history=False)
    left = empty.model_copy(
        update={
            "conversion_rate": Decimal("0.2"),
            "cac_minor": 300,
            "contribution_margin_rate": Decimal("0.35"),
        }
    )
    right = empty.model_copy(
        update={
            "conversion_rate": Decimal("0.1"),
            "cac_minor": 500,
            "contribution_margin_rate": Decimal("0.4"),
        }
    )
    delta = subtract_totals(left, right)
    assert delta.conversion_rate == Decimal("0.1")
    assert delta.cac_minor == -200
    assert delta.contribution_margin_rate == Decimal("-0.05")


def test_engine_version_and_spending_limits_are_reproducibility_inputs() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    assert state.engine_version == ENGINE_VERSION
    before = state.state_hash
    state.total_spend_limit_minor = 5000
    assert state.state_hash != before
    state.engine_version = "simulator.1"
    with pytest.raises(ValueError, match="engine changed"):
        advance_state(state=state, definition=definition, hours=24)
