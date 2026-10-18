"""Goal, budget, constraint, and autonomy domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from open_commerce.core.enums import (
    ActionType,
    AutonomyMode,
    ConstraintOperator,
    GoalStatus,
    MetricName,
    ObjectiveDirection,
)
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.core.metrics import validate_metric_operator
from open_commerce.core.money import Money
from open_commerce.core.types import StrictDomainModel, TimeWindow, ensure_utc


class ObjectiveSpec(StrictDomainModel):
    """A finite measurable objective."""

    metric: MetricName
    direction: ObjectiveDirection
    target: Decimal | None = None
    scope: Literal["store", "excess_inventory"] = "store"

    @model_validator(mode="after")
    def validate_scope(self) -> ObjectiveSpec:
        if self.scope == "excess_inventory" and self.metric != MetricName.UNITS_SOLD:
            raise ValueError("Excess inventory scope is defined only for units_sold")
        return self


class HorizonSpec(TimeWindow):
    """Goal horizon."""


class BudgetSpec(StrictDomainModel):
    """Budget allocated to a goal."""

    kind: str
    amount: Money
    period: TimeWindow | None = None


class ConstraintSpec(StrictDomainModel):
    """Typed metric constraint with a finite operator."""

    metric: MetricName
    operator: ConstraintOperator
    value: Decimal | Money
    hard: bool = True

    @model_validator(mode="after")
    def validate_registry(self) -> ConstraintSpec:
        validate_metric_operator(self.metric, self.operator)
        return self


class AutonomyPolicy(StrictDomainModel):
    """Goal-level autonomy policy with per-action overrides."""

    default_mode: AutonomyMode = AutonomyMode.APPROVAL_REQUIRED
    per_action: dict[ActionType, AutonomyMode] = Field(default_factory=dict)

    def mode_for(self, action_type: ActionType) -> AutonomyMode:
        """Return the effective autonomy mode for an action type."""

        return self.per_action.get(action_type, self.default_mode)


class EvaluationSchedule(StrictDomainModel):
    """Cadence for goal evaluation."""

    cadence: str = Field(pattern="^(hourly|daily|manual)$")
    timezone: str = "UTC"


class GoalSpec(StrictDomainModel):
    """Canonical merchant goal specification."""

    id: UUID
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=200)
    objective: ObjectiveSpec
    horizon: HorizonSpec
    budgets: list[BudgetSpec]
    constraints: list[ConstraintSpec]
    autonomy: AutonomyPolicy
    allowed_action_types: set[ActionType]
    evaluation_schedule: EvaluationSchedule
    status: GoalStatus
    created_at: datetime
    merchandising: MerchandisingConstraints | None = Field(
        default=None, exclude_if=lambda v: v is None
    )

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_goal(self) -> GoalSpec:
        if self.merchandising is not None:
            if self.allowed_action_types & self.merchandising.prohibited_actions:
                raise ValueError("goal allows a prohibited merchandising action")
            if any(budget.amount.amount_minor for budget in self.budgets):
                raise ValueError(
                    "merchandising uses its separate promotion cap, not acquisition budgets"
                )
        if not self.allowed_action_types:
            raise ValueError("allowed_action_types must not be empty")
        if self.horizon.end_at <= self.created_at:
            raise ValueError("horizon must end after goal creation")
        for budget in self.budgets:
            if budget.period and budget.period.start_at < self.horizon.start_at:
                raise ValueError("budget period cannot start before horizon")
        return self
