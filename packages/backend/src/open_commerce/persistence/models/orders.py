"""Order and pseudonymous customer fact tables."""

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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin


class CustomerFact(MutableTimestampMixin, Base):
    """Pseudonymous customer facts with no raw PII."""

    __tablename__ = "customer_facts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    source_customer_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_customer_hash",
            name="uq_customer_facts_tenant_integration_hash",
        ),
    )


class Order(Base):
    """Normalized order facts without customer PII."""

    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    integration_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False
    )
    source_order_id: Mapped[str] = mapped_column(String(240), nullable=False)
    customer_fact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_facts.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    financial_status: Mapped[str] = mapped_column(String(80), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refund_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_first_order: Mapped[bool | None] = mapped_column(Boolean)
    source_channel: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_order_id",
            name="uq_orders_tenant_integration_source",
        ),
        Index("ix_orders_tenant_created", "tenant_id", "created_at"),
        Index("ix_orders_tenant_customer_created", "tenant_id", "customer_fact_id", "created_at"),
    )


class OrderLine(Base):
    """Normalized order line facts."""

    __tablename__ = "order_lines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id")
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refund_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_minor: Mapped[int | None] = mapped_column(BigInteger)
