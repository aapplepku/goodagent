"""Authenticated store setup, private publication, and single-use identity grants."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0020_store_setup"
down_revision = "0019_shopper_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_credentials",
        sa.Column("user_id", pg.UUID(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("recovery_hash", sa.String(64)),
    )
    op.create_table(
        "merchant_sessions",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("user_id", pg.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_merchant_session_owner", "merchant_sessions", ["tenant_id", "user_id"])
    op.create_table(
        "auth_tickets",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id")),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "store_setup",
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("goal", sa.String(300), nullable=False),
        sa.Column("logo_asset", sa.String(200)),
        sa.Column("sharing_enabled", sa.Boolean(), nullable=False),
        sa.Column("published_catalog_id", pg.UUID(), sa.ForeignKey("integrations.id")),
        sa.Column("readiness", pg.JSONB, nullable=False),
        sa.Column("sample_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "setup_events",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("event_key", sa.String(200), nullable=False),
        sa.Column("details", pg.JSONB, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("uq_setup_event", "setup_events", ["tenant_id", "event_key"], unique=True)


def downgrade() -> None:
    for table in (
        "setup_events",
        "store_setup",
        "auth_tickets",
        "merchant_sessions",
        "merchant_credentials",
    ):
        op.drop_table(table)
