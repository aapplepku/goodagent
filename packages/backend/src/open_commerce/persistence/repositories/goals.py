"""Goal repository implementation."""

from typing import cast
from uuid import UUID

from sqlalchemy import case, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.goals import BudgetSpec, ConstraintSpec, GoalSpec
from open_commerce.persistence.models.goals import Goal, GoalBudget, GoalConstraint


class SqlGoalRepository:
    """Tenant-scoped SQLAlchemy goal repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant_id: UUID, goal: GoalSpec) -> None:
        """Insert or replace a goal and its child budget/constraint rows."""

        if goal.tenant_id != tenant_id:
            raise ValueError("goal tenant does not match repository scope")
        await self._session.execute(
            delete(GoalConstraint).where(
                GoalConstraint.tenant_id == tenant_id, GoalConstraint.goal_id == goal.id
            )
        )
        await self._session.execute(
            delete(GoalBudget).where(
                GoalBudget.tenant_id == tenant_id, GoalBudget.goal_id == goal.id
            )
        )
        record = await self._session.scalar(
            select(Goal).where(Goal.tenant_id == tenant_id, Goal.id == goal.id)
        )
        values = dict(
            id=goal.id,
            tenant_id=tenant_id,
            name=goal.name,
            objective=cast(dict[str, object], goal.objective.model_dump(mode="json")),
            horizon=cast(dict[str, object], goal.horizon.model_dump(mode="json")),
            autonomy=cast(dict[str, object], goal.autonomy.model_dump(mode="json")),
            allowed_action_types=sorted(action.value for action in goal.allowed_action_types),
            evaluation_schedule=cast(
                dict[str, object],
                goal.evaluation_schedule.model_dump(mode="json"),
            ),
            status=goal.status.value,
            created_at=goal.created_at,
            merchandising=goal.merchandising.model_dump(mode="json")
            if goal.merchandising
            else None,
        )
        if record is None:
            self._session.add(Goal(**values))
        else:
            for key, value in values.items():
                setattr(record, key, value)
            record.version += 1
        await self._session.flush()
        for budget in goal.budgets:
            period = budget.period or goal.horizon
            self._session.add(
                GoalBudget(
                    tenant_id=tenant_id,
                    goal_id=goal.id,
                    kind=budget.kind,
                    allocated_minor=budget.amount.amount_minor,
                    currency=budget.amount.currency,
                    period_start=period.start_at,
                    period_end=period.end_at,
                ),
            )
        for constraint in goal.constraints:
            self._session.add(
                GoalConstraint(
                    tenant_id=tenant_id,
                    goal_id=goal.id,
                    metric=constraint.metric.value,
                    operator=constraint.operator.value,
                    value=cast(dict[str, object], constraint.model_dump(mode="json")["value"]),
                    hard=constraint.hard,
                    created_at=goal.created_at,
                ),
            )

    async def get(self, tenant_id: UUID, goal_id: UUID) -> GoalSpec | None:
        """Load a goal only inside the provided tenant scope."""

        goal = await self._session.scalar(
            select(Goal).where(Goal.tenant_id == tenant_id, Goal.id == goal_id),
        )
        if goal is None:
            return None
        budgets = (
            await self._session.scalars(
                select(GoalBudget)
                .where(GoalBudget.tenant_id == tenant_id, GoalBudget.goal_id == goal_id)
                .order_by(case((GoalBudget.kind == "goal", 0), else_=1), GoalBudget.kind),
            )
        ).all()
        constraints = (
            await self._session.scalars(
                select(GoalConstraint)
                .where(
                    GoalConstraint.tenant_id == tenant_id,
                    GoalConstraint.goal_id == goal_id,
                )
                .order_by(GoalConstraint.metric, GoalConstraint.operator, GoalConstraint.id),
            )
        ).all()
        payload = {
            "id": goal.id,
            "tenant_id": goal.tenant_id,
            "name": goal.name,
            "objective": goal.objective,
            "horizon": goal.horizon,
            "budgets": [
                BudgetSpec(
                    kind=budget.kind,
                    amount={"amount_minor": budget.allocated_minor, "currency": budget.currency},
                    period={"start_at": budget.period_start, "end_at": budget.period_end},
                ).model_dump(mode="json")
                for budget in budgets
            ],
            "constraints": [
                ConstraintSpec(
                    metric=constraint.metric,
                    operator=constraint.operator,
                    value=constraint.value,
                    hard=constraint.hard,
                ).model_dump(mode="json")
                for constraint in constraints
            ],
            "autonomy": goal.autonomy,
            "allowed_action_types": goal.allowed_action_types,
            "evaluation_schedule": goal.evaluation_schedule,
            "status": goal.status,
            "created_at": goal.created_at,
            "merchandising": goal.merchandising,
        }
        return GoalSpec.model_validate(payload)
