"""Behavioral event tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class BehavioralEventRecord(Base):
    """Pseudonymous event record."""

    __tablename__ = "behavioral_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(240), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_id_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    anonymous_user_id_hash: Mapped[str | None] = mapped_column(String(128))
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id")
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id")
    )
    query_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    result_position: Mapped[int | None] = mapped_column(Integer)
    surface: Mapped[str] = mapped_column(String(80), nullable=False)
    consent: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    safe_properties: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source", "source_event_id", name="uq_events_tenant_source_event"
        ),
        Index("ix_events_tenant_type_occurred", "tenant_id", "event_type", "occurred_at"),
    )
