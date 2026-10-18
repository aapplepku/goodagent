"""Tenant-scoped cart, reservation, local order, and payment records."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class ShopperCartRecord(MutableTimestampMixin, Base):
    __tablename__ = "shopper_carts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    __table_args__ = (
        CheckConstraint("status IN ('open', 'converted', 'abandoned')", name="ck_cart_status"),
        Index(
            "uq_shopper_open_cart",
            "tenant_id",
            "account_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_shopper_carts_tenant_updated", "tenant_id", "updated_at"),
    )


class ShopperCartLineRecord(TimestampMixin, Base):
    __tablename__ = "shopper_cart_lines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    cart_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_carts.id", ondelete="CASCADE"), nullable=False
    )
    catalog_product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    catalog_variant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=False
    )
    source_product_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_variant_id: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    variant_title: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 20", name="ck_cart_line_quantity"),
        CheckConstraint("unit_price_minor >= 0", name="ck_cart_line_price"),
        UniqueConstraint(
            "tenant_id", "account_id", "cart_id", "catalog_variant_id", name="uq_cart_variant"
        ),
        Index("ix_cart_lines_tenant_cart", "tenant_id", "account_id", "cart_id"),
    )


class InventoryReservationRecord(MutableTimestampMixin, Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_carts.id", ondelete="CASCADE"), nullable=False
    )
    checkout_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    cart_line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_cart_lines.id"), nullable=False
    )
    catalog_product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    catalog_variant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=False
    )
    source_product_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_variant_id: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    release_reason: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_reservation_quantity"),
        CheckConstraint(
            "status IN ('active', 'released', 'consumed', 'expired')",
            name="ck_reservation_status",
        ),
        UniqueConstraint(
            "tenant_id", "checkout_id", "catalog_variant_id", name="uq_checkout_variant_reservation"
        ),
        Index(
            "ix_reservations_tenant_variant_active",
            "tenant_id",
            "catalog_variant_id",
            "status",
            "expires_at",
        ),
    )


class PaymentAttemptRecord(MutableTimestampMixin, Base):
    __tablename__ = "payment_attempts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_carts.id", ondelete="CASCADE"), nullable=False
    )
    cart_version: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="local_test")
    provider_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    idempotency_key_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_decision: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    preconditions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    rollback_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_payment_amount"),
        CheckConstraint(
            "status IN ('requires_confirmation', 'processing', "
            "'requires_payment_method', 'succeeded', 'cancelled')",
            name="ck_payment_status",
        ),
        UniqueConstraint("tenant_id", "cart_id", "cart_version", name="uq_cart_version_payment"),
        Index("ix_payment_attempts_tenant_created", "tenant_id", "created_at"),
    )


class ShopperOrderRecord(TimestampMixin, Base):
    __tablename__ = "shopper_orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("shopper_carts.id"), nullable=False
    )
    payment_attempt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payment_attempts.id"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    line_snapshots: Mapped[list[object]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('paid', 'cancelled')", name="ck_shopper_order_status"),
        CheckConstraint("amount_minor >= 0", name="ck_shopper_order_amount"),
        UniqueConstraint("tenant_id", "payment_attempt_id", name="uq_order_payment_attempt"),
        UniqueConstraint("tenant_id", "order_number", name="uq_shopper_order_number"),
        Index("ix_shopper_orders_tenant_created", "tenant_id", "created_at"),
    )
