"""Focused tests for shopper authentication primitives and grounded agent search."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from open_commerce.search.agent_tools import CatalogSearchTool, CatalogSearchToolInput
from open_commerce.shopper_agent.auth import hash_password, verify_password
from open_commerce.shopper_agent.model_agent import (
    ShopperConversationalAgent,
    explicit_memory,
    memory_only_message,
)
from open_commerce.shopper_agent.models import ShopperMessage


class FakeCatalogSearch(CatalogSearchTool):
    def __init__(self) -> None:
        super().__init__(None)

    async def run(
        self,
        *,
        tenant_id: UUID,
        arguments: CatalogSearchToolInput,
        source: Literal["uploaded_catalog", "simulator_fallback"],
    ) -> dict[str, object]:
        assert tenant_id == UUID(int=1)
        assert arguments.query == "snacks for a road trip"
        assert source == "uploaded_catalog"
        return {
            "ok": True,
            "query": arguments.query,
            "mode": arguments.mode,
            "result_count": 1,
            "results": [
                {
                    "product_id": "snack-1",
                    "title": "Trail Mix",
                    "brand": "Northstar",
                    "category": "Pantry > Snacks",
                    "price_minor": 699,
                    "currency": "USD",
                    "score": "0.91",
                    "highlights": ["road trip"],
                    "image_url": None,
                    "url": None,
                }
            ],
        }


async def test_passwords_are_salted_and_verified_without_plaintext() -> None:
    first = await hash_password("local-demo-password")
    second = await hash_password("local-demo-password")

    assert first != second
    assert "local-demo-password" not in first
    assert await verify_password("local-demo-password", first) is True
    assert await verify_password("wrong-password", first) is False


async def test_deterministic_shopper_agent_returns_only_observed_products() -> None:
    agent = ShopperConversationalAgent(
        catalog_search=FakeCatalogSearch(),
        provider=None,
        max_iterations=2,
        max_tool_calls=2,
        max_output_tokens=800,
    )

    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="snacks for a road trip",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )

    assert [item.product_id for item in result.products] == ["snack-1"]
    assert "Trail Mix" in result.content
    assert "USD 6.99\n\nTell me" in result.content
    assert any(step.stage == "search" for step in result.steps)


def test_shopper_prompt_requires_explicit_hard_filters() -> None:
    from open_commerce.shopper_agent.model_agent import SHOPPER_INSTRUCTIONS

    assert "include them only" in SHOPPER_INSTRUCTIONS
    assert "shopper explicitly requests" in SHOPPER_INSTRUCTIONS


def test_only_explicit_shopper_preferences_become_memory() -> None:
    assert explicit_memory("Remember that I avoid peanuts") == "I avoid peanuts"
    assert explicit_memory("I prefer unsweetened drinks") == "I prefer unsweetened drinks"
    assert explicit_memory("Show me unsweetened drinks") is None


def test_preference_followup_uses_the_shoppers_words_not_assistant_inferences() -> None:
    preference = "i like premium expensive stuff, keep that in mind"
    history = [
        ShopperMessage(
            id=UUID(int=1),
            conversation_id=UUID(int=3),
            role="user",
            content=preference,
            created_at=datetime.now(UTC),
        ),
        ShopperMessage(
            id=UUID(int=2),
            conversation_id=UUID(int=3),
            role="assistant",
            content="Remember that you prefer expensive home items",
            created_at=datetime.now(UTC),
        ),
    ]
    assert explicit_memory(preference) == "i like premium expensive stuff"
    assert explicit_memory("save that preference you should automatic save that", history) == (
        "i like premium expensive stuff"
    )
    assert explicit_memory("save that preference", history[1:]) is None
    assert explicit_memory("save that preference") is None
    assert explicit_memory("I like premium stuff, but do not save this") is None
    assert explicit_memory("I like premium stuff. Find a gift under $40") == "I like premium stuff"
    assert explicit_memory("I like premium stuff, find a gift") == "I like premium stuff"
    assert not memory_only_message("I like premium stuff. Find a gift under $40")
    assert memory_only_message(preference)
