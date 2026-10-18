"""Actual synthetic spend is bounded and settles once in PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.durable_executor import DurableExecutor
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import ActionStatus
from open_commerce.core.money import Money
from open_commerce.persistence.models.budgets import BudgetAccountRecord, BudgetLedgerEntryRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.engine import totals_for_metrics
from open_commerce.simulator.service import SimulatorBusyError

from .test_durable_controller import approve, prepared_goal

pytestmark = pytest.mark.integration


async def test_total_and_daily_caps_apply_to_actual_campaign_spend(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant_id,
            request=GoalCreateRequest(
                budget=Money(amount_minor=5000, currency="USD"),
                daily_budget=Money(amount_minor=2000, currency="USD"),
            ),
            idempotency_key="small-budget",
        )
        simulator = service.simulator_service
        first = await simulator.advance(
            tenant_id=tenant_id,
            instance_id=goal.simulator_instance_id,
            hours=96,
            idempotency_key="four-days",
        )
        replay = await simulator.advance(
            tenant_id=tenant_id,
            instance_id=goal.simulator_instance_id,
            hours=96,
            idempotency_key="four-days",
        )
        assert first == replay
        state = await simulator.get_full_state(
            tenant_id=tenant_id, instance_id=goal.simulator_instance_id
        )
        days = [item for item in state.metrics if not item.is_history]
        assert [item.ad_spend_minor for item in days] == [2000, 2000, 1000, 0]
        async with database.transaction(tenant_id) as session:
            accounts = list(
                await session.scalars(
                    select(BudgetAccountRecord).where(BudgetAccountRecord.tenant_id == tenant_id)
                )
            )
            for account in accounts:
                entries = list(
                    await session.scalars(
                        select(BudgetLedgerEntryRecord).where(
                            BudgetLedgerEntryRecord.tenant_id == tenant_id,
                            BudgetLedgerEntryRecord.account_id == account.id,
                        )
                    )
                )
                spent = sum(item.amount_minor for item in entries if item.entry_type == "committed")
                assert spent <= account.allocated_minor
                if account.budget_kind == "goal":
                    assert spent == 5000
    finally:
        await database.close()


async def test_discount_reservations_settle_actual_cost_and_rollback_releases_only_unused(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database, "create_discount")
        await approve(database, tenant_id, action_id)
        service = DurableControllerService(database)
        executed = await service.execute_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
        )
        assert executed.action.status == ActionStatus.SUCCEEDED
        instance_id = UUID(executed.action.target_provider.resource_id)
        await service.simulator_service.advance(
            tenant_id=tenant_id, instance_id=instance_id, hours=48, idempotency_key="two-days"
        )
        state = await service.simulator_service.get_full_state(
            tenant_id=tenant_id, instance_id=instance_id
        )
        totals = totals_for_metrics(state.metrics, include_history=False)
        discount = state.discounts[0]
        assert discount.spent_minor == totals.discounts_minor
        assert 0 < discount.spent_minor <= 12000
        assert all(
            item.ad_spend_minor + item.discounts_minor <= 25000
            for item in state.metrics
            if not item.is_history
        )
        rolled_back = await service.rollback_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key="rollback"
        )
        assert rolled_back.action.status == ActionStatus.ROLLED_BACK
        async with database.transaction(tenant_id) as session:
            account = await session.scalar(
                select(BudgetAccountRecord).where(
                    BudgetAccountRecord.tenant_id == tenant_id,
                    BudgetAccountRecord.budget_kind == "goal",
                )
            )
            assert account is not None
            entries = list(
                await session.scalars(
                    select(BudgetLedgerEntryRecord).where(
                        BudgetLedgerEntryRecord.tenant_id == tenant_id,
                        BudgetLedgerEntryRecord.account_id == account.id,
                    )
                )
            )
            committed = sum(item.amount_minor for item in entries if item.entry_type == "committed")
            reserved = sum(item.amount_minor for item in entries if item.entry_type == "reserved")
            released = sum(item.amount_minor for item in entries if item.entry_type == "released")
            assert committed == totals.ad_spend_minor + totals.discounts_minor
            assert reserved == released
    finally:
        await database.close()


async def test_advance_and_reset_cannot_race_an_unfinished_execution(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        await approve(database, tenant_id, action_id)

        class Interrupted(DurableExecutor):
            async def _after_prepare(self, attempt_id: UUID) -> None:
                raise RuntimeError("interrupted")

        with pytest.raises(RuntimeError):
            await Interrupted(database).execute(
                tenant_id=tenant_id, action_id=action_id, idempotency_key="execute"
            )
        service = DurableControllerService(database)
        record = await service.get_action(tenant_id=tenant_id, action_id=action_id)
        instance_id = UUID(record.action.target_provider.resource_id)
        with pytest.raises(SimulatorBusyError):
            await service.simulator_service.advance(
                tenant_id=tenant_id, instance_id=instance_id, hours=24, idempotency_key="advance"
            )
        with pytest.raises(SimulatorBusyError):
            await service.simulator_service.reset(
                tenant_id=tenant_id, instance_id=instance_id, seed=42, idempotency_key="reset"
            )
    finally:
        await database.close()
