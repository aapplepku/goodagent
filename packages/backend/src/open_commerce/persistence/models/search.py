"""Search metadata tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin


class CatalogIndexJob(MutableTimestampMixin, Base):
    """Recoverable indexing work for one immutable uploaded catalog."""

    __tablename__ = "catalog_index_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )
    source_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    product_count: Mapped[int] = mapped_column(Integer, nullable=False)
    indexed_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_catalog_index_jobs_due", "tenant_id", "status", "available_at"),
        Index(
            "uq_catalog_index_jobs_tenant_integration",
            "tenant_id",
            "integration_id",
            unique=True,
        ),
        CheckConstraint("attempts >= 0 AND failures >= 0", name="ck_catalog_index_job_attempts"),
        CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')",
            name="ck_catalog_index_job_status",
        ),
    )


class SearchIndexVersion(Base):
    """Reconstructable Qdrant index version metadata."""

    __tablename__ = "search_index_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    sparse_model: Mapped[str] = mapped_column(String(160), nullable=False)
    document_template_version: Mapped[str] = mapped_column(String(80), nullable=False)
    ranking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    indexed_product_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchBoostRule(Base):
    """Internal search boost metadata produced by actions."""

    __tablename__ = "search_boost_rules"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    query_pattern: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    product_scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    multiplier: Mapped[object] = mapped_column(Numeric(8, 4), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("compiled_actions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
