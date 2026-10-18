"""Offline reproduction of the synthetic clear/tall/painted final-card mismatch."""

from collections.abc import Awaitable, Callable, Sequence
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from tests.shopper_review import supported_review_session

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
)
from open_commerce.core.types import JsonObject, utc_now
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.search.agent_tools import CatalogSearchTool
from open_commerce.shopper_agent.memory_tools import SaveShoppingMemoryInput
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome, ShopperConversationalAgent
from open_commerce.shopper_agent.models import ShopperMemory
from open_commerce.shopper_agent.product_tools import product_card
from open_commerce.telemetry.activity_tools import ActivityTools

FINAL_MESSAGE = (
    "I found three options under $30. Two fit your dishwasher-safe request: "
    "Clear Drinking Glasses ($19.99) and Tall Drinking Glasses ($24.99). "
    "Painted Drinking Glasses are hand wash only, so I excluded them. "
    "If you want, I can help you compare the two dishwasher-safe sets."
)
ALL_IDS = ["glass-clear", "glass-tall", "glass-painted"]
FINAL_IDS = ["glass-clear", "glass-tall"]


def call(name: str, arguments: JsonObject) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[ManagerToolCall(call_id=name, name=name, arguments=arguments)]
    )


def recorded_turns() -> list[ManagerModelTurn]:
    # The four decisions and final text match the private synthetic verification trace.
    return [
        call(
            "catalog_search",
            {
                "in_stock": True,
                "query": "dishwasher-safe drinking glasses",
                "mode": "hybrid_reranked",
                "top_k": 6,
                "category": None,
                "brand": None,
                "min_price_minor": None,
                "max_price_minor": 3000,
                "currency": "USD",
            },
        ),
        call("select_catalog_products", {"product_ids": ALL_IDS}),
        call("complete_shopping_turn", {"kind": "conversation", "message": FINAL_MESSAGE}),
        call("complete_shopping_turn", {"kind": "catalog", "message": FINAL_MESSAGE}),
    ]


class ScriptedProvider:
    provider_name = "scripted"
    model_id = "offline"

    def __init__(self, turns: Sequence[ManagerModelTurn | ManagerModelUnavailableError]) -> None:
        self.turns = iter(turns)
        self.results: list[list[ManagerToolResult]] = []

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
        review = supported_review_session(messages, tools)
        if review is not None:
            return review
        return self

    async def next(self, results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.results.append(results)
        turn = next(self.turns)
        if isinstance(turn, ManagerModelUnavailableError):
            raise turn
        return turn


async def run_script(
    monkeypatch: pytest.MonkeyPatch,
    turns: Sequence[ManagerModelTurn | ManagerModelUnavailableError],
    *,
    save_memory: Callable[[SaveShoppingMemoryInput], Awaitable[ShopperMemory]] | None = None,
    activity_tools: ActivityTools | None = None,
    max_tool_calls: int = 3,
    expected_first_selection: Sequence[str] = tuple(ALL_IDS),
    review_budget: int = 0,
) -> tuple[ShopperAgentOutcome, ScriptedProvider]:
    products = {
        f"glass-{key}": CatalogBrowseProduct.model_validate(
            {
                "product_id": f"glass-{key}",
                "title": f"{key.title()} Drinking Glasses",
                "description": description,
                "brand": None,
                "category": "",
                "image_url": None,
                "variant_id": f"glass-{key}-default",
                "price": {"amount_minor": price, "currency": "USD"},
                "availability": "available",
                "provenance": None,
                "variants": [
                    {
                        "id": f"glass-{key}-default",
                        "title": "Default",
                        "options": {},
                        "price": {"amount_minor": price, "currency": "USD"},
                        "available": True,
                        "availability": "available",
                    }
                ],
            }
        )
        for key, price, description in [
            ("clear", 1999, "Set of four dishwasher-safe drinking glasses."),
            ("tall", 2499, "Set of two tall dishwasher-safe drinking glasses."),
            ("painted", 1599, "Decorated drinking glasses. Hand wash only."),
        ]
    }

    async def browse(*, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        assert tenant_id == UUID(int=1)
        assert query.product_id in products
        return CatalogBrowseResponse.model_validate(
            {
                "catalog": {
                    "id": UUID(int=20),
                    "filename": "synthetic.csv",
                    "source_version": "test",
                    "product_count": len(products),
                    "published_at": None,
                },
                "indexing": {},
                "categories": [],
                "items": [products[query.product_id]],
                "total": 1,
                "offset": 0,
                "limit": query.limit,
            }
        )

    reader = AsyncMock()
    reader.browse.side_effect = browse
    monkeypatch.setattr(
        CatalogSearchTool,
        "run",
        AsyncMock(
            return_value={
                "ok": True,
                "result_count": len(products),
                "results": [
                    product_card(item).model_dump(mode="json") for item in products.values()
                ],
            }
        ),
    )
    provider = ScriptedProvider(turns)
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        catalog_reader=reader,
        max_iterations=len(turns) + review_budget,
        max_tool_calls=max_tool_calls,
        max_output_tokens=1500,
    ).respond(
        tenant_id=UUID(int=1),
        content="Find dishwasher-safe drinking glasses under $30.",
        history=[],
        memories=[],
        source="uploaded_catalog",
        save_memory=save_memory,
        activity_tools=activity_tools,
    )
    if len(provider.results) > 2:
        selection = provider.results[2][0].output["selected_products"]
        assert isinstance(selection, list)
        assert [item["product_id"] for item in selection] == list(expected_first_selection)
        for item in selection:
            assert item["catalog_description"] == products[item["product_id"]].description
    return result, provider


async def test_recorded_completion_requires_final_card_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, provider = await run_script(monkeypatch, recorded_turns())
    assert len(provider.results) == 4
    assert result.steps[-1].status != "completed", (
        result.content,
        [product.product_id for product in result.products],
    )
    assert result.content != FINAL_MESSAGE
    assert result.products == []


@pytest.mark.parametrize(
    "stop",
    [
        "mismatched_completion",
        "conversation_completion",
        "selection",
        "provider",
        "incomplete",
        "tool_budget",
    ],
)
async def test_unfinished_turn_never_presents_unconfirmed_selected_cards(
    monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    turns: list[ManagerModelTurn | ManagerModelUnavailableError] = list(recorded_turns()[:2])
    if stop == "mismatched_completion":
        turns.append(
            call(
                "complete_shopping_turn",
                {"kind": "catalog", "message": FINAL_MESSAGE, "product_ids": FINAL_IDS},
            )
        )
    elif stop == "conversation_completion":
        turns.append(
            call(
                "complete_shopping_turn",
                {"kind": "conversation", "message": FINAL_MESSAGE, "product_ids": None},
            )
        )
    elif stop == "provider":
        turns.append(ManagerModelUnavailableError("Synthetic provider failure"))
    elif stop == "incomplete":
        turns.append(ManagerModelTurn(content="Unfinished", stop_reason="incomplete"))
    elif stop == "tool_budget":
        turns.append(call("inspect_shopping_activity", {}))
    result, _ = await run_script(monkeypatch, turns, max_tool_calls=2)
    assert result.steps[-1].status == "fallback"
    assert result.products == []
    assert "Drinking Glasses" not in result.content
    assert "No new recommendations were confirmed" in result.content


async def test_failed_completion_preserves_committed_memory_without_cards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = ShopperMemory(id=UUID(int=30), content="I prefer glass", created_at=utc_now())
    save = AsyncMock(return_value=memory)
    turns: list[ManagerModelTurn | ManagerModelUnavailableError] = list(recorded_turns()[:2])
    turns.extend(
        [
            call(
                "save_shopping_memory",
                {"source_message_id": str(UUID(int=2)), "preference": memory.content},
            ),
            ManagerModelUnavailableError("Synthetic provider failure"),
        ]
    )
    result, _ = await run_script(monkeypatch, turns, save_memory=save)
    save.assert_awaited_once()
    assert "Saved to your shopping memory: I prefer glass" in result.content
    assert result.products == []
    assert "Drinking Glasses" not in result.content
    assert result.steps[-1].status == "fallback"


async def test_declared_two_cards_require_reselection_then_complete_with_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turns = recorded_turns()
    turns[2].tool_calls[0].arguments["product_ids"] = None
    turns[3].tool_calls[0].arguments["product_ids"] = FINAL_IDS
    turns.extend(
        [
            call("select_catalog_products", {"product_ids": FINAL_IDS}),
            call(
                "complete_shopping_turn",
                {"kind": "catalog", "message": FINAL_MESSAGE, "product_ids": FINAL_IDS},
            ),
        ]
    )
    result, provider = await run_script(monkeypatch, turns, review_budget=1)
    correction = provider.results[4][0]
    assert correction.is_error
    assert correction.output["error"] == "INCOMPLETE_SHOPPING_TURN"
    assert "select_catalog_products again" in str(correction.output["correction"])
    reselected = provider.results[5][0].output["selected_products"]
    assert isinstance(reselected, list)
    assert [item["product_id"] for item in reselected] == FINAL_IDS
    assert [product.product_id for product in result.products] == FINAL_IDS
    assert result.content == FINAL_MESSAGE
    assert result.steps[-1].status == "completed"
    assert len(provider.results) == 6


async def test_scripted_review_approval_is_not_proof_of_freeform_attribute_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turns = recorded_turns()
    turns[2].tool_calls[0].arguments["product_ids"] = None
    turns[3].tool_calls[0].arguments["product_ids"] = ALL_IDS
    result, _ = await run_script(monkeypatch, turns, review_budget=1)
    # This explicitly scripted approval is not a semantic oracle. Live review must
    # independently catch the mismatch; mocks only test enforcement of its decision.
    assert [product.product_id for product in result.products] == ALL_IDS
    assert result.content == FINAL_MESSAGE
    assert result.steps[-1].status == "completed"


@pytest.mark.parametrize("kind", ["clarification", "memory", "activity", "blocked", "refusal"])
async def test_non_catalog_completion_with_null_declaration_returns_no_prior_cards(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    turns = recorded_turns()[:2]
    save = None
    activity = None
    if kind == "memory":
        save = AsyncMock(
            return_value=ShopperMemory(
                id=UUID(int=30), content="dishwasher-safe drinking glasses", created_at=utc_now()
            )
        )
        turns.append(
            call(
                "save_shopping_memory",
                {
                    "source_message_id": str(UUID(int=2)),
                    "preference": "dishwasher-safe drinking glasses",
                },
            )
        )
    elif kind in {"activity", "blocked"}:
        activity = AsyncMock(spec=ActivityTools)
        activity.execute.return_value = (
            {"ok": True, "events": []}
            if kind == "activity"
            else {"ok": False, "error": "ACTIVITY_UNAVAILABLE"}
        )
        turns.append(call("inspect_shopping_activity", {}))
    answer = {
        "clarification": "Which glass size do you need?",
        "memory": "Your preference was saved.",
        "activity": "There are no matching activity events.",
        "blocked": "Shopping activity is currently unavailable.",
        "refusal": "I cannot place an order. Use the explicit cart and checkout controls.",
    }[kind]
    turns.append(
        call("complete_shopping_turn", {"kind": kind, "message": answer, "product_ids": None})
    )
    result, provider = await run_script(
        monkeypatch, turns, save_memory=save, activity_tools=activity
    )
    assert result.content == answer
    assert result.steps[-1].status == (
        "needs_input" if kind in {"clarification", "blocked"} else "completed"
    )
    assert len(provider.results) == len(turns)
    if save is not None:
        save.assert_awaited_once()
    if activity is not None:
        activity.execute.assert_awaited_once()
    assert result.products == []


@pytest.mark.parametrize("selected_ids", [[], ["glass-clear"]])
async def test_catalog_answer_recovers_from_wrong_kind_without_repeating_reads(
    monkeypatch: pytest.MonkeyPatch, selected_ids: list[str]
) -> None:
    answer = "Only the default variant exists." if selected_ids else "That option is not listed."
    turns = [
        call("lookup_catalog_products", {"product_ids": ["glass-clear"], "queries": []}),
        call("select_catalog_products", {"product_ids": selected_ids}),
        call(
            "complete_shopping_turn",
            {"kind": "conversation", "message": answer, "product_ids": None},
        ),
        call(
            "complete_shopping_turn",
            {"kind": "catalog", "message": answer, "product_ids": selected_ids},
        ),
    ]
    result, provider = await run_script(
        monkeypatch,
        turns,
        max_tool_calls=2,
        expected_first_selection=selected_ids,
        review_budget=int(bool(selected_ids)),
    )
    correction = provider.results[-1][0]
    assert correction.is_error and correction.output["error"] == "INCOMPLETE_SHOPPING_TURN"
    assert 'kind="catalog"' in str(correction.output["correction"])
    assert "no match is not a tool failure" in str(correction.output["correction"])
    assert result.content == answer
    assert [item.product_id for item in result.products] == selected_ids
    assert result.steps[-1].status == "completed"
    assert len(provider.results) == 4


@pytest.mark.parametrize("lookup_first", [True, False])
async def test_permission_refusal_needs_no_failed_tool_probe(
    monkeypatch: pytest.MonkeyPatch, lookup_first: bool
) -> None:
    answer = "I cannot bypass cart confirmation or access another shopper's data."
    turns = (
        [call("lookup_catalog_products", {"product_ids": ["glass-clear"], "queries": []})]
        if lookup_first
        else []
    )
    turns.append(
        call(
            "complete_shopping_turn",
            {"kind": "refusal", "message": answer, "product_ids": None},
        )
    )
    result, provider = await run_script(monkeypatch, turns, max_tool_calls=int(lookup_first))
    assert result.content == answer
    assert not result.products
    assert result.steps[-1].title == "Explain permission limits"
    assert result.steps[-1].status == "completed"
    assert len(provider.results) == len(turns)


async def test_failed_tool_answer_recovers_to_blocked_without_repeating_operation() -> None:
    answer = "That comparison needs a fresh catalog read. No prices were compared."
    turns = [
        call("compare_catalog_prices", {"items": []}),
        call(
            "complete_shopping_turn",
            {"kind": "conversation", "message": answer, "product_ids": None},
        ),
        call(
            "complete_shopping_turn",
            {"kind": "blocked", "message": answer, "product_ids": None},
        ),
    ]
    # This scenario has no selection; inspect its actual error receipts separately.
    provider = ScriptedProvider(turns)
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        catalog_reader=AsyncMock(),
        max_iterations=3,
        max_tool_calls=1,
        max_output_tokens=1500,
    ).respond(
        tenant_id=UUID(int=1),
        content="Compare these products.",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert provider.results[1][0].output["error"] == "INVALID_TOOL_ARGUMENTS"
    assert 'kind="blocked"' in str(provider.results[2][0].output["correction"])
    assert result.content == answer and not result.products
    assert result.steps[-1].title == "Explain the blocker"
