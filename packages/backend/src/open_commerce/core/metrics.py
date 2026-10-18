"""Metric registry and metric value models."""

from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from pydantic import Field, field_validator

from open_commerce.core.enums import Capability, ConstraintOperator, MetricName, MetricUnit
from open_commerce.core.errors import MetricRegistryError
from open_commerce.core.types import StrictDomainModel, TimeWindow, ensure_utc


class ConfidenceInterval(StrictDomainModel):
    """Numeric interval for impact estimates and observed metrics."""

    lower: Decimal
    point: Decimal
    upper: Decimal
    level: Decimal = Field(gt=0, le=1)


class MetricPoint(StrictDomainModel):
    """A timestamped metric value with definition metadata."""

    metric: MetricName
    value: Decimal
    unit: MetricUnit
    window: TimeWindow
    dimensions: dict[str, str] = Field(default_factory=dict)
    definition_version: str
    freshness_at: datetime

    @field_validator("freshness_at")
    @classmethod
    def normalize_freshness(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MetricDefinition(StrictDomainModel):
    """Finite metric metadata used by goals, constraints, and tests."""

    metric: MetricName
    unit: MetricUnit
    definition_version: str
    allowed_operators: set[ConstraintOperator]
    required_capabilities: set[Capability]
    description: str


_ALL_OPERATORS = {
    ConstraintOperator.LT,
    ConstraintOperator.LTE,
    ConstraintOperator.EQ,
    ConstraintOperator.GTE,
    ConstraintOperator.GT,
}

_REGISTRY = {
    MetricName.NEW_CUSTOMERS: MetricDefinition(
        metric=MetricName.NEW_CUSTOMERS,
        unit=MetricUnit.COUNT,
        definition_version="metric.new_customers.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_ORDERS},
        description="First-time purchasers in the measurement window.",
    ),
    MetricName.CAC: MetricDefinition(
        metric=MetricName.CAC,
        unit=MetricUnit.MONEY_MINOR,
        definition_version="metric.cac.v1",
        allowed_operators={ConstraintOperator.LT, ConstraintOperator.LTE},
        required_capabilities={Capability.READ_ORDERS, Capability.READ_CAMPAIGNS},
        description="Acquisition spend divided by new customers.",
    ),
    MetricName.REVENUE: MetricDefinition(
        metric=MetricName.REVENUE,
        unit=MetricUnit.MONEY_MINOR,
        definition_version="metric.revenue.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_ORDERS},
        description="Gross order revenue before refunds.",
    ),
    MetricName.CONTRIBUTION_PROFIT: MetricDefinition(
        metric=MetricName.CONTRIBUTION_PROFIT,
        unit=MetricUnit.MONEY_MINOR,
        definition_version="metric.contribution_profit.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_ORDERS},
        description="Revenue less discounts, COGS, variable fees, and attributed spend.",
    ),
    MetricName.CONTRIBUTION_MARGIN_RATE: MetricDefinition(
        metric=MetricName.CONTRIBUTION_MARGIN_RATE,
        unit=MetricUnit.RATE,
        definition_version="metric.contribution_margin_rate.v1",
        allowed_operators={ConstraintOperator.GT, ConstraintOperator.GTE},
        required_capabilities={Capability.READ_ORDERS},
        description="Contribution profit divided by gross revenue.",
    ),
    MetricName.CONVERSION_RATE: MetricDefinition(
        metric=MetricName.CONVERSION_RATE,
        unit=MetricUnit.RATE,
        definition_version="metric.conversion_rate.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_BEHAVIOR_EVENTS, Capability.READ_ORDERS},
        description="Purchase conversions divided by eligible sessions.",
    ),
    MetricName.DISCOUNT_RATE: MetricDefinition(
        metric=MetricName.DISCOUNT_RATE,
        unit=MetricUnit.RATE,
        definition_version="metric.discount_rate.v1",
        allowed_operators={ConstraintOperator.LT, ConstraintOperator.LTE},
        required_capabilities={Capability.READ_DISCOUNTS},
        description="Discount value divided by eligible merchandise value.",
    ),
    MetricName.UNITS_SOLD: MetricDefinition(
        metric=MetricName.UNITS_SOLD,
        unit=MetricUnit.COUNT,
        definition_version="metric.units_sold.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_ORDERS},
        description="Units sold in the measurement window.",
    ),
    MetricName.INVENTORY_DAYS_OF_SUPPLY: MetricDefinition(
        metric=MetricName.INVENTORY_DAYS_OF_SUPPLY,
        unit=MetricUnit.DAYS,
        definition_version="metric.inventory_days_of_supply.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_INVENTORY, Capability.READ_ORDERS},
        description="Inventory divided by trailing average daily demand.",
    ),
    MetricName.SEARCH_CONVERSION_RATE: MetricDefinition(
        metric=MetricName.SEARCH_CONVERSION_RATE,
        unit=MetricUnit.RATE,
        definition_version="metric.search_conversion_rate.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_BEHAVIOR_EVENTS},
        description="Search-attributed purchases divided by search sessions.",
    ),
    MetricName.SEARCH_ATTRIBUTED_PURCHASES: MetricDefinition(
        metric=MetricName.SEARCH_ATTRIBUTED_PURCHASES,
        unit=MetricUnit.COUNT,
        definition_version="metric.search_attributed_purchases.v1",
        allowed_operators=_ALL_OPERATORS,
        required_capabilities={Capability.READ_BEHAVIOR_EVENTS, Capability.READ_ORDERS},
        description="Purchases attributed to this project's search surface.",
    ),
}

METRIC_REGISTRY = MappingProxyType(_REGISTRY)


def get_metric_definition(metric: MetricName) -> MetricDefinition:
    """Return metadata for a supported metric."""

    try:
        return METRIC_REGISTRY[metric]
    except KeyError as exc:
        raise MetricRegistryError(f"Unsupported metric: {metric.value}") from exc


def validate_metric_operator(metric: MetricName, operator: ConstraintOperator) -> None:
    """Raise when an operator is not allowed for the metric."""

    definition = get_metric_definition(metric)
    if operator not in definition.allowed_operators:
        raise MetricRegistryError(f"{operator.value} is not valid for {metric.value}")
