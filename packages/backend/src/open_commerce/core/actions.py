"""Typed action intents, compiled actions, state machine, and hashes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from open_commerce.core.enums import ActionStatus, ActionType, RiskTier
from open_commerce.core.errors import InvalidTransitionError
from open_commerce.core.merchandising import RecommendationControls
from open_commerce.core.metrics import ConfidenceInterval
from open_commerce.core.money import Money
from open_commerce.core.policy_types import RiskAssessment, RollbackPlan
from open_commerce.core.types import (
    ActorRef,
    JsonObject,
    Precondition,
    ProviderRef,
    StrictDomainModel,
    TimeWindow,
    canonical_hash,
    ensure_utc,
)


class ProductScope(StrictDomainModel):
    """Product targeting scope."""

    product_ids: list[str] = Field(default_factory=list)
    category_paths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CustomerScope(StrictDomainModel):
    """Coarse customer targeting scope without PII."""

    segment: str = "all"
    new_customers_only: bool = False


class BudgetReservationRequest(StrictDomainModel):
    """Budget capacity requested by a compiled action."""

    budget_kind: str
    amount: Money
    operation_id: str


class ImpactEstimate(StrictDomainModel):
    """Conservative deterministic estimate for a compiled action."""

    metric: str
    interval: ConfidenceInterval | None
    method: str
    assumptions: list[str] = Field(default_factory=list)
    feature_snapshot_ref: str | None = None
    out_of_distribution: bool = False


class ActionIntentBase(StrictDomainModel):
    """Common fields for every typed action intent."""

    rationale: str
    opportunity_ids: list[UUID]
    requested_by: ActorRef
    source_run_id: UUID
    proposed_at: datetime

    @field_validator("proposed_at")
    @classmethod
    def normalize_proposed_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class CreateDiscountIntent(ActionIntentBase):
    """Intent to create a bounded discount."""

    type: Literal["create_discount"] = "create_discount"
    discount_kind: Literal["percentage", "fixed_amount"]
    value: Decimal
    starts_at: datetime
    ends_at: datetime
    product_scope: ProductScope
    customer_scope: CustomerScope
    minimum_subtotal_minor: int | None = Field(default=None, ge=0)
    maximum_cost_minor: int | None = Field(default=None, gt=0)
    code: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_discount(self) -> CreateDiscountIntent:
        if self.discount_kind == "percentage" and not (Decimal("0") < self.value < Decimal("1")):
            raise ValueError("percentage discount value must be greater than 0 and less than 1")
        if self.discount_kind == "fixed_amount" and self.value <= 0:
            raise ValueError("fixed_amount discount value must be positive")
        if self.ends_at <= self.starts_at:
            raise ValueError("discount end must be after start")
        return self


class DisableDiscountIntent(ActionIntentBase):
    """Intent to disable an existing discount."""

    type: Literal["disable_discount"] = "disable_discount"
    provider_discount_id: str


class VariantPriceChange(StrictDomainModel):
    """Requested variant price change."""

    product_id: str
    variant_id: str
    current_price: Money
    new_price: Money

    @model_validator(mode="after")
    def validate_currency(self) -> VariantPriceChange:
        self.current_price.require_same_currency(self.new_price)
        return self


class SetVariantPriceIntent(ActionIntentBase):
    """Intent to set one or more variant prices."""

    type: Literal["set_variant_price"] = "set_variant_price"
    changes: list[VariantPriceChange] = Field(min_length=1)
    window: TimeWindow | None = Field(default=None, exclude_if=lambda v: v is None)
    current_versions: dict[str, int] | None = Field(default=None, exclude_if=lambda v: v is None)


class SetRecommendationPolicyIntent(ActionIntentBase):
    """Replace one finite, versioned PDP policy for a bounded window."""

    type: Literal["set_recommendation_policy"] = "set_recommendation_policy"
    expected_version: int = Field(ge=0)
    controls: RecommendationControls
    window: TimeWindow


class SetSearchBoostIntent(ActionIntentBase):
    """Intent to create an internal search boost rule."""

    type: Literal["set_search_boost"] = "set_search_boost"
    query_pattern: JsonObject
    product_scope: ProductScope
    multiplier: Decimal = Field(gt=Decimal("0"))
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_window(self) -> SetSearchBoostIntent:
        if self.ends_at <= self.starts_at:
            raise ValueError("search boost end must be after start")
        return self


class SetCampaignBudgetIntent(ActionIntentBase):
    """Intent to change a simulated or future ads campaign budget."""

    type: Literal["set_campaign_budget"] = "set_campaign_budget"
    campaign_id: str
    current_budget: Money
    new_budget: Money

    @model_validator(mode="after")
    def validate_currency(self) -> SetCampaignBudgetIntent:
        self.current_budget.require_same_currency(self.new_budget)
        return self


class NoOpIntent(ActionIntentBase):
    """Explicit no-op decision."""

    type: Literal["no_op"] = "no_op"


ActionIntent = Annotated[
    CreateDiscountIntent
    | DisableDiscountIntent
    | SetVariantPriceIntent
    | SetSearchBoostIntent
    | SetRecommendationPolicyIntent
    | SetCampaignBudgetIntent
    | NoOpIntent,
    Field(discriminator="type"),
]


class CompiledAction(StrictDomainModel):
    """Action intent resolved against current authoritative state."""

    id: UUID
    tenant_id: UUID
    goal_id: UUID
    run_id: UUID
    intent: ActionIntent
    target_provider: ProviderRef
    normalized_parameters: JsonObject
    preconditions: list[Precondition]
    expected_impact: ImpactEstimate
    estimated_cost: Money
    budget_reservations: list[BudgetReservationRequest]
    risk: RiskAssessment = Field(
        default_factory=lambda: RiskAssessment(
            tier=RiskTier.R2_REVERSIBLE_MATERIAL,
            confidence=Decimal("0.75"),
            reasons=[],
        ),
    )
    rollback_plan: RollbackPlan
    idempotency_key: str
    expires_at: datetime
    status: ActionStatus = ActionStatus.COMPILED

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def version_hash(self) -> str:
        """Stable hash used by policy and approval records."""

        return compute_action_version_hash(self)


_ALLOWED_TRANSITIONS: dict[ActionStatus, set[ActionStatus]] = {
    ActionStatus.DRAFT: {ActionStatus.COMPILED, ActionStatus.CANCELLED, ActionStatus.EXPIRED},
    ActionStatus.COMPILED: {
        ActionStatus.DENIED,
        ActionStatus.AWAITING_APPROVAL,
        ActionStatus.APPROVED,
        ActionStatus.EXECUTABLE,
        ActionStatus.CANCELLED,
        ActionStatus.EXPIRED,
    },
    ActionStatus.AWAITING_APPROVAL: {
        ActionStatus.APPROVED,
        ActionStatus.DENIED,
        ActionStatus.CANCELLED,
        ActionStatus.EXPIRED,
    },
    ActionStatus.APPROVED: {
        ActionStatus.EXECUTABLE,
        ActionStatus.CANCELLED,
        ActionStatus.EXPIRED,
    },
    ActionStatus.EXECUTABLE: {
        ActionStatus.EXECUTING,
        ActionStatus.CANCELLED,
        ActionStatus.EXPIRED,
    },
    ActionStatus.EXECUTING: {
        ActionStatus.SUCCEEDED,
        ActionStatus.FAILED,
        ActionStatus.UNCERTAIN,
    },
    ActionStatus.SUCCEEDED: {
        ActionStatus.EVALUATING,
        ActionStatus.COMPLETED,
        ActionStatus.ROLLBACK_PROPOSED,
    },
    ActionStatus.UNCERTAIN: {
        ActionStatus.SUCCEEDED,
        ActionStatus.FAILED,
        ActionStatus.ROLLBACK_PROPOSED,
    },
    ActionStatus.EVALUATING: {ActionStatus.COMPLETED, ActionStatus.ROLLBACK_PROPOSED},
    ActionStatus.COMPLETED: {ActionStatus.ROLLBACK_PROPOSED},
    ActionStatus.ROLLBACK_PROPOSED: {ActionStatus.ROLLING_BACK, ActionStatus.CANCELLED},
    ActionStatus.ROLLING_BACK: {ActionStatus.ROLLED_BACK, ActionStatus.ROLLBACK_FAILED},
    ActionStatus.DENIED: set(),
    ActionStatus.FAILED: set(),
    ActionStatus.ROLLED_BACK: set(),
    ActionStatus.ROLLBACK_FAILED: set(),
    ActionStatus.EXPIRED: set(),
    ActionStatus.CANCELLED: set(),
}


def can_transition(current: ActionStatus, target: ActionStatus) -> bool:
    """Return whether an action status transition is valid."""

    return target in _ALLOWED_TRANSITIONS[current]


def validate_transition(current: ActionStatus, target: ActionStatus) -> None:
    """Raise when a status transition is invalid."""

    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)


def transition_action(current: ActionStatus, target: ActionStatus) -> ActionStatus:
    """Validate and return the target status."""

    validate_transition(current, target)
    return target


def compute_action_version_hash(action: CompiledAction) -> str:
    """Compute a stable hash over action semantics, excluding workflow status."""

    return canonical_hash(action.model_dump(mode="json", exclude={"status"}))


def build_action_idempotency_key(
    *,
    tenant_id: UUID,
    goal_id: UUID,
    action_type: ActionType,
    target_provider: ProviderRef,
    normalized_parameters: JsonObject,
    decision_window: TimeWindow,
) -> str:
    """Build a deterministic idempotency key for a logical action decision."""

    digest = canonical_hash(
        {
            "tenant_id": tenant_id,
            "goal_id": goal_id,
            "action_type": action_type.value,
            "target_provider": target_provider,
            "normalized_parameters": normalized_parameters,
            "decision_window": decision_window,
        },
    )
    return f"idem_{digest.removeprefix('sha256:')}"
