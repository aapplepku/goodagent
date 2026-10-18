"""Controller graph, policy API, trace, and approval models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from open_commerce.core.actions import CompiledAction
from open_commerce.core.enums import (
    ActionStatus,
    ActionType,
    ActorRole,
    AutonomyMode,
    ConstraintOperator,
    GoalStatus,
    MetricName,
    ObjectiveDirection,
    PolicyOutcome,
    RiskTier,
)
from open_commerce.core.goals import ConstraintSpec, GoalSpec, ObjectiveSpec
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.core.money import Money
from open_commerce.core.policy_types import Approval, ApprovalRequest, PolicyDecision
from open_commerce.core.providers import ProviderResult, ReconciliationResult
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash, ensure_utc
from open_commerce.simulator.models import ScenarioId

ControllerNode = Literal[
    "load_goal_and_policy",
    "acquire_run_lock",
    "build_snapshot",
    "detect_opportunities",
    "generate_hypotheses",
    "generate_action_intents",
    "compile_actions",
    "estimate",
    "evaluate_policy",
    "select_portfolio",
    "persist_proposals",
    "approval_interrupt",
    "execute_actions",
    "reconcile",
    "schedule_measurement",
    "summarize",
]
RunStatus = Literal["queued", "running", "awaiting_approval", "completed", "cancelled", "failed"]
PlanningMode = Literal["deterministic", "model_backed"]
OpportunityType = Literal[
    "merchandising_investigation",
    "conversion_gap",
    "excess_inventory",
    "campaign_efficiency",
    "search_exposure_gap",
    "guardrail_review",
]


CONTROLLER_GRAPH: tuple[ControllerNode, ...] = (
    "load_goal_and_policy",
    "acquire_run_lock",
    "build_snapshot",
    "detect_opportunities",
    "generate_hypotheses",
    "generate_action_intents",
    "compile_actions",
    "estimate",
    "evaluate_policy",
    "select_portfolio",
    "persist_proposals",
    "approval_interrupt",
    "execute_actions",
    "reconcile",
    "schedule_measurement",
    "summarize",
)
PROVIDER_WRITE_NODE: ControllerNode = "execute_actions"


class ControllerError(Exception):
    """Base controller service error."""


class GoalNotFoundError(ControllerError):
    """Raised when a tenant-scoped goal is missing."""


class RunNotFoundError(ControllerError):
    """Raised when a tenant-scoped run is missing."""


class ActionNotFoundError(ControllerError):
    """Raised when a tenant-scoped action is missing."""


class PolicyViolationError(ControllerError):
    """Raised when execution is blocked by policy."""


class ApprovalError(ControllerError):
    """Raised when an approval decision is invalid."""


class ControllerPolicyConfig(StrictDomainModel):
    """Tenant policy controls enforced before every simulator write."""

    tenant_id: UUID
    policy_version: int = Field(default=1, ge=1)
    default_mode: AutonomyMode = AutonomyMode.APPROVAL_REQUIRED
    kill_switch_enabled: bool = False
    blocked_provider_resources: set[str] = Field(default_factory=set)
    allowed_action_types: set[ActionType] = Field(
        default_factory=lambda: {
            ActionType.CREATE_DISCOUNT,
            ActionType.DISABLE_DISCOUNT,
            ActionType.SET_SEARCH_BOOST,
            ActionType.SET_CAMPAIGN_BUDGET,
            ActionType.NO_OP,
        }
    )
    per_action_modes: dict[ActionType, AutonomyMode] = Field(
        default_factory=lambda: {
            ActionType.CREATE_DISCOUNT: AutonomyMode.APPROVAL_REQUIRED,
            ActionType.DISABLE_DISCOUNT: AutonomyMode.APPROVAL_REQUIRED,
            ActionType.SET_VARIANT_PRICE: AutonomyMode.APPROVAL_REQUIRED,
            ActionType.SET_SEARCH_BOOST: AutonomyMode.BOUNDED_AUTO,
            ActionType.SET_CAMPAIGN_BUDGET: AutonomyMode.APPROVAL_REQUIRED,
            ActionType.NO_OP: AutonomyMode.BOUNDED_AUTO,
        }
    )
    max_actions_per_run: int = Field(default=5, gt=0, le=25)
    max_parallel_interventions: int = Field(default=3, gt=0, le=25)
    max_total_estimated_cost: Money = Field(
        default_factory=lambda: Money(amount_minor=25_000, currency="USD")
    )
    min_observations_for_auto_action: int = Field(default=500, ge=0)
    min_action_confidence: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    max_data_age_minutes: int = Field(default=120, gt=0)
    discount_max_percentage: Decimal = Field(default=Decimal("0.15"), gt=0, lt=1)
    discount_minimum_margin_rate: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    price_max_delta_rate: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    campaign_budget_max_change_rate: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    search_boost_max_multiplier: Decimal = Field(default=Decimal("1.15"), gt=0)
    search_boost_min_relevance: Decimal = Field(default=Decimal("0.55"), ge=0, le=1)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    def mode_for(self, action_type: ActionType) -> AutonomyMode:
        """Return the effective autonomy mode for one action type."""

        return self.per_action_modes.get(action_type, self.default_mode)


class PolicyUpdateRequest(StrictDomainModel):
    """Patchable tenant policy settings. Tenant comes from request context."""

    default_mode: AutonomyMode | None = None
    kill_switch_enabled: bool | None = None
    blocked_provider_resources: set[str] | None = None
    allowed_action_types: set[ActionType] | None = None
    per_action_modes: dict[ActionType, AutonomyMode] | None = None
    max_actions_per_run: int | None = Field(default=None, gt=0, le=25)
    max_parallel_interventions: int | None = Field(default=None, gt=0, le=25)
    max_total_estimated_cost: Money | None = None
    min_observations_for_auto_action: int | None = Field(default=None, ge=0)
    min_action_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    max_data_age_minutes: int | None = Field(default=None, gt=0)
    discount_max_percentage: Decimal | None = Field(default=None, gt=0, lt=1)
    discount_minimum_margin_rate: Decimal | None = Field(default=None, ge=0, le=1)
    price_max_delta_rate: Decimal | None = Field(default=None, ge=0, le=1)
    campaign_budget_max_change_rate: Decimal | None = Field(default=None, ge=0, le=1)
    search_boost_max_multiplier: Decimal | None = Field(default=None, gt=0)
    search_boost_min_relevance: Decimal | None = Field(default=None, ge=0, le=1)


class PolicyValidateRequest(StrictDomainModel):
    """Dry-run validation payload for a policy update."""

    policy: PolicyUpdateRequest


class PolicyValidationResponse(StrictDomainModel):
    """Result of validating a policy patch."""

    valid: bool
    reason_codes: list[str]
    effective_policy: ControllerPolicyConfig


class PolicyHistoryEntry(StrictDomainModel):
    """Tenant policy version history entry."""

    version: int
    changed_at: datetime
    idempotency_key: str
    previous_hash: str
    new_hash: str

    @field_validator("changed_at")
    @classmethod
    def normalize_changed_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PolicyHistoryResponse(StrictDomainModel):
    """Policy history response."""

    items: list[PolicyHistoryEntry]
    next_cursor: str | None = None


class KillSwitchResponse(StrictDomainModel):
    """Current tenant kill-switch state."""

    tenant_id: UUID
    enabled: bool
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class EvidenceItem(StrictDomainModel):
    """Evidence attached to a deterministic controller observation."""

    source: str
    key: str
    value: JsonObject


class ObservationSnapshot(StrictDomainModel):
    """Read-only simulator/search snapshot for one controller run."""

    id: UUID
    tenant_id: UUID
    run_id: UUID
    simulator_instance_id: UUID
    scenario_id: ScenarioId
    observed_at: datetime
    state_hash: str
    sample_size: int = Field(ge=0)
    data_age_minutes: dict[str, int]
    catalog_summary: JsonObject
    metric_summary: JsonObject
    campaign_summary: list[JsonObject]

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Opportunity(StrictDomainModel):
    """A deterministic opportunity detected from read-only evidence."""

    id: UUID
    tenant_id: UUID
    run_id: UUID
    type: OpportunityType
    title: str
    description: str
    confidence: Decimal = Field(ge=0, le=1)
    expected_metric: MetricName
    evidence: list[EvidenceItem]
    detected_at: datetime

    @field_validator("detected_at")
    @classmethod
    def normalize_detected_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class Hypothesis(StrictDomainModel):
    """Planner hypothesis derived from opportunities."""

    id: UUID
    tenant_id: UUID
    run_id: UUID
    opportunity_ids: list[UUID]
    statement: str
    confidence: Decimal = Field(ge=0, le=1)
    source: Literal["deterministic_planner"] = "deterministic_planner"
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class IntentDraft(StrictDomainModel):
    """Untrusted planner output that must be compiled before policy/execution."""

    id: UUID
    tenant_id: UUID
    run_id: UUID
    hypothesis_id: UUID
    opportunity_ids: list[UUID]
    action_type: ActionType
    rationale: str
    parameters: JsonObject
    confidence: Decimal = Field(ge=0, le=1)


class MeasurementSchedule(StrictDomainModel):
    """Deterministic post-execution measurement window."""

    action_id: UUID
    starts_at: datetime
    ends_at: datetime
    metric_names: list[MetricName]
    baseline_ref: str
    baseline_totals: JsonObject = Field(default_factory=dict)
    baseline_kind: Literal["recent_runtime", "historical_prior", "unavailable"] = "unavailable"
    minimum_sample: int = Field(default=500, ge=1)
    minimum_days: int = Field(default=2, ge=1)
    margin_floor: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    cac_ceiling_minor: int | None = Field(default=None, ge=0)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ActionAuditEntry(StrictDomainModel):
    """Controller-local action audit entry."""

    id: UUID
    tenant_id: UUID
    action_id: UUID
    event_type: str
    actor_role: ActorRole
    message: str
    occurred_at: datetime
    details: JsonObject = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MeasurementOutcome(StrictDomainModel):
    """Persisted descriptive outcome; no causal action lift is claimed."""

    id: UUID
    evaluated_at: datetime
    metric_results: JsonObject
    method: str
    sample_size: int | None
    conclusion: str
    guardrail_status: Literal["breached", "clear", "insufficient_data"]

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ControllerActionRecord(StrictDomainModel):
    """Stored action proposal and execution state."""

    action: CompiledAction
    action_version_hash: str
    policy_version: int = 1
    approval_policy_version: int | None = None
    policy_decision: PolicyDecision
    approval_request: ApprovalRequest | None = None
    approval: Approval | None = None
    execution_result: ProviderResult | None = None
    reconciliation: ReconciliationResult | None = None
    measurement: MeasurementSchedule | None = None
    outcome: MeasurementOutcome | None = None
    audit: list[ActionAuditEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ControllerTraceEvent(StrictDomainModel):
    """Ordered public trace event for a controller run."""

    id: UUID
    tenant_id: UUID
    run_id: UUID
    sequence: int = Field(ge=1)
    node: ControllerNode
    occurred_at: datetime
    message: str
    details: JsonObject = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ControllerRunRecord(StrictDomainModel):
    """Stored controller run state."""

    id: UUID
    tenant_id: UUID
    goal_id: UUID
    simulator_instance_id: UUID
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    snapshot: ObservationSnapshot | None = None
    opportunities: list[Opportunity] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    intent_drafts: list[IntentDraft] = Field(default_factory=list)
    action_ids: list[UUID] = Field(default_factory=list)
    trace: list[ControllerTraceEvent] = Field(default_factory=list)
    summary: JsonObject = Field(default_factory=dict)
    next_run_at: datetime | None = None

    @field_validator("started_at", "completed_at", "next_run_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class GoalRecord(StrictDomainModel):
    """Stored tenant goal plus simulator binding."""

    spec: GoalSpec
    scenario_id: ScenarioId
    simulator_instance_id: UUID
    seed: int
    created_at: datetime
    updated_at: datetime
    revision: int = Field(default=1, ge=1)
    planning_mode: PlanningMode = "deterministic"
    soft_preferences: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class GoalCreateRequest(StrictDomainModel):
    """Create a local-demo goal. Tenant comes from request context."""

    name: str = Field(default="Simulator goal", min_length=1, max_length=200)
    merchandising: MerchandisingConstraints | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    scenario_id: ScenarioId = "acquisition_v1"
    seed: int = 42
    objective_metric: MetricName | None = None
    objective_direction: ObjectiveDirection | None = None
    objective_scope: Literal["store", "excess_inventory"] | None = None
    target_value: Decimal | None = None
    horizon_days: int = Field(default=30, gt=0, le=366)
    budget: Money = Field(default_factory=lambda: Money(amount_minor=1_000_000, currency="USD"))
    daily_budget: Money = Field(default_factory=lambda: Money(amount_minor=25_000, currency="USD"))
    default_mode: AutonomyMode = AutonomyMode.APPROVAL_REQUIRED
    per_action_modes: dict[ActionType, AutonomyMode] = Field(default_factory=dict)
    planning_mode: PlanningMode = "deterministic"
    constraints: list[ConstraintSpec] | None = Field(default=None, max_length=20)
    soft_preferences: list[str] = Field(default_factory=list, max_length=10)
    review_hash: str | None = None
    allowed_action_types: set[ActionType] = Field(
        default_factory=lambda: {
            ActionType.CREATE_DISCOUNT,
            ActionType.SET_SEARCH_BOOST,
            ActionType.SET_CAMPAIGN_BUDGET,
        }
    )

    @field_validator("budget", "daily_budget")
    @classmethod
    def validate_simulator_currency(cls, value: Money) -> Money:
        if value.currency != "USD":
            raise ValueError("v0.1 simulator scenarios use USD")
        return value

    @model_validator(mode="before")
    @classmethod
    def merchandising_defaults(cls, value: object) -> object:
        if not isinstance(value, dict) or value.get("merchandising") is None:
            return value
        payload = dict(value)
        payload.setdefault("name", "Improve contribution profit from existing traffic")
        payload.setdefault("budget", {"amount_minor": 0, "currency": "USD"})
        payload.setdefault("daily_budget", {"amount_minor": 0, "currency": "USD"})
        payload.setdefault("objective_metric", MetricName.CONTRIBUTION_PROFIT)
        payload.setdefault("objective_direction", ObjectiveDirection.MAXIMIZE)
        payload.setdefault("constraints", [])
        limits = MerchandisingConstraints.model_validate(payload["merchandising"])
        payload.setdefault(
            "allowed_action_types",
            {
                ActionType.SET_VARIANT_PRICE,
                ActionType.CREATE_DISCOUNT,
                ActionType.DISABLE_DISCOUNT,
                ActionType.SET_SEARCH_BOOST,
                ActionType.SET_RECOMMENDATION_POLICY,
                ActionType.NO_OP,
            }
            - limits.prohibited_actions,
        )
        return payload

    def resolved_objective(self) -> ObjectiveSpec:
        defaults = {
            "acquisition_v1": MetricName.NEW_CUSTOMERS,
            "excess_inventory_v1": MetricName.UNITS_SOLD,
            "search_conversion_v1": MetricName.SEARCH_ATTRIBUTED_PURCHASES,
        }
        metric = self.objective_metric or defaults[self.scenario_id]
        scope: Literal["store", "excess_inventory"] = self.objective_scope or (
            "excess_inventory"
            if self.scenario_id == "excess_inventory_v1" and metric == MetricName.UNITS_SOLD
            else "store"
        )
        return ObjectiveSpec(
            metric=metric,
            scope=scope,
            direction=self.objective_direction
            or (
                ObjectiveDirection.MINIMIZE
                if metric in {MetricName.CAC, MetricName.DISCOUNT_RATE}
                else ObjectiveDirection.REACH
            ),
            target=self.target_value
            if self.target_value is not None
            else (Decimal("200") if self.objective_metric is None else None),
        )

    @model_validator(mode="after")
    def validate_objective(self) -> GoalCreateRequest:
        if self.merchandising is not None:
            if self.budget.amount_minor or self.daily_budget.amount_minor:
                raise ValueError("merchandising uses promotion_cap_minor, not acquisition budgets")
            if self.allowed_action_types & self.merchandising.prohibited_actions:
                raise ValueError("prohibited merchandising action")
            if any(item.metric == MetricName.CAC for item in self.resolved_constraints()):
                raise ValueError("CAC is not a merchandising goal constraint")
        objective = self.resolved_objective()
        if objective.metric in {
            MetricName.SEARCH_CONVERSION_RATE,
            MetricName.INVENTORY_DAYS_OF_SUPPLY,
        }:
            raise ValueError("The simulator does not measure this objective")
        if objective.target is not None:
            if not objective.target.is_finite():
                raise ValueError("Objective target must be finite")
            if objective.metric != MetricName.CONTRIBUTION_PROFIT and objective.target < 0:
                raise ValueError("Objective target cannot be negative")
            if (
                objective.metric
                in {
                    MetricName.CONVERSION_RATE,
                    MetricName.DISCOUNT_RATE,
                    MetricName.CONTRIBUTION_MARGIN_RATE,
                }
                and objective.target > 1
            ):
                raise ValueError("Rate targets use fractions, not percentages")
        if not self.allowed_action_types:
            raise ValueError("Use no_op for an explicitly read-only goal")
        resolved = self.resolved_constraints()
        if len({item.metric for item in resolved}) != len(resolved):
            raise ValueError("Review one unambiguous constraint per metric")
        for constraint in resolved:
            if not constraint.hard:
                raise ValueError("Use soft_preferences for non-binding preferences")
            if constraint.metric == MetricName.CAC:
                if not isinstance(constraint.value, Money) or constraint.value.currency != "USD":
                    raise ValueError("CAC ceiling must be USD minor units")
                if constraint.operator != ConstraintOperator.LTE:
                    raise ValueError("Supported CAC constraint is an observed upper bound")
            elif constraint.metric in {
                MetricName.DISCOUNT_RATE,
                MetricName.CONTRIBUTION_MARGIN_RATE,
            }:
                expected = (
                    ConstraintOperator.LTE
                    if constraint.metric == MetricName.DISCOUNT_RATE
                    else ConstraintOperator.GTE
                )
                if (
                    not isinstance(constraint.value, Decimal)
                    or not constraint.value.is_finite()
                    or not Decimal(0) <= constraint.value <= Decimal(1)
                    or constraint.operator != expected
                ):
                    raise ValueError("Supported rate constraints use finite fractional bounds")
            else:
                raise ValueError("This constraint is not enforced or monitored by the simulator")
        if any(len(item) > 300 for item in self.soft_preferences):
            raise ValueError("Soft preferences must be concise")
        if self.review_hash is not None and self.review_hash != self.configuration_hash:
            raise ValueError("Reviewed goal configuration changed; review a new draft")
        return self

    def resolved_constraints(self) -> list[ConstraintSpec]:
        """Explicit constraints win; defaults only apply to legacy typed requests."""
        if self.constraints is not None:
            return sorted(
                [item.model_copy(deep=True) for item in self.constraints],
                key=lambda item: (item.metric.value, item.operator.value),
            )
        return [
            ConstraintSpec(
                metric=MetricName.CAC,
                operator=ConstraintOperator.LTE,
                value=Money(amount_minor=4000, currency="USD"),
            ),
            ConstraintSpec(
                metric=MetricName.CONTRIBUTION_MARGIN_RATE,
                operator=ConstraintOperator.GTE,
                value=Decimal("0.25"),
            ),
            ConstraintSpec(
                metric=MetricName.DISCOUNT_RATE,
                operator=ConstraintOperator.LTE,
                value=Decimal("0.15"),
            ),
        ]

    @property
    def configuration_hash(self) -> str:
        """Hash exactly the form values presented for explicit review."""
        return canonical_hash(self.model_dump(mode="python", exclude={"review_hash"}))


class GoalUpdateRequest(StrictDomainModel):
    """Patch a goal's editable local-demo fields."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    default_mode: AutonomyMode | None = None
    allowed_action_types: set[ActionType] | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    replacement: GoalCreateRequest | None = None


class GoalListResponse(StrictDomainModel):
    """Goal list response."""

    items: list[GoalRecord]
    next_cursor: str | None = None


class GoalAssessment(StrictDomainModel):
    """Descriptive progress and conservative feasibility, not a causal forecast."""

    metric: MetricName
    scope: Literal["store", "excess_inventory"]
    current_value: Decimal | None
    target_value: Decimal | None
    projected_value: Decimal | None
    physical_upper_bound: Decimal | None
    feasibility: Literal["infeasible", "not_ruled_out"]
    trajectory: Literal["achieved", "on_track", "at_risk", "no_target", "insufficient_data"]
    reason_codes: list[str]
    forecast_method: Literal["recent_rate_heuristic_not_calibrated"] = (
        "recent_rate_heuristic_not_calibrated"
    )


class GoalProgressResponse(StrictDomainModel):
    """Goal progress summary derived from simulator state and controller actions."""

    goal_id: UUID
    tenant_id: UUID
    status: GoalStatus
    objective_metric: MetricName
    current_value: Decimal | None
    assessment: GoalAssessment | None = None
    target_value: Decimal | None
    pending_approvals: int
    executable_actions: int
    denied_actions: int
    succeeded_actions: int
    latest_run_id: UUID | None


class RunListResponse(StrictDomainModel):
    """Run list response."""

    items: list[ControllerRunRecord]
    next_cursor: str | None = None


class RunTraceResponse(StrictDomainModel):
    """Trace response."""

    run_id: UUID
    items: list[ControllerTraceEvent]
    next_cursor: str | None = None


class RunEventListResponse(StrictDomainModel):
    """Run events response."""

    run_id: UUID
    items: list[ControllerTraceEvent]
    next_cursor: str | None = None


class ActionListResponse(StrictDomainModel):
    """Action list response."""

    items: list[ControllerActionRecord]
    next_cursor: str | None = None


class ActionApprovalRequest(StrictDomainModel):
    """Approve or reject an action bound to its current version hash."""

    action_version_hash: str = Field(min_length=10)
    comment: str | None = Field(default=None, max_length=1000)
    actor_id: str = Field(default="local-operator", min_length=1, max_length=200)


class ActionAuditResponse(StrictDomainModel):
    """Action audit response."""

    action_id: UUID
    items: list[ActionAuditEntry]
    next_cursor: str | None = None


class ControllerRunRequest(StrictDomainModel):
    """Optional run controls for a manual controller run."""

    execute_bounded_auto: bool = False


class ControllerGraphResponse(StrictDomainModel):
    """Documented controller graph and effect boundary."""

    nodes: list[ControllerNode]
    provider_write_node: ControllerNode
    side_effect_boundaries: JsonObject


def action_status_for_policy(outcome: PolicyOutcome) -> ActionStatus:
    """Map policy outcome to the initial action workflow status."""

    if outcome == PolicyOutcome.DENY:
        return ActionStatus.DENIED
    if outcome == PolicyOutcome.REQUIRE_APPROVAL:
        return ActionStatus.AWAITING_APPROVAL
    return ActionStatus.EXECUTABLE


def action_type_for_compiled(action: CompiledAction) -> ActionType:
    """Return the finite action type for a compiled action."""

    return ActionType(action.intent.type)


def risk_sort_key(tier: RiskTier) -> int:
    """Return stable risk rank for sorting."""

    order = {
        RiskTier.R0_READ_ONLY: 0,
        RiskTier.R1_REVERSIBLE_LOW: 1,
        RiskTier.R2_REVERSIBLE_MATERIAL: 2,
        RiskTier.R3_HIGH_IMPACT: 3,
        RiskTier.R4_PROHIBITED: 4,
    }
    return order[tier]
