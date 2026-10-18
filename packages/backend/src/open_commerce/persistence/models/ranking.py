"""Immutable engagement snapshots and recoverable local ranking candidates."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin


class EngagementSnapshot(Base):
    __tablename__ = "engagement_snapshots"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    events: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("uq_engagement_snapshot", "tenant_id", "fingerprint", unique=True),)


class RankingModelRecord(MutableTimestampMixin, Base):
    __tablename__ = "ranking_models"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    catalog_id: Mapped[UUID] = mapped_column(ForeignKey("integrations.id"), nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("engagement_snapshots.id"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(30), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    artifact: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    artifact_hash: Mapped[str | None] = mapped_column(String(80))
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    __table_args__ = (
        Index("ix_ranking_jobs", "tenant_id", "status"),
        Index("uq_active_ranker", "tenant_id", unique=True, postgresql_where=text("active")),
    )
