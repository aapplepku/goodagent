import pytest

from open_commerce.controller.models import (
    ActionApprovalRequest,
    ApprovalError,
    PolicyViolationError,
)
from open_commerce.core.actions import CreateDiscountIntent
from open_commerce.core.enums import ActionStatus

from .helpers import TENANT_ID, create_active_run


async def test_execute_allowed_action_is_idempotent_and_reconciled() -> None:
    service, goal, run = await create_active_run()
    boost = next(
        record
        for record in service.list_actions(tenant_id=TENANT_ID, run_id=run.id).items
        if record.action.intent.type == "set_search_boost"
    )

    first = await service.execute_action(
        tenant_id=TENANT_ID,
        action_id=boost.action.id,
        idempotency_key="execute-boost",
    )
    second = await service.execute_action(
        tenant_id=TENANT_ID,
        action_id=boost.action.id,
        idempotency_key="execute-boost",
    )
    state = service.simulator_service.get_full_state(
        tenant_id=TENANT_ID,
        instance_id=goal.simulator_instance_id,
    )

    assert first.action.status == ActionStatus.SUCCEEDED
    assert second.action.id == first.action.id
    assert first.reconciliation is not None
    assert first.measurement is not None
    assert len(state.command_history) == 1
    assert len(state.search_boosts) == 1


async def test_approval_hash_is_required_before_discount_execution() -> None:
    service, goal, run = await create_active_run()
    discount = next(
        record
        for record in service.list_actions(tenant_id=TENANT_ID, run_id=run.id).items
        if record.action.intent.type == "create_discount"
        and record.action.status == ActionStatus.AWAITING_APPROVAL
    )

    with pytest.raises(ApprovalError):
        service.approve_action(
            tenant_id=TENANT_ID,
            action_id=discount.action.id,
            request=ActionApprovalRequest(action_version_hash="sha256:stale-action"),
            actor_roles={"operator"},
            decision="approve",
            idempotency_key="approve-stale",
        )

    approved = service.approve_action(
        tenant_id=TENANT_ID,
        action_id=discount.action.id,
        request=ActionApprovalRequest(action_version_hash=discount.action.version_hash),
        actor_roles={"operator"},
        decision="approve",
        idempotency_key="approve-discount",
    )
    executed = await service.execute_action(
        tenant_id=TENANT_ID,
        action_id=approved.action.id,
        idempotency_key="execute-discount",
    )
    state = service.simulator_service.get_full_state(
        tenant_id=TENANT_ID,
        instance_id=goal.simulator_instance_id,
    )

    assert executed.action.status == ActionStatus.SUCCEEDED
    assert len(state.discounts) == 1
    assert isinstance(discount.action.intent, CreateDiscountIntent)
    assert state.discounts[0].value == discount.action.intent.value


async def test_kill_switch_blocks_between_planning_and_execution() -> None:
    service, goal, run = await create_active_run()
    boost = next(
        record
        for record in service.list_actions(tenant_id=TENANT_ID, run_id=run.id).items
        if record.action.intent.type == "set_search_boost"
    )
    service.set_kill_switch(tenant_id=TENANT_ID, enabled=True, idempotency_key="kill")

    with pytest.raises(PolicyViolationError):
        await service.execute_action(
            tenant_id=TENANT_ID,
            action_id=boost.action.id,
            idempotency_key="execute-blocked",
        )
    state = service.simulator_service.get_full_state(
        tenant_id=TENANT_ID,
        instance_id=goal.simulator_instance_id,
    )

    assert state.command_history == []
    assert service.get_action(tenant_id=TENANT_ID, action_id=boost.action.id).action.status == (
        ActionStatus.DENIED
    )
