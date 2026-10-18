"""Reviewed merchandising constraints; legacy goals remain unchanged.

Revision ID: 0008_merchandising
Revises: 0007_inference_journal
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0008_merchandising"
down_revision = "0007_inference_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("merchandising", pg.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("goals", "merchandising")
