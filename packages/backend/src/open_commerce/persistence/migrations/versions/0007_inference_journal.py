"""Durable, independently budgeted model requests.

Revision ID: 0007_inference_journal
Revises: 0006_goal_revisions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007_inference_journal"
down_revision = "0006_goal_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inference_calls",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("scope", sa.String(160), nullable=False),
        sa.Column("operation_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reserved_tokens", sa.Integer, nullable=False),
        sa.Column("request_data", pg.JSONB, nullable=False),
        sa.Column("response_data", pg.JSONB),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "operation_key", name="uq_inference_tenant_operation"),
        sa.CheckConstraint("reserved_tokens > 0", name="ck_inference_reservation_positive"),
        sa.CheckConstraint(
            "status IN ('dispatched', 'completed', 'failed', 'uncertain')",
            name="ck_inference_status",
        ),
    )
    op.create_index("ix_inference_tenant_scope", "inference_calls", ["tenant_id", "scope"])
    op.create_index("ix_inference_tenant_created", "inference_calls", ["tenant_id", "created_at"])
    op.execute("""
        CREATE FUNCTION protect_inference_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'inference evidence cannot be deleted';
          END IF;
          IF OLD.status <> 'dispatched' OR NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
             OR NEW.scope <> OLD.scope OR NEW.operation_key <> OLD.operation_key
             OR NEW.request_hash <> OLD.request_hash OR NEW.request_data <> OLD.request_data
             OR NEW.reserved_tokens <> OLD.reserved_tokens OR NEW.created_at <> OLD.created_at
             OR NEW.lease_until <> OLD.lease_until THEN
            RAISE EXCEPTION 'inference evidence is immutable after dispatch/settlement';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER immutable_inference_evidence BEFORE UPDATE OR DELETE ON "
        "inference_calls FOR EACH ROW EXECUTE FUNCTION protect_inference_evidence()"
    )


def downgrade() -> None:
    # Export inference/audit evidence before a destructive downgrade.
    op.drop_table("inference_calls")
    op.execute("DROP FUNCTION protect_inference_evidence()")
