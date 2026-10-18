"""Connect controller state, durable requests and recoverable jobs to PostgreSQL."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0004_durable_runtime"
down_revision = "0003_simulator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column(
            "policy_version_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("policy_versions.id"),
        ),
    )
    op.add_column(
        "policy_versions",
        sa.Column(
            "history_data",
            pg.JSONB,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column("goals", sa.Column("simulator_instance_id", pg.UUID(as_uuid=True)))
    op.add_column(
        "goal_runs",
        sa.Column("runtime_data", pg.JSONB, nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "opportunities",
        sa.Column("data", pg.JSONB, nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "compiled_actions",
        sa.Column("budget_reservations", pg.JSONB, nullable=False, server_default=sa.text("'[]'")),
    )
    op.create_table(
        "tenant_runtime",
        sa.Column(
            "tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), primary_key=True
        ),
        sa.Column("policy_version_id", pg.UUID(as_uuid=True), sa.ForeignKey("policy_versions.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "idempotency_records",
        sa.Column(
            "tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), primary_key=True
        ),
        sa.Column("scope", sa.String(240), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("fingerprint", sa.String(80), nullable=False),
        sa.Column("response", pg.JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "workflow_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("goal_id", pg.UUID(as_uuid=True), sa.ForeignKey("goals.id")),
        sa.Column("run_id", pg.UUID(as_uuid=True), sa.ForeignKey("goal_runs.id")),
        sa.Column("action_id", pg.UUID(as_uuid=True), sa.ForeignKey("compiled_actions.id")),
        sa.Column("instance_id", pg.UUID(as_uuid=True), sa.ForeignKey("simulator_instances.id")),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", pg.UUID(as_uuid=True)),
        sa.Column("error_code", sa.String(120)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_workflow_job_attempts"),
        sa.CheckConstraint(
            "kind IN ('plan', 'execute', 'reconcile', 'measure', 'index', 'cycle')",
            name="ck_workflow_job_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'dead_letter')",
            name="ck_workflow_job_status",
        ),
    )
    op.create_index(
        "ix_workflow_jobs_due", "workflow_jobs", ["tenant_id", "status", "available_at"]
    )
    op.create_index(
        "uq_active_goal_planning_run",
        "goal_runs",
        ["tenant_id", "goal_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'awaiting_approval')"),
    )
    # These checks protect writes even when a repository assertion is accidentally omitted.
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    tenant_tables = {
        table
        for table in tables
        if {"id", "tenant_id"}.issubset({column["name"] for column in inspector.get_columns(table)})
    }
    for table in sorted(tenant_tables):
        op.create_unique_constraint(f"uq_tenant_id_{table}", table, ["tenant_id", "id"])
    for table in sorted(tables):
        if "tenant_id" not in {column["name"] for column in inspector.get_columns(table)}:
            continue
        for foreign in inspector.get_foreign_keys(table):
            columns = foreign["constrained_columns"]
            target = foreign["referred_table"]
            if (
                len(columns) == 1
                and foreign["referred_columns"] == ["id"]
                and target in tenant_tables
            ):
                op.create_foreign_key(
                    f"fk_tenant_{table}_{columns[0]}",
                    table,
                    target,
                    ["tenant_id", columns[0]],
                    ["tenant_id", "id"],
                    ondelete=foreign.get("options", {}).get("ondelete"),
                )
    op.create_foreign_key(
        "fk_tenant_goals_simulator",
        "goals",
        "simulator_instances",
        ["tenant_id", "simulator_instance_id"],
        ["tenant_id", "id"],
    )
    op.execute("""
        CREATE FUNCTION reject_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'append-only record cannot be updated or deleted'; END $$
    """)
    for table in ("audit_events", "budget_ledger_entries"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()"
            )
        )


def downgrade() -> None:
    for table in ("audit_events", "budget_ledger_entries"):
        op.execute(sa.text(f"DROP TRIGGER immutable_{table} ON {table}"))
    op.execute("DROP FUNCTION reject_immutable_change()")
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    for table in tables:
        for constraint in inspector.get_foreign_keys(table):
            name = constraint.get("name")
            if name and name.startswith("fk_tenant_"):
                op.drop_constraint(name, table, type_="foreignkey")
    for table in tables:
        for unique_constraint in inspector.get_unique_constraints(table):
            name = unique_constraint.get("name")
            if name and name.startswith("uq_tenant_id_"):
                op.drop_constraint(name, table, type_="unique")
    op.drop_index("uq_active_goal_planning_run", table_name="goal_runs")
    op.drop_table("workflow_jobs")
    op.drop_table("idempotency_records")
    op.drop_table("tenant_runtime")
    op.drop_column("compiled_actions", "budget_reservations")
    op.drop_column("opportunities", "data")
    op.drop_column("goal_runs", "runtime_data")
    op.drop_column("goals", "simulator_instance_id")
    op.drop_column("policy_versions", "history_data")
    op.drop_column("approval_requests", "policy_version_id")
