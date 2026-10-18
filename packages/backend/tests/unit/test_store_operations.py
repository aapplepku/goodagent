"""Merchant operations grounding, coverage and model tool boundaries."""

from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from open_commerce.manager_agent.catalog_operations import audit_catalog, review_stock
from open_commerce.manager_agent.model_agent import MANAGER_INSTRUCTIONS, _tool_registry
from open_commerce.manager_agent.model_provider import ManagerToolCall
from open_commerce.manager_agent.operations import OPERATIONS_DESCRIPTIONS, StoreOperations
from open_commerce.manager_agent.operations_models import (
    CatalogAuditInput,
    CatalogFacts,
    CatalogProductFact,
    CatalogVariantFact,
    OperationsWindow,
    StockReviewInput,
)
from open_commerce.manager_agent.tools import ManagerToolRuntime
from open_commerce.manager_agent.workspace_tools import WorkspaceTools
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.agent_tools import CatalogSearchTool

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def facts() -> CatalogFacts:
    return CatalogFacts(
        catalog_id=UUID(int=1),
        source_version="test-v1",
        checked_at=NOW,
        product_count=1,
        variant_count=1,
        products=[
            CatalogProductFact(
                id=UUID(int=2),
                product_id="tea",
                title="Tea",
                missing_description=True,
                missing_image=True,
                image_failed=False,
                missing_category=False,
            )
        ],
        variants=[
            CatalogVariantFact(
                product_id=UUID(int=2),
                variant_id="tea-small",
                sku="TEA",
                price_minor=1000,
                cost_minor=None,
                compare_at_price_minor=None,
                available=True,
                observed_quantity=7,
                observed_at=NOW,
                reserved_quantity=3,
            )
        ],
    )


def test_catalog_audit_reports_actual_fields_without_invented_economics() -> None:
    result = audit_catalog(facts(), CatalogAuditInput())
    assert result.issue_counts == {"missing_description": 1, "missing_image": 1}
    assert result.examples[0].product_id == "tea"
    assert result.coverage_complete
    assert "price_below_recorded_cost" not in result.issue_counts
    assert result.next_actions[0].execution == "owner_control"


def test_duplicate_skus_and_price_flags_are_per_variant_with_bounded_examples() -> None:
    catalog = facts()
    catalog.variants[0].cost_minor = 1100
    catalog.variants[0].compare_at_price_minor = 900
    catalog.variants.append(
        catalog.variants[0].model_copy(
            update={
                "variant_id": "tea-large",
                "sku": " tea ",
                "price_minor": 0,
            }
        )
    )
    catalog.variant_count = 2
    result = audit_catalog(catalog, CatalogAuditInput(limit=1))
    assert result.issue_counts["duplicate_sku"] == 2
    assert result.issue_counts["price_below_recorded_cost"] == 2
    assert result.issue_counts["nonpositive_price_review"] == 1
    assert result.issue_counts["compare_at_not_above_price"] == 1
    assert len(result.examples) == 1 and result.examples_truncated
    assert '"sku":' not in result.model_dump_json()


def test_partial_catalog_does_not_claim_missing_variants_from_a_truncated_read() -> None:
    catalog = facts().model_copy(update={"variants": [], "coverage_complete": False})
    result = audit_catalog(catalog, CatalogAuditInput())
    assert "no_variants" not in result.issue_counts
    assert not result.coverage_complete
    assert result.variants_checked == 0


def test_missing_catalog_is_not_a_successful_clean_audit() -> None:
    result = audit_catalog(CatalogFacts(checked_at=NOW), CatalogAuditInput())
    assert result.catalog_id is None and result.product_count == 0
    assert result.next_actions[0].priority == "high"
    assert "confirm" in result.next_actions[0].next_step


def test_inventory_uses_holds_and_keeps_unknown_separate() -> None:
    catalog = facts()
    result = review_stock(catalog, StockReviewInput())
    assert result.examples[0].sellable_quantity == 4
    assert result.examples[0].state == "low"
    assert result.counts["fresh_low_or_out"] == 1
    catalog.variants[0].observed_quantity = None
    catalog.variants[0].observed_at = None
    result = review_stock(catalog, StockReviewInput())
    assert result.examples[0].state == "unknown"
    assert result.examples[0].sellable_quantity is None
    assert result.counts.get("out", 0) == 0
    assert all(action.priority != "high" for action in result.next_actions)


def test_stale_low_stock_is_not_a_current_restock_claim() -> None:
    catalog = facts()
    catalog.variants[0].observed_at = NOW - timedelta(days=2)
    result = review_stock(catalog, StockReviewInput())
    assert result.examples[0].stale
    assert result.counts["stale"] == 1
    assert result.counts.get("fresh_low_or_out", 0) == 0
    assert result.next_actions[0].topic == "stock_freshness"


def test_unavailable_variants_do_not_become_healthy_with_positive_stock() -> None:
    catalog = facts()
    catalog.variants[0].available = False
    result = review_stock(catalog, StockReviewInput())
    assert result.examples[0].state == "unavailable"
    assert result.counts.get("healthy", 0) == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"hours": 0},
        {"hours": 721},
        {"tenant_id": str(UUID(int=3))},
        {"account_id": str(UUID(int=4))},
        {"sql": "select * from users"},
    ],
)
def test_operations_arguments_reject_unbounded_or_model_owned_scope(
    arguments: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        OperationsWindow.model_validate(arguments)


def test_registry_exposes_read_only_strict_tools_in_all_channels() -> None:
    registry = _tool_registry()
    for name in OPERATIONS_DESCRIPTIONS:
        tool = registry.specs[name]
        assert tool.permission == "read"
        assert not tool.definition.simulated
        schema = tool.definition.parameters
        assert schema["additionalProperties"] is False
        required, properties = schema["required"], schema["properties"]
        assert isinstance(required, list) and isinstance(properties, dict)
        assert set(required) == set(properties)
    assert "Refunds, fulfillment, source" in MANAGER_INSTRUCTIONS
    assert "demo values" in MANAGER_INSTRUCTIONS


async def test_workspace_dispatch_passes_server_tenant_to_read_only_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call = ManagerToolCall(
        name="review_shopper_performance", call_id="call-1", arguments={"hours": 24}
    )
    execute = AsyncMock(return_value={"observed": True})
    monkeypatch.setattr(StoreOperations, "execute", execute)
    tenant = UUID(int=8)
    workspace = WorkspaceTools(cast(RuntimeDatabase, object()))
    assert await workspace.execute(call, tenant, None) == {"observed": True}
    execute.assert_awaited_once_with(call, tenant)


async def test_model_can_follow_daily_review_with_inventory_in_an_unrelated_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_manager_model_agent import _agent

    from open_commerce.manager_agent.model_provider import ManagerModelTurn
    from open_commerce.manager_agent.models import ManagerThread, ManagerWorkingMemory

    execute = AsyncMock(
        side_effect=[
            {"read_only": True, "priorities": [{"topic": "stock", "evidence": "2 low variants"}]},
            {"counts": {"low": 2}, "inventory_writes_enabled": False},
        ]
    )
    monkeypatch.setattr(StoreOperations, "execute", execute)
    agent, provider = _agent(
        [
            ManagerModelTurn(
                tool_calls=[ManagerToolCall(name="review_store_day", call_id="day", arguments={})]
            ),
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(name="review_inventory_risks", call_id="stock", arguments={})
                ]
            ),
            ManagerModelTurn(
                content=(
                    "Two variants look low. Verify stock in your source; "
                    "I have not changed quantities."
                )
            ),
        ]
    )
    agent.tool_runtime = ManagerToolRuntime(
        catalog_search=CatalogSearchTool(None),
        workspace=WorkspaceTools(cast(RuntimeDatabase, object())),
    )
    tenant = UUID(int=8)
    result = await agent.respond(
        tenant_id=tenant,
        content="What needs my attention today?",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        channel=ManagerThread(
            id=UUID(int=9),
            tenant_id=tenant,
            title="Search",
            slug="search",
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    assert "Two variants" in result.content
    assert execute.await_count == 2
    assert provider.session.results[1][0].name == "review_store_day"
    assert provider.session.results[2][0].output["counts"] == {"low": 2}
    assert all(call.args[1] == tenant for call in execute.await_args_list)
