"""Add local carts, inventory reservations, payment attempts, and shopper orders.

Revision ID: 0016_cart_checkout_inventory
Revises: 0015_shopper_accounts
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_cart_checkout_inventory"
down_revision = "0015_shopper_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopper_carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'converted', 'abandoned')", name="ck_cart_status"),
        sa.ForeignKeyConstraint(["account_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_shopper_open_cart",
        "shopper_carts",
        ["tenant_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index("ix_shopper_carts_tenant_updated", "shopper_carts", ["tenant_id", "updated_at"])
    op.create_table(
        "shopper_cart_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_product_id", sa.String(length=240), nullable=False),
        sa.Column("source_variant_id", sa.String(length=240), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("variant_title", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity BETWEEN 1 AND 20", name="ck_cart_line_quantity"),
        sa.CheckConstraint("unit_price_minor >= 0", name="ck_cart_line_price"),
        sa.ForeignKeyConstraint(["account_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["shopper_carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["catalog_variant_id"], ["product_variants.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "account_id", "cart_id", "catalog_variant_id", name="uq_cart_variant"
        ),
    )
    op.create_index(
        "ix_cart_lines_tenant_cart",
        "shopper_cart_lines",
        ["tenant_id", "account_id", "cart_id"],
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_reference", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("idempotency_key_digest", sa.String(length=80), nullable=False),
        sa.Column(
            "policy_decision",
            postgresql.JSONB(astext_type=sa.Text()),  # type: ignore[no-untyped-call]
            nullable=False,
        ),
        sa.Column(
            "preconditions",
            postgresql.JSONB(astext_type=sa.Text()),  # type: ignore[no-untyped-call]
            nullable=False,
        ),
        sa.Column(
            "rollback_metadata",
            postgresql.JSONB(astext_type=sa.Text()),  # type: ignore[no-untyped-call]
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name="ck_payment_amount"),
        sa.CheckConstraint(
            "status IN ('requires_confirmation', 'processing', "
            "'requires_payment_method', 'succeeded', 'cancelled')",
            name="ck_payment_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["shopper_carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "cart_id", "cart_version", name="uq_cart_version_payment"),
    )
    op.create_index(
        "ix_payment_attempts_tenant_created", "payment_attempts", ["tenant_id", "created_at"]
    )
    op.create_table(
        "inventory_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_product_id", sa.String(length=240), nullable=False),
        sa.Column("source_variant_id", sa.String(length=240), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("release_reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_reservation_quantity"),
        sa.CheckConstraint(
            "status IN ('active', 'released', 'consumed', 'expired')",
            name="ck_reservation_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["shopper_carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_line_id"], ["shopper_cart_lines.id"]),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["catalog_variant_id"], ["product_variants.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "checkout_id", "catalog_variant_id", name="uq_checkout_variant_reservation"
        ),
    )
    op.create_index(
        "ix_reservations_tenant_variant_active",
        "inventory_reservations",
        ["tenant_id", "catalog_variant_id", "status", "expires_at"],
    )
    op.create_table(
        "shopper_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "line_snapshots",
            postgresql.JSONB(astext_type=sa.Text()),  # type: ignore[no-untyped-call]
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('paid', 'cancelled')", name="ck_shopper_order_status"),
        sa.CheckConstraint("amount_minor >= 0", name="ck_shopper_order_amount"),
        sa.ForeignKeyConstraint(["account_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["shopper_carts.id"]),
        sa.ForeignKeyConstraint(["payment_attempt_id"], ["payment_attempts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_shopper_order_number"),
        sa.UniqueConstraint("tenant_id", "payment_attempt_id", name="uq_order_payment_attempt"),
    )
    op.create_index(
        "ix_shopper_orders_tenant_created", "shopper_orders", ["tenant_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("shopper_orders")
    op.drop_table("inventory_reservations")
    op.drop_table("payment_attempts")
    op.drop_table("shopper_cart_lines")
    op.drop_table("shopper_carts")
