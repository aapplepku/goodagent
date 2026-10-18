from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from open_commerce.core.enums import (
    ActionType,
    AutonomyMode,
    ConstraintOperator,
    GoalStatus,
    MetricName,
    ObjectiveDirection,
)
from open_commerce.core.goals import (
    AutonomyPolicy,
    BudgetSpec,
    ConstraintSpec,
    EvaluationSchedule,
    GoalSpec,
    HorizonSpec,
    ObjectiveSpec,
)
from open_commerce.core.metrics import get_metric_definition
from open_commerce.core.money import Money, decimal_to_minor_units
from open_commerce.core.types import TimeWindow


def test_money_uses_minor_units_and_uppercase_currency() -> None:
    money = Money(amount_minor=1299, currency="usd")

    assert money.currency == "USD"
    assert money.as_major_decimal() == Decimal("12.99")
    assert decimal_to_minor_units(Decimal("12.995")) == 1300


def test_money_rejects_negative_or_cross_currency_math() -> None:
    with pytest.raises(ValidationError):
        Money(amount_minor=-1, currency="USD")
    with pytest.raises(ValidationError):
        Money.model_validate({"amount_minor": 1.2, "currency": "USD"})

    with pytest.raises(ValueError, match="currency mismatch"):
        Money(amount_minor=100, currency="USD").add(Money(amount_minor=100, currency="EUR"))


def test_time_window_requires_aware_ordered_utc_datetimes() -> None:
    start = datetime(2026, 9, 1, tzinfo=UTC)

    window = TimeWindow(start_at=start, end_at=start + timedelta(days=1))

    assert window.start_at.tzinfo == UTC
    with pytest.raises(ValidationError):
        TimeWindow(start_at=datetime(2026, 9, 1), end_at=start + timedelta(days=1))
    with pytest.raises(ValidationError):
        TimeWindow(start_at=start, end_at=start)


def test_metric_registry_rejects_invalid_operator_for_metric() -> None:
    definition = get_metric_definition(MetricName.CAC)

    assert ConstraintOperator.LTE in definition.allowed_operators
    with pytest.raises(ValidationError):
        ConstraintSpec(metric=MetricName.CAC, operator=ConstraintOperator.GTE, value=Decimal("40"))


def test_goal_spec_validates_allowed_actions_and_horizon() -> None:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    goal = GoalSpec(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Acquire new customers",
        objective=ObjectiveSpec(
            metric=MetricName.NEW_CUSTOMERS,
            direction=ObjectiveDirection.MAXIMIZE,
            target=Decimal("200"),
        ),
        horizon=HorizonSpec(start_at=now, end_at=now + timedelta(days=30)),
        budgets=[
            BudgetSpec(
                kind="total_acquisition_and_promotion",
                amount=Money(amount_minor=1_000_000, currency="USD"),
            ),
        ],
        constraints=[
            ConstraintSpec(
                metric=MetricName.CONTRIBUTION_MARGIN_RATE,
                operator=ConstraintOperator.GTE,
                value=Decimal("0.25"),
            ),
        ],
        autonomy=AutonomyPolicy(
            default_mode=AutonomyMode.APPROVAL_REQUIRED,
            per_action={ActionType.SET_SEARCH_BOOST: AutonomyMode.BOUNDED_AUTO},
        ),
        allowed_action_types={ActionType.CREATE_DISCOUNT, ActionType.SET_SEARCH_BOOST},
        evaluation_schedule=EvaluationSchedule(cadence="daily", timezone="UTC"),
        status=GoalStatus.DRAFT,
        created_at=now,
    )

    assert goal.autonomy.mode_for(ActionType.SET_SEARCH_BOOST) == AutonomyMode.BOUNDED_AUTO
    assert goal.autonomy.mode_for(ActionType.CREATE_DISCOUNT) == AutonomyMode.APPROVAL_REQUIRED

    with pytest.raises(ValidationError):
        GoalSpec.model_validate({**goal.model_dump(), "allowed_action_types": set()})
