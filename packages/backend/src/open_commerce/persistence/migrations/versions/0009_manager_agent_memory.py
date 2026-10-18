"""Durable manager conversation and three-layer memory.

Revision ID: 0009_manager_agent_memory
Revises: 0008_merchandising
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0009_manager_agent_memory"
down_revision = "0008_merchandising"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manager_threads",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("working_memory", pg.JSONB(), nullable=False),  # type: ignore[no-untyped-call]
        sa.Column("user_turn_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_manager_thread_status"),
        sa.CheckConstraint("user_turn_count >= 0", name="ck_manager_thread_turns"),
    )
    op.create_index(
        "ix_manager_threads_tenant_updated", "manager_threads", ["tenant_id", "updated_at"]
    )
    op.create_table(
        "manager_messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "thread_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("manager_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("steps", pg.JSONB(), nullable=False),  # type: ignore[no-untyped-call]
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_manager_message_role"),
    )
    op.create_index(
        "ix_manager_messages_tenant_thread_created",
        "manager_messages",
        ["tenant_id", "thread_id", "created_at"],
    )
    op.create_table(
        "manager_memories",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "thread_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("manager_threads.id", ondelete="CASCADE"),
        ),
        sa.Column("layer", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_message_id", pg.UUID(as_uuid=True)),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("layer IN ('long_term', 'periodic')", name="ck_manager_memory_layer"),
        sa.CheckConstraint(
            "source IN ('explicit_manager', 'periodic_summary')",
            name="ck_manager_memory_source",
        ),
    )
    op.create_index(
        "ix_manager_memories_tenant_layer",
        "manager_memories",
        ["tenant_id", "layer", "created_at"],
    )
    op.create_index(
        "ix_manager_memories_tenant_thread",
        "manager_memories",
        ["tenant_id", "thread_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_manager_memories_tenant_thread", table_name="manager_memories")
    op.drop_index("ix_manager_memories_tenant_layer", table_name="manager_memories")
    op.drop_table("manager_memories")
    op.drop_index("ix_manager_messages_tenant_thread_created", table_name="manager_messages")
    op.drop_table("manager_messages")
    op.drop_index("ix_manager_threads_tenant_updated", table_name="manager_threads")
    op.drop_table("manager_threads")
