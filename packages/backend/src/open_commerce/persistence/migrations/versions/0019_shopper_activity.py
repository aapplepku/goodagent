"""Private shopper operational logs and scoped monitor definitions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0019_shopper_activity"
down_revision = "0018_engagement_ranking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopper_activity",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "account_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("shopper_accounts.id"),
            nullable=False,
        ),
        sa.Column("event_key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("result_count", sa.Integer),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", "event_key", name="uq_shopper_activity_key"),
    )
    op.create_index("ix_shopper_activity_time", "shopper_activity", ["tenant_id", "occurred_at"])
    op.create_table(
        "activity_rules",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("account_id", pg.UUID(as_uuid=True), sa.ForeignKey("shopper_accounts.id")),
        sa.Column("owner_key", sa.String(40), nullable=False),
        sa.Column("name_key", sa.String(60), nullable=False),
        sa.Column("definition", pg.JSONB, nullable=False),
        sa.Column("last_check", pg.JSONB, nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "owner_key", "name_key", name="uq_activity_rule_owner"),
    )
    op.create_index("ix_activity_rule_due", "activity_rules", ["tenant_id", "next_check_at"])
    op.create_table(
        "activity_checks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "rule_id", pg.UUID(as_uuid=True), sa.ForeignKey("activity_rules.id"), nullable=False
        ),
        sa.Column("definition", pg.JSONB, nullable=False),
        sa.Column("result", pg.JSONB, nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activity_check_time", "activity_checks", ["tenant_id", "checked_at"])


def downgrade() -> None:
    op.drop_table("activity_checks")
    op.drop_table("activity_rules")
    op.drop_table("shopper_activity")
