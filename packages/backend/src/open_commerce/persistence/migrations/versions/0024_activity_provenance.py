"""Separate private previews and sample catalogs from live-store aggregates."""

import sqlalchemy as sa
from alembic import op

revision = "0024_activity_provenance"
down_revision = "0023_guest_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("is_preview", "is_sample"):
        op.add_column(
            "shopper_activity",
            sa.Column(column, sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("shopper_activity", "is_sample")
    op.drop_column("shopper_activity", "is_preview")
