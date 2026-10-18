"""Offline sample/context evidence, not a reproduction of live model decisions."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from open_commerce.catalog.browse_models import CatalogBrowseQuery, CatalogBrowseResponse
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.search.agent_tools import CatalogSearchTool
from open_commerce.search.parser import parse_search_intent
from open_commerce.shopper_agent.model_agent import ShopperConversationalAgent
from open_commerce.stores.import_validation import validate_import
from open_commerce.stores.sample import sample_catalog_bytes

PROMPT = "Find dishwasher-safe drinking glasses under $30."


@pytest.mark.parametrize(
    ("product_id", "price_minor", "quantity"),
    [("B0896LJNLH", 1388, 52), ("B07FS68L6N", 2853, 115)],
)
def test_fixed_preview_task_has_importable_catalog_matches(
    product_id: str, price_minor: int, quantity: int
) -> None:
    _, products, errors = validate_import(sample_catalog_bytes().decode(), "sample.csv")
    assert errors == []
    assert len(products) == 48
    product = next(item for item in products if item.source_product_id == product_id)
    [variant] = product.variants
    assert variant.source_variant_id == f"{product_id}-default"
    assert variant.price_minor == price_minor < 3000
    assert variant.currency == "USD"
    assert variant.available is True
    assert variant.inventory_quantity == quantity > 0
    assert "glass" in product.title.casefold()
    # The feature survives the same description bound used by lookup/selection tools.
    assert "dishwasher safe" in product.description_text[:1000].casefold().replace("-", " ")
    filters = parse_search_intent(PROMPT).required_filters
    assert filters.max_price_minor == 3000
    assert filters.currency == "USD"
    assert filters.category is None
    assert filters.brand is None


class UnusedCatalogReader:
    async def browse(self, *, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        raise AssertionError("No catalog lookup is scripted in this evidence test")


class ScriptedProvider:
    provider_name = "offline-script"
    model_id = "no-model"

    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.turns = list(turns)
        self.receipts: list[list[ManagerToolResult]] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        assert require_tool
        [current] = messages
        assert current.role == "user"
        assert json.loads(current.content) == {
            "source_message_id": str(UUID(int=2)),
            "content": PROMPT,
        }
        assert "Explicit shopper preferences:\n[]" in instructions
        assert {tool.name for tool in tools} == {
            "complete_shopping_turn",
            "catalog_search",
            "lookup_catalog_products",
            "compare_catalog_prices",
            "select_catalog_products",
        }
        return self

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.receipts.append(tool_results)
        return self.turns.pop(0)


@pytest.mark.parametrize("did_search", [False, True])
async def test_first_turn_no_search_and_zero_hits_have_distinct_steps(
    did_search: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    search = CatalogSearchTool(None)
    run_search = AsyncMock(return_value={"ok": True, "result_count": 0, "results": []})
    monkeypatch.setattr(search, "run", run_search)
    turns = (
        [
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="search-1", name="catalog_search", arguments={"query": PROMPT}
                    )
                ]
            )
        ]
        if did_search
        else []
    )
    answer = "No matching products were found." if did_search else "I will look for those glasses."
    if did_search:
        turns.extend(
            [
                ManagerModelTurn(
                    tool_calls=[
                        ManagerToolCall(
                            call_id="select",
                            name="select_catalog_products",
                            arguments={"product_ids": []},
                        )
                    ]
                ),
                ManagerModelTurn(
                    tool_calls=[
                        ManagerToolCall(
                            call_id="finish",
                            name="complete_shopping_turn",
                            arguments={"kind": "catalog", "message": answer, "product_ids": []},
                        )
                    ]
                ),
            ]
        )
    else:
        turns.append(ManagerModelTurn(content=answer, phase="final_answer"))
    provider = ScriptedProvider(turns)
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=search,
        catalog_reader=UnusedCatalogReader(),
        max_iterations=len(turns),
        max_tool_calls=6,
        max_output_tokens=1500,
    ).respond(
        tenant_id=UUID(int=1),
        content=PROMPT,
        history=[],
        memories=[],
        current_message_id=UUID(int=2),
        source="uploaded_catalog",
        memory_scope="temporary",
    )
    if did_search:
        assert result.content == answer
    else:
        assert answer not in result.content
        assert result.steps[-1].status == "needs_input"
    assert result.products == []
    assert all(step.status != "fallback" for step in result.steps)
    assert run_search.await_count == int(did_search)
    assert any(step.stage == "search" and step.status == "completed" for step in result.steps) == (
        did_search
    )
    if did_search:
        assert provider.receipts[1][0].output["result_count"] == 0
        assert any("Observed 0 candidates" in step.detail for step in result.steps)
    else:
        assert provider.receipts == [[]]
