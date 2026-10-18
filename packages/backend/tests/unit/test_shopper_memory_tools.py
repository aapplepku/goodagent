"""Model-directed memory decisions use validated, grounded tool calls."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from open_commerce.core.types import utc_now
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
from open_commerce.shopper_agent.memory_tools import (
    SAVE_SHOPPING_MEMORY,
    SaveShoppingMemoryInput,
    ShopperMemoryToolError,
    grounded_preference,
)
from open_commerce.shopper_agent.model_agent import ShopperConversationalAgent
from open_commerce.shopper_agent.models import ShopperMemory, ShopperMessage


class FakeSession:
    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.turns = turns
        self.results: list[list[ManagerToolResult]] = []

    async def next(self, results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.results.append(results)
        return self.turns.pop(0)


class FakeProvider:
    provider_name = "fake"
    model_id = "test"

    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.session = FakeSession(turns)
        self.messages: list[ManagerModelMessage] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        self.messages = messages
        return self.session


def finish(content: str, kind: str) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[
            ManagerToolCall(
                call_id="finish",
                name="complete_shopping_turn",
                arguments={"kind": kind, "message": content, "product_ids": None},
            )
        ]
    )


@pytest.mark.parametrize("exhausted", [False, True])
async def test_shopper_commentary_continues_within_existing_budget(exhausted: bool) -> None:
    provider = FakeProvider(
        [
            ManagerModelTurn(content="I will look", phase="commentary"),
            ManagerModelTurn(content="Which occasion?", phase="commentary")
            if exhausted
            else finish("Which occasion?", "clarification"),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=2,
        max_tool_calls=0,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Help me choose",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert provider.session.results == [[], []]
    assert result.products == []
    if exhausted:
        assert "stopped before completing" in result.content
        assert result.steps[-1].status == "needs_input"
    else:
        assert result.content == "Which occasion?"


async def test_shopper_does_not_present_incomplete_provider_text_as_final() -> None:
    provider = FakeProvider(
        [
            ManagerModelTurn(
                content="Unfinished answer", phase="final_answer", stop_reason="incomplete"
            )
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=2,
        max_tool_calls=0,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Hello",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert "stopped before completing" in result.content
    assert "Unfinished answer" not in result.content
    assert len(provider.session.results) == 1


@pytest.mark.parametrize(
    "stop_reason", ["incomplete", "failed", "cancelled", "in_progress", "queued", "unknown"]
)
async def test_shopper_does_not_save_memory_from_unfinished_turns(stop_reason: str) -> None:
    source = message("I prefer green products")
    memory = ShopperMemory(id=UUID(int=30), content=source.content, created_at=utc_now())
    save = AsyncMock(return_value=memory)
    provider = FakeProvider(
        [
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="unfinished-save",
                        name="save_shopping_memory",
                        arguments={
                            "source_message_id": str(source.id),
                            "preference": source.content,
                        },
                    )
                ],
                stop_reason=stop_reason,
            ),
            ManagerModelTurn(content="Should not reach this response"),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=3,
        max_tool_calls=2,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content=source.content,
        history=[],
        memories=[],
        source="uploaded_catalog",
        current_message_id=source.id,
        save_memory=save,
    )
    save.assert_not_awaited()
    assert "stopped before completing" in result.content
    assert provider.session.results == [[]]


def message(content: str, *, assistant: bool = False) -> ShopperMessage:
    return ShopperMessage(
        id=UUID(int=10),
        conversation_id=UUID(int=20),
        role="assistant" if assistant else "user",
        content=content,
        created_at=utc_now(),
    )


@pytest.mark.parametrize("content", ["i am into organic stuffs", "Premium is my usual choice"])
def test_natural_preferences_are_grounded_without_preference_phrase_matching(content: str) -> None:
    source = message(content)
    args = SaveShoppingMemoryInput(source_message_id=source.id, preference=content)
    assert grounded_preference(args, messages=[source], current_message=source) == content
    properties = SAVE_SHOPPING_MEMORY.parameters["properties"]
    assert isinstance(properties, dict) and "tenant_id" not in properties


@pytest.mark.parametrize(
    "content,quote,assistant,code",
    [
        ("i am into organic stuffs", "I am wealthy", False, "MEMORY_QUOTE_NOT_GROUNDED"),
        ("i am into organic stuffs", "i am into organic stuffs", True, "INVALID_MEMORY_SOURCE"),
        ("I like green; don't save this", "I like green", False, "MEMORY_OPTED_OUT"),
        ("I like green; don\u2019t remember it", "I like green", False, "MEMORY_OPTED_OUT"),
        ("I like green; this conversation only", "I like green", False, "MEMORY_OPTED_OUT"),
        ("I like green. My email is person@example.com", "I like green", False, "UNSAFE_MEMORY"),
    ],
)
def test_untrusted_memory_requests_are_rejected(
    content: str, quote: str, assistant: bool, code: str
) -> None:
    source = message(content, assistant=assistant)
    with pytest.raises(ShopperMemoryToolError, match=code):
        grounded_preference(
            SaveShoppingMemoryInput(source_message_id=source.id, preference=quote),
            messages=[source],
            current_message=source,
        )


def test_model_cannot_supply_account_authority() -> None:
    with pytest.raises(ValidationError):
        SaveShoppingMemoryInput.model_validate(
            {
                "source_message_id": str(UUID(int=1)),
                "preference": "I like organic",
                "account_id": str(UUID(int=2)),
            }
        )


@pytest.mark.parametrize("failure", [False, True])
async def test_model_observes_committed_memory_receipt_or_typed_failure(failure: bool) -> None:
    source = message("i am into organic stuffs")
    memory = ShopperMemory(id=UUID(int=30), content=source.content, created_at=utc_now())
    save = AsyncMock(return_value=memory)
    if failure:
        save.side_effect = ShopperMemoryToolError("MEMORY_STORAGE_UNAVAILABLE")
    provider = FakeProvider(
        [
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="save-1",
                        name="save_shopping_memory",
                        arguments={
                            "source_message_id": str(source.id),
                            "preference": source.content,
                        },
                    )
                ]
            ),
            finish(
                "Could not save." if failure else "Saved your organic preference.",
                "blocked" if failure else "memory",
            ),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=4,
        max_tool_calls=3,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content=source.content,
        history=[],
        memories=[],
        source="uploaded_catalog",
        current_message_id=source.id,
        save_memory=save,
    )
    assert save.await_count == 1
    assert json.loads(provider.messages[-1].content)["source_message_id"] == str(source.id)
    receipt = provider.session.results[1][0]
    assert receipt.call_id == "save-1"
    assert receipt.is_error is failure
    assert receipt.output["ok"] is not failure
    if failure:
        assert result.content == "Could not save."
    else:
        assert receipt.output["memory"] == memory.model_dump(mode="json")


async def test_provider_failure_after_save_retains_verified_success() -> None:
    source = message("i am into organic stuffs")
    memory = ShopperMemory(id=UUID(int=30), content=source.content, created_at=utc_now())
    provider = FakeProvider([])
    provider.session.next = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="save-1",
                        name="save_shopping_memory",
                        arguments={
                            "source_message_id": str(source.id),
                            "preference": source.content,
                        },
                    )
                ]
            ),
            ManagerModelUnavailableError("test unavailable"),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=4,
        max_tool_calls=3,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content=source.content,
        history=[],
        memories=[],
        source="uploaded_catalog",
        current_message_id=source.id,
        save_memory=AsyncMock(return_value=memory),
    )
    assert source.content in result.content
    assert "model stopped" in result.content
