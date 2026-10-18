from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from open_commerce.core.actions import (
    ActionIntent,
    CompiledAction,
    ImpactEstimate,
    NoOpIntent,
    build_action_idempotency_key,
    compute_action_version_hash,
    transition_action,
)
from open_commerce.core.enums import ActionStatus, ActionType, RiskTier
from open_commerce.core.errors import InvalidTransitionError
from open_commerce.core.metrics import ConfidenceInterval
from open_commerce.core.money import Money
from open_commerce.core.policy_types import RiskAssessment, RollbackPlan
from open_commerce.core.types import ActorRef, Precondition, ProviderRef, TimeWindow


def _actor() -> ActorRef:
    return ActorRef(type="system", id="controller", roles={"operator"})


def _compiled_action(
    *,
    amount_minor: int = 0,
    status: ActionStatus = ActionStatus.COMPILED,
) -> CompiledAction:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    goal_id = UUID("00000000-0000-0000-0000-000000000002")
    window = TimeWindow(
        start_at=datetime(2026, 9, 1, tzinfo=UTC),
        end_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    provider = ProviderRef(
        provider_type="simulator",
        integration_id=None,
        resource_type="goal",
        resource_id=str(goal_id),
    )
    parameters = {"reason": "nothing safe to do", "amount_minor": amount_minor}
    return CompiledAction(
        id=uuid4(),
        tenant_id=tenant_id,
        goal_id=goal_id,
        run_id=uuid4(),
        intent=NoOpIntent(
            rationale="No safe action.",
            opportunity_ids=[],
            requested_by=_actor(),
            source_run_id=uuid4(),
            proposed_at=datetime(2026, 9, 1, tzinfo=UTC),
        ),
        target_provider=provider,
        normalized_parameters=parameters,
        preconditions=[Precondition(field="goal.status", operator="eq", value="active")],
        expected_impact=ImpactEstimate(
            metric="new_customers",
            interval=ConfidenceInterval(
                lower=Decimal("0"),
                point=Decimal("0"),
                upper=Decimal("0"),
                level=Decimal("0.90"),
            ),
            method="no_op_v1",
        ),
        estimated_cost=Money(amount_minor=0, currency="USD"),
        budget_reservations=[],
        risk=RiskAssessment(
            tier=RiskTier.R0_READ_ONLY,
            confidence=Decimal("1"),
            reasons=["no_effect"],
        ),
        rollback_plan=RollbackPlan(available=True, summary="No rollback needed."),
        idempotency_key=build_action_idempotency_key(
            tenant_id=tenant_id,
            goal_id=goal_id,
            action_type=ActionType.NO_OP,
            target_provider=provider,
            normalized_parameters=parameters,
            decision_window=window,
        ),
        expires_at=datetime(2026, 9, 2, tzinfo=UTC),
        status=status,
    )


def test_action_state_machine_allows_documented_path_and_rejects_invalid_jump() -> None:
    assert transition_action(ActionStatus.DRAFT, ActionStatus.COMPILED) == ActionStatus.COMPILED
    assert (
        transition_action(ActionStatus.COMPILED, ActionStatus.AWAITING_APPROVAL)
        == ActionStatus.AWAITING_APPROVAL
    )

    with pytest.raises(InvalidTransitionError):
        transition_action(ActionStatus.DRAFT, ActionStatus.SUCCEEDED)


def test_action_version_hash_is_stable_but_parameter_sensitive() -> None:
    action = _compiled_action(amount_minor=0)
    same_semantics = action.model_copy(update={"status": ActionStatus.EXECUTABLE})
    changed_parameters = action.model_copy(update={"normalized_parameters": {"amount_minor": 1}})

    assert compute_action_version_hash(action) == compute_action_version_hash(same_semantics)
    assert compute_action_version_hash(action) != compute_action_version_hash(changed_parameters)


def test_action_intent_union_rejects_unknown_action_fields() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(ActionIntent)
    payload = {
        "type": "no_op",
        "rationale": "No safe action.",
        "opportunity_ids": [],
        "requested_by": _actor().model_dump(),
        "source_run_id": str(uuid4()),
        "proposed_at": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        "raw_provider_command": {"unsafe": True},
    }

    with pytest.raises(ValidationError):
        adapter.validate_python(payload)
