"""Goals, budgets, constraints, and policy version tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class Goal(MutableTimestampMixin, Base):
    """Merchant goal."""

    __tablename__ = "goals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    horizon: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    autonomy: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    allowed_action_types: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False)
    evaluation_schedule: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    simulator_instance_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    configuration_revision: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    planning_mode: Mapped[str] = mapped_column(
        String(30), server_default="deterministic", nullable=False
    )
    soft_preferences: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    merchandising: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_goals_active", "tenant_id", "status"),)


class GoalRevisionRecord(TimestampMixin, Base):
    """Append-only reviewed goal configuration, independent of workflow status."""

    __tablename__ = "goal_revisions"
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    goal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "goal_id"],
            ["goals.tenant_id", "goals.id"],
            name="fk_goal_revisions_tenant_goal",
        ),
        CheckConstraint("revision >= 1", name="ck_goal_revision_positive"),
    )


class GoalBudget(Base):
    """Budget configured for a goal."""

    __tablename__ = "goal_budgets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    allocated_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "goal_id", "kind", "period_start", name="uq_goal_budgets_goal_kind_period"
        ),
    )


class GoalConstraint(TimestampMixin, Base):
    """Constraint configured for a goal."""

    __tablename__ = "goal_constraints"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    hard: Mapped[bool] = mapped_column(nullable=False)


class PolicyVersion(TimestampMixin, Base):
    """Versioned policy document."""

    __tablename__ = "policy_versions"

    history_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
