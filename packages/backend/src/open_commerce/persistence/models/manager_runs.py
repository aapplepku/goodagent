"""Durable operator runs, cursor events, and bounded local recovery commands."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class ManagerRunRecord(MutableTimestampMixin, Base):
    __tablename__ = "manager_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    thread_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("manager_threads.id", ondelete="CASCADE"), nullable=False
    )
    user_message_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assistant_message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    thread_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    phase: Mapped[str] = mapped_column(String(240), nullable=False, default="Waiting for agent")
    error_code: Mapped[str | None] = mapped_column(String(100))
    checkpoint: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    active_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    __table_args__ = (
        Index("ix_manager_runs_due", "tenant_id", "status", "available_at"),
        Index(
            "uq_manager_active_run",
            "tenant_id",
            "thread_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'waiting')"),
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'cancelled')",
            name="ck_manager_run_status",
        ),
    )


class ManagerRunEventRecord(TimestampMixin, Base):
    __tablename__ = "manager_run_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("manager_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    tool: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        Index("uq_manager_run_event", "tenant_id", "run_id", "sequence", unique=True),
    )


class RuntimeOperationRecord(MutableTimestampMixin, Base):
    __tablename__ = "runtime_operations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("manager_runs.id", ondelete="SET NULL"), nullable=True
    )
    service: Mapped[str] = mapped_column(String(30), nullable=False)
    runtime_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    rollback: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        Index("uq_runtime_operation_key", "tenant_id", "idempotency_key", unique=True),
        CheckConstraint(
            "service IN ('api', 'manager_web', 'shopper_web', 'worker')",
            name="ck_runtime_operation_service",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runtime_operation_status",
        ),
    )
