"""Durable uploaded-catalog indexing jobs.

Revision ID: 0012_catalog_index_jobs
Revises: 0011_manager_workspace_channels
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0012_catalog_index_jobs"
down_revision = "0011_manager_workspace_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_index_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("indexed_product_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_token", pg.UUID(as_uuid=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("safe_error", pg.JSONB()),  # type: ignore[no-untyped-call]
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("attempts >= 0 AND failures >= 0", name="ck_catalog_index_job_attempts"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')",
            name="ck_catalog_index_job_status",
        ),
    )
    op.create_index(
        "ix_catalog_index_jobs_due",
        "catalog_index_jobs",
        ["tenant_id", "status", "available_at"],
    )
    op.create_index(
        "uq_catalog_index_jobs_tenant_integration",
        "catalog_index_jobs",
        ["tenant_id", "integration_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_catalog_index_jobs_tenant_integration", table_name="catalog_index_jobs")
    op.drop_index("ix_catalog_index_jobs_due", table_name="catalog_index_jobs")
    op.drop_table("catalog_index_jobs")
