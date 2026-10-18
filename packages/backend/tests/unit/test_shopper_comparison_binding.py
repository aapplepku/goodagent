"""Offline comparison snapshots bind final cards to freshly rechecked variants."""

from uuid import UUID

import pytest
from pydantic import ValidationError
from test_shopper_completion import finish, receipt
from test_shopper_product_tools import FakeProvider, FakeReader, FakeSearch, call, product

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
)
from open_commerce.core.money import Money
from open_commerce.core.types import JsonObject
from open_commerce.search.agent_tools import CatalogSearchTool
from open_commerce.search.models import ProductFilters
from open_commerce.shopper_agent.completion import CompleteShoppingTurn, completion_error
from open_commerce.shopper_agent.model_agent import ShopperConversationalAgent
from open_commerce.shopper_agent.product_tools import (
    COMPARE_PRODUCTS,
    LOOKUP_PRODUCTS,
    SELECT_PRODUCTS,
    ProductToolError,
    ShopperProductTools,
    product_card,
)

TENANT = UUID(int=123)
PAIR: JsonObject = {"items": [{"product_id": "a"}, {"product_id": "b"}]}


def setup_tools(
    products: list[CatalogBrowseProduct] | None = None,
    filters: ProductFilters | None = None,
) -> tuple[ShopperProductTools, FakeReader]:
    reader = FakeReader(
        products if products is not None else [product("a", 1000), product("b", 2000)]
    )
    tools = ShopperProductTools(tenant_id=TENANT, reader=reader)
    tools.observe([product_card(item) for item in reader.products], filters)
    return tools, reader


def multivariant_product() -> CatalogBrowseProduct:
    item = product("a", 1000)
    item.variants.append(
        item.variants[0].model_copy(
            update={
                "id": "a-large",
                "title": "Large",
                "price": Money(amount_minor=3000, currency="USD"),
            }
        )
    )
    return item


async def test_implicit_and_explicit_same_resolved_variant_are_duplicates() -> None:
    tools, _ = setup_tools()
    with pytest.raises(ProductToolError, match="DUPLICATE_COMPARISON_ITEM"):
        await tools.execute(
            COMPARE_PRODUCTS.name,
            {"items": [{"product_id": "a"}, {"product_id": "a", "variant_id": "a-small"}]},
        )
    assert not tools.selected


async def test_card_uses_compared_variant_not_observed_representative() -> None:
    tools, reader = setup_tools([multivariant_product(), product("b", 2000)])
    comparison = await tools.execute(
        COMPARE_PRODUCTS.name,
        {"items": [{"product_id": "a", "variant_id": "a-large"}, {"product_id": "b"}]},
    )
    reader.queries.clear()
    selection = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert [(card.product_id, card.price_minor, card.currency) for card in tools.selected] == [
        ("a", 3000, "USD")
    ]
    selected = selection["selected_products"]
    assert isinstance(selected, list)
    assert selected[0]["variant_id"] == "a-large"
    assert selected[0]["variant_title"] == "Large"
    assert [query.product_id for query in reader.queries] == ["a", "b"]
    assert set(reader.tenant_ids) == {TENANT}
    assert (
        completion_error(
            CompleteShoppingTurn(kind="price_comparison", message="Compared.", product_ids=["a"]),
            [
                receipt(LOOKUP_PRODUCTS.name),
                receipt(COMPARE_PRODUCTS.name, output=comparison),
                receipt(SELECT_PRODUCTS.name, output=selection),
            ],
        )
        is None
    )


async def test_same_product_distinct_variants_keep_one_card_and_deduplicate_reads() -> None:
    tools, reader = setup_tools([multivariant_product()])
    comparison = await tools.execute(
        COMPARE_PRODUCTS.name,
        {
            "items": [
                {"product_id": "a", "variant_id": "a-small"},
                {"product_id": "a", "variant_id": "a-large"},
            ]
        },
    )
    assert comparison["price_spread_minor"] == 2000
    assert [query.product_id for query in reader.queries] == ["a"]
    selection = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert [query.product_id for query in reader.queries] == ["a", "a"]
    assert len(tools.selected) == 1
    assert tools.selected[0].price_minor == 1000
    selected = selection["selected_products"]
    assert isinstance(selected, list) and selected[0]["variant_id"] == "a-small"
    assert "one card per product" in str(selection["notice"]).lower()


@pytest.mark.parametrize("changed_key", ["a", "b"])
@pytest.mark.parametrize(
    "change",
    [
        "price",
        "currency",
        "product_missing",
        "variant_missing",
        "unsafe_id",
        "blank_id",
        "duplicate_variant",
        "negative_price",
        "boolean_price",
        "bad_currency",
    ],
)
async def test_selection_rechecks_selected_and_unselected_comparison_facts(
    changed_key: str,
    change: str,
) -> None:
    tools, reader = setup_tools()
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    original = [item.model_copy(deep=True) for item in reader.products]
    changed = next(item for item in reader.products if item.product_id == changed_key)
    variant = changed.variants[0]
    if change == "price":
        variant.price = Money(amount_minor=4000, currency="USD")
    elif change == "currency":
        variant.price = Money(amount_minor=variant.price.amount_minor, currency="EUR")
    elif change == "product_missing":
        reader.products.remove(changed)
    elif change == "variant_missing":
        changed.variants = []
    elif change in {"unsafe_id", "blank_id"}:
        variant.id = "person@example.com" if change == "unsafe_id" else "  "
    elif change == "duplicate_variant":
        changed.variants.append(variant.model_copy(deep=True))
    else:
        variant.price = variant.price.model_copy(
            update={"currency": "U$D"}
            if change == "bad_currency"
            else {"amount_minor": -1 if change == "negative_price" else True}
        )
    with pytest.raises(ProductToolError, match="COMPARISON_REQUIRES_REFRESH"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert not tools.selected
    # Restoring data must not revive the invalidated comparison without a new compare.
    reader.products = original
    with pytest.raises(ProductToolError, match="COMPARISON_REQUIRES_REFRESH"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert tools.selected[0].price_minor == 1000


@pytest.mark.parametrize("failure", ["unpublished", "reader_missing", "unavailable"])
async def test_failed_comparison_revalidation_requires_a_new_compare(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools, reader = setup_tools()
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    if failure == "unpublished":
        reader.published = False
    elif failure == "reader_missing":
        tools.reader = None
    else:

        async def unavailable(*, tenant_id: UUID, query: CatalogBrowseQuery) -> None:
            raise RuntimeError("private backend failure")

        monkeypatch.setattr(reader, "browse", unavailable)
    with pytest.raises(ProductToolError, match="COMPARISON_REQUIRES_REFRESH"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert not tools.selected
    assert (await tools.execute(SELECT_PRODUCTS.name, {"product_ids": []}))["ok"] is True


@pytest.mark.parametrize("malformed", [False, True])
async def test_new_failed_comparison_cannot_reuse_last_success(malformed: bool) -> None:
    tools, _ = setup_tools()
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    with pytest.raises((ProductToolError, ValidationError)):
        await tools.execute(
            COMPARE_PRODUCTS.name,
            {"items": []}
            if malformed
            else {"items": [{"product_id": "a", "variant_id": "missing"}, {"product_id": "b"}]},
        )
    with pytest.raises(ProductToolError, match="COMPARISON_REQUIRES_REFRESH"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})


@pytest.mark.parametrize("reset", ["observe", "lookup", "failed_lookup", "search_attempt_hook"])
async def test_new_catalog_read_clears_comparison_binding(reset: str) -> None:
    tools, reader = setup_tools([product("a", 1000), product("b", 2000), product("c", 1500)])
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    if reset == "observe":
        tools.observe([product_card(item) for item in reader.products])
    elif reset == "lookup":
        await tools.execute(LOOKUP_PRODUCTS.name, {"product_ids": ["c"]})
    elif reset == "search_attempt_hook":
        tools.invalidate_comparison()
    else:
        with pytest.raises(ValidationError):
            await tools.execute(LOOKUP_PRODUCTS.name, {})
    reader.products[0].variants[0].price = Money(amount_minor=5000, currency="USD")
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["c", "a"]})
    assert [(item.product_id, item.price_minor) for item in tools.selected] == [
        ("c", 1500),
        ("a", 5000),
    ]


async def test_active_comparison_rejects_unrelated_cards_but_allows_reselection() -> None:
    tools, _ = setup_tools([product("a"), product("b"), product("c")])
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    with pytest.raises(ProductToolError, match="PRODUCT_NOT_COMPARED"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["c"]})
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["b", "a"]})
    assert [card.product_id for card in tools.selected] == ["b", "a"]


async def test_selection_never_substitutes_uncompared_variant_to_satisfy_filters() -> None:
    tools, _ = setup_tools(
        [multivariant_product(), product("b", 2000)],
        ProductFilters(max_price_minor=2500, in_stock=True, currency="USD"),
    )
    await tools.execute(
        COMPARE_PRODUCTS.name,
        {"items": [{"product_id": "a", "variant_id": "a-large"}, {"product_id": "b"}]},
    )
    with pytest.raises(ProductToolError, match="PRODUCT_NO_LONGER_MATCHES_CONSTRAINTS"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["b"]})
    assert [card.product_id for card in tools.selected] == ["b"]


async def test_empty_selection_can_retract_cards_even_when_compared_facts_disappear() -> None:
    tools, reader = setup_tools()
    await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    reader.products = []
    reader.queries.clear()
    assert (await tools.execute(SELECT_PRODUCTS.name, {"product_ids": []}))[
        "selected_products"
    ] == []
    assert not reader.queries
    assert not tools.selected


@pytest.mark.parametrize("unsafe", [None, -1, True, "1000", "U$D", "usd", "\u00c9UR"])
async def test_comparison_rejects_unsafe_price_facts_before_publishing(unsafe: object) -> None:
    tools, reader = setup_tools()
    variant = reader.products[1].variants[0]
    variant.price = variant.price.model_copy(
        update={"currency": unsafe}
        if isinstance(unsafe, str) and unsafe != "1000"
        else {"amount_minor": unsafe}
    )
    with pytest.raises(ProductToolError, match="INVALID_COMPARISON_PRICE"):
        await tools.execute(COMPARE_PRODUCTS.name, PAIR)
    with pytest.raises(ProductToolError, match="COMPARISON_REQUIRES_REFRESH"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})


async def test_same_product_comparison_selects_only_qualifying_compared_variant() -> None:
    item = multivariant_product()
    tools, _ = setup_tools([item], ProductFilters(in_stock=True))
    await tools.execute(
        COMPARE_PRODUCTS.name,
        {
            "items": [
                {"product_id": "a", "variant_id": "a-small"},
                {"product_id": "a", "variant_id": "a-large"},
            ]
        },
    )
    item.variants[0].available = False
    selection = await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert tools.selected[0].price_minor == 3000
    selected = selection["selected_products"]
    assert isinstance(selected, list) and selected[0]["variant_id"] == "a-large"
    item.variants[1].available = False
    with pytest.raises(ProductToolError, match="PRODUCT_NO_LONGER_MATCHES_CONSTRAINTS"):
        await tools.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert not tools.selected


async def test_comparison_state_does_not_cross_turns() -> None:
    first, reader = setup_tools([multivariant_product(), product("b", 2000)])
    await first.execute(
        COMPARE_PRODUCTS.name,
        {"items": [{"product_id": "a", "variant_id": "a-large"}, {"product_id": "b"}]},
    )
    second = ShopperProductTools(tenant_id=TENANT, reader=reader)
    second.observe([product_card(item) for item in reader.products])
    await second.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    await first.execute(SELECT_PRODUCTS.name, {"product_ids": ["a"]})
    assert second.selected[0].price_minor == 1000
    assert first.selected[0].price_minor == 3000


async def test_scripted_loop_recompares_after_unselected_counterpart_drift() -> None:
    class DriftingReader(FakeReader):
        async def browse(
            self,
            *,
            tenant_id: UUID,
            query: CatalogBrowseQuery,
        ) -> CatalogBrowseResponse:
            if query.product_id == "b" and sum(q.product_id == "b" for q in self.queries) == 2:
                self.products[1].variants[0].price = Money(amount_minor=500, currency="USD")
            return await super().browse(tenant_id=tenant_id, query=query)

    reader = DriftingReader([product("a", 1000), product("b", 2000)])
    answer = "The refreshed comparison shows b's small variant at USD 5.00."
    provider = FakeProvider(
        [
            call(LOOKUP_PRODUCTS.name, {"product_ids": ["a", "b"]}),
            call(COMPARE_PRODUCTS.name, PAIR),
            call(SELECT_PRODUCTS.name, {"product_ids": ["a"]}),
            finish("Do not accept this stale completion.", "price_comparison", product_ids=["a"]),
            call(COMPARE_PRODUCTS.name, PAIR),
            call(SELECT_PRODUCTS.name, {"product_ids": ["b"]}),
            finish(answer, "price_comparison", product_ids=["b"]),
        ]
    )
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=FakeSearch([]),
        catalog_reader=reader,
        max_iterations=8,  # Seven repair decisions plus a scripted answer review.
        max_tool_calls=5,
        max_output_tokens=800,
    ).respond(
        tenant_id=TENANT,
        content="Compare a and b and show the cheaper option.",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    errors = [entry for batch in provider.session.results for entry in batch if entry.is_error]
    assert [entry.output["error"] for entry in errors] == [
        "COMPARISON_REQUIRES_REFRESH",
        "INCOMPLETE_SHOPPING_TURN",
    ]
    assert result.content == answer
    assert [(card.product_id, card.price_minor) for card in result.products] == [("b", 500)]
    assert result.steps[-1].status == "completed"
    assert set(reader.tenant_ids) == {TENANT}


@pytest.mark.parametrize("failure", ["invalid", "unavailable", "search_limit", "tool_budget"])
async def test_loop_invalidates_comparison_before_rejected_search_attempt(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalidated_active_comparisons: list[bool] = []
    invalidate = ShopperProductTools.invalidate_comparison

    def record_invalidation(tools: ShopperProductTools) -> None:
        # The budget path exits immediately, so also check invalidation at admission.
        if tools._comparison is not None:
            invalidated_active_comparisons.append(True)
        invalidate(tools)

    monkeypatch.setattr(ShopperProductTools, "invalidate_comparison", record_invalidation)
    reader = FakeReader([multivariant_product(), product("b", 2000)])
    turns = [
        *([call("catalog_search", {})] * 3 if failure == "search_limit" else []),
        call(LOOKUP_PRODUCTS.name, {"product_ids": ["a", "b"]}),
        call(
            COMPARE_PRODUCTS.name,
            {"items": [{"product_id": "a", "variant_id": "a-large"}, {"product_id": "b"}]},
        ),
        call("catalog_search", {} if failure == "invalid" else {"query": "mug"}),
    ]
    answer = "Here is product a without a completed comparison."
    if failure != "tool_budget":
        turns.extend(
            [
                call(SELECT_PRODUCTS.name, {"product_ids": ["a"]}),
                finish(
                    "Do not accept stale comparison evidence.",
                    "price_comparison",
                    product_ids=["a"],
                ),
                finish(answer, "catalog", product_ids=["a"]),
            ]
        )
    provider = FakeProvider(list(turns))
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        catalog_reader=reader,
        max_iterations=len(turns) + 1,
        max_tool_calls=2 if failure == "tool_budget" else 8,
        max_output_tokens=800,
    ).respond(
        tenant_id=TENANT,
        content="Compare mugs, then look for another option.",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert invalidated_active_comparisons == [True]
    if failure == "tool_budget":
        assert result.products == []
        assert result.steps[-1].status == "fallback"
    else:
        errors = [
            entry.output["error"]
            for batch in provider.session.results
            for entry in batch
            if entry.is_error
        ]
        expected = {
            "invalid": ["INVALID_TOOL_ARGUMENTS"],
            "unavailable": ["SEARCH_RUNTIME_UNAVAILABLE"],
            "search_limit": ["INVALID_TOOL_ARGUMENTS"] * 3 + ["SEARCH_TURN_LIMIT"],
        }[failure]
        assert errors == [*expected, "INCOMPLETE_SHOPPING_TURN"]
        assert result.content == answer
        # Ordinary catalog selection must no longer inherit a-large's comparison price.
        assert [(card.product_id, card.price_minor) for card in result.products] == [("a", 1000)]
