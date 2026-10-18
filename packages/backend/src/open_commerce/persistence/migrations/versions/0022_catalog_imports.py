"""Encrypted expiring catalog staging and safe raster assets."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0022_catalog_imports"
down_revision = "0021_model_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_imports",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("encrypted_data", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("mapping", pg.JSONB, nullable=False),
        sa.Column("currency", sa.String(3)),
        sa.Column("catalog_id", pg.UUID(), sa.ForeignKey("integrations.id")),
        sa.Column("report", pg.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_import_tenant_expiry", "catalog_imports", ["tenant_id", "expires_at"])
    op.create_table(
        "catalog_assets",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("tenant_id", pg.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("import_id", pg.UUID(), sa.ForeignKey("catalog_imports.id"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_tenant_import", "catalog_assets", ["tenant_id", "import_id"])


def downgrade() -> None:
    op.drop_table("catalog_assets")
    op.drop_table("catalog_imports")
