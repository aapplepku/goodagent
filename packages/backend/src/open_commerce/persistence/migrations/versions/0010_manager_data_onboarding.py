"""Tenant-level manager data onboarding.

Revision ID: 0010_manager_data_onboarding
Revises: 0009_manager_agent_memory
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010_manager_data_onboarding"
down_revision = "0009_manager_agent_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manager_data_onboarding",
        sa.Column(
            "tenant_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state", pg.JSONB(), nullable=False),  # type: ignore[no-untyped-call]
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("manager_data_onboarding")
