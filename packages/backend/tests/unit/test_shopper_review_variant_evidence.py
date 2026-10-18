"""Fresh selection evidence reaches review; no model judgment is exercised."""

import json
from typing import cast
from uuid import UUID

from test_shopper_product_tools import FakeReader, product

from open_commerce.core.types import JsonObject
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.shopper_agent.answer_review import review_catalog_answer
from open_commerce.shopper_agent.completion import CompleteShoppingTurn
from open_commerce.shopper_agent.product_tools import (
    LOOKUP_PRODUCTS,
    SELECT_PRODUCTS,
    ShopperProductTools,
)


class CaptureReviewInput:
    provider_name = "offline-capture"
    model_id = "no-model"

    def __init__(self) -> None:
        self.documents: list[JsonObject] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        document = "".join(message.content.split("\n", 1)[1] for message in messages)
        self.documents.append(cast(JsonObject, json.loads(document)))
        raise ManagerModelUnavailableError("Captured review input without making a model request")


def variant_ids(facts: JsonObject) -> list[str]:
    variants = cast(list[JsonObject], facts["variants"])
    return [str(variant["variant_id"]) for variant in variants]


async def test_separate_lookups_review_fresh_variants_and_refresh_removed_option() -> None:
    first = product("a")
    first.variants.append(
        first.variants[0].model_copy(
            deep=True,
            update={"id": "a-large", "title": "Large", "options": {"size": "large"}},
        )
    )
    reader = FakeReader([first, product("b")])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    receipts = [
        ManagerToolResult(
            call_id=f"lookup-{key}",
            name=LOOKUP_PRODUCTS.name,
            output=await tools.execute(LOOKUP_PRODUCTS.name, {"product_ids": [key]}),
        )
        for key in ("a", "b")
    ]
    groups = cast(list[JsonObject], receipts[0].output["groups"])
    original_a = cast(list[JsonObject], groups[0]["products"])[0]
    assert variant_ids(original_a) == ["a-small", "a-large"]
    provider = CaptureReviewInput()
    reply = CompleteShoppingTurn(
        kind="catalog", message="Here are the requested mugs.", product_ids=["a", "b"]
    )

    for expected_variants in (["a-small", "a-large"], ["a-small"]):
        reader.queries.clear()
        selection = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a", "b"]})
        assert [query.product_id for query in reader.queries] == ["a", "b"]
        receipts.append(
            ManagerToolResult(
                call_id=f"select-{len(receipts)}", name=SELECT_PRODUCTS.name, output=selection
            )
        )
        review = await review_catalog_answer(
            provider=provider,
            reply=reply,
            messages=[
                ManagerModelMessage(role="user", content="Show A and B and their available sizes.")
            ],
            preferences=[],
            receipts=receipts,
            max_output_tokens=500,
        )
        assert review.status == "unavailable"
        evidence = cast(list[JsonObject], provider.documents[-1]["catalog_evidence"])
        lookup = next(item for item in evidence if item["tool"] == LOOKUP_PRODUCTS.name)
        assert lookup["output"] == receipts[1].output
        selected = next(item for item in evidence if item["tool"] == SELECT_PRODUCTS.name)
        selected_output = cast(JsonObject, selected["output"])
        cards = cast(list[JsonObject], selected_output["selected_products"])
        assert [card["product_id"] for card in cards] == ["a", "b"]
        assert variant_ids(cards[0]) == expected_variants
        assert variant_ids(cards[1]) == ["b-small"]
        assert cards[0]["variants_truncated"] is False
        assert cards[0]["variants_withheld"] is False
        assert cards[0]["options"] == {"size": "small"}
        assert cards[0]["available"] is True
        assert cards[0]["brand"] == "Sample"
        assert cards[0]["category"] == "Home"
        first.variants = first.variants[:1]

    # Old receipts remain unchanged; only the authoritative selection snapshot refreshes.
    assert variant_ids(original_a) == ["a-small", "a-large"]
    assert provider.documents[0]["candidate_id"] != provider.documents[1]["candidate_id"]
