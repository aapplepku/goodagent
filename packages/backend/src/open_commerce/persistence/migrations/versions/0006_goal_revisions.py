"""Reviewed goal revisions and explicit planning mode.

Revision ID: 0006_goal_revisions
Revises: 0005_worker_failures
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0006_goal_revisions"
down_revision = "0005_worker_failures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("configuration_revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "goals",
        sa.Column("planning_mode", sa.String(30), server_default="deterministic", nullable=False),
    )
    op.add_column(
        "goals", sa.Column("soft_preferences", pg.JSONB, server_default="[]", nullable=False)
    )
    op.create_check_constraint(
        "ck_goal_configuration_revision", "goals", "configuration_revision >= 1"
    )
    op.create_check_constraint(
        "ck_goal_planning_mode", "goals", "planning_mode IN ('deterministic', 'model_backed')"
    )
    op.create_table(
        "goal_revisions",
        sa.Column("tenant_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("goal_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("configuration", pg.JSONB, nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "goal_id"],
            ["goals.tenant_id", "goals.id"],
            name="fk_goal_revisions_tenant_goal",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_goal_revision_positive"),
    )
    op.execute(
        "CREATE TRIGGER immutable_goal_revisions BEFORE UPDATE OR DELETE ON goal_revisions "
        "FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()"
    )


def downgrade() -> None:
    # Downgrade is destructive to newly recorded review evidence; export/backup first.
    op.execute("DROP TRIGGER immutable_goal_revisions ON goal_revisions")
    op.drop_table("goal_revisions")
    op.drop_constraint("ck_goal_planning_mode", "goals", type_="check")
    op.drop_constraint("ck_goal_configuration_revision", "goals", type_="check")
    op.drop_column("goals", "soft_preferences")
    op.drop_column("goals", "planning_mode")
    op.drop_column("goals", "configuration_revision")
