"""Provider protocols, capability envelopes, and command/result models."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import Field, field_validator

from open_commerce.core.enums import Capability, ExecutionStatus, ProviderType
from open_commerce.core.events import BehavioralEvent
from open_commerce.core.merchandising import RecommendationControls
from open_commerce.core.money import Money
from open_commerce.core.types import (
    JsonObject,
    ProviderRef,
    SafeError,
    StrictDomainModel,
    TimeWindow,
    ensure_utc,
)


class CapabilitySet(StrictDomainModel):
    """Capabilities advertised by a provider instance."""

    provider_type: ProviderType
    capabilities: set[Capability]
    limits: JsonObject = Field(default_factory=dict)


class SyncPage(StrictDomainModel):
    """Opaque sync page for provider reads."""

    items: list[JsonObject]
    next_cursor: str | None = None


class CreateDiscountCommand(StrictDomainModel):
    """Typed provider command to create a discount."""

    tenant_id: UUID
    idempotency_key: str
    code: str | None
    discount_kind: str
    value: str
    starts_at: datetime
    ends_at: datetime
    product_scope: JsonObject
    minimum_subtotal_minor: int | None = None
    maximum_cost_minor: int | None = Field(default=None, gt=0)
    new_customers_only: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DisableDiscountCommand(StrictDomainModel):
    """Typed provider command to disable a discount."""

    tenant_id: UUID
    idempotency_key: str
    provider_discount_id: str


class SetVariantPricesCommand(StrictDomainModel):
    """Typed provider command to update variant prices."""

    tenant_id: UUID
    idempotency_key: str
    changes: list[JsonObject]
    window: TimeWindow | None = Field(default=None, exclude_if=lambda v: v is None)
    current_versions: dict[str, int] | None = Field(default=None, exclude_if=lambda v: v is None)


class SetRecommendationPolicyCommand(StrictDomainModel):
    """Bounded PDP policy replacement with optimistic concurrency."""

    tenant_id: UUID
    idempotency_key: str
    expected_version: int = Field(ge=0)
    controls: RecommendationControls
    window: TimeWindow


class SetCampaignBudgetCommand(StrictDomainModel):
    """Typed provider command to update a campaign budget."""

    tenant_id: UUID
    idempotency_key: str
    campaign_id: str
    budget: Money


class ExecutionRef(StrictDomainModel):
    """Reference to a persisted execution attempt."""

    tenant_id: UUID
    execution_id: UUID
    action_id: UUID
    provider: ProviderRef


class ProviderResult(StrictDomainModel):
    """Redacted provider write result."""

    status: ExecutionStatus
    provider_request_id: str | None = None
    provider_resource_id: str | None = None
    before_state: JsonObject
    after_state: JsonObject | None = None
    error: SafeError | None = None
    reconciliation_required: bool = False


class ReconciliationResult(StrictDomainModel):
    """Observed provider state after a write attempt."""

    execution_id: UUID
    status: ExecutionStatus
    observed_remote_state: JsonObject
    details: JsonObject = Field(default_factory=dict)


class StoreSnapshot(StrictDomainModel):
    """Provider-neutral store snapshot for simulator and future connectors."""

    tenant_id: UUID
    as_of: datetime
    catalog_summary: JsonObject
    inventory_summary: JsonObject
    order_summary: JsonObject
    discount_summary: JsonObject

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class CampaignSnapshot(StrictDomainModel):
    """Provider-neutral campaign snapshot."""

    tenant_id: UUID
    campaign_id: str
    name: str
    channel_id: str
    daily_budget: Money
    active: bool
    observed_at: datetime
    metrics: JsonObject = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class SpendFact(StrictDomainModel):
    """Provider-neutral spend fact."""

    tenant_id: UUID
    campaign_id: str
    window: TimeWindow
    spend: Money
    attributed_orders: int = 0
    attributed_new_customers: int = 0


class CommerceProvider(Protocol):
    """Minimal commerce provider contract used by the simulator checkpoint."""

    async def capabilities(self) -> CapabilitySet:
        """Return provider capabilities."""
        ...

    async def sync_catalog(self, cursor: str | None) -> SyncPage:
        """Return a page of catalog records."""
        ...

    async def get_store_snapshot(self, as_of: datetime) -> StoreSnapshot:
        """Return a point-in-time store snapshot."""
        ...

    async def create_discount(self, command: CreateDiscountCommand) -> ProviderResult:
        """Create a provider discount."""
        ...

    async def disable_discount(self, command: DisableDiscountCommand) -> ProviderResult:
        """Disable a provider discount."""
        ...

    async def set_variant_prices(self, command: SetVariantPricesCommand) -> ProviderResult:
        """Set variant prices."""
        ...

    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult:
        """Reconcile an execution attempt."""
        ...


class AdsProvider(Protocol):
    """Minimal ads provider contract used by simulator campaigns."""

    async def capabilities(self) -> CapabilitySet:
        """Return provider capabilities."""
        ...

    async def get_campaigns(self, as_of: datetime) -> list[CampaignSnapshot]:
        """Return campaign snapshots."""
        ...

    async def set_campaign_budget(self, command: SetCampaignBudgetCommand) -> ProviderResult:
        """Set a campaign budget."""
        ...

    async def reconcile(self, execution: ExecutionRef) -> ReconciliationResult:
        """Reconcile an execution attempt."""
        ...


class BehavioralEventProvider(Protocol):
    """Provider contract for normalized behavioral events."""

    async def events(self, start: datetime, end: datetime) -> AsyncIterator[BehavioralEvent]:
        """Yield normalized events within a time window."""
        ...


class RecommendationPolicyProvider(Protocol):
    async def set_recommendation_policy(
        self, command: SetRecommendationPolicyCommand
    ) -> ProviderResult:
        """Replace only the supported product-detail policy."""
        ...


class VirtualClock(Protocol):
    """Provider-neutral virtual clock used by the simulator."""

    async def advance(self, hours: int) -> None:
        """Advance virtual time by hours."""
        ...

    async def run_until(self, timestamp: datetime) -> None:
        """Advance virtual time until timestamp."""
        ...

    async def reset(self, seed: int | None = None) -> None:
        """Reset virtual time and state."""
        ...
