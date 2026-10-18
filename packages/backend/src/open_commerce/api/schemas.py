"""Pydantic response schemas for public API endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from open_commerce.controller.goal_interpretation import GoalInterpretation
from open_commerce.controller.models import PlanningMode
from open_commerce.core.enums import ActionStatus, ActionType, AutonomyMode, MetricName
from open_commerce.core.money import Money
from open_commerce.simulator.models import DailyMetrics, MetricTotals, ScenarioId

ServiceStatus = Literal["ready", "not_ready"]
ErrorType = Literal[
    "validation_error",
    "authentication_error",
    "authorization_error",
    "not_found",
    "conflict",
    "precondition_failed",
    "policy_denied",
    "provider_error",
    "rate_limited",
    "temporarily_unavailable",
    "internal_error",
]


class DependencyStatus(BaseModel):
    """Readiness status for one external dependency."""

    name: str
    ok: bool
    latency_ms: float | None = None
    detail: str | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "postgres", "ok": True}]})


class LiveResponse(BaseModel):
    """Liveness response."""

    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    """Readiness response with per-dependency status."""

    status: ServiceStatus
    dependencies: list[DependencyStatus]


class MetaResponse(BaseModel):
    """Service metadata exposed to the frontend and generated SDK."""

    app_name: str
    version: str
    environment: str
    status: ServiceStatus
    dependencies: list[DependencyStatus]


class ApiError(BaseModel):
    """Stable redacted API error body."""

    type: ErrorType
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    """Common public error envelope."""

    error: ApiError


class CursorPage(BaseModel):
    """Common cursor-page shape for growing collections."""

    next_cursor: str | None = None


class CapabilitySummary(BaseModel):
    """Local-demo capability exposed to the UI."""

    key: str
    label: str
    status: Literal["available", "disabled", "teaser"]
    detail: str


class CapabilitiesResponse(BaseModel):
    """Release-facing capability and context summary."""

    api_version: Literal["v1"] = "v1"
    mode: Literal["local_demo", "self_hosted"] = "local_demo"
    tenant_id: UUID
    actor_id: str
    roles: list[str]
    default_autonomy: AutonomyMode
    supported_scenarios: list[ScenarioId]
    supported_action_types: list[ActionType]
    capabilities: list[CapabilitySummary]
    limitations: list[str]


class GoalDraftRequest(BaseModel):
    """Natural-language goal draft request for local deterministic parsing."""

    text: str = Field(min_length=1, max_length=1200)
    seed: int = 42
    planning_mode: PlanningMode = "deterministic"


class GoalDraftResponse(GoalInterpretation):
    """Structured goal draft plus warnings requiring merchant confirmation."""


class MetricDefinition(BaseModel):
    """Public metric definition for UI labels and guardrails."""

    name: MetricName
    label: str
    unit: Literal["count", "money", "rate", "minor_money"]
    description: str
    version: str
    freshness: Literal["fresh", "stale", "empty"]


class MetricsDefinitionsResponse(CursorPage):
    """Metric definition collection."""

    items: list[MetricDefinition]


class MetricSeriesPoint(BaseModel):
    """One metric series point; null means unavailable, not a measured zero."""

    timestamp: datetime
    value: str | None


class MetricsSeriesResponse(CursorPage):
    """Metric time series with release-facing metadata."""

    metric: MetricName
    definition_version: str
    timezone: str
    attribution_model: str
    freshness: Literal["fresh", "stale", "empty"]
    completeness_warnings: list[str]
    items: list[MetricSeriesPoint]


class MetricsSummaryResponse(BaseModel):
    """Current simulator outcome summary."""

    instance_id: UUID | None
    scenario_id: ScenarioId | None
    seed: int | None
    totals: MetricTotals
    latest: DailyMetrics | None
    freshness: Literal["fresh", "stale", "empty"]
    definitions: list[MetricDefinition]


class ProductVariantSummary(BaseModel):
    """Catalog variant details safe for operator UI."""

    id: str
    sku: str
    title: str
    price: Money
    original_price: Money
    inventory: int
    available: bool


class ProductSummary(BaseModel):
    """Catalog product summary without provider secrets or customer data."""

    product_id: str
    title: str
    brand: str
    category: str
    price: Money
    inventory_units: int
    stock_state: Literal["out", "low", "normal", "excess"]
    quality_score: Decimal
    popularity_score: Decimal
    tags: list[str]
    index_status: Literal["indexed", "pending", "not_checked"]
    source_updated_at: datetime
    active_action_count: int | None


class ProductDetail(ProductSummary):
    """Catalog product detail safe for local operator UI."""

    description_text: str
    attributes: dict[str, str]
    variants: list[ProductVariantSummary]
    search_document_preview: str


class ProductListResponse(CursorPage):
    """Product cursor page."""

    items: list[ProductSummary]


class InventoryItem(BaseModel):
    """Inventory row for operator UI."""

    product_id: str
    title: str
    category: str
    inventory_units: int
    stock_state: Literal["out", "low", "normal", "excess"]


class InventoryResponse(CursorPage):
    """Inventory cursor page."""

    items: list[InventoryItem]


class InterventionSummary(BaseModel):
    """Controller action summarized for dashboard/intervention lists."""

    id: UUID
    run_id: UUID
    goal_id: UUID
    type: ActionType
    status: ActionStatus
    policy_outcome: str
    summary: str
    created_at: datetime
    updated_at: datetime


class InterventionListResponse(CursorPage):
    """Intervention cursor page."""

    items: list[InterventionSummary]


class AuditFeedEntry(BaseModel):
    """Redacted audit feed item."""

    id: UUID
    action_id: UUID
    event_type: str
    actor_role: str
    message: str
    occurred_at: datetime
    details: dict[str, Any]


class AuditFeedResponse(CursorPage):
    """Tenant audit feed cursor page."""

    items: list[AuditFeedEntry]
