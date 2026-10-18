"""Product selection and comparisons use current scoped facts, not generated prices."""

import json
from typing import Literal
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from tests.shopper_review import supported_review_session

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
    CatalogVariant,
    PublishedCatalog,
)
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.money import Money
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
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.search.agent_tools import CatalogSearchTool, CatalogSearchToolInput
from open_commerce.search.models import ProductFilters
from open_commerce.shopper_agent.model_agent import ShopperConversationalAgent
from open_commerce.shopper_agent.models import ShopperMessage
from open_commerce.shopper_agent.product_tools import (
    CARD_SELECTION_NOTICE,
    COMPARE_PRODUCTS,
    LOOKUP_PRODUCTS,
    PRODUCT_TOOLS,
    SELECT_PRODUCTS,
    ProductToolError,
    ShopperProductTools,
    product_card,
)


def product(key: str, price: int = 1999, *, currency: str = "USD") -> CatalogBrowseProduct:
    money = Money(amount_minor=price, currency=currency)
    return CatalogBrowseProduct(
        product_id=key,
        title=f"Travel mug {key}",
        description="Stainless steel. Contact person@example.com for help.",
        brand="Sample",
        category="Home",
        image_url=None,
        variant_id=f"{key}-small",
        price=money,
        availability="available",
        provenance=None,
        variants=[
            CatalogVariant(
                id=f"{key}-small",
                title="Small",
                options={"size": "small"},
                price=money,
                available=True,
                availability="available",
            )
        ],
    )


class FakeReader:
    def __init__(self, products: list[CatalogBrowseProduct]) -> None:
        self.products = products
        self.queries: list[CatalogBrowseQuery] = []
        self.tenant_ids: list[UUID] = []
        self.published = True

    async def browse(self, *, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        self.queries.append(query)
        self.tenant_ids.append(tenant_id)
        items = [
            item
            for item in self.products
            if (not query.product_id or item.product_id == query.product_id)
            and (not query.q or query.q.casefold() in item.title.casefold())
        ]
        return CatalogBrowseResponse(
            catalog=PublishedCatalog(
                id=UUID(int=20),
                filename="private-source.csv",
                source_version="test",
                product_count=len(self.products),
                published_at=None,
            )
            if self.published
            else None,
            indexing=CatalogIndexStatus(),
            categories=[],
            items=items[: query.limit],
            total=len(items),
            offset=0,
            limit=query.limit,
        )


class FakeSearch(CatalogSearchTool):
    def __init__(self, products: list[CatalogBrowseProduct]) -> None:
        super().__init__(None)
        self.products = products

    async def run(
        self,
        *,
        tenant_id: UUID,
        arguments: CatalogSearchToolInput,
        source: Literal["uploaded_catalog", "simulator_fallback"],
    ) -> JsonObject:
        return {
            "ok": True,
            "result_count": len(self.products),
            "results": [product_card(item).model_dump(mode="json") for item in self.products],
        }


class FakeSession:
    def __init__(self, turns: list[ManagerModelTurn | ManagerModelUnavailableError]) -> None:
        self.turns = turns
        self.results: list[list[ManagerToolResult]] = []

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.results.append(tool_results)
        item = self.turns.pop(0)
        if isinstance(item, ManagerModelUnavailableError):
            raise item
        return item


class FakeProvider:
    provider_name = "test"
    model_id = "test"

    def __init__(self, turns: list[ManagerModelTurn | ManagerModelUnavailableError]) -> None:
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
        review = supported_review_session(messages, tools)
        if review is not None:
            return review
        self.messages = messages
        return self.session


def call(name: str, arguments: JsonObject) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[ManagerToolCall(call_id=name, name=name, arguments=arguments)]
    )


async def test_lookup_decomposes_named_products_and_bounds_untrusted_context() -> None:
    reader = FakeReader([product("a"), product("b")])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    result = await tools.execute(LOOKUP_PRODUCTS.name, {"queries": ["mug a", "mug b"]})
    assert [query.q for query in reader.queries] == ["mug a", "mug b"]
    assert set(reader.tenant_ids) == {UUID(int=1)}
    assert set(tools.observed) == {"a", "b"}
    assert tools.selected == []
    assert "person@example.com" not in str(result)
    assert "private-source.csv" not in str(result)
    assert "Stainless steel" in str(result)
    assert "variants_truncated" in str(result)
    assert result["card_selection"] == CARD_SELECTION_NOTICE


async def test_noncontiguous_product_name_uses_bounded_disclosed_candidate_lookup() -> None:
    item = product("eastlake")
    item.title = "Example Eastlake Coolers Glass Drinkware Set, 15-Ounce, Set of 6"
    reader = FakeReader([item])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    result = await tools.execute(LOOKUP_PRODUCTS.name, {"queries": ["Eastlake 15-Ounce Set of 6"]})
    assert len(reader.queries) == 3
    groups = result["groups"]
    assert isinstance(groups, list)
    assert groups[0]["broadened_name_lookup"] is True
    assert groups[0]["matched_query"] == "Eastlake"
    assert groups[0]["products"][0]["title"] == item.title
    assert not tools.selected


async def test_cards_must_be_selected_and_are_refreshed_from_authoritative_data() -> None:
    reader = FakeReader([product("a", 1234), product("b", 4321)])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    tools.observe([product_card(product("a", 9999)), product_card(product("b", 9999))])
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["b"]})
    assert [(item.product_id, item.price_minor) for item in tools.selected] == [("b", 4321)]
    with pytest.raises(ProductToolError, match="PRODUCT_NOT_OBSERVED"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["made-up"]})
    assert tools.selected == []


async def test_selection_provides_only_selected_current_redacted_description() -> None:
    first = product("a")
    first.description = "Unselected product details."
    selected = product("b")
    selected.description = "Hand wash only. Contact person@example.com. " + "x" * 1100
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=FakeReader([first, selected]))
    tools.observe([product_card(first), product_card(selected)])
    result = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["b"]})
    facts = result["selected_products"]
    assert isinstance(facts, list) and len(facts) == 1
    assert facts[0]["product_id"] == "b"
    assert facts[0]["catalog_description"].startswith("Hand wash only.")
    assert len(facts[0]["catalog_description"]) == 1000
    assert "person@example.com" not in json.dumps(result)
    assert "Unselected product details" not in json.dumps(result)
    notice = result["notice"]
    assert isinstance(notice, str) and "untrusted product claims" in notice
    selected.description = "Updated care: dishwasher safe."
    refreshed = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["b"]})
    refreshed_facts = refreshed["selected_products"]
    assert isinstance(refreshed_facts, list)
    assert refreshed_facts[0]["catalog_description"] == selected.description


@pytest.mark.parametrize("with_reader", [True, False])
async def test_selection_does_not_invent_missing_description(with_reader: bool) -> None:
    item = product("a")
    item.description = ""
    tools = ShopperProductTools(
        tenant_id=UUID(int=1), reader=FakeReader([item]) if with_reader else None
    )
    tools.observe([product_card(item)])
    result = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    facts = result["selected_products"]
    assert isinstance(facts, list)
    assert facts[0]["catalog_description"] is None
    if not with_reader:
        assert facts[0]["available"] is None
        assert facts[0]["availability"] == "unknown"
        assert facts[0]["options"] == {}


async def test_selection_review_evidence_has_current_variant_options_and_stock() -> None:
    item = product("a")
    item.brand = "Synthetic Brand"
    item.category = "Home"
    item.variants[0].options = {"size": "small", "note": "Contact person@example.com"}
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=FakeReader([item]))
    tools.observe([product_card(item)])
    first = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    facts = first["selected_products"]
    assert isinstance(facts, list)
    assert facts[0]["variant_id"] == item.variants[0].id
    assert facts[0]["brand"] == "Synthetic Brand"
    assert facts[0]["category"] == "Home"
    assert facts[0]["options"]["size"] == "small"
    assert "person@example.com" not in json.dumps(facts)
    assert facts[0]["available"] is True
    assert facts[0]["availability"] == "available"
    item.variants[0].available = False
    item.variants[0].availability = "out_of_stock"
    item.variants[0].options["size"] = "large"
    second = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    refreshed = second["selected_products"]
    assert isinstance(refreshed, list)
    assert refreshed[0]["available"] is False
    assert refreshed[0]["availability"] == "out_of_stock"
    assert refreshed[0]["options"]["size"] == "large"


async def test_disappeared_or_unpublished_product_is_not_presented() -> None:
    reader = FakeReader([])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    tools.observe([product_card(product("a"))])
    with pytest.raises(ProductToolError, match="PRODUCT_NOT_IN_CURRENT_CATALOG"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    reader.published = False
    with pytest.raises(ProductToolError, match="CATALOG_NOT_PUBLISHED"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert tools.selected == []


async def test_comparison_is_exact_and_reports_ties_without_rounding() -> None:
    reader = FakeReader([product("a", 100000000000001), product("b", 100000000000002)])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    tools.observe([product_card(item) for item in reader.products])
    args: JsonObject = {"items": [{"product_id": "b"}, {"product_id": "a"}]}
    comparison = await tools.execute(COMPARE_PRODUCTS.name, args)
    assert comparison["price_spread_minor"] == 1
    items = comparison["items"]
    assert isinstance(items, list)
    assert items[0]["difference_from_lowest_minor"] == 1
    assert items[0]["lowest_price"] is False
    assert items[1]["lowest_price"] is True
    reader.products[1].variants[0].price = reader.products[0].price
    tied = await tools.execute(COMPARE_PRODUCTS.name, args)
    assert tied["price_spread_minor"] == 0
    tied_items = tied["items"]
    assert isinstance(tied_items, list)
    assert all(item["lowest_price"] for item in tied_items)


async def test_multiple_variants_require_a_real_variant_and_retain_availability() -> None:
    first = product("a")
    first.variants.append(
        CatalogVariant(
            id="a-large",
            title="Large",
            options={"size": "large"},
            price=Money(amount_minor=2999, currency="USD"),
            available=False,
        )
    )
    reader = FakeReader([first, product("b", 2499)])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    tools.observe([product_card(item) for item in reader.products])
    with pytest.raises(ProductToolError, match="EXPLICIT_VARIANT_REQUIRED"):
        await tools.execute(
            COMPARE_PRODUCTS.name, {"items": [{"product_id": "a"}, {"product_id": "b"}]}
        )
    with pytest.raises(ProductToolError, match="VARIANT_NOT_IN_PRODUCT"):
        await tools.execute(
            COMPARE_PRODUCTS.name,
            {"items": [{"product_id": "a", "variant_id": "a-invented"}, {"product_id": "b"}]},
        )
    result = await tools.execute(
        COMPARE_PRODUCTS.name,
        {"items": [{"product_id": "a", "variant_id": "a-large"}, {"product_id": "b"}]},
    )
    assert result["price_spread_minor"] == 500
    items = result["items"]
    assert isinstance(items, list)
    assert items[0]["available"] is False
    assert items[1]["lowest_price"] is True


async def test_comparison_rejects_different_currencies_and_unobserved_ids() -> None:
    reader = FakeReader([product("a"), product("b", currency="EUR")])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    args: JsonObject = {"items": [{"product_id": "a"}, {"product_id": "b"}]}
    with pytest.raises(ProductToolError, match="PRODUCT_NOT_OBSERVED"):
        await tools.execute(COMPARE_PRODUCTS.name, args)
    tools.observe([product_card(item) for item in reader.products])
    with pytest.raises(ProductToolError, match="CURRENCY_MISMATCH"):
        await tools.execute(COMPARE_PRODUCTS.name, args)


@pytest.mark.parametrize("name", [tool.name for tool in PRODUCT_TOOLS])
async def test_tools_reject_model_supplied_authority(name: str) -> None:
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=FakeReader([]))
    with pytest.raises(ValidationError):
        await tools.execute(name, {"tenant_id": str(UUID(int=2)), "catalog_id": str(UUID(int=3))})


@pytest.mark.parametrize("selection", [None, [], ["b"]])
async def test_model_returns_only_explicitly_selected_cards(selection: list[str] | None) -> None:
    reader = FakeReader([product("a"), product("b")])
    turns: list[ManagerModelTurn | ManagerModelUnavailableError] = [
        call("catalog_search", {"query": "Travel mugs"})
    ]
    if selection is not None:
        turns.append(call(SELECT_PRODUCTS.name, {"product_ids": selection}))
    turns.append(
        call(
            "complete_shopping_turn",
            {"kind": "catalog", "message": "Here is my answer.", "product_ids": selection or []},
        )
    )
    if selection is None:
        turns.append(ManagerModelUnavailableError("No further scripted work"))
    provider = FakeProvider(turns)
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch(reader.products),
        catalog_reader=reader,
        max_iterations=6,
        max_tool_calls=5,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Find a mug",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert [item.product_id for item in result.products] == (selection or [])
    assert (result.steps[-1].status == "fallback") is (selection is None)


@pytest.mark.parametrize("commentary_first", [False, True])
async def test_lookup_compare_selection_loop_and_followup_product_references(
    commentary_first: bool,
) -> None:
    reader = FakeReader([product("a", 2100), product("b", 2000)])
    provider = FakeProvider(
        [
            *(
                [ManagerModelTurn(content="I will compare them", phase="commentary")]
                if commentary_first
                else []
            ),
            call(LOOKUP_PRODUCTS.name, {"queries": ["mug a", "mug b"]}),
            call(COMPARE_PRODUCTS.name, {"items": [{"product_id": "a"}, {"product_id": "b"}]}),
            call(SELECT_PRODUCTS.name, {"product_ids": ["b"]}),
            call(
                "complete_shopping_turn",
                {
                    "kind": "price_comparison",
                    "message": "Mug b costs USD 1.00 less for the small variants.",
                    "product_ids": ["b"],
                },
            ),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch([]),
        catalog_reader=reader,
        max_iterations=6,
        max_tool_calls=5,
        max_output_tokens=800,
    )
    history = [
        ShopperMessage(
            id=UUID(int=4),
            conversation_id=UUID(int=5),
            role="assistant",
            content="Previous options",
            products=[product_card(product("a", 1))],
            created_at=utc_now(),
        )
    ]
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Compare it with mug b",
        history=history,
        memories=[],
        source="uploaded_catalog",
    )
    assert "product IDs" in provider.messages[0].content
    assert '"a"' in provider.messages[0].content
    assert "price_minor" not in provider.messages[0].content
    assert result.products[0].product_id == "b"
    assert (
        provider.session.results[2 + int(commentary_first)][0].output["price_spread_minor"] == 100
    )
    assert (
        provider.session.results[2 + int(commentary_first)][0].output["card_selection"]
        == CARD_SELECTION_NOTICE
    )


async def test_followup_receives_selection_guidance_and_refreshes_its_own_card() -> None:
    reader = FakeReader([product("a", 2100)])
    provider = FakeProvider(
        [
            call(LOOKUP_PRODUCTS.name, {"product_ids": ["a"]}),
            call(SELECT_PRODUCTS.name, {"product_ids": ["a"]}),
            call(
                "complete_shopping_turn",
                {
                    "kind": "catalog",
                    "message": "The small variant is available. Nothing was added to cart.",
                    "product_ids": ["a"],
                },
            ),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch([]),
        catalog_reader=reader,
        max_iterations=6,
        max_tool_calls=5,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="What variant of that set is available? Do not add it to my cart.",
        history=[
            ShopperMessage(
                id=UUID(int=4),
                conversation_id=UUID(int=5),
                role="assistant",
                content="Here is that set.",
                products=[product_card(product("a", 1))],
                created_at=utc_now(),
            )
        ],
        memories=[],
        source="uploaded_catalog",
    )
    assert provider.session.results[1][0].output["card_selection"] == CARD_SELECTION_NOTICE
    assert [(item.product_id, item.price_minor) for item in result.products] == [("a", 2100)]
    assert all(query.product_id == "a" for query in reader.queries)
    assert set(reader.tenant_ids) == {UUID(int=1)}


async def test_failure_does_not_promote_unselected_hits_to_recommendations() -> None:
    reader = FakeReader([product("a")])
    provider = FakeProvider(
        [
            call("catalog_search", {"query": "mug"}),
            ManagerModelUnavailableError("unavailable"),
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch(reader.products),
        catalog_reader=reader,
        max_iterations=4,
        max_tool_calls=3,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Find a mug",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert not result.products
    assert "No new recommendations were confirmed" in result.content


async def test_new_search_clears_previous_selection() -> None:
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=FakeReader([product("a")]))
    tools.observe([product_card(product("a"))])
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert tools.selected
    tools.observe([])
    assert not tools.selected


async def test_selection_preserves_qualifying_variant_and_rejects_price_drift() -> None:
    item = product("mug", 10000)
    cheap = product("cheap", 2000).variants[0]
    item.variants.append(cheap)
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=FakeReader([item]))
    observed = product_card(item).model_copy(update={"price_minor": 2000})
    tools.observe([observed], ProductFilters(max_price_minor=2500, currency="USD", in_stock=True))
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["mug"]})
    assert tools.selected[0].price_minor == 2000
    cheap.price = Money(amount_minor=3000, currency="USD")
    with pytest.raises(ProductToolError, match="PRODUCT_NO_LONGER_MATCHES_CONSTRAINTS"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["mug"]})
    assert not tools.selected


@pytest.mark.parametrize(
    "retraction",
    [
        call(SELECT_PRODUCTS.name, {"product_ids": []}),
        call("catalog_search", {"query": "something else"}),
    ],
)
async def test_tool_limit_discards_superseded_selection(retraction: ManagerModelTurn) -> None:
    reader = FakeReader([product("a")])
    provider = FakeProvider(
        [
            call("catalog_search", {"query": "mug"}),
            call(SELECT_PRODUCTS.name, {"product_ids": ["a"]}),
            retraction,
        ]
    )
    agent = ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch(reader.products),
        catalog_reader=reader,
        max_iterations=4,
        max_tool_calls=2,
        max_output_tokens=800,
    )
    result = await agent.respond(
        tenant_id=UUID(int=1),
        content="Find a mug",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert result.products == []
    assert "No new recommendations were confirmed" in result.content


@pytest.mark.parametrize("sensitive", ["person@example.com", "sk-synthetic01234567890123456789"])
async def test_sensitive_source_ids_never_enter_lookup_comparison_or_provider(
    sensitive: str,
) -> None:
    first = product("safe")
    first.variants[0].id = sensitive
    first.variants.append(product("safe-option").variants[0])
    reader = FakeReader([product(sensitive), first, product("other")])
    tools = ShopperProductTools(tenant_id=UUID(int=1), reader=reader)
    observation = await tools.execute(LOOKUP_PRODUCTS.name, {"queries": ["Travel"]})
    assert sensitive not in json.dumps(observation)
    assert sensitive not in tools.observed
    groups = observation["groups"]
    assert isinstance(groups, list)
    assert groups[0]["products"][0]["variants_withheld"] is True
    with pytest.raises(ProductToolError, match="VARIANT_IDENTIFIER_NOT_MODEL_SAFE"):
        await tools.execute(
            COMPARE_PRODUCTS.name,
            {"items": [{"product_id": "safe", "variant_id": sensitive}, {"product_id": "other"}]},
        )
    with pytest.raises(ProductToolError, match="PRODUCT_NOT_OBSERVED"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": [sensitive]})
    # Start an ordinary catalog selection after the rejected comparison.
    await tools.execute(LOOKUP_PRODUCTS.name, {"product_ids": ["safe"]})
    selected = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["safe"]})
    assert sensitive not in json.dumps(selected)

    def handler(request: httpx.Request) -> httpx.Response:
        assert sensitive not in request.content.decode()
        return httpx.Response(200, json={"status": "completed", "output": []})

    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"), model_id="test", transport=httpx.MockTransport(handler)
    )
    session = provider.begin(
        instructions="Test", messages=[], tools=PRODUCT_TOOLS, max_output_tokens=400
    )
    await session.next(
        [
            ManagerToolResult(call_id="lookup", name=LOOKUP_PRODUCTS.name, output=observation),
            ManagerToolResult(call_id="select", name=SELECT_PRODUCTS.name, output=selected),
        ]
    )
