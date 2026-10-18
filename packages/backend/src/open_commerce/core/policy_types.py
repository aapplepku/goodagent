"""Policy, risk, approval, and rollback domain models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from open_commerce.core.enums import ActorRole, PolicyOutcome, RiskTier
from open_commerce.core.money import Money
from open_commerce.core.types import ActorRef, JsonObject, StrictDomainModel, ensure_utc


class RuleEvaluation(StrictDomainModel):
    """Result of one explicit policy rule."""

    code: str
    passed: bool
    reason: str
    details: JsonObject = Field(default_factory=dict)


class RiskAssessment(StrictDomainModel):
    """Risk tier and supporting details for a compiled action."""

    tier: RiskTier
    confidence: Decimal
    reasons: list[str] = Field(default_factory=list)


class RollbackPlan(StrictDomainModel):
    """Rollback metadata prepared before execution."""

    available: bool
    summary: str
    action_type: str | None = None
    parameters: JsonObject = Field(default_factory=dict)
    non_reversible_reason: str | None = None


class PolicyDecision(StrictDomainModel):
    """Deterministic policy outcome for one action version."""

    outcome: PolicyOutcome
    reason_codes: list[str]
    evaluated_rules: list[RuleEvaluation]
    required_approver_roles: set[ActorRole] = Field(default_factory=set)
    valid_until: datetime

    @field_validator("valid_until")
    @classmethod
    def normalize_valid_until(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ApprovalRequest(StrictDomainModel):
    """Approval request bound to an exact action version hash."""

    id: UUID
    tenant_id: UUID
    action_id: UUID
    action_version_hash: str
    required_roles: set[ActorRole]
    status: str
    expires_at: datetime
    created_at: datetime

    @field_validator("expires_at", "created_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Approval(StrictDomainModel):
    """Human decision bound to an approval request and action hash."""

    id: UUID
    tenant_id: UUID
    request_id: UUID
    actor: ActorRef
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str | None = None
    action_version_hash: str
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def normalize_decided_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DataFreshnessPolicy(StrictDomainModel):
    """Maximum data age by source in minutes."""

    catalog_max_age_minutes: int = Field(default=60, gt=0)
    inventory_max_age_minutes: int = Field(default=15, gt=0)
    orders_max_age_minutes: int = Field(default=30, gt=0)
    ads_max_age_minutes: int = Field(default=120, gt=0)


class PolicyLimits(StrictDomainModel):
    """Global and goal-level action limits."""

    max_actions_per_day: int = Field(default=10, gt=0)
    max_parallel_interventions: int = Field(default=3, gt=0)
    max_total_discount_cost: Money = Field(
        default_factory=lambda: Money(amount_minor=25000, currency="USD"),
    )
    min_observations_for_auto_action: int = Field(default=500, ge=0)
    min_action_confidence: Decimal = Decimal("0.75")


class DiscountPolicy(StrictDomainModel):
    """Discount policy controls."""

    enabled: bool = True
    autonomy: str = "approval_required"
    max_percentage: Decimal = Decimal("0.15")
    max_duration_hours: int = Field(default=168, gt=0)
    minimum_subtotal_minor: int = Field(default=3000, ge=0)
    allow_stacking: bool = False
    cooldown_hours_per_scope: int = Field(default=168, ge=0)
    minimum_contribution_margin_rate: Decimal = Decimal("0.25")


class SearchBoostPolicy(StrictDomainModel):
    """Search boost policy controls."""

    enabled: bool = True
    autonomy: str = "bounded_auto"
    max_products_per_rule: int = Field(default=20, gt=0)
    max_boost_multiplier: Decimal = Decimal("1.15")
    minimum_relevance_score: Decimal = Decimal("0.55")
    duration_hours: int = Field(default=72, gt=0)


class PolicyConfig(StrictDomainModel):
    """Versioned policy configuration."""

    policy_version: int = 1
    default_mode: str = "shadow"
    kill_switch: bool = False
    data_freshness: DataFreshnessPolicy = Field(default_factory=DataFreshnessPolicy)
    limits: PolicyLimits = Field(default_factory=PolicyLimits)
    discounts: DiscountPolicy = Field(default_factory=DiscountPolicy)
    search_boost: SearchBoostPolicy = Field(default_factory=SearchBoostPolicy)
