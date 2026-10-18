"""Tenant-scoped shopper identity, conversation, and memory records."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class ShopperAccountRecord(MutableTimestampMixin, Base):
    __tablename__ = "shopper_accounts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_hash: Mapped[str | None] = mapped_column(String(64))
    preview_catalog_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_shopper_account_username"),
        Index("ix_shopper_accounts_tenant_created", "tenant_id", "created_at"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_shopper_account_status"),
    )


class ShopperSessionRecord(TimestampMixin, Base):
    __tablename__ = "shopper_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_shopper_session_token_hash"),
        Index(
            "ix_shopper_sessions_tenant_account",
            "tenant_id",
            "account_id",
            "expires_at",
        ),
    )


class ShopperConversationRecord(MutableTimestampMixin, Base):
    __tablename__ = "shopper_conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        Index(
            "ix_shopper_conversations_tenant_account_updated",
            "tenant_id",
            "account_id",
            "updated_at",
        ),
    )


class ShopperMessageRecord(TimestampMixin, Base):
    __tablename__ = "shopper_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    products: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index(
            "ix_shopper_messages_tenant_conversation_created",
            "tenant_id",
            "account_id",
            "conversation_id",
            "created_at",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_shopper_message_role"),
    )


class ShopperMemoryRecord(TimestampMixin, Base):
    __tablename__ = "shopper_memories"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    source_message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopper_messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "account_id", "source_message_id", name="uq_shopper_memory_source"
        ),
        Index(
            "ix_shopper_memories_tenant_account_created",
            "tenant_id",
            "account_id",
            "created_at",
        ),
    )
