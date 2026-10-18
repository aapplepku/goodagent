"""Allow the seeded manager status channel.

Revision ID: 0014_status_channel
Revises: 0013_refresh_search_intro
"""

from alembic import op

revision = "0014_status_channel"
down_revision = "0013_refresh_search_intro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_manager_thread_channel_kind", "manager_threads", type_="check")
    op.create_check_constraint(
        "ck_manager_thread_channel_kind",
        "manager_threads",
        "channel_kind IS NULL OR channel_kind IN "
        "('onboarding', 'status', 'search', 'recommendations', 'buy_again', 'custom')",
    )


def downgrade() -> None:
    op.execute("UPDATE manager_threads SET channel_kind = 'custom' WHERE channel_kind = 'status'")
    op.drop_constraint("ck_manager_thread_channel_kind", "manager_threads", type_="check")
    op.create_check_constraint(
        "ck_manager_thread_channel_kind",
        "manager_threads",
        "channel_kind IS NULL OR channel_kind IN "
        "('onboarding', 'search', 'recommendations', 'buy_again', 'custom')",
    )
