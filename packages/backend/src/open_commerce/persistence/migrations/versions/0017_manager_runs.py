"""Durable operator runs and local recovery commands."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0017_manager_runs"
down_revision = "0016_cart_checkout_inventory"
branch_labels = None
depends_on = None


def _identity() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
    ]


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "manager_runs",
        *_identity(),
        sa.Column(
            "thread_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("manager_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_message_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_message_id", pg.UUID(as_uuid=True)),
        sa.Column("thread_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("phase", sa.String(240), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("checkpoint", pg.JSONB, nullable=False),
        sa.Column("result", pg.JSONB),
        sa.Column("active_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", pg.UUID(as_uuid=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'cancelled')",
            name="ck_manager_run_status",
        ),
    )
    op.create_index("ix_manager_runs_due", "manager_runs", ["tenant_id", "status", "available_at"])
    op.create_index(
        "uq_manager_active_run",
        "manager_runs",
        ["tenant_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'waiting')"),
    )
    op.create_table(
        "manager_run_events",
        *_identity(),
        sa.Column(
            "run_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("manager_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("tool", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_manager_run_event",
        "manager_run_events",
        ["tenant_id", "run_id", "sequence"],
        unique=True,
    )
    op.create_table(
        "runtime_operations",
        *_identity(),
        sa.Column(
            "run_id", pg.UUID(as_uuid=True), sa.ForeignKey("manager_runs.id", ondelete="SET NULL")
        ),
        sa.Column("service", sa.String(30), nullable=False),
        sa.Column("runtime_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("evidence", pg.JSONB, nullable=False),
        sa.Column("outcome", pg.JSONB),
        sa.Column("rollback", pg.JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "service IN ('api', 'manager_web', 'shopper_web', 'worker')",
            name="ck_runtime_operation_service",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runtime_operation_status",
        ),
    )
    op.create_index(
        "uq_runtime_operation_key",
        "runtime_operations",
        ["tenant_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("runtime_operations")
    op.drop_table("manager_run_events")
    op.drop_table("manager_runs")
