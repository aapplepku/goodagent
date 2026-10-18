"""Typed simulator models and public summaries."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from open_commerce.core.enums import Capability, ExecutionStatus
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash, ensure_utc
from open_commerce.simulator.merchandising_models import MerchandisingState, MerchandisingSummary

ScenarioId = Literal["acquisition_v1", "excess_inventory_v1", "search_conversion_v1"]
ENGINE_VERSION = "simulator.2"
PAIRED_ENGINE_VERSION = "simulator.2-paired-exogenous-v1"
SimulatorStatus = Literal["created", "running", "completed"]


class CatalogGeneratorConfig(StrictDomainModel):
    """Seeded catalog generation settings."""

    product_count: int = Field(default=1000, ge=1)
    categories: list[str] = Field(
        default_factory=lambda: ["apparel", "footwear", "outdoor", "electronics", "home"],
        min_length=1,
    )
    variants_min: int = Field(default=1, ge=1)
    variants_max: int = Field(default=5, ge=1)
    cold_start_rate: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    excess_inventory_rate: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    low_stock_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)

    @model_validator(mode="after")
    def validate_variant_range(self) -> CatalogGeneratorConfig:
        if self.variants_max < self.variants_min:
            raise ValueError("variants_max must be greater than or equal to variants_min")
        return self


class CustomerSegment(StrictDomainModel):
    """Pseudonymous shopper segment without PII."""

    id: str
    label: str
    share: Decimal = Field(gt=0)
    price_sensitivity: Decimal = Field(ge=0)
    quality_preference: Decimal = Field(ge=0)
    discount_elasticity: Decimal = Field(ge=0)
    category_affinities: dict[str, Decimal]
    base_conversion_adjustment: Decimal = Decimal("0")
    new_customer_probability: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)


class TrafficChannel(StrictDomainModel):
    """Traffic channel fixture."""

    id: str
    label: str
    base_sessions: int = Field(ge=0)
    paid: bool = False
    search_surface: bool = False


class CampaignState(StrictDomainModel):
    """Simulated paid campaign state."""

    id: str
    name: str
    channel_id: str
    daily_budget_minor: int = Field(ge=0)
    initial_daily_budget_minor: int = Field(ge=0)
    max_reach: int = Field(gt=0)
    scale_minor: int = Field(gt=0)
    baseline_quality: Decimal = Field(ge=0, le=1)
    saturation_penalty: Decimal = Field(ge=0, le=1)
    active: bool = True


class EconomicParameters(StrictDomainModel):
    """Inspectible economic parameters for demand and contribution math."""

    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_fee_rate: Decimal = Field(default=Decimal("0.029"), ge=0, le=1)
    click_intercept: Decimal = Decimal("-3.15")
    conversion_intercept: Decimal = Decimal("-3.65")
    cart_rate: Decimal = Field(default=Decimal("0.42"), ge=0, le=1)
    trust: Decimal = Decimal("0.42")
    shipping_friction: Decimal = Decimal("0.18")
    promotion_urgency_lift: Decimal = Decimal("0.22")
    seasonality_amplitude: Decimal = Decimal("0.08")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ScenarioDefinition(StrictDomainModel):
    """Versioned simulator scenario definition."""

    id: ScenarioId
    version: str
    display_name: str
    description: str
    seed: int
    start_at: datetime
    catalog: CatalogGeneratorConfig
    customer_segments: list[CustomerSegment]
    traffic_channels: list[TrafficChannel]
    campaigns: list[CampaignState]
    economics: EconomicParameters
    default_goal: JsonObject
    default_policy: JsonObject
    response_curves: JsonObject = Field(default_factory=dict)

    @field_validator("start_at")
    @classmethod
    def normalize_start_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ProductVariantState(StrictDomainModel):
    """Mutable simulator variant state."""

    id: str
    source_variant_id: str
    sku: str
    title: str
    price_minor: int = Field(gt=0)
    original_price_minor: int = Field(gt=0)
    cost_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    inventory: int = Field(ge=0)
    initial_inventory: int = Field(ge=0)
    available: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ProductState(StrictDomainModel):
    """Mutable simulator product state."""

    id: str
    source_product_id: str
    title: str
    category: str
    brand: str
    description_text: str
    tags: list[str]
    attributes: dict[str, str]
    quality_score: Decimal = Field(ge=0, le=1)
    popularity_score: Decimal = Field(ge=0, le=1)
    age_days: int = Field(ge=0)
    cold_start: bool = False
    excess_inventory: bool = False
    low_stock: bool = False
    variants: list[ProductVariantState] = Field(min_length=1)

    @property
    def total_inventory(self) -> int:
        """Return available inventory across variants."""

        return sum(variant.inventory for variant in self.variants)


class DiscountState(StrictDomainModel):
    """Simulator discount state."""

    id: str
    code: str | None
    discount_kind: Literal["percentage", "fixed_amount"]
    value: Decimal
    starts_at: datetime
    ends_at: datetime
    product_ids: list[str] = Field(default_factory=list)
    category_paths: list[str] = Field(default_factory=list)
    active: bool = True
    created_by_command: str

    maximum_cost_minor: int | None = Field(default=None, gt=0)
    spent_minor: int = Field(default=0, ge=0)
    spend_cap_for_day_minor: int | None = Field(default=None, ge=0)
    minimum_subtotal_minor: int | None = Field(default=None, ge=0)
    new_customers_only: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def applies_to(self, product: ProductState, at: datetime) -> bool:
        """Return whether the discount can affect this product at a virtual time."""

        normalized_at = ensure_utc(at)
        if not self.active or not (self.starts_at <= normalized_at < self.ends_at):
            return False
        return (
            (not self.product_ids and not self.category_paths)
            or product.id in self.product_ids
            or (not self.product_ids and product.category in self.category_paths)
        )


class SearchBoostState(StrictDomainModel):
    """Internal simulator search exposure boost."""

    id: str
    query_text: str
    category: str | None = None
    product_ids: list[str] = Field(default_factory=list)
    multiplier: Decimal = Field(gt=0)
    starts_at: datetime
    ends_at: datetime
    active: bool = True
    created_by_command: str

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def applies_to(self, query_text: str, product: ProductState, at: datetime) -> bool:
        """Return whether this boost applies without bypassing relevance."""

        normalized_at = ensure_utc(at)
        query_matches = self.query_text.lower() in query_text.lower()
        product_matches = not self.product_ids or product.id in self.product_ids
        category_matches = self.category is None or product.category == self.category
        return (
            self.active
            and self.starts_at <= normalized_at < self.ends_at
            and query_matches
            and product_matches
            and category_matches
        )


class Exposure(StrictDomainModel):
    """One ranked product exposure candidate."""

    product_id: str
    score: Decimal
    relevance: Decimal
    position: int = Field(ge=1)


class DailyMetrics(StrictDomainModel):
    """Materialized simulator metrics for one virtual day."""

    metric_date: date
    day_index: int
    is_history: bool = False
    sessions: int = Field(ge=0)
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    carts: int = Field(ge=0)
    orders: int = Field(ge=0)
    units_sold: int = Field(ge=0)
    new_customers: int = Field(ge=0)
    gross_revenue_minor: int = Field(ge=0)
    discounts_minor: int = Field(ge=0)
    cogs_minor: int = Field(ge=0)
    variable_fees_minor: int = Field(ge=0)
    ad_spend_minor: int = Field(ge=0)
    contribution_profit_minor: int
    conversion_rate: Decimal
    cac_minor: int | None
    contribution_margin_rate: Decimal
    discount_rate: Decimal
    search_attributed_purchases: int = Field(ge=0)
    ending_inventory_units: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_accounting_identity(self) -> DailyMetrics:
        expected = (
            self.gross_revenue_minor
            - self.discounts_minor
            - self.cogs_minor
            - self.variable_fees_minor
            - self.ad_spend_minor
        )
        if self.contribution_profit_minor != expected:
            raise ValueError("contribution profit does not match accounting identity")
        return self


class SimulatorEvent(StrictDomainModel):
    """Aggregated normalized simulator event."""

    id: str
    occurred_at: datetime
    type: str
    count: int = Field(ge=0)
    dimensions: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, int | str] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class SimulatorCommandRecord(StrictDomainModel):
    """Idempotent simulator provider command history."""

    execution_id: UUID
    tenant_id: UUID
    instance_id: UUID
    action_type: str
    idempotency_key: str
    status: ExecutionStatus
    before_state: JsonObject
    after_state: JsonObject | None = None
    rollback_state: JsonObject | None = None
    created_at: datetime
    rollback_of: UUID | None = None

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class SimulatorSnapshot(StrictDomainModel):
    """Immutable snapshot marker for simulator state inspection."""

    id: str
    label: str
    virtual_time: datetime
    state_hash: str
    summary: JsonObject

    @field_validator("virtual_time")
    @classmethod
    def normalize_virtual_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class SimulatorState(StrictDomainModel):
    """Full mutable simulator state for one tenant-owned instance."""

    id: UUID
    tenant_id: UUID
    scenario_id: ScenarioId
    scenario_version: str
    engine_version: str = "simulator.1"
    seed: int
    current_time: datetime
    start_at: datetime
    day: int = 0
    generation: int = Field(default=0, ge=0)
    total_spend_limit_minor: int | None = Field(default=None, ge=0)
    daily_spend_limit_minor: int | None = Field(default=None, ge=0)
    ad_spend_limit_minor: int | None = Field(default=None, ge=0)
    status: SimulatorStatus = "created"
    products: list[ProductState]
    customer_segments: list[CustomerSegment]
    traffic_channels: list[TrafficChannel]
    campaigns: list[CampaignState]
    discounts: list[DiscountState] = Field(default_factory=list)
    search_boosts: list[SearchBoostState] = Field(default_factory=list)
    metrics: list[DailyMetrics] = Field(default_factory=list)
    events: list[SimulatorEvent] = Field(default_factory=list)
    snapshots: list[SimulatorSnapshot] = Field(default_factory=list)
    command_history: list[SimulatorCommandRecord] = Field(default_factory=list)
    merchandising: MerchandisingState | None = Field(default=None, exclude_if=lambda v: v is None)

    @field_validator("current_time", "start_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def state_hash(self) -> str:
        """Stable hash over public state relevant to simulator reproducibility."""

        return canonical_hash(
            {
                "scenario_id": self.scenario_id,
                "scenario_version": self.scenario_version,
                "engine_version": self.engine_version,
                "seed": self.seed,
                "current_time": self.current_time,
                "day": self.day,
                "total_spend_limit_minor": self.total_spend_limit_minor,
                "daily_spend_limit_minor": self.daily_spend_limit_minor,
                "ad_spend_limit_minor": self.ad_spend_limit_minor,
                "products": [
                    {
                        "id": product.id,
                        "inventory": [variant.inventory for variant in product.variants],
                        "prices": [variant.price_minor for variant in product.variants],
                    }
                    for product in self.products
                ],
                "campaigns": [
                    {
                        "id": campaign.id,
                        "daily_budget_minor": campaign.daily_budget_minor,
                        "active": campaign.active,
                    }
                    for campaign in self.campaigns
                ],
                "discounts": self.discounts,
                "search_boosts": self.search_boosts,
                "metrics": self.metrics,
                **({"merchandising": self.merchandising} if self.merchandising is not None else {}),
            }
        )


class ScenarioSummary(StrictDomainModel):
    """Public scenario listing item."""

    id: ScenarioId
    version: str
    display_name: str
    description: str
    default_seed: int
    product_count: int
    categories: list[str]
    capabilities: list[Capability]
    default_goal: JsonObject
    default_policy: JsonObject


class ScenarioListResponse(StrictDomainModel):
    """Scenario collection response."""

    items: list[ScenarioSummary]
    next_cursor: str | None = None


class CatalogSummary(StrictDomainModel):
    """Compact catalog status for APIs and CLI."""

    product_count: int
    variant_count: int
    inventory_units: int
    cold_start_products: int
    excess_inventory_products: int
    low_stock_products: int


class CampaignSummary(StrictDomainModel):
    """Compact campaign status."""

    id: str
    name: str
    channel_id: str
    daily_budget_minor: int
    active: bool


class SimulatorStateResponse(StrictDomainModel):
    """Public state summary for a simulator instance."""

    id: UUID
    tenant_id: UUID
    scenario_id: ScenarioId
    scenario_version: str
    engine_version: str
    seed: int
    current_time: datetime
    start_at: datetime
    day: int
    status: SimulatorStatus
    state_hash: str
    catalog: CatalogSummary
    campaigns: list[CampaignSummary]
    active_discounts: int
    active_search_boosts: int
    latest_metrics: DailyMetrics | None
    command_count: int
    merchandising: MerchandisingSummary | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SimulatorMetricsResponse(StrictDomainModel):
    """Daily metric series response."""

    instance_id: UUID
    items: list[DailyMetrics]
    next_cursor: str | None = None


class MetricTotals(StrictDomainModel):
    """Aggregated simulator outcome totals."""

    days: int
    sessions: int
    orders: int
    units_sold: int
    new_customers: int
    gross_revenue_minor: int
    discounts_minor: int
    cogs_minor: int
    variable_fees_minor: int
    ad_spend_minor: int
    contribution_profit_minor: int
    search_attributed_purchases: int
    conversion_rate: Decimal
    cac_minor: int | None
    contribution_margin_rate: Decimal


class BaselineComparisonResponse(StrictDomainModel):
    """Current scenario outcome compared with a no-intervention baseline."""

    instance_id: UUID
    scenario_id: ScenarioId
    scenario_version: str
    seed: int
    current: MetricTotals
    baseline: MetricTotals
    delta: MetricTotals
    baseline_hash: str


class CreateSimulatorInstanceRequest(StrictDomainModel):
    """Create a simulator instance from a scenario."""

    seed: int | None = None


class CreateSimulatorInstanceAliasRequest(CreateSimulatorInstanceRequest):
    """Create a simulator instance through the contract root route."""

    scenario_id: ScenarioId = "acquisition_v1"


class AdvanceSimulatorRequest(StrictDomainModel):
    """Advance a simulator instance by virtual hours."""

    hours: int = Field(default=24, gt=0, le=24 * 366)


class RunUntilSimulatorRequest(StrictDomainModel):
    """Advance virtual time until a timestamp."""

    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ResetSimulatorRequest(StrictDomainModel):
    """Reset an instance, optionally replacing the seed."""

    seed: int | None = None
