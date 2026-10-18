"""core domain and persistence schema."""

# mypy: ignore-errors

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_domain"
down_revision: str | None = "0001_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *, nullable: bool = False, primary_key: bool = False) -> sa.Column:
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), primary_key=primary_key, nullable=nullable
    )


def tenant_column(*, nullable: bool = False) -> sa.Column:
    return uuid_column("tenant_id", nullable=nullable)


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def version_column() -> sa.Column:
    return sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False)


def upgrade() -> None:
    """Create the provider-independent domain schema."""

    op.create_table(
        "tenants",
        uuid_column("id", primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        created_at_column(),
        updated_at_column(),
        version_column(),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "users",
        uuid_column("id", primary_key=True),
        sa.Column("external_subject", sa.String(length=240), nullable=False),
        sa.Column("email_hash", sa.String(length=128), nullable=True),
        created_at_column(),
        sa.UniqueConstraint("external_subject", name="uq_users_external_subject"),
    )
    op.create_table(
        "tenant_memberships",
        tenant_column(),
        uuid_column("user_id"),
        sa.Column("role", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "user_id"),
    )
    op.create_table(
        "integrations",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("external_account_id", sa.String(length=240), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("non_secret_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
        version_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_account_id",
            name="uq_integrations_tenant_provider_account",
        ),
    )
    op.create_index("ix_integrations_tenant_id", "integrations", ["tenant_id"])
    op.create_table(
        "integration_credentials",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        created_at_column(),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("integration_id", name="uq_integration_credentials_integration_id"),
    )
    op.create_index(
        "ix_integration_credentials_tenant_id", "integration_credentials", ["tenant_id"]
    )

    op.create_table(
        "products",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("source_product_id", sa.String(length=240), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("handle", sa.String(length=240), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(length=160), nullable=True),
        sa.Column("category_path", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("primary_image_url", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        version_column(),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_product_id",
            name="uq_products_tenant_integration_source",
        ),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index(
        "ix_products_tenant_integration_updated",
        "products",
        ["tenant_id", "integration_id", "source_updated_at"],
    )
    op.create_table(
        "product_variants",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("product_id"),
        sa.Column("source_variant_id", sa.String(length=240), nullable=False),
        sa.Column("sku", sa.String(length=160), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("option_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("compare_at_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("cost_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        version_column(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "product_id",
            "source_variant_id",
            name="uq_variants_tenant_product_source",
        ),
    )
    op.create_index("ix_product_variants_tenant_id", "product_variants", ["tenant_id"])
    op.create_index(
        "ix_variants_tenant_product_sku",
        "product_variants",
        ["tenant_id", "product_id", "sku"],
    )
    op.create_table(
        "inventory_snapshots",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        uuid_column("variant_id"),
        sa.Column("source_location_id", sa.String(length=240), nullable=True),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("on_hand_quantity", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
    )
    op.create_index("ix_inventory_snapshots_tenant_id", "inventory_snapshots", ["tenant_id"])
    op.create_index(
        "ix_inventory_tenant_variant_observed",
        "inventory_snapshots",
        ["tenant_id", "variant_id", "observed_at"],
    )

    op.create_table(
        "customer_facts",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("source_customer_hash", sa.String(length=128), nullable=False),
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("lifetime_value_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        created_at_column(),
        updated_at_column(),
        version_column(),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_customer_hash",
            name="uq_customer_facts_tenant_integration_hash",
        ),
    )
    op.create_index("ix_customer_facts_tenant_id", "customer_facts", ["tenant_id"])
    op.create_table(
        "orders",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("source_order_id", sa.String(length=240), nullable=False),
        uuid_column("customer_fact_id", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("financial_status", sa.String(length=80), nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("refund_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=False),
        sa.Column("shipping_minor", sa.BigInteger(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_first_order", sa.Boolean(), nullable=True),
        sa.Column("source_channel", sa.String(length=120), nullable=True),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["customer_fact_id"], ["customer_facts.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "source_order_id",
            name="uq_orders_tenant_integration_source",
        ),
    )
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    op.create_index("ix_orders_tenant_created", "orders", ["tenant_id", "created_at"])
    op.create_index(
        "ix_orders_tenant_customer_created",
        "orders",
        ["tenant_id", "customer_fact_id", "created_at"],
    )
    op.create_table(
        "order_lines",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("order_id"),
        uuid_column("product_id", nullable=True),
        uuid_column("variant_id", nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("refund_minor", sa.BigInteger(), nullable=False),
        sa.Column("cost_minor", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
    )
    op.create_index("ix_order_lines_tenant_id", "order_lines", ["tenant_id"])

    op.create_table(
        "behavioral_events",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id", nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_event_id", sa.String(length=240), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id_hash", sa.String(length=128), nullable=False),
        sa.Column("anonymous_user_id_hash", sa.String(length=128), nullable=True),
        uuid_column("product_id", nullable=True),
        uuid_column("variant_id", nullable=True),
        uuid_column("query_id", nullable=True),
        sa.Column("result_position", sa.Integer(), nullable=True),
        sa.Column("surface", sa.String(length=80), nullable=False),
        sa.Column("consent", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safe_properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.UniqueConstraint(
            "tenant_id", "source", "source_event_id", name="uq_events_tenant_source_event"
        ),
    )
    op.create_index("ix_behavioral_events_tenant_id", "behavioral_events", ["tenant_id"])
    op.create_index(
        "ix_events_tenant_type_occurred",
        "behavioral_events",
        ["tenant_id", "event_type", "occurred_at"],
    )

    op.create_table(
        "policy_versions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        uuid_column("scope_id", nullable=True),
        version_column(),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        uuid_column("created_by", nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_policy_versions_tenant_id", "policy_versions", ["tenant_id"])
    op.create_table(
        "goals",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("objective", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("horizon", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("autonomy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_action_types", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("evaluation_schedule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        uuid_column("policy_version_id", nullable=True),
        created_at_column(),
        updated_at_column(),
        version_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
    )
    op.create_index("ix_goals_tenant_id", "goals", ["tenant_id"])
    op.create_index("ix_goals_active", "goals", ["tenant_id", "status"])
    op.create_table(
        "goal_budgets",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("allocated_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.UniqueConstraint(
            "goal_id", "kind", "period_start", name="uq_goal_budgets_goal_kind_period"
        ),
    )
    op.create_index("ix_goal_budgets_tenant_id", "goal_budgets", ["tenant_id"])
    op.create_table(
        "goal_constraints",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hard", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
    )
    op.create_index("ix_goal_constraints_tenant_id", "goal_constraints", ["tenant_id"])
    op.create_table(
        "goal_runs",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        sa.Column("thread_id", sa.String(length=240), nullable=False),
        sa.Column("trigger", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        uuid_column("observation_snapshot_id", nullable=True),
        uuid_column("policy_version_id", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("safe_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
        sa.UniqueConstraint("tenant_id", "goal_id", "thread_id", name="uq_runs_tenant_goal_thread"),
    )
    op.create_index("ix_goal_runs_tenant_id", "goal_runs", ["tenant_id"])
    op.create_index(
        "ix_runs_tenant_goal_started", "goal_runs", ["tenant_id", "goal_id", "started_at"]
    )
    op.create_table(
        "goal_run_steps",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("run_id"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("node_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_id", sa.String(length=160), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["goal_runs.id"]),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_steps_run_sequence"),
    )
    op.create_index("ix_goal_run_steps_tenant_id", "goal_run_steps", ["tenant_id"])
    op.create_table(
        "observation_snapshots",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
    )
    op.create_index("ix_observation_snapshots_tenant_id", "observation_snapshots", ["tenant_id"])
    op.create_table(
        "opportunities",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        uuid_column("snapshot_id"),
        sa.Column("type", sa.String(length=120), nullable=False),
        sa.Column("entity_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("estimated_value_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("detector_code", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        created_at_column(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["observation_snapshots.id"]),
    )
    op.create_index("ix_opportunities_tenant_id", "opportunities", ["tenant_id"])
    op.create_index(
        "ix_opportunities_tenant_goal_status", "opportunities", ["tenant_id", "goal_id", "status"]
    )

    op.create_table(
        "action_intents",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        uuid_column("run_id"),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "opportunity_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False
        ),
        sa.Column("actor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["goal_runs.id"]),
    )
    op.create_index("ix_action_intents_tenant_id", "action_intents", ["tenant_id"])
    op.create_table(
        "compiled_actions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        uuid_column("run_id"),
        uuid_column("intent_id", nullable=True),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("target_provider", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preconditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_impact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("estimated_cost_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("risk", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rollback_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("version_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        created_at_column(),
        updated_at_column(),
        version_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["goal_runs.id"]),
        sa.ForeignKeyConstraint(["intent_id"], ["action_intents.id"]),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_actions_tenant_idempotency"),
    )
    op.create_index("ix_compiled_actions_tenant_id", "compiled_actions", ["tenant_id"])
    op.create_index("ix_actions_tenant_status", "compiled_actions", ["tenant_id", "status"])

    op.create_table(
        "search_index_versions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("sparse_model", sa.String(length=160), nullable=False),
        sa.Column("document_template_version", sa.String(length=80), nullable=False),
        sa.Column("ranking_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("indexed_product_count", sa.Integer(), nullable=False),
        created_at_column(),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_search_index_versions_tenant_id", "search_index_versions", ["tenant_id"])
    op.create_table(
        "search_boost_rules",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("query_pattern", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("product_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("multiplier", sa.Numeric(8, 4), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        uuid_column("action_id"),
        sa.Column("status", sa.String(length=40), nullable=False),
        version_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
    )
    op.create_index("ix_search_boost_rules_tenant_id", "search_boost_rules", ["tenant_id"])

    op.create_table(
        "policy_decisions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("action_id"),
        uuid_column("policy_version_id", nullable=True),
        sa.Column("action_version_hash", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("reason_codes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("evaluated_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("required_roles", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
        sa.ForeignKeyConstraint(["policy_version_id"], ["policy_versions.id"]),
    )
    op.create_index("ix_policy_decisions_tenant_id", "policy_decisions", ["tenant_id"])
    op.create_table(
        "approval_requests",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("action_id"),
        sa.Column("action_version_hash", sa.String(length=80), nullable=False),
        sa.Column("required_roles", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_table(
        "approvals",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("request_id"),
        uuid_column("actor_user_id"),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("action_version_hash", sa.String(length=80), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.UniqueConstraint("request_id", "actor_user_id", name="uq_approvals_request_actor"),
    )
    op.create_index("ix_approvals_tenant_id", "approvals", ["tenant_id"])
    op.create_table(
        "action_executions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("action_id"),
        uuid_column("integration_id", nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_request_id", sa.String(length=240), nullable=True),
        sa.Column("provider_resource_id", sa.String(length=240), nullable=True),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.UniqueConstraint("action_id", "attempt", name="uq_execution_action_attempt"),
    )
    op.create_index("ix_action_executions_tenant_id", "action_executions", ["tenant_id"])
    op.create_index("ix_executions_unreconciled", "action_executions", ["tenant_id", "status"])
    op.create_table(
        "action_reconciliations",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("execution_id"),
        sa.Column("observed_remote_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["action_executions.id"]),
    )
    op.create_index("ix_action_reconciliations_tenant_id", "action_reconciliations", ["tenant_id"])
    op.create_table(
        "interventions",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("action_id"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("primary_metric", sa.String(length=80), nullable=False),
        sa.Column("monitor_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
    )
    op.create_index("ix_interventions_tenant_id", "interventions", ["tenant_id"])
    op.create_table(
        "intervention_outcomes",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("intervention_id"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("method", sa.String(length=120), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column("guardrail_status", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"]),
    )
    op.create_index("ix_intervention_outcomes_tenant_id", "intervention_outcomes", ["tenant_id"])

    op.create_table(
        "budget_accounts",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("goal_id"),
        sa.Column("budget_kind", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("allocated_minor", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        version_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.UniqueConstraint(
            "goal_id",
            "budget_kind",
            "period_start",
            name="uq_budget_accounts_goal_kind_period",
        ),
    )
    op.create_index("ix_budget_accounts_tenant_id", "budget_accounts", ["tenant_id"])
    op.create_table(
        "budget_ledger_entries",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("account_id"),
        uuid_column("action_id", nullable=True),
        sa.Column("operation_id", sa.String(length=160), nullable=False),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        created_at_column(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["budget_accounts.id"]),
        sa.ForeignKeyConstraint(["action_id"], ["compiled_actions.id"]),
        sa.UniqueConstraint(
            "account_id", "operation_id", name="uq_budget_entries_account_operation"
        ),
    )
    op.create_index("ix_budget_ledger_entries_tenant_id", "budget_ledger_entries", ["tenant_id"])

    op.create_table(
        "audit_events",
        uuid_column("id", primary_key=True),
        tenant_column(),
        sa.Column("actor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        uuid_column("entity_id"),
        sa.Column("request_id", sa.String(length=160), nullable=False),
        uuid_column("run_id", nullable=True),
        sa.Column("safe_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=80), nullable=True),
        sa.Column("event_hash", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index(
        "ix_audit_tenant_entity",
        "audit_events",
        ["tenant_id", "entity_type", "entity_id", "occurred_at"],
    )

    op.create_table(
        "webhook_receipts",
        uuid_column("id", primary_key=True),
        tenant_column(nullable=True),
        uuid_column("integration_id", nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("source_event_id", sa.String(length=240), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload_hash", sa.String(length=80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.UniqueConstraint("provider", "source_event_id", name="uq_webhooks_provider_event"),
    )
    op.create_index("ix_webhooks_pending_failed", "webhook_receipts", ["provider", "status"])
    op.create_table(
        "sync_jobs",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_cursor", sa.String(length=500), nullable=True),
        sa.Column("high_watermark", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_count", sa.BigInteger(), nullable=True),
        sa.Column("normalized_count", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
    )
    op.create_index(
        "ix_sync_jobs_tenant_integration_resource",
        "sync_jobs",
        ["tenant_id", "integration_id", "resource_type", "started_at"],
    )
    op.create_table(
        "source_mappings",
        uuid_column("id", primary_key=True),
        tenant_column(),
        uuid_column("integration_id"),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.String(length=240), nullable=False),
        uuid_column("normalized_id"),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_payload_hash", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"]),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "entity_type",
            "source_id",
            name="uq_source_mappings_tenant_integration_entity_source",
        ),
    )
    op.create_index("ix_source_mappings_tenant_id", "source_mappings", ["tenant_id"])


def downgrade() -> None:
    """Drop the provider-independent domain schema."""

    tables = [
        "source_mappings",
        "sync_jobs",
        "webhook_receipts",
        "audit_events",
        "budget_ledger_entries",
        "budget_accounts",
        "intervention_outcomes",
        "interventions",
        "action_reconciliations",
        "action_executions",
        "approvals",
        "approval_requests",
        "policy_decisions",
        "search_boost_rules",
        "search_index_versions",
        "compiled_actions",
        "action_intents",
        "opportunities",
        "observation_snapshots",
        "goal_run_steps",
        "goal_runs",
        "goal_constraints",
        "goal_budgets",
        "goals",
        "policy_versions",
        "behavioral_events",
        "order_lines",
        "orders",
        "customer_facts",
        "inventory_snapshots",
        "product_variants",
        "products",
        "integration_credentials",
        "integrations",
        "tenant_memberships",
        "users",
        "tenants",
    ]
    for table in tables:
        op.drop_table(table)
