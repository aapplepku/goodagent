"""Simulator persistence tables."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class SimulatorInstanceRecord(MutableTimestampMixin, Base):
    """Tenant-owned simulator instance state."""

    __tablename__ = "simulator_instances"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[str] = mapped_column(String(120), nullable=False)
    scenario_version: Mapped[str] = mapped_column(String(80), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    current_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_simulator_instances_tenant_scenario", "tenant_id", "scenario_id"),
        Index("ix_simulator_instances_tenant_current_time", "tenant_id", "current_time"),
    )


class SimulatorSnapshotRecord(TimestampMixin, Base):
    """Append-only simulator state snapshot."""

    __tablename__ = "simulator_snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    instance_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulator_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    virtual_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (Index("ix_simulator_snapshots_tenant_instance", "tenant_id", "instance_id"),)


class SimulatorDailyMetricRecord(TimestampMixin, Base):
    """Simulator daily metric materialization."""

    __tablename__ = "simulator_daily_metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    instance_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulator_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_history: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "instance_id",
            "metric_date",
            name="uq_simulator_daily_metrics_tenant_instance_date",
        ),
        Index("ix_simulator_daily_metrics_tenant_instance", "tenant_id", "instance_id"),
    )


class SimulatorEventRecord(TimestampMixin, Base):
    """Aggregated simulator event persistence."""

    __tablename__ = "simulator_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    instance_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulator_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index(
            "ix_simulator_events_tenant_instance_time", "tenant_id", "instance_id", "occurred_at"
        ),
    )


class SimulatorCommandRecordModel(TimestampMixin, Base):
    """Simulator provider command history."""

    __tablename__ = "simulator_commands"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    instance_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("simulator_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    before_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    rollback_state: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    rollback_of: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "instance_id",
            "action_type",
            "idempotency_key",
            name="uq_simulator_commands_tenant_instance_action_key",
        ),
        Index("ix_simulator_commands_tenant_instance", "tenant_id", "instance_id"),
    )


class SimulatorBaselineRecord(TimestampMixin, Base):
    """Cached no-intervention simulator baseline."""

    __tablename__ = "simulator_baselines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[str] = mapped_column(String(120), nullable=False)
    scenario_version: Mapped[str] = mapped_column(String(80), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    code_version: Mapped[str] = mapped_column(String(80), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scenario_id",
            "scenario_version",
            "seed",
            "code_version",
            "horizon_days",
            name="uq_simulator_baselines_identity",
        ),
        Index("ix_simulator_baselines_tenant_scenario", "tenant_id", "scenario_id"),
    )
