"""Durable coordination records; jobs reference domain IDs, never live objects."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class TenantRuntime(MutableTimestampMixin, Base):
    """Current policy pointer and tenant workflow serialization boundary."""

    __tablename__ = "tenant_runtime"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    policy_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy_versions.id")
    )


class IdempotencyRecord(TimestampMixin, Base):
    """A request fingerprint and its committed response, scoped to one operation."""

    __tablename__ = "idempotency_records"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(240), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    response: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class WorkflowJob(MutableTimestampMixin, Base):
    """PostgreSQL outbox and recoverable job state, with bounded retry leases."""

    __tablename__ = "workflow_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    goal_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id"))
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goal_runs.id"))
    action_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id")
    )
    instance_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("simulator_instances.id")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        Index("ix_workflow_jobs_due", "tenant_id", "status", "available_at"),
        CheckConstraint("attempts >= 0", name="ck_workflow_job_attempts"),
        CheckConstraint("failures >= 0", name="ck_workflow_job_failures"),
        CheckConstraint(
            "kind IN ('plan', 'execute', 'reconcile', 'measure', 'index', 'cycle')",
            name="ck_workflow_job_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'dead_letter')",
            name="ck_workflow_job_status",
        ),
    )
