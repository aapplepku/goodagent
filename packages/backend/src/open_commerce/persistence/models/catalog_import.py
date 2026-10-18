"""Encrypted temporary imports and immutable safe raster assets."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import TimestampMixin


class CatalogImportRecord(TimestampMixin, Base):
    __tablename__ = "catalog_imports"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    filename: Mapped[str] = mapped_column(String(255))
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="mapping")
    mapping: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    currency: Mapped[str | None] = mapped_column(String(3))
    catalog_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    report: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    __table_args__ = (Index("ix_import_tenant_expiry", "tenant_id", "expires_at"),)


class CatalogAssetRecord(TimestampMixin, Base):
    __tablename__ = "catalog_assets"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    import_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("catalog_imports.id"))
    sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (Index("ix_asset_tenant_import", "tenant_id", "import_id"),)
