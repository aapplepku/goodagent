"""Action, policy decision, approval, execution, and intervention tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class ActionIntentRecord(TimestampMixin, Base):
    """Persisted typed action intent payload."""

    __tablename__ = "action_intents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goal_runs.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    opportunity_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )
    actor: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class CompiledActionRecord(MutableTimestampMixin, Base):
    """Compiled action ready for policy/approval/execution."""

    __tablename__ = "compiled_actions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goal_runs.id"), nullable=False
    )
    intent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("action_intents.id")
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_provider: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    normalized_parameters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    preconditions: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    expected_impact: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    estimated_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    risk: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    rollback_plan: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    version_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    budget_reservations: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_actions_tenant_idempotency"),
        Index("ix_actions_tenant_status", "tenant_id", "status"),
    )


class PolicyDecisionRecord(TimestampMixin, Base):
    """Policy decision for an action hash."""

    __tablename__ = "policy_decisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id"), nullable=False
    )
    policy_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy_versions.id")
    )
    action_version_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list)
    evaluated_rules: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    required_roles: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalRequestRecord(TimestampMixin, Base):
    """Approval request for an exact action version."""

    __tablename__ = "approval_requests"

    policy_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy_versions.id")
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id"), nullable=False
    )
    action_version_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    required_roles: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalRecord(Base):
    """Human approval/rejection decision."""

    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    action_version_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("request_id", "actor_user_id", name="uq_approvals_request_actor"),
    )


class ActionExecution(Base):
    """One provider execution attempt."""

    __tablename__ = "action_executions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id"), nullable=False
    )
    integration_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    request_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    response_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    provider_request_id: Mapped[str | None] = mapped_column(String(240))
    provider_resource_id: Mapped[str | None] = mapped_column(String(240))
    before_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        UniqueConstraint("action_id", "attempt", name="uq_execution_action_attempt"),
        Index("ix_executions_unreconciled", "tenant_id", "status"),
    )


class ActionReconciliation(Base):
    """Provider state observed after execution."""

    __tablename__ = "action_reconciliations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("action_executions.id"), nullable=False
    )
    observed_remote_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class Intervention(Base):
    """Active intervention created by an action."""

    __tablename__ = "interventions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primary_metric: Mapped[str] = mapped_column(String(80), nullable=False)
    monitor_spec: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class InterventionOutcome(Base):
    """Measured intervention outcome."""

    __tablename__ = "intervention_outcomes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    intervention_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interventions.id"), nullable=False
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_results: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    method: Mapped[str] = mapped_column(String(120), nullable=False)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    guardrail_status: Mapped[str] = mapped_column(String(40), nullable=False)
