"""Controller recovery against a real migrated PostgreSQL database."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.durable_executor import DurableExecutor
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerRunRequest,
    GoalCreateRequest,
)
from open_commerce.core.enums import ActionStatus, ActorRole, GoalStatus
from open_commerce.persistence.models.actions import ActionExecution
from open_commerce.persistence.models.simulator import SimulatorCommandRecordModel
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration


async def prepared_goal(
    database: RuntimeDatabase, action_type: str | None = None
) -> tuple[UUID, UUID, UUID]:
    tenant_id = uuid4()
    await database.initialize_tenant(tenant_id)
    service = DurableControllerService(database)
    goal = await service.create_goal(
        tenant_id=tenant_id,
        request=GoalCreateRequest(
            target_value=Decimal("10000") if action_type != "set_campaign_budget" else None
        ),
        idempotency_key="create",
    )
    await service.set_goal_status(
        tenant_id=tenant_id,
        goal_id=goal.spec.id,
        status=GoalStatus.ACTIVE,
        idempotency_key="activate",
    )
    run = await service.run_goal(
        tenant_id=tenant_id,
        goal_id=goal.spec.id,
        request=ControllerRunRequest(),
        idempotency_key="run",
    )
    planned = await service.process_run(tenant_id=tenant_id, run_id=run.id)
    assert planned.id == run.id
    actions = (await service.list_actions(tenant_id=tenant_id, run_id=run.id)).items
    action = next(
        item
        for item in actions
        if item.action.status == ActionStatus.AWAITING_APPROVAL
        and (action_type is None or item.action.intent.type == action_type)
    )
    return tenant_id, run.id, action.action.id


async def approve(database: RuntimeDatabase, tenant_id: UUID, action_id: UUID) -> None:
    service = DurableControllerService(database)
    record = await service.get_action(tenant_id=tenant_id, action_id=action_id)
    await service.approve_action(
        tenant_id=tenant_id,
        action_id=action_id,
        request=ActionApprovalRequest(action_version_hash=record.action_version_hash),
        idempotency_key="approve",
        actor_roles={ActorRole.OWNER, ActorRole.OPERATOR},
        decision="approve",
    )


async def test_pending_approval_and_trace_survive_pool_restart(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, run_id, action_id = await prepared_goal(database)
        before = await DurableControllerService(database).get_run(
            tenant_id=tenant_id, run_id=run_id
        )
    finally:
        await database.close()
    restarted = RuntimeDatabase(integration_settings)
    try:
        service = DurableControllerService(restarted)
        after = await service.get_run(tenant_id=tenant_id, run_id=run_id)
        assert after.id == before.id
        assert after.trace == before.trace
        assert after.status == "awaiting_approval"
        await approve(restarted, tenant_id, action_id)
        result = await service.execute_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
        )
        assert result.action.status == ActionStatus.SUCCEEDED
        assert result.measurement is not None
    finally:
        await restarted.close()


@pytest.mark.parametrize("boundary", ["prepared", "provider_committed"])
async def test_committed_execution_boundaries_recover_without_duplicate_effect(
    integration_settings: Settings, boundary: str
) -> None:
    class InterruptedExecutor(DurableExecutor):
        async def _after_prepare(self, attempt_id: UUID) -> None:
            if boundary == "prepared":
                raise RuntimeError("injected interruption")

        async def _after_provider_commit(self, attempt_id: UUID) -> None:
            if boundary == "provider_committed":
                raise RuntimeError("injected interruption")

    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        await approve(database, tenant_id, action_id)
        with pytest.raises(RuntimeError, match="injected interruption"):
            await InterruptedExecutor(database).execute(
                tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
            )
    finally:
        await database.close()
    restarted = RuntimeDatabase(integration_settings)
    try:
        result = await DurableExecutor(restarted).execute(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
        )
        assert result.action.status == ActionStatus.SUCCEEDED
        async with restarted.transaction(tenant_id) as session:
            receipts = list(
                await session.scalars(
                    select(SimulatorCommandRecordModel).where(
                        SimulatorCommandRecordModel.tenant_id == tenant_id
                    )
                )
            )
            attempts = list(
                await session.scalars(
                    select(ActionExecution).where(ActionExecution.tenant_id == tenant_id)
                )
            )
            assert len(receipts) == len(attempts) == 1
    finally:
        await restarted.close()


async def test_duplicate_delivery_and_double_rollback_are_idempotent(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    second = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        await approve(database, tenant_id, action_id)
        results = await asyncio.gather(
            *[
                DurableExecutor(pool).execute(
                    tenant_id=tenant_id, action_id=action_id, idempotency_key=f"delivery-{index}"
                )
                for index, pool in enumerate((database, second, database, second))
            ]
        )
        assert all(result.action.status == ActionStatus.SUCCEEDED for result in results)
        rolled_back = await DurableExecutor(database).rollback_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="rollback-one"
        )
        replay = await DurableExecutor(second).rollback_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="rollback-two"
        )
        assert rolled_back.action.status == replay.action.status == ActionStatus.ROLLED_BACK
        async with database.transaction(tenant_id) as session:
            receipts = list(
                await session.scalars(
                    select(SimulatorCommandRecordModel).where(
                        SimulatorCommandRecordModel.tenant_id == tenant_id
                    )
                )
            )
            assert len(receipts) == 2
    finally:
        await database.close()
        await second.close()
