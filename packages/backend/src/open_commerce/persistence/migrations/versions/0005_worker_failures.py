"""Separate failed job attempts from healthy measurement polling.

Revision ID: 0005_worker_failures
Revises: 0004_durable_runtime
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_worker_failures"
down_revision = "0004_durable_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_jobs", sa.Column("failures", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_check_constraint("ck_workflow_job_failures", "workflow_jobs", "failures >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_workflow_job_failures", "workflow_jobs", type_="check")
    op.drop_column("workflow_jobs", "failures")
