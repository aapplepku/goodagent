"""Guest accounts extend existing shopper identity and preserve all historical data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0023_guest_accounts"
down_revision = "0022_catalog_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shopper_accounts",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "shopper_accounts",
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("shopper_accounts", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("shopper_accounts", sa.Column("recovery_hash", sa.String(64)))
    op.add_column("shopper_accounts", sa.Column("preview_catalog_id", pg.UUID()))


def downgrade() -> None:
    for column in (
        "preview_catalog_id",
        "recovery_hash",
        "expires_at",
        "memory_enabled",
        "is_guest",
    ):
        op.drop_column("shopper_accounts", column)
