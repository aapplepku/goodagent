"""Tenant-scoped manager conversations and explicit memory layers."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from open_commerce.persistence.db import Base
from open_commerce.persistence.models.base import MutableTimestampMixin, TimestampMixin


class ManagerThreadRecord(MutableTimestampMixin, Base):
    __tablename__ = "manager_threads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    thread_type: Mapped[str] = mapped_column(String(20), nullable=False, default="channel")
    channel_kind: Mapped[str | None] = mapped_column(String(30))
    slug: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(240))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    parent_thread_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("manager_threads.id", ondelete="CASCADE"),
    )
    root_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "manager_messages.id",
            ondelete="CASCADE",
            use_alter=True,
            name="fk_manager_threads_root_message",
        ),
    )
    working_memory: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    user_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_manager_threads_tenant_updated", "tenant_id", "updated_at"),
        Index("ix_manager_threads_tenant_parent", "tenant_id", "parent_thread_id"),
        Index(
            "uq_manager_channel_slug",
            "tenant_id",
            "slug",
            unique=True,
            postgresql_where=text("thread_type = 'channel'"),
        ),
        Index(
            "uq_manager_reply_root",
            "tenant_id",
            "root_message_id",
            unique=True,
            postgresql_where=text("thread_type = 'reply'"),
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_manager_thread_status"),
        CheckConstraint("thread_type IN ('channel', 'reply')", name="ck_manager_thread_type"),
        CheckConstraint(
            "channel_kind IS NULL OR channel_kind IN "
            "('onboarding', 'status', 'search', 'recommendations', 'buy_again', 'custom')",
            name="ck_manager_thread_channel_kind",
        ),
        CheckConstraint("position >= 0", name="ck_manager_thread_position"),
        CheckConstraint(
            "(thread_type = 'channel' AND parent_thread_id IS NULL AND root_message_id IS NULL "
            "AND slug IS NOT NULL AND channel_kind IS NOT NULL) OR "
            "(thread_type = 'reply' AND parent_thread_id IS NOT NULL "
            "AND root_message_id IS NOT NULL "
            "AND slug IS NULL AND channel_kind IS NULL)",
            name="ck_manager_thread_shape",
        ),
        CheckConstraint("user_turn_count >= 0", name="ck_manager_thread_turns"),
    )


class ManagerMessageRecord(TimestampMixin, Base):
    __tablename__ = "manager_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    thread_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("manager_threads.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index(
            "ix_manager_messages_tenant_thread_created",
            "tenant_id",
            "thread_id",
            "created_at",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_manager_message_role"),
    )


class ManagerMemoryRecord(TimestampMixin, Base):
    __tablename__ = "manager_memories"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    thread_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("manager_threads.id", ondelete="CASCADE")
    )
    layer: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_manager_memories_tenant_layer", "tenant_id", "layer", "created_at"),
        Index("ix_manager_memories_tenant_thread", "tenant_id", "thread_id", "created_at"),
        CheckConstraint("layer IN ('long_term', 'periodic')", name="ck_manager_memory_layer"),
        CheckConstraint(
            "source IN ('explicit_manager', 'periodic_summary')",
            name="ck_manager_memory_source",
        ),
    )


class ManagerDataOnboardingRecord(MutableTimestampMixin, Base):
    """One durable, non-secret data-intake draft for each tenant."""

    __tablename__ = "manager_data_onboarding"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
