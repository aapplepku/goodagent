"""Tenant-scoped inference reservations, responses and restart evidence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class InferenceCall(Base):
    __tablename__ = "inference_calls"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    scope: Mapped[str] = mapped_column(String(160))
    operation_key: Mapped[str] = mapped_column(String(180))
    request_hash: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    request_data: Mapped[dict[str, object]] = mapped_column(JSONB)
    response_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_key", name="uq_inference_tenant_operation"),
        Index("ix_inference_tenant_scope", "tenant_id", "scope"),
        Index("ix_inference_tenant_created", "tenant_id", "created_at"),
    )
