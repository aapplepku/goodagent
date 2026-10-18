"""Catalog and inventory tables."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base


class Product(Base):
    """Normalized product."""

    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    source_product_id: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str | None] = mapped_column(String(240))
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(160))
    category_path: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    primary_image_url: Mapped[str | None] = mapped_column(Text)
    product_url: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_product_id",
            name="uq_products_tenant_integration_source",
        ),
        Index(
            "ix_products_tenant_integration_updated",
            "tenant_id",
            "integration_id",
            "source_updated_at",
        ),
    )


class ProductVariant(Base):
    """Normalized product variant."""

    __tablename__ = "product_variants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    source_variant_id: Mapped[str] = mapped_column(String(240), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    option_values: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compare_at_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    cost_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "product_id",
            "source_variant_id",
            name="uq_variants_tenant_product_source",
        ),
        Index("ix_variants_tenant_product_sku", "tenant_id", "product_id", "sku"),
    )


class InventorySnapshot(Base):
    """Observed inventory state."""

    __tablename__ = "inventory_snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    variant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=False
    )
    source_location_id: Mapped[str | None] = mapped_column(String(240))
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    on_hand_quantity: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_inventory_tenant_variant_observed", "tenant_id", "variant_id", "observed_at"),
    )
