"""add simulator tables

Revision ID: 0003_simulator
Revises: 0002_core_domain
Create Date: 2026-09-04 00:00:02.000000
"""

# mypy: ignore-errors

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_simulator"
down_revision: str | None = "0002_core_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulator_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.String(length=120), nullable=False),
        sa.Column("scenario_version", sa.String(length=80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_hash", sa.String(length=80), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulator_instances_tenant_current_time",
        "simulator_instances",
        ["tenant_id", "current_time"],
    )
    op.create_index(
        "ix_simulator_instances_tenant_scenario",
        "simulator_instances",
        ["tenant_id", "scenario_id"],
    )

    op.create_table(
        "simulator_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("virtual_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_hash", sa.String(length=80), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["simulator_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulator_snapshots_tenant_instance",
        "simulator_snapshots",
        ["tenant_id", "instance_id"],
    )

    op.create_table(
        "simulator_daily_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("is_history", sa.Boolean(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["simulator_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "instance_id",
            "metric_date",
            name="uq_simulator_daily_metrics_tenant_instance_date",
        ),
    )
    op.create_index(
        "ix_simulator_daily_metrics_tenant_instance",
        "simulator_daily_metrics",
        ["tenant_id", "instance_id"],
    )

    op.create_table(
        "simulator_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["simulator_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulator_events_tenant_instance_time",
        "simulator_events",
        ["tenant_id", "instance_id", "occurred_at"],
    )

    op.create_table(
        "simulator_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rollback_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rollback_of", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["simulator_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "instance_id",
            "action_type",
            "idempotency_key",
            name="uq_simulator_commands_tenant_instance_action_key",
        ),
    )
    op.create_index(
        "ix_simulator_commands_tenant_instance",
        "simulator_commands",
        ["tenant_id", "instance_id"],
    )

    op.create_table(
        "simulator_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.String(length=120), nullable=False),
        sa.Column("scenario_version", sa.String(length=80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("code_version", sa.String(length=80), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("summary_hash", sa.String(length=80), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "scenario_id",
            "scenario_version",
            "seed",
            "code_version",
            "horizon_days",
            name="uq_simulator_baselines_identity",
        ),
    )
    op.create_index(
        "ix_simulator_baselines_tenant_scenario",
        "simulator_baselines",
        ["tenant_id", "scenario_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_simulator_baselines_tenant_scenario", table_name="simulator_baselines")
    op.drop_table("simulator_baselines")
    op.drop_index("ix_simulator_commands_tenant_instance", table_name="simulator_commands")
    op.drop_table("simulator_commands")
    op.drop_index("ix_simulator_events_tenant_instance_time", table_name="simulator_events")
    op.drop_table("simulator_events")
    op.drop_index(
        "ix_simulator_daily_metrics_tenant_instance", table_name="simulator_daily_metrics"
    )
    op.drop_table("simulator_daily_metrics")
    op.drop_index("ix_simulator_snapshots_tenant_instance", table_name="simulator_snapshots")
    op.drop_table("simulator_snapshots")
    op.drop_index("ix_simulator_instances_tenant_scenario", table_name="simulator_instances")
    op.drop_index("ix_simulator_instances_tenant_current_time", table_name="simulator_instances")
    op.drop_table("simulator_instances")
