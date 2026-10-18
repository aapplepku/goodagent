"""Slack-style manager channels, reply threads, and workspace metadata.

Revision ID: 0011_manager_workspace_channels
Revises: 0010_manager_data_onboarding
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0011_manager_workspace_channels"
down_revision = "0010_manager_data_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manager_threads", sa.Column("thread_type", sa.String(length=20)))
    op.add_column("manager_threads", sa.Column("channel_kind", sa.String(length=30)))
    op.add_column("manager_threads", sa.Column("slug", sa.String(length=120)))
    op.add_column("manager_threads", sa.Column("description", sa.String(length=240)))
    op.add_column("manager_threads", sa.Column("position", sa.Integer()))
    op.add_column("manager_threads", sa.Column("parent_thread_id", pg.UUID(as_uuid=True)))
    op.add_column("manager_threads", sa.Column("root_message_id", pg.UUID(as_uuid=True)))

    op.execute(
        "UPDATE manager_threads SET thread_type = 'channel', channel_kind = 'custom', "
        "slug = 'channel-' || replace(id::text, '-', ''), position = 100"
    )
    op.alter_column("manager_threads", "thread_type", nullable=False)
    op.alter_column("manager_threads", "position", nullable=False)

    op.create_foreign_key(
        "fk_manager_threads_parent_thread",
        "manager_threads",
        "manager_threads",
        ["parent_thread_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_manager_threads_root_message",
        "manager_threads",
        "manager_messages",
        ["root_message_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_manager_thread_type",
        "manager_threads",
        "thread_type IN ('channel', 'reply')",
    )
    op.create_check_constraint(
        "ck_manager_thread_channel_kind",
        "manager_threads",
        "channel_kind IS NULL OR channel_kind IN "
        "('onboarding', 'search', 'recommendations', 'buy_again', 'custom')",
    )
    op.create_check_constraint("ck_manager_thread_position", "manager_threads", "position >= 0")
    op.create_check_constraint(
        "ck_manager_thread_shape",
        "manager_threads",
        "(thread_type = 'channel' AND parent_thread_id IS NULL AND root_message_id IS NULL "
        "AND slug IS NOT NULL AND channel_kind IS NOT NULL) OR "
        "(thread_type = 'reply' AND parent_thread_id IS NOT NULL AND root_message_id IS NOT NULL "
        "AND slug IS NULL AND channel_kind IS NULL)",
    )
    op.create_index(
        "ix_manager_threads_tenant_parent",
        "manager_threads",
        ["tenant_id", "parent_thread_id"],
    )
    op.create_index(
        "uq_manager_channel_slug",
        "manager_threads",
        ["tenant_id", "slug"],
        unique=True,
        postgresql_where=sa.text("thread_type = 'channel'"),
    )
    op.create_index(
        "uq_manager_reply_root",
        "manager_threads",
        ["tenant_id", "root_message_id"],
        unique=True,
        postgresql_where=sa.text("thread_type = 'reply'"),
    )


def downgrade() -> None:
    op.drop_index("uq_manager_reply_root", table_name="manager_threads")
    op.drop_index("uq_manager_channel_slug", table_name="manager_threads")
    op.drop_index("ix_manager_threads_tenant_parent", table_name="manager_threads")
    op.drop_constraint("ck_manager_thread_shape", "manager_threads", type_="check")
    op.drop_constraint("ck_manager_thread_position", "manager_threads", type_="check")
    op.drop_constraint("ck_manager_thread_channel_kind", "manager_threads", type_="check")
    op.drop_constraint("ck_manager_thread_type", "manager_threads", type_="check")
    op.drop_constraint("fk_manager_threads_root_message", "manager_threads", type_="foreignkey")
    op.drop_constraint("fk_manager_threads_parent_thread", "manager_threads", type_="foreignkey")
    op.drop_column("manager_threads", "root_message_id")
    op.drop_column("manager_threads", "parent_thread_id")
    op.drop_column("manager_threads", "position")
    op.drop_column("manager_threads", "description")
    op.drop_column("manager_threads", "slug")
    op.drop_column("manager_threads", "channel_kind")
    op.drop_column("manager_threads", "thread_type")
