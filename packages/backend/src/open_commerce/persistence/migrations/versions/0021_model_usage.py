"""Shared request and token ceilings across API/worker processes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0021_model_usage"
down_revision = "0020_store_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_usage",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("account_id", pg.UUID(), sa.ForeignKey("shopper_accounts.id")),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("observed_tokens", sa.Integer()),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_usage_day", "model_usage", ["tenant_id", "day"])


def downgrade() -> None:
    op.drop_table("model_usage")
