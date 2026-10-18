"""Engagement snapshots and local ranking candidates."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0018_engagement_ranking"
down_revision = "0017_manager_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "engagement_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("fingerprint", sa.String(80), nullable=False),
        sa.Column("events", pg.JSONB, nullable=False),
        sa.Column("summary", pg.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_engagement_snapshot", "engagement_snapshots", ["tenant_id", "fingerprint"], unique=True
    )
    op.create_table(
        "ranking_models",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "catalog_id", pg.UUID(as_uuid=True), sa.ForeignKey("integrations.id"), nullable=False
        ),
        sa.Column(
            "dataset_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("engagement_snapshots.id"),
            nullable=False,
        ),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("target", sa.String(30), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("artifact", pg.JSONB),
        sa.Column("artifact_hash", sa.String(80)),
        sa.Column("metrics", pg.JSONB, nullable=False),
        sa.Column("error", sa.String(500)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", pg.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')", name="ck_ranker_status"
        ),
        sa.CheckConstraint("NOT active OR status = 'ready'", name="ck_ranker_active_ready"),
    )
    op.create_index("ix_ranking_jobs", "ranking_models", ["tenant_id", "status"])
    op.create_index(
        "uq_active_ranker",
        "ranking_models",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_table("ranking_models")
    op.drop_table("engagement_snapshots")
