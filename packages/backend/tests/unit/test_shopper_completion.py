"""Completion is an explicit model decision checked against actual turn receipts."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from tests.shopper_review import supported_review_session

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
)
from open_commerce.core.types import JsonObject
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.search.agent_tools import CatalogSearchTool
from open_commerce.shopper_agent.completion import (
    COMPLETE_SHOPPING_TURN,
    CompleteShoppingTurn,
    completion_error,
)
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome, ShopperConversationalAgent


def finish(
    message: str, kind: str = "conversation", *, product_ids: list[str] | None = None
) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[
            ManagerToolCall(
                call_id="finish",
                name="complete_shopping_turn",
                arguments={"kind": kind, "message": message, "product_ids": product_ids},
            )
        ]
    )


def receipt(
    name: str, *, failed: bool = False, output: JsonObject | None = None
) -> ManagerToolResult:
    return ManagerToolResult(
        call_id=name,
        name=name,
        output=output if output is not None else {"ok": not failed},
        is_error=failed,
    )


def comparison_receipt(*product_ids: str) -> ManagerToolResult:
    return receipt(
        "compare_catalog_prices",
        output={
            "ok": True,
            "currency": "USD",
            "items": [
                {
                    "product_id": product_id,
                    "title": f"Travel mug {product_id}",
                    "variant_id": f"{product_id}-size-{index}",
                    "variant_title": f"Size {index}",
                    "options": {"size": str(index)},
                    "price_minor": 2000 + index * 100,
                    "currency": "USD",
                    "available": True,
                    "availability": "available",
                    "difference_from_lowest_minor": index * 100,
                    "lowest_price": index == 0,
                }
                for index, product_id in enumerate(product_ids)
            ],
            "price_spread_minor": (len(product_ids) - 1) * 100,
            "basis": "Listed prices of these exact variants; availability is separate.",
        },
    )


def selection_receipt(*product_ids: str) -> ManagerToolResult:
    return receipt(
        "select_catalog_products",
        output={
            "ok": True,
            "selected_products": [
                {
                    "product_id": product_id,
                    "title": f"Travel mug {product_id}",
                    "price_minor": 2000,
                    "currency": "USD",
                    "catalog_description": "Stainless steel travel mug.",
                }
                for product_id in product_ids
            ],
            "notice": "Cards show a representative variant. Selection does not add to cart.",
        },
    )


@pytest.mark.parametrize("extra", [{"tenant_id": str(UUID(int=9))}, {"message": "   "}])
def test_completion_input_is_bounded_and_cannot_claim_authority(extra: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CompleteShoppingTurn.model_validate(
            {"kind": "conversation", "message": "Hello", "product_ids": None, **extra}
        )


def test_completion_schema_requires_nullable_final_card_declaration() -> None:
    schema = COMPLETE_SHOPPING_TURN.parameters
    required = schema["required"]
    properties = schema["properties"]
    assert isinstance(required, list) and "product_ids" in required
    assert isinstance(properties, dict)
    declaration = properties["product_ids"]
    assert "default" not in declaration
    assert {branch["type"] for branch in declaration["anyOf"]} == {"array", "null"}
    with pytest.raises(ValidationError) as error:
        CompleteShoppingTurn.model_validate({"kind": "conversation", "message": "Hello"})
    assert error.value.errors()[0]["loc"] == ("product_ids",)
    assert CompleteShoppingTurn(kind="conversation", message="Hello", product_ids=None)


@pytest.mark.parametrize(
    "product_ids",
    [
        "a",
        {},
        ("a",),
        [None],
        [1],
        [True],
        [{}],
        [["a"]],
        [""],
        ["  "],
        ["a", "a"],
        ["x" * 161],
        [str(index) for index in range(7)],
    ],
)
def test_completion_rejects_malformed_or_duplicate_declared_ids(product_ids: object) -> None:
    with pytest.raises(ValidationError):
        CompleteShoppingTurn.model_validate(
            {"kind": "catalog", "message": "Results", "product_ids": product_ids}
        )


@pytest.mark.parametrize(
    "kind", ["conversation", "clarification", "memory", "activity", "blocked", "refusal"]
)
@pytest.mark.parametrize("product_ids", [[], ["a"]])
def test_non_catalog_completion_requires_null_card_ids(kind: str, product_ids: list[str]) -> None:
    receipts = {
        "conversation": [],
        "clarification": [],
        "memory": [receipt("save_shopping_memory")],
        "activity": [receipt("inspect_shopping_activity")],
        "blocked": [receipt("catalog_search", failed=True)],
        "refusal": [],
    }[kind]
    reply = CompleteShoppingTurn.model_validate(
        {"kind": kind, "message": "Completed", "product_ids": product_ids}
    )
    assert (
        completion_error(reply, receipts) == "Use product_ids=null for noncatalog completion kinds."
    )
    reply.product_ids = None
    assert completion_error(reply, receipts) is None


@pytest.mark.parametrize(
    "kind,product_ids", [("catalog", None), ("price_comparison", None), ("price_comparison", [])]
)
def test_catalog_kinds_require_explicit_appropriate_card_ids(
    kind: str, product_ids: list[str] | None
) -> None:
    reply = CompleteShoppingTurn.model_validate(
        {"kind": kind, "message": "Results", "product_ids": product_ids}
    )
    assert completion_error(
        reply, [receipt("catalog_search"), comparison_receipt("a", "b"), selection_receipt()]
    )


@pytest.mark.parametrize("kind", ["catalog", "price_comparison"])
@pytest.mark.parametrize("declared_ids", [["a"], ["b", "a"], ["c"], ["A", "b"]])
def test_final_card_declaration_requires_exact_selection_in_order(
    kind: str, declared_ids: list[str]
) -> None:
    reply = CompleteShoppingTurn.model_validate(
        {"kind": kind, "message": "Results", "product_ids": declared_ids}
    )
    receipts = [
        receipt("catalog_search"),
        comparison_receipt("a", "b", "c", "A"),
        selection_receipt("a", "b"),
    ]
    error = completion_error(reply, receipts)
    assert error and "select_catalog_products again" in error
    assert completion_error(reply, [*receipts, selection_receipt(*declared_ids)]) is None


def test_empty_catalog_declaration_requires_an_empty_selection() -> None:
    reply = CompleteShoppingTurn(kind="catalog", message="None fit", product_ids=[])
    receipts = [receipt("catalog_search"), selection_receipt("a")]
    assert completion_error(reply, receipts)
    assert completion_error(reply, [*receipts, selection_receipt()]) is None


@pytest.mark.parametrize("selected", [[], ["a"]])
def test_catalog_misclassification_correction_names_valid_completion(selected: list[str]) -> None:
    receipts = [receipt("lookup_catalog_products"), selection_receipt(*selected)]
    for kind in ("conversation", "blocked"):
        reply = CompleteShoppingTurn(kind=kind, message="Observed result", product_ids=None)
        error = completion_error(reply, receipts)
        assert error and 'kind="catalog"' in error
        assert "product_ids" in error and "select_catalog_products" in error
        assert "no match is not a tool failure" in error


def test_refusal_can_finish_without_attempting_an_unauthorized_action() -> None:
    reply = CompleteShoppingTurn(
        kind="refusal", message="Use the explicit cart controls.", product_ids=None
    )
    assert completion_error(reply, []) is None
    assert completion_error(reply, [receipt("lookup_catalog_products")]) is None
    reply.product_ids = ["a"]
    assert completion_error(reply, [receipt("lookup_catalog_products"), selection_receipt("a")])


def test_blocked_correction_distinguishes_refusal_and_missing_receipt() -> None:
    reply = CompleteShoppingTurn(
        kind="blocked", message="I cannot charge a card.", product_ids=None
    )
    error = completion_error(reply, [])
    assert error and 'kind="refusal"' in error
    assert "Do not attempt" in error
    assert completion_error(reply, [receipt("catalog_search", failed=True)]) is None


def test_failed_tool_guidance_names_blocked_but_does_not_count_completion_errors() -> None:
    reply = CompleteShoppingTurn(kind="conversation", message="Unavailable", product_ids=None)
    error = completion_error(reply, [receipt("catalog_search", failed=True)])
    assert error and 'kind="blocked"' in error
    error = completion_error(
        reply, [receipt("lookup_catalog_products"), receipt("complete_shopping_turn", failed=True)]
    )
    assert error and 'kind="blocked"' not in error


@pytest.mark.parametrize("name", ["inspect_shopping_activity", "configure_activity_monitor"])
def test_correction_recognizes_activity_receipts_without_ok_field(name: str) -> None:
    observed = receipt(name, output={"events": [], "verified": True})
    wrong_kind = CompleteShoppingTurn(kind="conversation", message="Checked", product_ids=None)
    error = completion_error(wrong_kind, [observed])
    assert error and 'kind="activity"' in error
    correct = wrong_kind.model_copy(update={"kind": "activity"})
    assert completion_error(correct, [observed]) is None
    for failed in (
        observed.model_copy(update={"is_error": True}),
        receipt(name, output={"ok": False}),
        receipt(name, output={"error": "ACTIVITY_UNAVAILABLE"}),
    ):
        error = completion_error(wrong_kind, [failed])
        assert error and 'kind="activity"' not in error
        assert completion_error(correct, [failed])


@pytest.mark.parametrize(
    "evidence",
    [
        None,
        {},
        "a",
        [None],
        [{}],
        [{"product_id": 1}],
        [{"product_id": ""}],
        [{"product_id": "  "}],
        [{"product_id": "x" * 161}],
        [{"product_id": "a"}, {"product_id": "a"}],
        [{"product_id": "a"}, {}],
    ],
)
def test_catalog_rejects_malformed_selection_receipt(evidence: object) -> None:
    reply = CompleteShoppingTurn(kind="catalog", message="Results", product_ids=["a"])
    selection = selection_receipt("a")
    selection.output["selected_products"] = evidence
    assert completion_error(reply, [receipt("catalog_search"), selection])


@pytest.mark.parametrize(
    "failure", [{}, {"ok": True}, {"ok": True, "error": "UNAVAILABLE"}, {"ok": False}, {"ok": 1}]
)
def test_catalog_cannot_reuse_prior_selection_after_missing_or_failed_evidence(
    failure: JsonObject,
) -> None:
    reply = CompleteShoppingTurn(kind="catalog", message="Results", product_ids=["a"])
    assert completion_error(
        reply,
        [
            receipt("catalog_search"),
            selection_receipt("a"),
            receipt("select_catalog_products", output=failure),
        ],
    )


@pytest.mark.parametrize("kind", ["catalog", "price_comparison", "memory", "activity", "blocked"])
def test_action_completion_requires_receipts(kind: str) -> None:
    reply = CompleteShoppingTurn.model_validate(
        {
            "kind": kind,
            "message": "Done",
            "product_ids": ["a"] if kind in {"catalog", "price_comparison"} else None,
        }
    )
    assert completion_error(reply, [])
    assert completion_error(reply, [receipt("complete_shopping_turn", failed=True)])


def test_catalog_needs_read_and_fresh_successful_selection() -> None:
    reply = CompleteShoppingTurn(kind="catalog", message="Here are the results", product_ids=["a"])
    read, selection = receipt("catalog_search"), selection_receipt("a")
    assert completion_error(reply, [selection])
    assert completion_error(reply, [read])
    assert completion_error(reply, [read, receipt("select_catalog_products", failed=True)])
    assert completion_error(reply, [read, selection, receipt("lookup_catalog_products")])
    assert completion_error(reply, [read, selection]) is None


@pytest.mark.parametrize("product_ids", [(), ("a",), ("c",)])
def test_catalog_selection_does_not_require_comparison(product_ids: tuple[str, ...]) -> None:
    reply = CompleteShoppingTurn(
        kind="catalog", message="Here are the results", product_ids=list(product_ids)
    )
    assert (
        completion_error(reply, [receipt("catalog_search"), selection_receipt(*product_ids)])
        is None
    )


def test_price_comparison_needs_arithmetic_receipt() -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    assert completion_error(reply, [receipt("lookup_catalog_products"), selection_receipt("a")])
    assert (
        completion_error(
            reply,
            [
                receipt("lookup_catalog_products"),
                comparison_receipt("a", "b"),
                selection_receipt("a"),
            ],
        )
        is None
    )


@pytest.mark.parametrize("name", ["catalog_search", "lookup_catalog_products"])
@pytest.mark.parametrize("failed", [False, True])
def test_price_comparison_requires_fresh_comparison_after_latest_read(
    name: str, failed: bool
) -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    receipts = [
        receipt("lookup_catalog_products"),
        comparison_receipt("a", "b"),
        receipt(name, failed=failed),
        selection_receipt("a"),
    ]
    assert completion_error(reply, receipts)
    assert (
        completion_error(reply, [*receipts, comparison_receipt("a", "b"), selection_receipt("a")])
        is None
    )


@pytest.mark.parametrize(
    "compared,selected",
    [(("a", "b"), ("a",)), (("a", "b"), ("b", "a")), (("a", "a"), ("a",))],
)
def test_price_comparison_accepts_subsets_and_same_product_variants(
    compared: tuple[str, ...], selected: tuple[str, ...]
) -> None:
    reply = CompleteShoppingTurn(
        kind="price_comparison", message="Exact prices", product_ids=list(selected)
    )
    assert (
        completion_error(
            reply,
            [
                receipt("lookup_catalog_products"),
                comparison_receipt(*compared),
                selection_receipt(*selected),
            ],
        )
        is None
    )


@pytest.mark.parametrize("selected", [("c",), ("a", "c"), ("A",)])
def test_price_comparison_rejects_unrelated_selection(selected: tuple[str, ...]) -> None:
    reply = CompleteShoppingTurn(
        kind="price_comparison", message="Exact prices", product_ids=list(selected)
    )
    assert completion_error(
        reply,
        [
            receipt("lookup_catalog_products"),
            comparison_receipt("a", "b"),
            selection_receipt(*selected),
        ],
    )


def test_price_comparison_uses_only_latest_comparison_and_selection() -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    receipts = [
        receipt("lookup_catalog_products"),
        comparison_receipt("a", "b"),
        selection_receipt("a"),
        comparison_receipt("b", "c"),
        selection_receipt("a"),
    ]
    assert completion_error(reply, receipts)
    reply.product_ids = ["b"]
    assert completion_error(reply, [*receipts, selection_receipt("b")]) is None


@pytest.mark.parametrize("name", ["compare_catalog_prices", "select_catalog_products"])
@pytest.mark.parametrize(
    "failure", [{"ok": False}, {"ok": "true"}, {"ok": 1}, {"error": "CATALOG_UNAVAILABLE"}]
)
def test_price_comparison_cannot_reuse_success_after_failed_receipt(
    name: str, failure: JsonObject
) -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    latest = (
        comparison_receipt("a", "b") if name == "compare_catalog_prices" else selection_receipt("a")
    )
    latest.output.update(failure)
    receipts = [
        receipt("lookup_catalog_products"),
        comparison_receipt("a", "b"),
        selection_receipt("a"),
        latest,
    ]
    if name == "compare_catalog_prices":
        receipts.append(selection_receipt("a"))
    assert completion_error(reply, receipts)


@pytest.mark.parametrize("name", ["compare_catalog_prices", "select_catalog_products"])
def test_price_comparison_rejects_error_flag_even_with_success_output(name: str) -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    comparison, selection = comparison_receipt("a", "b"), selection_receipt("a")
    latest = comparison if name == "compare_catalog_prices" else selection
    latest.is_error = True
    assert completion_error(
        reply,
        [receipt("lookup_catalog_products"), comparison_receipt("a", "b"), comparison, selection],
    )


@pytest.mark.parametrize(
    "name,key",
    [("compare_catalog_prices", "items"), ("select_catalog_products", "selected_products")],
)
@pytest.mark.parametrize(
    "evidence",
    [
        None,
        {},
        "a",
        [],
        ["a", "b"],
        [None],
        [{}],
        [{"product_id": None}],
        [{"product_id": 1}],
        [{"product_id": True}],
        [{"product_id": ""}],
        [{"product_id": "  "}],
        [{"product_id": ["a"]}],
        [{"product_id": "a"}, {}],
    ],
)
def test_price_comparison_rejects_malformed_product_evidence(
    name: str, key: str, evidence: object
) -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    comparison, selection = comparison_receipt("a", "b"), selection_receipt("a")
    latest = comparison if name == "compare_catalog_prices" else selection
    latest.output[key] = evidence
    assert completion_error(
        reply,
        [receipt("lookup_catalog_products"), comparison_receipt("a", "b"), comparison, selection],
    )


@pytest.mark.parametrize("name", ["compare_catalog_prices", "select_catalog_products"])
def test_price_comparison_rejects_missing_product_evidence(name: str) -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    assert completion_error(
        reply,
        [
            receipt("lookup_catalog_products"),
            receipt(name) if name == "compare_catalog_prices" else comparison_receipt("a", "b"),
            receipt(name) if name == "select_catalog_products" else selection_receipt("a"),
        ],
    )


def test_other_receipts_do_not_invalidate_price_comparison() -> None:
    reply = CompleteShoppingTurn(kind="price_comparison", message="Exact prices", product_ids=["a"])
    assert (
        completion_error(
            reply,
            [
                receipt("lookup_catalog_products"),
                comparison_receipt("a", "b"),
                receipt("save_shopping_memory"),
                selection_receipt("a"),
                receipt("inspect_shopping_activity"),
                receipt("complete_shopping_turn", failed=True),
            ],
        )
        is None
    )


@pytest.mark.parametrize(
    "kind,name",
    [
        ("memory", "save_shopping_memory"),
        ("activity", "inspect_shopping_activity"),
        ("activity", "configure_activity_monitor"),
    ],
)
def test_completed_action_cannot_use_failed_receipt(kind: str, name: str) -> None:
    reply = CompleteShoppingTurn.model_validate(
        {"kind": kind, "message": "Completed", "product_ids": None}
    )
    assert completion_error(reply, [receipt(name, failed=True)])
    assert completion_error(reply, [receipt(name)]) is None


class Provider:
    provider_name = "scripted"
    model_id = "offline"

    def __init__(self, turns: list[ManagerModelTurn]) -> None:
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
        assert "complete_shopping_turn" in {t.name for t in tools}
        return self

    async def next(self, results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.results.append(results)
        return next(self.turns)


async def respond(
    provider: Provider,
    iterations: int,
    content: str = "Find dishwasher-safe drinking glasses under $30.",
) -> ShopperAgentOutcome:
    return await ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        max_iterations=iterations,
        max_tool_calls=6,
        max_output_tokens=1500,
    ).respond(
        tenant_id=UUID(int=1),
        content=content,
        history=[],
        memories=[],
        source="uploaded_catalog",
    )


async def test_prose_only_promise_is_not_completed_or_repeated_beyond_budget() -> None:
    promise = "If you want, I can search the catalog and narrow to a best few options."
    provider = Provider([ManagerModelTurn(content=promise, phase="final_answer")] * 2)
    result = await respond(provider, 2)
    assert promise not in result.content
    assert result.products == []
    assert result.steps[-1].status == "needs_input"
    assert len(provider.results) == 2


@pytest.mark.parametrize("kind", ["conversation", "clarification"])
async def test_no_catalog_tool_is_required_for_chat_or_material_clarification(kind: str) -> None:
    answer = "Hello!" if kind == "conversation" else "Which size do you need?"
    provider = Provider([finish(answer, kind)])
    result = await respond(
        provider, 1, "Hello" if kind == "conversation" else "Which size fits me?"
    )
    assert result.content == answer
    assert result.products == []


async def test_rejected_completion_can_investigate_and_finish_in_same_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Provider(
        [
            finish("I can search for you", "catalog", product_ids=[]),
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="read", name="catalog_search", arguments={"query": "glass"}
                    )
                ]
            ),
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="select",
                        name="select_catalog_products",
                        arguments={"product_ids": []},
                    )
                ]
            ),
            finish("No suitable products were found.", "catalog", product_ids=[]),
        ]
    )
    monkeypatch.setattr(
        CatalogSearchTool,
        "run",
        AsyncMock(return_value={"ok": True, "results": [], "result_count": 0}),
    )
    result = await respond(provider, 4)
    assert provider.results[1][0].output["error"] == "INCOMPLETE_SHOPPING_TURN"
    assert result.content == "No suitable products were found."
    assert result.steps[-1].status == "completed"


@pytest.mark.parametrize("scenario", ["unrelated_selection", "later_lookup", "failed_comparison"])
async def test_price_comparison_loop_rejects_and_repairs_receipts(scenario: str) -> None:
    products = {
        key: CatalogBrowseProduct.model_validate(
            {
                "product_id": key,
                "title": f"Travel mug {key}",
                "description": "Stainless steel travel mug.",
                "brand": "Sample",
                "category": "Home",
                "image_url": None,
                "variant_id": f"{key}-small",
                "price": {"amount_minor": 2000 + index * 100, "currency": "USD"},
                "availability": "available",
                "provenance": None,
                "variants": [
                    {
                        "id": f"{key}-small",
                        "title": "Small",
                        "options": {"size": "small"},
                        "price": {"amount_minor": 2000 + index * 100, "currency": "USD"},
                        "available": True,
                        "availability": "available",
                    }
                ],
            }
        )
        for index, key in enumerate(("a", "b", "c"))
    }

    async def browse(*, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        assert tenant_id == UUID(int=1)
        assert query.product_id in products
        return CatalogBrowseResponse.model_validate(
            {
                "catalog": {
                    "id": UUID(int=20),
                    "filename": "fixture.csv",
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

    def call(name: str, arguments: JsonObject) -> ManagerModelTurn:
        return ManagerModelTurn(
            tool_calls=[ManagerToolCall(call_id=name, name=name, arguments=arguments)]
        )

    compare = call("compare_catalog_prices", {"items": [{"product_id": "a"}, {"product_id": "b"}]})
    interrupted = []
    if scenario == "later_lookup":
        interrupted.append(call("lookup_catalog_products", {"product_ids": ["c"]}))
    elif scenario == "failed_comparison":
        interrupted.append(
            call(
                "compare_catalog_prices",
                {"items": [{"product_id": "a", "variant_id": "missing"}, {"product_id": "b"}]},
            )
        )
    answer = "Mug a's small variant is USD 1.00 cheaper than mug b's."
    turns = [
        call("lookup_catalog_products", {"product_ids": list(products)}),
        compare,
        *interrupted,
        call("select_catalog_products", {"product_ids": ["c" if not interrupted else "a"]}),
        finish(
            "This completion must be rejected.",
            "price_comparison",
            product_ids=["c" if not interrupted else "a"],
        ),
        *([compare] if interrupted else []),
        call("select_catalog_products", {"product_ids": ["a"]}),
        finish(answer, "price_comparison", product_ids=["a"]),
    ]
    provider = Provider(turns)
    result = await ShopperConversationalAgent(
        provider=provider,
        catalog_search=CatalogSearchTool(None),
        catalog_reader=reader,
        max_iterations=len(turns) + 1,  # Includes the separately scripted answer review.
        max_tool_calls=6,
        max_output_tokens=1500,
    ).respond(
        tenant_id=UUID(int=1),
        content="Compare mug a with mug b and show the cheaper one.",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    errors = [receipt for batch in provider.results for receipt in batch if receipt.is_error]
    assert [error.output["error"] for error in errors] == {
        "failed_comparison": [
            "VARIANT_NOT_IN_PRODUCT",
            "COMPARISON_REQUIRES_REFRESH",
            "INCOMPLETE_SHOPPING_TURN",
        ],
        "unrelated_selection": ["PRODUCT_NOT_COMPARED", "INCOMPLETE_SHOPPING_TURN"],
        "later_lookup": ["INCOMPLETE_SHOPPING_TURN"],
    }[scenario]
    assert errors[-1].output["correction"]
    assert result.content == answer
    assert [product.product_id for product in result.products] == ["a"]
    assert result.steps[-1].status == "completed"
    assert len(provider.results) == len(turns)
