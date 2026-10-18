"""Durable safety races and fail-closed recovery with real PostgreSQL state."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.durable_executor import DurableExecutor
from open_commerce.controller.models import (
    ControllerRunRequest,
    GoalCreateRequest,
    PolicyUpdateRequest,
    PolicyViolationError,
)
from open_commerce.core.enums import ActionStatus, GoalStatus
from open_commerce.core.errors import BudgetOverspendError
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.models.simulator import SimulatorCommandRecordModel
from open_commerce.persistence.repositories.budgets import SqlBudgetRepository
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state

from .test_durable_controller import approve, prepared_goal

pytestmark = pytest.mark.integration


async def test_parallel_intervention_reservation_race(integration_settings: Settings) -> None:
    database = RuntimeDatabase(integration_settings)
    other = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableControllerService(database)
        await service.update_policy(
            tenant_id=tenant,
            request=PolicyUpdateRequest(max_parallel_interventions=1),
            idempotency_key="one-at-a-time",
        )
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(target_value=Decimal("10000")),
            idempotency_key="goal",
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="activate",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="run",
        )
        run = await service.process_run(tenant_id=tenant, run_id=run.id)
        records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
        pending = [r for r in records if r.action.status == ActionStatus.AWAITING_APPROVAL]
        assert len(pending) >= 2
        for record in pending:
            await approve(database, tenant, record.action.id)
        results = await asyncio.gather(
            service.execute_action(
                tenant_id=tenant, action_id=pending[0].action.id, idempotency_key="one"
            ),
            DurableControllerService(other).execute_action(
                tenant_id=tenant, action_id=pending[1].action.id, idempotency_key="two"
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(r, PolicyViolationError) for r in results) == 1
        state = await service.simulator_service.get_full_state(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
        )
        assert len(state.command_history) == 1
        await database.close()
        database = RuntimeDatabase(integration_settings)
        for record in pending:
            current = await DurableControllerService(database).get_action(
                tenant_id=tenant,
                action_id=record.action.id,
            )
            if current.action.status == ActionStatus.APPROVED:
                with pytest.raises(PolicyViolationError, match="parallel_intervention_limit"):
                    await DurableControllerService(database).execute_action(
                        tenant_id=tenant,
                        action_id=record.action.id,
                        idempotency_key="restart",
                    )
    finally:
        await database.close()
        await other.close()


@pytest.mark.parametrize("change", ["kill", "policy", "target", "expiry"])
async def test_changes_after_approval_block_provider_write(
    integration_settings: Settings, change: str
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database, "set_campaign_budget")
        await approve(database, tenant_id, action_id)
        service = DurableControllerService(database)
        record = await service.get_action(tenant_id=tenant_id, action_id=action_id)
        if change == "kill":
            await service.set_kill_switch(tenant_id=tenant_id, enabled=True, idempotency_key="kill")
        elif change == "policy":
            await service.update_policy(
                tenant_id=tenant_id,
                request=PolicyUpdateRequest(min_observations_for_auto_action=501),
                idempotency_key="policy-change",
            )
        else:
            async with database.transaction(tenant_id, write=True) as session:
                state = await load_state(
                    session, tenant_id, UUID(record.action.target_provider.resource_id)
                )
                if change == "target":
                    campaign_id = str(record.action.normalized_parameters["campaign_id"])
                    next(
                        item for item in state.campaigns if item.id == campaign_id
                    ).daily_budget_minor += 1
                else:
                    state.current_time = record.action.expires_at
                await SqlSimulatorRepository(session).save_state(state)
        with pytest.raises(PolicyViolationError):
            await service.execute_action(
                tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
            )
        async with database.transaction(tenant_id) as session:
            assert (
                list(
                    await session.scalars(
                        select(SimulatorCommandRecordModel).where(
                            SimulatorCommandRecordModel.tenant_id == tenant_id
                        )
                    )
                )
                == []
            )
    finally:
        await database.close()


async def test_kill_after_preparation_releases_reservation_without_effect(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        await approve(database, tenant_id, action_id)

        class KillAfterPrepare(DurableExecutor):
            async def _after_prepare(self, attempt_id: UUID) -> None:
                await DurableControllerService(database).set_kill_switch(
                    tenant_id=tenant_id, enabled=True, idempotency_key="kill-before-write"
                )

        result = await KillAfterPrepare(database).execute(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
        )
        assert result.action.status == ActionStatus.FAILED
        async with database.transaction(tenant_id) as session:
            accounts = list(
                await session.scalars(
                    select(BudgetAccountRecord).where(BudgetAccountRecord.tenant_id == tenant_id)
                )
            )
            for account in accounts:
                assert (
                    await SqlBudgetRepository(session).available_minor(tenant_id, account.id)
                    == account.allocated_minor
                )
            assert (
                list(
                    await session.scalars(
                        select(SimulatorCommandRecordModel).where(
                            SimulatorCommandRecordModel.tenant_id == tenant_id
                        )
                    )
                )
                == []
            )
    finally:
        await database.close()


@pytest.mark.parametrize("kind", ["goal", "daily"])
async def test_budget_reservation_race_and_overrelease(
    integration_settings: Settings, kind: str
) -> None:
    database = RuntimeDatabase(integration_settings)
    other = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        async with database.transaction(tenant_id, write=True) as session:
            account = await session.scalar(
                select(BudgetAccountRecord).where(
                    BudgetAccountRecord.tenant_id == tenant_id,
                    BudgetAccountRecord.budget_kind == kind,
                )
            )
            assert account is not None
            account.allocated_minor = 100
            account_id = account.id

        async def reserve(pool: RuntimeDatabase, key: str) -> int:
            # Exercise the ledger row lock independently of the tenant advisory lock.
            async with pool.transaction(tenant_id) as session:
                return await SqlBudgetRepository(session).reserve(
                    tenant_id, account_id, 70, key, action_id
                )

        results = await asyncio.gather(
            reserve(database, "first"), reserve(other, "second"), return_exceptions=True
        )
        assert sum(isinstance(item, BudgetOverspendError) for item in results) == 1
        async with database.transaction(tenant_id) as session:
            assert await SqlBudgetRepository(session).available_minor(tenant_id, account_id) == 30
        with pytest.raises(BudgetOverspendError, match="release"):
            async with database.transaction(tenant_id) as session:
                await SqlBudgetRepository(session).release(
                    tenant_id, account_id, 71, "bad-release", action_id
                )
    finally:
        await database.close()
        await other.close()


async def test_ambiguous_execution_reconciles_before_retry(integration_settings: Settings) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database, "set_campaign_budget")
        await approve(database, tenant_id, action_id)

        class Interrupted(DurableExecutor):
            async def _after_provider_commit(self, attempt_id: UUID) -> None:
                raise RuntimeError("interrupted before reconciliation")

        with pytest.raises(RuntimeError):
            await Interrupted(database).execute(
                tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
            )
        service = DurableControllerService(database)
        record = await service.get_action(tenant_id=tenant_id, action_id=action_id)
        async with database.transaction(tenant_id, write=True) as session:
            state = await load_state(
                session, tenant_id, UUID(record.action.target_provider.resource_id)
            )
            campaign_id = str(record.action.normalized_parameters["campaign_id"])
            next(item for item in state.campaigns if item.id == campaign_id).daily_budget_minor += 1
            await SqlSimulatorRepository(session).save_state(state)
        for key in ("execute", "retry-delivery"):
            result = await service.execute_action(
                tenant_id=tenant_id, action_id=action_id, idempotency_key=key
            )
            assert result.action.status == ActionStatus.UNCERTAIN
        async with database.transaction(tenant_id) as session:
            receipts = list(
                await session.scalars(
                    select(SimulatorCommandRecordModel).where(
                        SimulatorCommandRecordModel.tenant_id == tenant_id
                    )
                )
            )
            assert len(receipts) == 1
    finally:
        await database.close()
