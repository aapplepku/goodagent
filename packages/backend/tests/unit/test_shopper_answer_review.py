"""Offline review regressions using synthetic facts and explicitly scripted verdicts.

These mocks prove admission and control flow, not semantic quality: a scripted
rejection does not show that a real model detects unsuitable recommendations.
The memory callback models an already committed receipt, not database persistence.
No network, hosted model, secrets, database, or Docker services are used.
"""

from __future__ import annotations

import hashlib
import json
import socket
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NoReturn, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
)
from open_commerce.core.types import JsonObject
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
from open_commerce.shopper_agent.answer_review import (
    MAX_REVIEW_BYTES,
    REVIEW_CATALOG_ANSWER,
    AnswerReview,
    CatalogAnswerVerdict,
    review_catalog_answer,
)
from open_commerce.shopper_agent.completion import CompleteShoppingTurn, completion_error
from open_commerce.shopper_agent.memory_tools import SaveShoppingMemoryInput
from open_commerce.shopper_agent.model_agent import (
    ShopperAgentOutcome,
    ShopperConversationalAgent,
)
from open_commerce.shopper_agent.models import ShopperMemory, ShopperMessage
from open_commerce.shopper_agent.product_tools import ShopperProductTools
from open_commerce.telemetry.activity_tools import ActivityTools

TENANT = UUID(int=1)
MESSAGE_ID = UUID(int=2)
ALL_IDS = ["glass-clear", "glass-tall", "glass-painted"]
GOOD_IDS = ALL_IDS[:2]
DRAFT = "The clear and tall sets are dishwasher-safe. I excluded the painted hand-wash set."
REQUEST = "Find dishwasher-safe drinking glasses under $30."


@pytest.fixture(autouse=True)
def prevent_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("These regressions must not open network connections")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


class SyntheticCatalog:
    def __init__(self) -> None:
        self.reads: list[str] = []
        self.products = {
            key: CatalogBrowseProduct.model_validate(
                {
                    "product_id": key,
                    "title": title,
                    "description": description,
                    "brand": None,
                    "category": "Glassware",
                    "image_url": None,
                    "variant_id": f"{key}-default",
                    "price": {"amount_minor": price, "currency": "USD"},
                    "availability": "available",
                    "provenance": None,
                    "variants": [
                        {
                            "id": f"{key}-default",
                            "title": "Default",
                            "options": {},
                            "price": {"amount_minor": price, "currency": "USD"},
                            "available": True,
                            "availability": "available",
                        }
                    ],
                }
            )
            for key, title, price, description in [
                (ALL_IDS[0], "Clear Drinking Glasses", 1999, "Four dishwasher-safe glasses."),
                (ALL_IDS[1], "Tall Drinking Glasses", 2499, "Two dishwasher-safe tall glasses."),
                (ALL_IDS[2], "Painted Drinking Glasses", 1599, "Painted glasses. Hand wash only."),
            ]
        }

    async def browse(self, *, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        assert tenant_id == TENANT
        assert query.product_id in self.products
        assert query.product_id is not None
        self.reads.append(query.product_id)
        return CatalogBrowseResponse.model_validate(
            {
                "catalog": {
                    "id": UUID(int=20),
                    "filename": "synthetic.csv",
                    "source_version": "offline-current",
                    "product_count": len(self.products),
                    "published_at": None,
                },
                "indexing": {},
                "categories": [],
                "items": [self.products[query.product_id].model_dump(mode="json")],
                "total": 1,
                "offset": 0,
                "limit": query.limit,
            }
        )


def tool_turn(name: str, arguments: JsonObject) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[ManagerToolCall(call_id=f"call-{name}", name=name, arguments=arguments)],
        stop_reason="tool_call",
    )


def complete(
    message: str = DRAFT, product_ids: list[str] | None = None, *, kind: str = "catalog"
) -> ManagerModelTurn:
    return tool_turn(
        "complete_shopping_turn",
        {"kind": kind, "message": message, "product_ids": product_ids},
    )


def catalog_turns(product_ids: list[str] = ALL_IDS, message: str = DRAFT) -> list[ManagerModelTurn]:
    return [
        tool_turn("lookup_catalog_products", {"queries": [], "product_ids": ALL_IDS}),
        tool_turn("select_catalog_products", {"product_ids": product_ids}),
        complete(message, product_ids),
    ]


@dataclass
class ReviewRequest:
    instructions: str
    messages: list[ManagerModelMessage]
    tools: list[ManagerToolDefinition]
    max_output_tokens: int
    require_tool: bool

    @property
    def text(self) -> str:
        return "".join(message.content.split("\n", 1)[1] for message in self.messages)

    @property
    def document(self) -> JsonObject:
        return cast(JsonObject, json.loads(self.text))


ReviewScript = Callable[[ReviewRequest], ManagerModelTurn]
TurnScript = ManagerModelTurn | ManagerModelUnavailableError | Callable[[], ManagerModelTurn]


class ScriptedSession:
    def __init__(self, turns: Sequence[TurnScript], calls: list[str], label: str) -> None:
        self.turns = deque(turns)
        self.calls = calls
        self.label = label
        self.inputs: list[list[ManagerToolResult]] = []
        self.observed: list[ManagerToolResult] = []

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.calls.append(self.label)
        self.inputs.append([item.model_copy(deep=True) for item in tool_results])
        assert self.turns, f"Unexpected extra {self.label} call"
        turn = self.turns.popleft()
        if isinstance(turn, ManagerModelUnavailableError):
            raise turn
        return turn() if callable(turn) else turn

    def observe_tool_result(self, result: ManagerToolResult) -> None:
        self.observed.append(result.model_copy(deep=True))


class ScriptedProvider:
    provider_name = "scripted"
    model_id = "offline-answer-review"

    def __init__(
        self,
        reviews: Sequence[ReviewScript | ManagerModelUnavailableError] = (),
        turns: Sequence[TurnScript] = (),
        *,
        begin_error: ManagerModelUnavailableError | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.actor = ScriptedSession(turns, self.calls, "actor")
        self.scripts = deque(reviews)
        self.reviews: list[ReviewRequest] = []
        self.review_sessions: list[ScriptedSession] = []
        self.actor_tools: list[ManagerToolDefinition] = []
        self.begin_error = begin_error

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
        if [tool.name for tool in tools] != [REVIEW_CATALOG_ANSWER.name]:
            assert not self.actor_tools, "The acting session must not restart to reset its budget"
            self.actor_tools = tools
            return self.actor
        request = ReviewRequest(instructions, messages, tools, max_output_tokens, require_tool)
        self.reviews.append(request)
        if self.begin_error is not None:
            raise self.begin_error
        assert self.scripts, "Review requires an explicitly scripted response"
        script = self.scripts.popleft()
        session = ScriptedSession(
            [
                script
                if isinstance(script, ManagerModelUnavailableError)
                else lambda: script(request)
            ],
            self.calls,
            "review",
        )
        self.review_sessions.append(session)
        return session


def verdict(
    *,
    changes: JsonObject | None = None,
    missing: Sequence[str] = (),
    name: str = REVIEW_CATALOG_ANSWER.name,
    stop_reason: str = "tool_call",
) -> ReviewScript:
    def respond(request: ReviewRequest) -> ManagerModelTurn:
        document = request.document
        candidate = cast(JsonObject, document["candidate"])
        arguments: JsonObject = {
            "candidate_id": document["candidate_id"],
            "product_ids": candidate["product_ids"],
            "verdict": "supported",
            "issues": [],
        }
        arguments.update(changes or {})
        for key in missing:
            arguments.pop(key)
        response = tool_turn(name, arguments)
        response.stop_reason = stop_reason
        return response

    return respond


def reject(issue: str = "answer_card_mismatch") -> ReviewScript:
    return verdict(changes={"verdict": "revise", "issues": [issue]})


@dataclass
class ReviewInput:
    reply: CompleteShoppingTurn
    receipts: list[ManagerToolResult]
    messages: list[ManagerModelMessage] = field(
        default_factory=lambda: [ManagerModelMessage(role="user", content=REQUEST)]
    )
    preferences: list[str] = field(default_factory=lambda: ["I prefer clear glasses."])

    async def run(self, provider: ScriptedProvider) -> AnswerReview:
        return await review_catalog_answer(
            provider=provider,
            reply=self.reply,
            messages=self.messages,
            preferences=self.preferences,
            receipts=self.receipts,
            max_output_tokens=731,
        )


@pytest.fixture
async def review_input() -> ReviewInput:
    product_tools = ShopperProductTools(tenant_id=TENANT, reader=SyntheticCatalog())
    receipts = []
    for turn in catalog_turns(GOOD_IDS)[:2]:
        call = turn.tool_calls[0]
        output = await product_tools.execute(call.name, call.arguments)
        receipts.append(ManagerToolResult(call_id=call.call_id, name=call.name, output=output))
    reply = CompleteShoppingTurn(kind="catalog", message=DRAFT, product_ids=GOOD_IDS)
    assert completion_error(reply, receipts) is None
    return ReviewInput(reply, receipts)


def expected_hash(document: JsonObject) -> str:
    payload = {key: value for key, value in document.items() if key != "candidate_id"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("status", ["supported", "revise"])
@pytest.mark.parametrize("stop_reason", ["tool_call", "completed"])
async def test_typed_exact_verdict_and_terminal_observer_receipt(
    review_input: ReviewInput, status: str, stop_reason: str
) -> None:
    issues = [] if status == "supported" else ["request_constraint_not_supported"]
    provider = ScriptedProvider(
        [verdict(changes={"verdict": status, "issues": issues}, stop_reason=stop_reason)]
    )
    result = await review_input.run(provider)
    document = provider.reviews[0].document
    assert result.status == status
    assert result.issues == tuple(issues)
    assert result.candidate_id == document["candidate_id"] == expected_hash(document)
    assert document["candidate"] == review_input.reply.model_dump(mode="json")
    assert document["conversation"] == [item.model_dump() for item in review_input.messages]
    assert document["preferences"] == review_input.preferences
    assert provider.calls == ["review"]
    session = provider.review_sessions[0]
    assert session.inputs == [[]]
    assert len(session.observed) == 1
    assert session.observed[0].output == {
        "ok": status == "supported",
        "status": status,
        "candidate_id": result.candidate_id,
        "product_ids": GOOD_IDS,
    }
    assert session.observed[0].is_error == (status != "supported")


@pytest.mark.parametrize(
    "changes",
    [
        {"candidate_id": "sha256:" + "a" * 64},
        {"candidate_id": "invalid"},
        {"candidate_id": 42},
        {"product_ids": list(reversed(GOOD_IDS))},
        {"product_ids": GOOD_IDS[:1]},
        {"product_ids": [GOOD_IDS[0], "unknown-product"]},
        {"product_ids": [GOOD_IDS[0], GOOD_IDS[0]]},
        {"product_ids": []},
        {"product_ids": None},
        {"product_ids": "glass-clear"},
        {"product_ids": [42]},
        {"product_ids": ["x" * 161]},
        {"verdict": "approved"},
        {"verdict": True},
        {"verdict": "supported", "issues": ["answer_card_mismatch"]},
        {"verdict": "revise", "issues": []},
        {"verdict": "revise", "issues": ["unknown_issue"]},
        {"verdict": "revise", "issues": ["answer_card_mismatch"] * 2},
        {"issues": None},
        {"issues": "insufficient_context"},
        {"issues": [17]},
        {"private_reasoning": "Unrequested output"},
    ],
)
async def test_inconsistent_unknown_or_malformed_verdict_is_denied(
    review_input: ReviewInput, changes: JsonObject
) -> None:
    provider = ScriptedProvider([verdict(changes=changes)])
    result = await review_input.run(provider)
    assert result.status == "unavailable" and result.issues == ()
    assert provider.calls == ["review"]
    receipt = provider.review_sessions[0].observed[0]
    assert receipt.is_error and receipt.output["ok"] is False
    assert receipt.output["status"] == "unavailable"
    assert receipt.output["candidate_id"] == provider.reviews[0].document["candidate_id"]
    assert receipt.output["product_ids"] == GOOD_IDS


@pytest.mark.parametrize("missing", ["candidate_id", "product_ids", "verdict", "issues"])
async def test_incomplete_verdict_is_denied(review_input: ReviewInput, missing: str) -> None:
    provider = ScriptedProvider([verdict(missing=[missing])])
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.calls == ["review"]


@pytest.mark.parametrize("stop_reason", ["incomplete", "failed", "cancelled", "max_tokens"])
async def test_incomplete_transport_never_admits_an_apparently_valid_verdict(
    review_input: ReviewInput, stop_reason: str
) -> None:
    provider = ScriptedProvider([verdict(stop_reason=stop_reason)])
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.calls == ["review"]


@pytest.mark.parametrize("count", [0, 2])
async def test_reviewer_requires_exactly_one_verdict_tool(
    review_input: ReviewInput, count: int
) -> None:
    def response(request: ReviewRequest) -> ManagerModelTurn:
        call = verdict()(request).tool_calls[0]
        # Bypass the provider contract deliberately to exercise defense in depth.
        return ManagerModelTurn.model_construct(
            content="supported", tool_calls=[call] * count, stop_reason="completed"
        )

    provider = ScriptedProvider([response])
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.calls == ["review"]


@pytest.mark.parametrize(
    "changed", ["draft", "request", "history", "preferences", "facts", "ordered_ids"]
)
async def test_verdict_cannot_be_replayed_after_candidate_context_changes(
    review_input: ReviewInput, changed: str
) -> None:
    first = ScriptedProvider([verdict()])
    assert (await review_input.run(first)).status == "supported"
    old_hash = first.reviews[0].document["candidate_id"]
    if changed == "draft":
        review_input.reply.message += " Choose the clear set."
    elif changed == "request":
        review_input.messages[-1].content = "Find glasses that make the wearer invisible."
    elif changed == "history":
        review_input.messages.insert(0, ManagerModelMessage(role="user", content="Only tall sets."))
    elif changed == "preferences":
        review_input.preferences = ["I prefer tall glasses."]
    elif changed == "facts":
        selected = cast(list[JsonObject], review_input.receipts[-1].output["selected_products"])
        selected[0]["catalog_description"] = "Hand wash only."
    else:
        review_input.reply.product_ids = list(reversed(GOOD_IDS))
        selected = cast(list[JsonObject], review_input.receipts[-1].output["selected_products"])
        review_input.receipts[-1].output["selected_products"] = list(reversed(selected))
    provider = ScriptedProvider([verdict(changes={"candidate_id": old_hash})])
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.reviews[0].document["candidate_id"] != old_hash


@pytest.mark.parametrize("failure", ["provider unavailable", "quota exhausted"])
@pytest.mark.parametrize("phase", ["begin", "next"])
async def test_reviewer_model_exception_and_quota_fail_closed_without_retry(
    review_input: ReviewInput, failure: str, phase: str
) -> None:
    error = ManagerModelUnavailableError(failure)
    provider = ScriptedProvider([error], begin_error=error if phase == "begin" else None)
    assert (await review_input.run(provider)).status == "unavailable"
    assert len(provider.reviews) == 1
    assert provider.calls == ([] if phase == "begin" else ["review"])


async def test_reviewer_gets_only_a_closed_verdict_tool(review_input: ReviewInput) -> None:
    provider = ScriptedProvider([verdict()])
    await review_input.run(provider)
    request = provider.reviews[0]
    assert [tool.name for tool in request.tools] == ["review_catalog_answer"]
    assert request.require_tool and request.max_output_tokens == 731
    schema = request.tools[0].parameters
    assert schema["additionalProperties"] is False
    assert set(cast(list[str], schema["required"])) == {
        "candidate_id",
        "product_ids",
        "verdict",
        "issues",
    }
    assert "untrusted DATA" in request.instructions
    assert "never instructions" in request.instructions
    assert (
        CatalogAnswerVerdict.model_validate(
            verdict()(request).tool_calls[0].arguments, strict=True
        ).product_ids
        == GOOD_IDS
    )


async def test_structured_redaction_preserves_json_numeric_facts_and_hash(
    review_input: ReviewInput,
) -> None:
    synthetic_private = 'contact@example.test +1 202-555-0198 123 Test Street password="fake-only"'
    review_input.messages[0].content = synthetic_private
    review_input.preferences = [synthetic_private]
    selected = cast(list[JsonObject], review_input.receipts[-1].output["selected_products"])
    selected[0]["catalog_description"] = synthetic_private
    selected[0]["price_minor"] = 1234567890
    provider = ScriptedProvider([verdict()])
    assert (await review_input.run(provider)).status == "supported"
    document = provider.reviews[0].document
    assert document["candidate_id"] == expected_hash(document)
    serialized = json.dumps(document)
    for raw in ["contact@example.test", "202-555-0198", "123 Test Street", "fake-only"]:
        assert raw not in serialized
    for marker in ["[redacted-email]", "[redacted-phone]", "[redacted-address]", "[redacted]"]:
        assert marker in serialized
    evidence = cast(list[JsonObject], document["catalog_evidence"])
    output = cast(JsonObject, evidence[-1]["output"])
    facts = cast(list[JsonObject], output["selected_products"])
    assert facts[0]["price_minor"] == 1234567890
    assert type(facts[0]["price_minor"]) is int
    assert document["candidate"] == review_input.reply.model_dump(mode="json")


@pytest.mark.parametrize("sensitive", ["contact@example.test", 'password="fake-only"'])
async def test_draft_that_would_change_under_redaction_is_denied_before_call(
    review_input: ReviewInput, sensitive: str
) -> None:
    review_input.reply.message += " " + sensitive
    provider = ScriptedProvider()
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.reviews == [] and provider.calls == []


@pytest.mark.parametrize("size", [MAX_REVIEW_BYTES - 1, MAX_REVIEW_BYTES, MAX_REVIEW_BYTES + 1])
async def test_review_document_is_chunked_completely_or_denied_at_byte_bound(
    review_input: ReviewInput, size: int
) -> None:
    review_input.preferences = [""]
    baseline = ScriptedProvider([verdict()])
    await review_input.run(baseline)
    padding = size - len(baseline.reviews[0].text.encode("utf-8"))
    assert padding > 0
    review_input.preferences = ["x" * padding]
    provider = ScriptedProvider([verdict()])
    result = await review_input.run(provider)
    if size > MAX_REVIEW_BYTES:
        assert result.status == "unavailable"
        assert provider.reviews == [] and provider.calls == []
        return
    assert result.status == "supported"
    request = provider.reviews[0]
    assert len(request.text.encode("utf-8")) == size
    assert len(request.messages) > 1
    for index, message in enumerate(request.messages, start=1):
        header, chunk = message.content.split("\n", 1)
        assert header == f"Review input part {index}/{len(request.messages)}:"
        assert message.role == "user" and len(message.content) <= 4000
        assert 0 < len(chunk) <= 3600
    assert request.document["preferences"] == review_input.preferences
    assert request.document["candidate"] == review_input.reply.model_dump(mode="json")


@pytest.mark.parametrize(
    "broken",
    [
        "missing_read",
        "missing_selection",
        "failed_selection",
        "stale_selection",
        "wrong_ids",
        "missing_comparison",
        "stale_comparison",
    ],
)
async def test_missing_failed_or_stale_required_evidence_denied_before_review(
    review_input: ReviewInput, broken: str
) -> None:
    if broken == "missing_read":
        review_input.receipts = review_input.receipts[1:]
    elif broken == "missing_selection":
        review_input.receipts.pop()
    elif broken == "failed_selection":
        review_input.receipts[-1].is_error = True
    elif broken == "stale_selection":
        review_input.receipts.append(review_input.receipts[0].model_copy(deep=True))
    elif broken == "wrong_ids":
        review_input.reply.product_ids = list(reversed(GOOD_IDS))
    else:
        review_input.reply.kind = "price_comparison"
        if broken == "stale_comparison":
            review_input.receipts.insert(
                0,
                ManagerToolResult(
                    call_id="stale-price",
                    name="compare_catalog_prices",
                    output={"ok": True, "items": [{"product_id": key} for key in GOOD_IDS]},
                ),
            )
    assert completion_error(review_input.reply, review_input.receipts) is not None
    provider = ScriptedProvider()
    assert (await review_input.run(provider)).status == "unavailable"
    assert provider.calls == [] and provider.reviews == []


@pytest.mark.parametrize("latest_read", ["lookup_catalog_products", "catalog_search"])
async def test_only_current_catalog_evidence_crosses_the_review_boundary(
    review_input: ReviewInput, latest_read: str
) -> None:
    excluded = [
        ("lookup_catalog_products", "stale-lookup"),
        ("compare_catalog_prices", "stale-arithmetic"),
        ("select_catalog_products", "stale-selection"),
        ("save_shopping_memory", "private-memory-receipt"),
        ("inspect_shopping_activity", "private-activity-receipt"),
    ]
    old = [
        ManagerToolResult(call_id=marker, name=name, output={"ok": True, "marker": marker})
        for name, marker in excluded
    ]
    if latest_read == "catalog_search":
        review_input.receipts[0] = ManagerToolResult(
            call_id="latest-search",
            name="catalog_search",
            output={"ok": True, "query": "raw-search-is-not-current-selection"},
        )
    review_input.receipts = [*old, *review_input.receipts]
    provider = ScriptedProvider([verdict()])
    assert (await review_input.run(provider)).status == "supported"
    text = provider.reviews[0].text
    assert all(marker not in text for _, marker in excluded)
    assert "raw-search-is-not-current-selection" not in text
    evidence = cast(list[JsonObject], provider.reviews[0].document["catalog_evidence"])
    expected = [latest_read] if latest_read == "lookup_catalog_products" else []
    assert [item["tool"] for item in evidence] == [*expected, "select_catalog_products"]
    assert "dishwasher-safe" in text


async def run_agent(
    provider: ScriptedProvider,
    *,
    max_calls: int,
    max_tool_calls: int = 8,
    content: str = REQUEST,
    save_memory: Callable[[SaveShoppingMemoryInput], Awaitable[ShopperMemory]] | None = None,
    activity_tools: ActivityTools | None = None,
    history: list[ShopperMessage] | None = None,
) -> ShopperAgentOutcome:
    search = AsyncMock(spec=CatalogSearchTool)
    search.run.side_effect = AssertionError("Only scripted current-product reads are expected")
    result = await ShopperConversationalAgent(
        catalog_search=search,
        provider=provider,
        catalog_reader=SyntheticCatalog(),
        max_iterations=max_calls,
        max_tool_calls=max_tool_calls,
        max_output_tokens=731,
    ).respond(
        tenant_id=TENANT,
        content=content,
        history=history or [],
        memories=[],
        source="uploaded_catalog",
        current_message_id=MESSAGE_ID,
        save_memory=save_memory,
        activity_tools=activity_tools,
    )
    assert len(provider.calls) <= max_calls
    search.run.assert_not_awaited()
    return result


def assert_hidden(result: ShopperAgentOutcome, draft: str = DRAFT) -> None:
    assert result.products == []
    assert draft not in result.content
    assert result.steps[-1].status == "fallback"
    assert "couldn't confirm" in result.content


@pytest.mark.parametrize(
    ("shopper_request", "draft", "issue"),
    [
        (
            "Find glasses that make the wearer invisible.",
            "These glasses cannot make you invisible, but here are three ordinary sets.",
            "request_constraint_not_supported",
        ),
        (REQUEST, DRAFT, "answer_card_mismatch"),
    ],
    ids=["matching-ids-invisibility", "matching-ids-misleading-exclusion"],
)
async def test_original_matching_id_failures_receive_scripted_rejection_and_hide_draft(
    shopper_request: str, draft: str, issue: str
) -> None:
    provider = ScriptedProvider([reject(issue)], catalog_turns(message=draft))
    result = await run_agent(provider, max_calls=4, content=shopper_request)
    assert_hidden(result, draft)
    document = provider.reviews[0].document
    assert cast(JsonObject, document["candidate"])["product_ids"] == ALL_IDS
    evidence = cast(list[JsonObject], document["catalog_evidence"])
    selection = cast(JsonObject, evidence[-1]["output"])
    cards = cast(list[JsonObject], selection["selected_products"])
    assert [item["product_id"] for item in cards] == ALL_IDS
    assert "Hand wash only" in str(cards[-1]["catalog_description"])
    assert shopper_request in json.dumps(document["conversation"])
    assert provider.actor.observed[-1].output["issues"] == [issue]
    assert provider.calls == ["actor", "actor", "actor", "review"]


@pytest.mark.parametrize("max_calls", [3, 4])
async def test_no_review_slot_denies_cards_and_exactly_one_slot_admits_bound_success(
    max_calls: int,
) -> None:
    provider = ScriptedProvider([verdict()], catalog_turns(GOOD_IDS))
    result = await run_agent(provider, max_calls=max_calls)
    assert len(provider.calls) == max_calls
    if max_calls == 3:
        assert_hidden(result)
        assert provider.reviews == []
        assert provider.actor.observed[-1].output["error"] == "ANSWER_REVIEW_LIMIT"
    else:
        assert [card.product_id for card in result.products] == GOOD_IDS
        assert result.content == DRAFT
        assert all(step.status != "fallback" for step in result.steps)
        receipt = provider.actor.observed[-1]
        assert receipt.output["ok"] is True
        assert receipt.output["answer_review"] == {
            "candidate_id": provider.reviews[0].document["candidate_id"],
            "status": "supported",
        }


@pytest.mark.parametrize("failure", ["unavailable", "quota", "incomplete", "wrong_hash"])
async def test_failed_review_attempt_counts_and_never_retries_or_exposes_candidate(
    failure: str,
) -> None:
    scripts: dict[str, ReviewScript | ManagerModelUnavailableError] = {
        "unavailable": ManagerModelUnavailableError("Synthetic unavailable"),
        "quota": ManagerModelUnavailableError("Synthetic quota exhausted"),
        "incomplete": verdict(stop_reason="incomplete"),
        "wrong_hash": verdict(changes={"candidate_id": "sha256:" + "a" * 64}),
    }
    provider = ScriptedProvider([scripts[failure], verdict()], [*catalog_turns(), *catalog_turns()])
    result = await run_agent(provider, max_calls=10)
    assert_hidden(result)
    assert provider.calls == ["actor", "actor", "actor", "review"]
    assert len(provider.reviews) == 1
    assert provider.actor.observed[-1].output["error"] == "ANSWER_REVIEW_NOT_PASSED"


@pytest.mark.parametrize("supported", [True, False])
async def test_price_comparison_review_receives_current_exact_variant_arithmetic(
    supported: bool,
) -> None:
    answer = "The clear default set is $5 cheaper than the tall default set, before tax/shipping."
    turns = [
        catalog_turns()[0],
        tool_turn(
            "compare_catalog_prices",
            {"items": [{"product_id": key, "variant_id": f"{key}-default"} for key in GOOD_IDS]},
        ),
        tool_turn("select_catalog_products", {"product_ids": GOOD_IDS}),
        complete(answer, GOOD_IDS, kind="price_comparison"),
    ]
    provider = ScriptedProvider(
        [verdict() if supported else reject("incorrect_price_or_variant")], turns
    )
    result = await run_agent(provider, max_calls=5, max_tool_calls=3)
    assert provider.calls == ["actor", "actor", "actor", "actor", "review"]
    evidence = cast(list[JsonObject], provider.reviews[0].document["catalog_evidence"])
    assert [item["tool"] for item in evidence] == [
        "lookup_catalog_products",
        "compare_catalog_prices",
        "select_catalog_products",
    ]
    arithmetic = cast(JsonObject, evidence[1]["output"])
    items = cast(list[JsonObject], arithmetic["items"])
    assert arithmetic["price_spread_minor"] == 500
    assert arithmetic["currency"] == "USD"
    assert [item["product_id"] for item in items] == GOOD_IDS
    assert [item["variant_id"] for item in items] == [f"{key}-default" for key in GOOD_IDS]
    assert [item["difference_from_lowest_minor"] for item in items] == [0, 500]
    if supported:
        assert result.content == answer
        assert [card.product_id for card in result.products] == GOOD_IDS
        assert result.steps[-1].status == "completed"
    else:
        assert_hidden(result, answer)


@pytest.mark.parametrize("name", ["save_shopping_memory", "add_to_cart", "unknown_review"])
async def test_reviewer_cannot_dispatch_memory_cart_or_unknown_tools(name: str) -> None:
    save = AsyncMock()
    provider = ScriptedProvider([verdict(name=name)], catalog_turns())
    result = await run_agent(provider, max_calls=8, save_memory=save)
    assert_hidden(result)
    save.assert_not_awaited()
    assert "save_shopping_memory" in [tool.name for tool in provider.actor_tools]
    assert [tool.name for tool in provider.reviews[0].tools] == ["review_catalog_answer"]
    assert provider.review_sessions[0].observed[-1].is_error
    assert provider.calls == ["actor", "actor", "actor", "review"]


@pytest.mark.parametrize("max_calls", [4, 5, 6])
async def test_rejection_repairs_to_empty_selection_only_with_remaining_shared_budget(
    max_calls: int,
) -> None:
    answer = "No selected products meet every requested requirement."
    turns = [
        *catalog_turns(),
        tool_turn("select_catalog_products", {"product_ids": []}),
        complete(answer, []),
    ]
    provider = ScriptedProvider([reject()], turns)
    result = await run_agent(provider, max_calls=max_calls)
    assert len(provider.calls) == max_calls
    assert len(provider.reviews) == 1
    assert result.products == []
    if max_calls < 6:
        assert_hidden(result)
    else:
        assert result.content == answer
        assert all(step.status != "fallback" for step in result.steps)
        assert any(step.title == "Revise product selection" for step in result.steps)
        assert provider.actor.inputs[3][0].output["error"] == "ANSWER_REVIEW_NOT_PASSED"


@pytest.mark.parametrize("max_calls", [6, 7])
async def test_repaired_product_answer_needs_fresh_review_inside_same_call_cap(
    max_calls: int,
) -> None:
    repaired = "The clear and tall sets are dishwasher-safe; only these two are shown."
    turns = [
        *catalog_turns(),
        tool_turn("select_catalog_products", {"product_ids": GOOD_IDS}),
        complete(repaired, GOOD_IDS),
    ]
    provider = ScriptedProvider([reject(), verdict()], turns)
    result = await run_agent(provider, max_calls=max_calls)
    assert len(provider.calls) == max_calls
    if max_calls == 6:
        assert_hidden(result, repaired)
        assert len(provider.reviews) == 1
        assert provider.actor.observed[-1].output["error"] == "ANSWER_REVIEW_LIMIT"
    else:
        assert result.content == repaired
        assert [card.product_id for card in result.products] == GOOD_IDS
        assert len(provider.reviews) == 2
        assert (
            provider.reviews[0].document["candidate_id"]
            != (provider.reviews[1].document["candidate_id"])
        )
        assert all(step.status != "fallback" for step in result.steps)


@pytest.mark.parametrize("max_calls", [4, 5])
@pytest.mark.parametrize(
    "attempt", ["prose", "malformed_completion", "missing_receipts", "bad_tool"]
)
async def test_failed_and_prose_only_actor_attempts_consume_the_review_call_budget(
    max_calls: int, attempt: str
) -> None:
    first = {
        "prose": ManagerModelTurn(content="I will look that up.", phase="final_answer"),
        "malformed_completion": tool_turn("complete_shopping_turn", {"kind": "catalog"}),
        "missing_receipts": complete("Unverified product answer", GOOD_IDS),
        "bad_tool": tool_turn("lookup_catalog_products", {"queries": [], "product_ids": []}),
    }[attempt]
    provider = ScriptedProvider([verdict()], [first, *catalog_turns(GOOD_IDS)])
    result = await run_agent(provider, max_calls=max_calls)
    assert len(provider.calls) == max_calls
    assert len(provider.reviews) == max_calls - 4
    if max_calls == 4:
        assert_hidden(result)
    else:
        assert result.content == DRAFT
        assert [card.product_id for card in result.products] == GOOD_IDS


@pytest.mark.parametrize(
    "kind", ["conversation", "clarification", "refusal", "catalog", "memory", "activity", "blocked"]
)
async def test_ordinary_and_no_card_completions_do_not_start_review(kind: str) -> None:
    answer = "This is the scripted no-card answer."
    turns: list[TurnScript] = []
    save = AsyncMock(
        return_value=ShopperMemory(
            id=UUID(int=30), content="I prefer glass", created_at=datetime(2026, 10, 17, tzinfo=UTC)
        )
    )
    activity = AsyncMock(spec=ActivityTools)
    activity.execute.return_value = {"ok": True, "events": []}
    if kind in {"catalog", "refusal"}:
        turns = list(catalog_turns([] if kind == "catalog" else ALL_IDS)[:2])
    elif kind == "memory":
        turns.append(
            tool_turn(
                "save_shopping_memory",
                {"source_message_id": str(MESSAGE_ID), "preference": "I prefer glass"},
            )
        )
    elif kind == "activity":
        turns.append(tool_turn("inspect_shopping_activity", {}))
    elif kind == "blocked":
        turns.append(tool_turn("lookup_catalog_products", {"queries": [], "product_ids": []}))
    turns.append(complete(answer, [] if kind == "catalog" else None, kind=kind))
    provider = ScriptedProvider(turns=turns)
    result = await run_agent(
        provider, max_calls=len(turns), save_memory=save, activity_tools=activity
    )
    assert result.content == answer and result.products == []
    assert provider.reviews == []
    assert provider.calls == ["actor"] * len(turns)


@pytest.mark.parametrize("failure", ["revise", "quota", "no_slot", "repair_model_failure"])
async def test_review_failure_preserves_already_committed_memory(failure: str) -> None:
    memory = ShopperMemory(
        id=UUID(int=30), content="I prefer glass", created_at=datetime(2026, 10, 17, tzinfo=UTC)
    )
    saved = memory.model_dump()
    save = AsyncMock(return_value=memory)
    turns: list[TurnScript] = [
        tool_turn(
            "save_shopping_memory",
            {"source_message_id": str(MESSAGE_ID), "preference": memory.content},
        ),
        *catalog_turns(),
    ]
    script: ReviewScript | ManagerModelUnavailableError = (
        ManagerModelUnavailableError("Synthetic quota exhausted")
        if failure == "quota"
        else reject()
    )
    max_calls = 4 if failure == "no_slot" else 5
    if failure == "repair_model_failure":
        turns.append(ManagerModelUnavailableError("Synthetic repair failure"))
        max_calls = 6
    provider = ScriptedProvider([script], turns)
    result = await run_agent(provider, max_calls=max_calls, save_memory=save)
    assert_hidden(result)
    assert f"Saved to your shopping memory: {memory.content}" in result.content
    save.assert_awaited_once_with(
        SaveShoppingMemoryInput(source_message_id=MESSAGE_ID, preference=memory.content)
    )
    assert memory.model_dump() == saved
    assert len(provider.calls) == max_calls
    for request in provider.reviews:
        assert "save_shopping_memory" not in request.text
        assert str(memory.id) not in request.text
