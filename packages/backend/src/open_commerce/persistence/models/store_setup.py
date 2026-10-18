"""Store setup and authentication records; credentials never form model context."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import TimestampMixin


class MerchantCredentialRecord(Base):
    __tablename__ = "merchant_credentials"
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    recovery_hash: Mapped[str | None] = mapped_column(String(64))


class MerchantSessionRecord(TimestampMixin, Base):
    __tablename__ = "merchant_sessions"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_merchant_session_owner", "tenant_id", "user_id"),)


class AuthTicketRecord(TimestampMixin, Base):
    """Pre-authentication grants are instance-scoped; store grants carry tenant_id."""

    __tablename__ = "auth_tickets"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, default=bytes)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StoreSetupRecord(Base):
    __tablename__ = "store_setup"
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    goal: Mapped[str] = mapped_column(
        String(300), nullable=False, default="Help shoppers find suitable products"
    )
    logo_asset: Mapped[str | None] = mapped_column(String(200))
    sharing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_catalog_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("integrations.id")
    )
    readiness: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    sample_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SetupEventRecord(Base):
    __tablename__ = "setup_events"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"))
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("uq_setup_event", "tenant_id", "event_key", unique=True),)
