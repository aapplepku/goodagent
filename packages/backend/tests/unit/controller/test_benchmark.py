"""Benchmark arithmetic and negative controls must not manufacture a clean gate."""

from decimal import Decimal
from uuid import uuid4

import pytest

from open_commerce.controller.benchmark import SCENARIOS, audit_evidence, case_request, distribution
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import ExecutionStatus
from open_commerce.simulator.engine import advance_state, create_initial_state
from open_commerce.simulator.models import ScenarioId, SimulatorCommandRecord
from open_commerce.simulator.scenarios import get_scenario


def test_statistics_include_unfavorable_values_and_missing_cac() -> None:
    result = distribution([0, Decimal("10"), -10, None])
    assert result["n"] == 3 and result["missing"] == 1
    assert result["mean"] == 0
    assert result["stddev"] == pytest.approx((200 / 3) ** 0.5)
    assert (result["p10"], result["p50"], result["p90"]) == (-8, 0, 8)
    assert distribution([None])["mean"] is None
    assert distribution([5])["stddev"] == 0


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_infeasible_targets_exceed_actual_scoped_inventory(scenario: ScenarioId) -> None:
    tenant = uuid4()
    request = case_request(scenario, 0, "inventory_infeasible", tenant, 30)
    initial = create_initial_state(
        definition=get_scenario(scenario),
        tenant_id=tenant,
        seed=0,
        instance_id=uuid4(),
    )
    bound = sum(
        p.total_inventory
        for p in initial.products
        if request.resolved_objective().scope == "store" or p.excess_inventory
    )
    assert request.target_value == bound + 1
    assert case_request(scenario, 0, "standard", tenant, 30).resolved_objective().target == 200


def test_auditor_detects_effects_without_actions_duplicates_and_overspend() -> None:
    tenant = uuid4()
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(
        definition=definition,
        tenant_id=tenant,
        seed=42,
        instance_id=uuid4(),
    )
    assert audit_evidence(state, [], [], [], GoalCreateRequest()) == []
    command = SimulatorCommandRecord(
        execution_id=uuid4(),
        tenant_id=tenant,
        instance_id=state.id,
        action_type="set_campaign_budget",
        idempotency_key="unexpected",
        status=ExecutionStatus.SUCCEEDED,
        before_state={},
        created_at=state.current_time,
    )
    state.command_history = [command, command.model_copy()]
    advance_state(state=state, definition=definition, hours=24)
    request = GoalCreateRequest.model_validate(
        {
            "budget": {"amount_minor": 0, "currency": "USD"},
            "daily_budget": {"amount_minor": 0, "currency": "USD"},
        }
    )
    findings = audit_evidence(state, [], [], [{"available_minor": -1}], request)
    assert findings == sorted(
        [
            "PROVIDER_EFFECT_WITHOUT_ACTION",
            "DUPLICATE_PROVIDER_EFFECT",
            "TOTAL_BUDGET_OVERSPEND",
            "DAILY_BUDGET_OVERSPEND",
            "NEGATIVE_LEDGER_BALANCE",
        ]
    )
