"""Webhook, sync job, and source mapping tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class WebhookReceipt(Base):
    """Minimal provider webhook receipt."""

    __tablename__ = "webhook_receipts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    integration_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(240), nullable=False)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    signature_valid: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        UniqueConstraint("provider", "source_event_id", name="uq_webhooks_provider_event"),
        Index("ix_webhooks_pending_failed", "provider", "status"),
    )


class SyncJob(Base):
    """Connector sync job metadata."""

    __tablename__ = "sync_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_cursor: Mapped[str | None] = mapped_column(String(500))
    high_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_count: Mapped[int | None] = mapped_column(BigInteger)
    normalized_count: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    __table_args__ = (
        Index(
            "ix_sync_jobs_tenant_integration_resource",
            "tenant_id",
            "integration_id",
            "resource_type",
            "started_at",
        ),
    )


class SourceMapping(Base):
    """Mapping from provider source IDs to normalized IDs."""

    __tablename__ = "source_mappings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_payload_hash: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "integration_id",
            "entity_type",
            "source_id",
            name="uq_source_mappings_tenant_integration_entity_source",
        ),
    )
