from open_commerce.persistence import models as _models
from open_commerce.persistence.db import Base

assert _models is not None


def test_core_domain_tables_are_registered_in_metadata() -> None:
    expected_tables = {
        "tenants",
        "users",
        "tenant_memberships",
        "integrations",
        "integration_credentials",
        "products",
        "product_variants",
        "inventory_snapshots",
        "customer_facts",
        "orders",
        "order_lines",
        "behavioral_events",
        "search_index_versions",
        "search_boost_rules",
        "goals",
        "goal_budgets",
        "goal_constraints",
        "policy_versions",
        "goal_runs",
        "goal_run_steps",
        "observation_snapshots",
        "opportunities",
        "action_intents",
        "compiled_actions",
        "policy_decisions",
        "approval_requests",
        "approvals",
        "action_executions",
        "action_reconciliations",
        "interventions",
        "intervention_outcomes",
        "budget_accounts",
        "budget_ledger_entries",
        "audit_events",
        "webhook_receipts",
        "sync_jobs",
        "source_mappings",
    }

    assert expected_tables.issubset(Base.metadata.tables)


def test_tenant_owned_tables_have_tenant_id_column() -> None:
    # Local credentials extend the global user identity, not tenant business data.
    # All resulting sessions still require a persisted owner membership.
    exempt = {"tenants", "users", "merchant_credentials"}
    missing = [
        table_name
        for table_name, table in Base.metadata.tables.items()
        if table_name not in exempt and "tenant_id" not in table.columns
    ]

    assert missing == []


def test_merchant_credentials_extend_existing_identity() -> None:
    credentials = Base.metadata.tables["merchant_credentials"]
    assert {fk.target_fullname for fk in credentials.foreign_keys} == {"users.id"}
