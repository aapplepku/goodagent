"""Operational shopper activity, saved views, and durable monitor checks."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class ShopperActivityRecord(Base):
    __tablename__ = "shopper_activity"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("shopper_accounts.id"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_preview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_sample: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "event_key", name="uq_shopper_activity_key"),
        Index("ix_shopper_activity_time", "tenant_id", "occurred_at"),
    )


class ActivityRuleRecord(Base):
    __tablename__ = "activity_rules"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("shopper_accounts.id"))
    owner_key: Mapped[str] = mapped_column(String(40), nullable=False)
    name_key: Mapped[str] = mapped_column(String(60), nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    last_check: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_key", "name_key", name="uq_activity_rule_owner"),
        Index("ix_activity_rule_due", "tenant_id", "next_check_at"),
    )


class ActivityCheckRecord(Base):
    __tablename__ = "activity_checks"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("activity_rules.id"), nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_activity_check_time", "tenant_id", "checked_at"),)
