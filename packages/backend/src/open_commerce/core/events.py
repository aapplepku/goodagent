"""Observation, opportunity, behavioral event, and audit models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from open_commerce.core.enums import (
    ActionType,
    AuditEventType,
    DataSource,
    EventType,
    MetricName,
)
from open_commerce.core.types import (
    ActorRef,
    ConfidenceSummary,
    EntityRef,
    FreshnessStatus,
    JsonObject,
    StrictDomainModel,
    ensure_utc,
)


class EvidenceItem(StrictDomainModel):
    """Evidence reference cited by a detector or hypothesis."""

    id: UUID
    kind: str
    entity_ref: EntityRef | None = None
    summary: str
    safe_details: JsonObject = Field(default_factory=dict)


class CatalogSummary(StrictDomainModel):
    """Compact catalog summary for planning snapshots."""

    product_count: int = Field(ge=0)
    variant_count: int = Field(ge=0)
    active_product_count: int = Field(ge=0)


class InventorySummary(StrictDomainModel):
    """Compact inventory summary."""

    total_units: int = Field(ge=0)
    low_stock_product_count: int = Field(ge=0)
    excess_inventory_product_count: int = Field(ge=0)


class CustomerSummary(StrictDomainModel):
    """Pseudonymous aggregate customer summary."""

    new_customers: int = Field(ge=0)
    returning_customers: int = Field(ge=0)


class ChannelSummary(StrictDomainModel):
    """Aggregate traffic/spend summary."""

    sessions: int = Field(ge=0)
    spend_minor: int = Field(ge=0)
    currency: str = "USD"


class ActiveIntervention(StrictDomainModel):
    """Active intervention reference included in snapshots."""

    action_id: UUID
    type: ActionType
    starts_at: datetime
    ends_at: datetime | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class ActionSummary(StrictDomainModel):
    """Unresolved action summary included in snapshots."""

    action_id: UUID
    type: ActionType
    status: str
    summary: str


class ObservationSnapshot(StrictDomainModel):
    """Immutable, versioned input to one planning cycle."""

    id: UUID
    tenant_id: UUID
    goal_id: UUID
    as_of: datetime
    data_freshness: dict[DataSource, FreshnessStatus]
    metric_values: dict[MetricName, Decimal]
    metric_series_refs: dict[MetricName, UUID] = Field(default_factory=dict)
    catalog_summary: CatalogSummary
    inventory_summary: InventorySummary
    customer_summary: CustomerSummary | None = None
    channel_summary: ChannelSummary | None = None
    active_interventions: list[ActiveIntervention] = Field(default_factory=list)
    unresolved_actions: list[ActionSummary] = Field(default_factory=list)
    confidence: ConfidenceSummary
    content_hash: str

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Opportunity(StrictDomainModel):
    """Deterministic business opportunity detected from a snapshot."""

    id: UUID
    tenant_id: UUID
    goal_id: UUID
    snapshot_id: UUID
    type: str
    entity_refs: list[EntityRef]
    evidence: list[EvidenceItem]
    estimated_value_minor: int | None = None
    currency: str | None = None
    confidence: Decimal = Field(ge=0, le=1)
    eligible_action_types: set[ActionType]
    diagnostic_code: str
    status: str = "open"


class BehavioralEvent(StrictDomainModel):
    """Consent-aware pseudonymous behavioral event."""

    event_id: str
    tenant_id: UUID
    occurred_at: datetime
    session_id_hash: str
    anonymous_user_id_hash: str | None = None
    event_type: EventType
    product_id: UUID | None = None
    variant_id: UUID | None = None
    query_id: UUID | None = None
    result_position: int | None = None
    surface: str
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AuditEvent(StrictDomainModel):
    """Append-only audit event with safe payload only."""

    id: UUID
    tenant_id: UUID
    actor: ActorRef
    event_type: AuditEventType
    entity_type: str
    entity_id: UUID
    request_id: str
    run_id: UUID | None = None
    safe_payload: JsonObject = Field(default_factory=dict)
    previous_event_hash: str | None = None
    event_hash: str | None = None
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)
