"""Settle actual simulator spend against durable total and daily accounts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.controller.models import ControllerActionRecord, GoalRecord
from open_commerce.core.actions import CreateDiscountIntent, SetCampaignBudgetIntent
from open_commerce.core.enums import ActionStatus
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.repositories.budgets import SqlBudgetRepository
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.simulator.models import DailyMetrics, SimulatorState


class SimulationBudget:
    """Use only inside the simulator mutation's tenant-locked transaction."""

    def __init__(self, session: AsyncSession, tenant_id: UUID, goal: GoalRecord) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.goal = goal
        self.repo = ControllerRepository(session, tenant_id)
        self.ledger = SqlBudgetRepository(session)
        self.accounts: list[BudgetAccountRecord] = []
        self.actions: list[ControllerActionRecord] = []
        self.ad_allowances: dict[UUID, int] = {}

    async def prepare_day(self, state: SimulatorState) -> None:
        await self.repo.ensure_daily_budget(self.goal, state.current_time)
        self.accounts = list(
            await self.session.scalars(
                select(BudgetAccountRecord).where(
                    BudgetAccountRecord.tenant_id == self.tenant_id,
                    BudgetAccountRecord.goal_id == self.goal.spec.id,
                    BudgetAccountRecord.period_start <= state.current_time,
                    BudgetAccountRecord.period_end > state.current_time,
                )
            )
        )
        total = next(item for item in self.accounts if item.budget_kind == "goal")
        daily = next(item for item in self.accounts if item.budget_kind == "daily")
        self.actions = await self.repo.list_actions(goal_id=self.goal.spec.id)
        self.ad_allowances = {}
        for record in self.actions:
            action = record.action
            outstanding = await self.ledger.outstanding_minor(self.tenant_id, total.id, action.id)
            intent = action.intent
            end = (
                intent.ends_at
                if isinstance(intent, CreateDiscountIntent)
                else self.goal.spec.horizon.end_at
            )
            if (
                action.status
                not in {ActionStatus.SUCCEEDED, ActionStatus.EVALUATING, ActionStatus.COMPLETED}
                or end <= state.current_time
            ):
                if outstanding:
                    await self.ledger.release(
                        self.tenant_id,
                        total.id,
                        outstanding,
                        f"{action.id}:unused:{state.current_time.date()}",
                        action.id,
                    )
                continue
            daily_reserved = await self.ledger.outstanding_minor(
                self.tenant_id, daily.id, action.id
            )
            allowance = outstanding
            if isinstance(intent, SetCampaignBudgetIntent):
                allowance = min(
                    outstanding,
                    max(0, intent.new_budget.amount_minor - intent.current_budget.amount_minor),
                )
            if daily_reserved == 0 and allowance:
                amount = min(allowance, await self.ledger.available_minor(self.tenant_id, daily.id))
                await self.ledger.reserve(
                    self.tenant_id,
                    daily.id,
                    amount,
                    f"{action.id}:carry:{state.current_time.date()}",
                    action.id,
                )
                daily_reserved = amount
            if isinstance(intent, CreateDiscountIntent):
                discount = next(
                    (
                        item
                        for item in state.discounts
                        if item.created_by_command == action.idempotency_key
                    ),
                    None,
                )
                if discount is not None:
                    discount.spend_cap_for_day_minor = discount.spent_minor + min(
                        outstanding, daily_reserved
                    )
            elif isinstance(intent, SetCampaignBudgetIntent):
                self.ad_allowances[action.id] = min(allowance, daily_reserved)
        free = min(
            [await self.ledger.available_minor(self.tenant_id, item.id) for item in self.accounts]
        )
        state.total_spend_limit_minor = total.allocated_minor
        state.daily_spend_limit_minor = daily.allocated_minor
        state.ad_spend_limit_minor = max(0, free) + sum(self.ad_allowances.values())

    async def settle_day(
        self, state: SimulatorState, metric: DailyMetrics, before_discounts: dict[str, int]
    ) -> None:
        prefix = f"sim:{state.id}:{state.generation}:{metric.metric_date}"
        for account in self.accounts:
            remaining_ads = metric.ad_spend_minor
            for action_id, allowance in self.ad_allowances.items():
                released = min(
                    remaining_ads,
                    allowance,
                    await self.ledger.outstanding_minor(self.tenant_id, account.id, action_id),
                )
                await self.ledger.release(
                    self.tenant_id,
                    account.id,
                    released,
                    f"{prefix}:ads:{action_id}:release",
                    action_id,
                )
                remaining_ads -= released
            await self.ledger.commit(
                self.tenant_id, account.id, metric.ad_spend_minor, f"{prefix}:ads"
            )
            for record in self.actions:
                discount = next(
                    (
                        item
                        for item in state.discounts
                        if item.created_by_command == record.action.idempotency_key
                    ),
                    None,
                )
                if discount is None:
                    continue
                used = discount.spent_minor - before_discounts.get(discount.id, 0)
                if used == 0:
                    continue
                outstanding = await self.ledger.outstanding_minor(
                    self.tenant_id, account.id, record.action.id
                )
                await self.ledger.release(
                    self.tenant_id,
                    account.id,
                    min(used, outstanding),
                    f"{prefix}:promo:{record.action.id}:release",
                    record.action.id,
                )
                await self.ledger.commit(
                    self.tenant_id,
                    account.id,
                    used,
                    f"{prefix}:promo:{record.action.id}:settle",
                    record.action.id,
                )
            if account.budget_kind == "daily":
                await self._release_unspent(account, prefix)
        await self.release_expired(state.current_time)

    async def _release_unspent(self, account: BudgetAccountRecord, prefix: str) -> None:
        for record in self.actions:
            outstanding = await self.ledger.outstanding_minor(
                self.tenant_id, account.id, record.action.id
            )
            if outstanding:
                await self.ledger.release(
                    self.tenant_id,
                    account.id,
                    outstanding,
                    f"{prefix}:close:{record.action.id}",
                    record.action.id,
                )

    async def release_expired(self, now: datetime) -> None:
        for account in self.accounts:
            if account.budget_kind != "goal":
                continue
            for record in self.actions:
                intent = record.action.intent
                end = (
                    intent.ends_at
                    if isinstance(intent, CreateDiscountIntent)
                    else self.goal.spec.horizon.end_at
                )
                if end > now:
                    continue
                outstanding = await self.ledger.outstanding_minor(
                    self.tenant_id, account.id, record.action.id
                )
                if outstanding:
                    await self.ledger.release(
                        self.tenant_id,
                        account.id,
                        outstanding,
                        f"{record.action.id}:expired",
                        record.action.id,
                    )
