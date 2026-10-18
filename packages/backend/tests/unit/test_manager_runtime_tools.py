"""Read-only manager search, status, and curated-code tool coverage."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from pydantic import ValidationError

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerRuntimeComponent,
    ManagerThread,
    ManagerWorkingMemory,
)
from open_commerce.manager_agent.tools import (
    InspectCodeToolInput,
    ManagerToolRuntime,
    channel_allows,
    extract_status_refresh,
)
from open_commerce.manager_agent.workspace_tools import WorkspaceTools
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.agent_tools import (
    CatalogSearchTool,
    CatalogSearchToolInput,
    catalog_search_tool_schema,
)
from open_commerce.search.service import SearchService


async def test_search_tool_runs_real_tenant_catalog_retrieval() -> None:
    runtime = ManagerToolRuntime(catalog_search=CatalogSearchTool(SearchService()))
    result = await runtime.test_search(
        tenant_id=UUID(int=1),
        arguments=CatalogSearchToolInput(query="outdoor shoes", top_k=4),
        catalog_index=CatalogIndexStatus(),
    )

    assert result["ok"] is True
    assert result["source"] == "simulator_fallback"
    assert isinstance(result["results"], list)
    assert result["results"]


def test_search_tool_does_not_advertise_unsupported_out_of_stock_mode() -> None:
    # The serving pipeline requires an available variant; false cannot broaden it.
    with pytest.raises(ValidationError):
        CatalogSearchToolInput.model_validate({"query": "drinking glasses", "in_stock": False})
    with pytest.raises(ValidationError):
        CatalogSearchToolInput.model_validate({"query": "drinking glasses", "in_stock": None})
    assert CatalogSearchToolInput(query="drinking glasses").in_stock is True
    schema = catalog_search_tool_schema()
    properties = schema["properties"]
    assert isinstance(properties, dict)
    stock = properties["in_stock"]
    assert stock["enum"] == [True]
    assert "False is not a way to broaden search" in stock["description"]


async def test_search_tool_matches_named_filters_case_insensitively() -> None:
    runtime = ManagerToolRuntime(catalog_search=CatalogSearchTool(SearchService()))
    result = await runtime.test_search(
        tenant_id=UUID(int=1),
        arguments=CatalogSearchToolInput(
            query="outdoor shoes",
            category="OUTDOOR",
            top_k=4,
        ),
        catalog_index=CatalogIndexStatus(),
    )

    assert result["ok"] is True
    assert isinstance(result["results"], list)
    assert result["results"]
    assert all(item["category"].casefold() == "outdoor" for item in result["results"])


async def test_status_aggregates_dependencies_and_commerce_surfaces() -> None:
    async def probe() -> list[ManagerRuntimeComponent]:
        return [
            ManagerRuntimeComponent(
                key="postgres", label="PostgreSQL", state="green", detail="Reachable"
            ),
            ManagerRuntimeComponent(
                key="redis", label="Redis jobs", state="green", detail="Reachable"
            ),
            ManagerRuntimeComponent(
                key="qdrant", label="Qdrant search", state="red", detail="Unavailable"
            ),
            ManagerRuntimeComponent(
                key="manager_web", label="Manager workspace", state="green", detail="Reachable"
            ),
            ManagerRuntimeComponent(
                key="shopper_web", label="Shopper app", state="green", detail="Reachable"
            ),
            ManagerRuntimeComponent(
                key="worker", label="Agent worker", state="red", detail="No recent heartbeat"
            ),
        ]

    runtime = ManagerToolRuntime(catalog_search=CatalogSearchTool(None), status_probe=probe)
    status = await runtime.status(
        catalog_index=CatalogIndexStatus(
            status="ready", product_count=40, indexed_product_count=40
        ),
        capabilities=ManagerAgentCapabilities(semantic_backend="test", learned_semantics=True),
    )

    by_key = {item.key: item for item in status.components}
    assert by_key["catalog_index"].state == "green"
    assert by_key["search"].state == "red"
    assert by_key["homepage"].state == "red"
    assert by_key["worker"].state == "red"


async def test_status_tool_uses_tenant_scoped_model_connection_evidence() -> None:
    database = cast(RuntimeDatabase, object())
    observed = ManagerRuntimeComponent(
        key="manager_agent",
        label="Conversation model",
        state="green",
        detail="Actual model response verified",
        observed_at=datetime.now(UTC),
        evidence_kind="model_call",
    )
    read = AsyncMock(return_value=observed)
    runtime = ManagerToolRuntime(
        catalog_search=CatalogSearchTool(None), workspace=WorkspaceTools(database)
    )
    with patch("open_commerce.runtime_services.model_connection", read):
        result = await runtime.status(
            tenant_id=UUID(int=7),
            catalog_index=CatalogIndexStatus(),
            capabilities=ManagerAgentCapabilities(semantic_backend="test", learned_semantics=False),
        )
    read.assert_awaited_once_with(database, UUID(int=7))
    assert next(item for item in result.components if item.key == "manager_agent") == observed


def test_code_inspection_is_curated_and_channel_focus_is_explicit() -> None:
    runtime = ManagerToolRuntime(catalog_search=CatalogSearchTool(None))
    result = runtime.inspect_code(InspectCodeToolInput(topic="search_retrieval"))
    excerpts = result["excerpts"]

    assert isinstance(excerpts, list)
    assert excerpts
    assert all(".env" not in str(item) for item in excerpts)
    custom = ManagerThread(
        id=UUID(int=2),
        tenant_id=UUID(int=1),
        title="Query analysis",
        description="Test search retrieval quality",
        slug="query-analysis",
        channel_kind="custom",
        working_memory=ManagerWorkingMemory(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert channel_allows(custom, "search") is True
    assert channel_allows(custom, "status") is False


def test_status_refresh_parser_requires_an_explicit_bounded_command() -> None:
    refresh = extract_status_refresh("Change status checks to every 10 minutes")
    disabled = extract_status_refresh("Turn status auto checks off")

    assert refresh is not None and refresh.minutes == 10
    assert disabled is not None and disabled.minutes == 0
    assert extract_status_refresh("Check every 5 minutes") is not None
    assert extract_status_refresh("Disable status refresh") == disabled
    assert extract_status_refresh("What is the current status?") is None
    assert extract_status_refresh("Check status every 90 minutes") is None
