"""Durable conservative admission accounting for shared hosted model budgets."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class ModelUsageRecord(Base):
    __tablename__ = "model_usage"
    id: Mapped[UUID] = mapped_column(PG_UUID(), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(), ForeignKey("tenants.id"), nullable=False)
    account_id: Mapped[UUID | None] = mapped_column(PG_UUID(), ForeignKey("shopper_accounts.id"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    reserved_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_tokens: Mapped[int | None] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_model_usage_day", "tenant_id", "day"),)
