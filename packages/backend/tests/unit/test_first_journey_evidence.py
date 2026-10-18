"""Offline terminal-receipt regressions using the real bounded shopper loop."""

import socket
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from tests.integration import test_first_journey as journey
from tests.shopper_review import supported_review_session

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
)
from open_commerce.core.redaction import redact_model_value
from open_commerce.core.types import JsonObject, canonical_hash, canonical_json, utc_now
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
from open_commerce.shopper_agent.answer_review import REVIEW_CATALOG_ANSWER
from open_commerce.shopper_agent.completion import COMPLETE_SHOPPING_TURN
from open_commerce.shopper_agent.model_agent import ShopperAgentOutcome, ShopperConversationalAgent
from open_commerce.shopper_agent.models import ShopperMessage, ShopperProductCard
from open_commerce.shopper_agent.product_tools import CatalogProductReader


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline evidence tests must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


class ScriptedProvider:
    provider_name = "offline-script"
    model_id = "synthetic"

    def __init__(
        self,
        turns: list[ManagerModelTurn],
        *,
        review_verdicts: list[Literal["supported", "revise"]] | None = None,
    ) -> None:
        self.turns = list(turns)
        self.deliveries: list[list[ManagerToolResult]] = []
        self.review_deliveries: list[list[ManagerToolResult]] = []
        self.review_verdicts = list(review_verdicts or [])

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
            deliveries = self.review_deliveries
            verdicts = self.review_verdicts
            review_session = review

            class Session:
                async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                    deliveries.append(tool_results)
                    turn = await review_session.next(tool_results)
                    if verdicts and verdicts.pop(0) == "revise":
                        turn.tool_calls[0].arguments.update(
                            verdict="revise", issues=["answer_card_mismatch"]
                        )
                    return turn

            return Session()
        return self

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.deliveries.append(tool_results)
        return self.turns.pop(0)


def call(identity: str, name: str, arguments: JsonObject) -> ManagerModelTurn:
    return ManagerModelTurn(
        tool_calls=[ManagerToolCall(call_id=identity, name=name, arguments=arguments)]
    )


def complete(identity: str, *, kind: str = "conversation") -> ManagerModelTurn:
    return call(
        identity,
        "complete_shopping_turn",
        {"kind": kind, "message": "Synthetic answer", "product_ids": None},
    )


async def respond(
    traced: journey.AlphaTraceProvider,
    iterations: int,
    content: str = "Synthetic request",
    *,
    catalog_reader: CatalogProductReader | None = None,
) -> ShopperAgentOutcome:
    return await ShopperConversationalAgent(
        provider=traced,
        catalog_search=CatalogSearchTool(None),
        max_iterations=iterations,
        max_tool_calls=6,
        max_output_tokens=1500,
        catalog_reader=catalog_reader,
    ).respond(
        tenant_id=UUID(int=1),
        content=content,
        history=[],
        memories=[],
        source="uploaded_catalog",
    )


def message(outcome: ShopperAgentOutcome) -> ShopperMessage:
    return ShopperMessage(
        id=UUID(int=2),
        conversation_id=UUID(int=3),
        role="assistant",
        content=outcome.content,
        products=outcome.products,
        steps=outcome.steps,
        created_at=utc_now(),
    )


@pytest.mark.parametrize("kind", ["conversation", "clarification", "refusal"])
async def test_accepted_terminal_receipt_exists_without_an_extra_provider_call(
    tmp_path: Path, kind: str
) -> None:
    provider = ScriptedProvider([complete("finish", kind=kind)])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 1)
    terminal = [e for e in traced.trace if e["kind"] == "terminal-tool-result"]
    assert len(terminal) == 1
    assert terminal[0]["payload"] == {
        "call_id": "finish",
        "name": "complete_shopping_turn",
        "output": {"ok": True, "kind": kind, "product_ids": None},
        "is_error": False,
    }
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert len(provider.deliveries) == 1
    assert provider.deliveries == [[]]


@pytest.mark.parametrize("malformed", [True, False])
async def test_rejected_final_iteration_keeps_actual_error_receipt(
    tmp_path: Path, malformed: bool
) -> None:
    turn = (
        call("finish", "complete_shopping_turn", {})
        if malformed
        else complete("finish", kind="catalog")
    )
    provider = ScriptedProvider([turn])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 1)
    assert outcome.products == []
    terminal = [e for e in traced.trace if e["kind"] == "terminal-tool-result"]
    assert len(terminal) == 1
    payload = terminal[0]["payload"]
    assert isinstance(payload, dict) and payload["is_error"] is True
    assert payload["output"]["error"] == (
        "INVALID_TOOL_ARGUMENTS" if malformed else "INCOMPLETE_SHOPPING_TURN"
    )
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert not journey._alpha_completed_model_response(traced.trace, message(outcome))
    if not malformed:
        assert payload["output"]["correction"]
    assert len(provider.deliveries) == 1


async def test_rejection_execution_and_delivery_agree_before_final_acceptance(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider([complete("reject", kind="catalog"), complete("finish")])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 2)
    terminals = [e for e in traced.trace if e["kind"] == "terminal-tool-result"]
    assert len(terminals) == 2
    rejected = cast(dict[str, Any], terminals[0]["payload"])
    assert rejected["output"]["correction"]
    assert rejected == provider.deliveries[1][0].model_dump(mode="json")
    assert terminals[0]["iteration"] == 1 and terminals[1]["iteration"] == 2
    assert len(provider.deliveries) == 2
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))


async def test_blocked_completion_requires_observed_real_failure(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [call("unknown", "unsupported_tool", {}), complete("blocked", kind="blocked")]
    )
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 2)
    assert outcome.steps[-1].status == "needs_input"
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert len(provider.deliveries) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "case",
        "session",
        "iteration",
        "call_id",
        "name",
        "error",
        "not_ok",
        "kind",
        "product_ids",
        "missing_product_ids",
        "invalid_arguments",
        "content",
        "cards",
        "status",
        "fallback",
    ],
)
async def test_acceptance_requires_exact_receipt_and_returned_response(
    tmp_path: Path, mutation: str
) -> None:
    traced = journey.AlphaTraceProvider(
        ScriptedProvider([complete("finish", kind="clarification")]),
        journey.AlphaEvidence(tmp_path),
    )
    outcome = await respond(traced, 1)
    visible = message(outcome)
    events = deepcopy(traced.trace)
    terminal = next(e for e in events if e["kind"] == "terminal-tool-result")
    result = cast(dict[str, Any], terminal["payload"])
    if mutation == "missing":
        events.remove(terminal)
    elif mutation == "duplicate":
        events.append(deepcopy(terminal))
    elif mutation in {"case", "session", "iteration"}:
        terminal[mutation] = "another"
    elif mutation in {"call_id", "name"}:
        result[mutation] = "another"
    elif mutation == "error":
        result["is_error"] = True
    elif mutation == "not_ok":
        result["output"]["ok"] = False
    elif mutation == "kind":
        result["output"]["kind"] = "conversation"
    elif mutation == "product_ids":
        result["output"]["product_ids"] = ["invented"]
    elif mutation == "missing_product_ids":
        del result["output"]["product_ids"]
    elif mutation == "invalid_arguments":
        turn = next(e for e in events if e["kind"] == "model-turn")
        cast(dict[str, Any], turn["payload"])["tool_calls"][0]["arguments"] = {}
    elif mutation == "content":
        visible.content = "Different response"
    elif mutation == "cards":
        # Even a well-formed accepted noncatalog receipt cannot authorize extra cards.
        visible.products = [
            ShopperProductCard(
                product_id="extra", title="Synthetic", price_minor=1, currency="USD", score="test"
            )
        ]
    elif mutation == "status":
        visible.steps[-1].status = "completed"
    elif mutation == "fallback":
        visible.steps[0].status = "fallback"
    assert not journey._alpha_completed_model_response(events, visible)


async def test_unconsumed_ordinary_call_and_bare_needs_input_still_fail(tmp_path: Path) -> None:
    traced = journey.AlphaTraceProvider(
        ScriptedProvider([call("ordinary", "unsupported_tool", {})]),
        journey.AlphaEvidence(tmp_path),
    )
    outcome = await respond(traced, 1)
    assert outcome.steps[-1].status == "needs_input"
    assert journey._alpha_receipt_gaps(traced.trace)
    assert not journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert not any(e["kind"] == "terminal-tool-result" for e in traced.trace)


async def test_provider_failure_does_not_discard_prior_terminal_rejection(tmp_path: Path) -> None:
    class FailingProvider(ScriptedProvider):
        async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
            if self.deliveries:
                raise ManagerModelUnavailableError("scripted offline failure")
            return await super().next(tool_results)

    traced = journey.AlphaTraceProvider(
        FailingProvider([complete("reject", kind="catalog")]), journey.AlphaEvidence(tmp_path)
    )
    with pytest.raises(ManagerModelUnavailableError):
        await respond(traced, 2)
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert len([e for e in traced.trace if e["kind"] == "terminal-tool-result"]) == 1
    assert traced.trace[-1]["kind"] == "provider-failure"


async def test_delivered_receipt_tampering_and_duplicate_calls_remain_gaps(tmp_path: Path) -> None:
    traced = journey.AlphaTraceProvider(
        ScriptedProvider([complete("reject", kind="catalog"), complete("finish")]),
        journey.AlphaEvidence(tmp_path),
    )
    await respond(traced, 2)
    events = deepcopy(traced.trace)
    delivered = next(e for e in events if e["kind"] == "tool-result")
    cast(dict[str, Any], delivered["payload"])["output"]["correction"] = "changed"
    assert "executed and delivered tool receipts disagree" in journey._alpha_receipt_gaps(events)
    events = deepcopy(traced.trace)
    events.append(next(e for e in events if e["kind"] == "model-turn"))
    assert "duplicate tool call/result identity" in journey._alpha_receipt_gaps(events)


async def test_session_binding_survives_reused_call_id_and_case_change(tmp_path: Path) -> None:
    traced = journey.AlphaTraceProvider(
        ScriptedProvider([complete("same"), complete("same")]), journey.AlphaEvidence(tmp_path)
    )
    first = traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)
    traced.case = "second"
    second = traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)
    for session in (first, second):
        await session.next([])
        cast(Any, session).observe_tool_result(
            ManagerToolResult(
                call_id="same",
                name="complete_shopping_turn",
                output={"ok": True, "kind": "conversation", "product_ids": None},
            )
        )
    terminals = [e for e in traced.trace if e["kind"] == "terminal-tool-result"]
    assert [(e["case"], e["session"]) for e in terminals] == [("unassigned", 1), ("second", 2)]
    assert not journey._alpha_receipt_gaps(traced.trace)
    with pytest.raises(AssertionError):
        cast(Any, first).observe_tool_result(
            ManagerToolResult(call_id="other", name="complete_shopping_turn", output={"ok": True})
        )


async def test_journey_trace_keeps_terminal_evidence_separate_from_deliveries() -> None:
    provider = ScriptedProvider([complete("finish")])
    traced = journey.SyntheticTraceProvider(provider)
    agent = ShopperConversationalAgent(
        provider=traced,
        catalog_search=CatalogSearchTool(None),
        max_iterations=1,
        max_tool_calls=6,
        max_output_tokens=1500,
    )
    await agent.respond(
        tenant_id=UUID(int=1),
        content="Synthetic request",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert len([e for e in traced.trace if "terminal_result" in e]) == 1
    assert not any("result" in e for e in traced.trace)
    assert provider.deliveries == [[]]


CARD_IDS = ["glass-clear", "glass-tall"]


def catalog_turns() -> list[ManagerModelTurn]:
    return [
        call("search", "catalog_search", {"query": "glass"}),
        call("select", "select_catalog_products", {"product_ids": CARD_IDS}),
        catalog_completion("finish", "These are the two selected products."),
    ]


def catalog_completion(
    identity: str, text: str, product_ids: list[str] | None = None
) -> ManagerModelTurn:
    return call(
        identity,
        "complete_shopping_turn",
        {
            "kind": "catalog",
            "message": text,
            "product_ids": CARD_IDS if product_ids is None else product_ids,
        },
    )


@pytest.fixture
def catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        CatalogSearchTool,
        "run",
        AsyncMock(
            return_value={
                "ok": True,
                "result_count": 2,
                "results": [
                    ShopperProductCard(
                        product_id=key,
                        title=f"Synthetic {key}",
                        price_minor=1999,
                        currency="USD",
                        score="fixture",
                    ).model_dump(mode="json")
                    for key in CARD_IDS
                ],
            }
        ),
    )


@pytest.fixture
async def reviewed_answer(
    catalog: None, tmp_path: Path
) -> tuple[ShopperAgentOutcome, journey.AlphaTraceProvider, ScriptedProvider]:
    provider = ScriptedProvider(catalog_turns())
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    # Exercise a multi-part context without relying on real or private shopper data.
    outcome = await respond(traced, 4, "Synthetic request " + "context " * 450)
    return outcome, traced, provider


def numbered_messages(document: dict[str, Any]) -> list[ManagerModelMessage]:
    encoded = canonical_json(document)
    chunks = [encoded[index : index + 3600] for index in range(0, len(encoded), 3600)]
    return [
        ManagerModelMessage(
            role="user", content=f"Review input part {i + 1}/{len(chunks)}:\n{part}"
        )
        for i, part in enumerate(chunks)
    ]


def begin_review(traced: journey.AlphaTraceProvider) -> ManagerModelSession:
    payload = {
        "conversation": [],
        "preferences": [],
        "candidate": {"kind": "catalog", "message": "Synthetic", "product_ids": CARD_IDS},
        "catalog_evidence": [],
    }
    return traced.begin(
        instructions="Offline budget fixture",
        messages=numbered_messages({"candidate_id": canonical_hash(payload), **payload}),
        tools=[REVIEW_CATALOG_ANSWER],
        max_output_tokens=1500,
        require_tool=True,
    )


async def test_reviewed_completion_binds_inputs_verdict_and_receipts(
    reviewed_answer: tuple[ShopperAgentOutcome, journey.AlphaTraceProvider, ScriptedProvider],
) -> None:
    outcome, traced, provider = reviewed_answer
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert [card.product_id for card in outcome.products] == CARD_IDS
    assert traced.sessions == 2 and traced.shopper_turns == 1
    assert traced.turn_requests == {1: 4} and traced.turn_calls == {1: 4}
    assert len(provider.deliveries) == 3 and provider.review_deliveries == [[]]
    review_begin = next(e for e in traced.trace if e["kind"] == "begin" and e["mode"] == "reviewer")
    inputs = cast(dict[str, Any], review_begin["payload"])
    assert len(inputs["messages"]) > 1
    document = journey._alpha_review_document(inputs)
    assert document is not None
    assert document["candidate"]["message"] == outcome.content
    assert document["candidate_id"] == canonical_hash(
        {key: value for key, value in document.items() if key != "candidate_id"}
    )
    main_receipt = next(e for e in traced.trace if e["kind"] == "terminal-tool-result")
    review_receipt = next(e for e in traced.trace if e["kind"] == "review-tool-result")
    assert (main_receipt["iteration"], main_receipt["request"]) == (3, 3)
    assert (review_receipt["iteration"], review_receipt["request"]) == (1, 4)
    output = cast(dict[str, Any], review_receipt["payload"])["output"]
    assert set(output) == {"ok", "status", "candidate_id", "product_ids"}


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_binding",
        "binding_status",
        "binding_id",
        "missing_begin",
        "admitted_only",
        "missing_review_receipt",
        "delivered_only",
        "duplicate_review_receipt",
        "review_case",
        "review_session",
        "review_iteration",
        "review_request",
        "review_turn",
        "review_mode",
        "receipt_id",
        "receipt_ids",
        "receipt_ok",
        "receipt_error",
        "receipt_status",
        "receipt_prose",
        "verdict_id",
        "verdict_ids",
        "verdict_issues",
        "verdict_revise",
        "verdict_extra",
        "wrong_tool",
        "incomplete",
        "main_text",
        "main_ids",
        "document_hash",
        "document_text",
        "document_context",
        "document_evidence",
        "chunk_order",
        "chunk_number",
        "chunk_total",
        "chunk_missing",
        "chunk_role",
        "chunk_invalid_json",
        "chunk_duplicate_key",
        "tools",
        "require_tool",
        "tokens",
        "receipt_before_review",
    ],
)
async def test_review_evidence_cannot_be_forged_or_reused(
    reviewed_answer: tuple[ShopperAgentOutcome, journey.AlphaTraceProvider, ScriptedProvider],
    mutation: str,
) -> None:
    outcome, traced, _ = reviewed_answer
    events = deepcopy(traced.trace)
    visible = message(outcome)
    begin = next(e for e in events if e["kind"] == "begin" and e["mode"] == "reviewer")
    review = next(e for e in events if e["kind"] == "model-turn" and e["mode"] == "reviewer")
    review_receipt = next(e for e in events if e["kind"] == "review-tool-result")
    main_receipt = next(e for e in events if e["kind"] == "terminal-tool-result")
    main = next(
        e
        for e in events
        if e["kind"] == "model-turn" and e["mode"] == "main" and e["iteration"] == 3
    )
    inputs = cast(dict[str, Any], begin["payload"])
    review_turn = cast(dict[str, Any], review["payload"])
    verdict = review_turn["tool_calls"][0]["arguments"]
    receipt = cast(dict[str, Any], review_receipt["payload"])
    completion = cast(dict[str, Any], main_receipt["payload"])["output"]
    wrong_id = "sha256:" + "0" * 64
    if mutation == "missing_binding":
        del completion["answer_review"]
    elif mutation in {"binding_status", "binding_id"}:
        completion["answer_review"][
            "status" if mutation == "binding_status" else "candidate_id"
        ] = "revise" if mutation == "binding_status" else wrong_id
    elif mutation == "missing_begin":
        events.remove(begin)
    elif mutation == "admitted_only":
        events.remove(review)
        events.remove(review_receipt)
    elif mutation == "missing_review_receipt":
        events.remove(review_receipt)
    elif mutation == "delivered_only":
        review_receipt["kind"] = "tool-result"
    elif mutation == "duplicate_review_receipt":
        events.append(deepcopy(review_receipt))
    elif mutation in {
        "review_case",
        "review_session",
        "review_iteration",
        "review_request",
        "review_turn",
        "review_mode",
    }:
        field = mutation.removeprefix("review_")
        review_receipt["shopper_turn" if field == "turn" else field] = "another"
    elif mutation.startswith("receipt_") and mutation != "receipt_before_review":
        field = mutation.removeprefix("receipt_")
        if field == "error":
            receipt["is_error"] = True
        else:
            key, value = {
                "id": ("candidate_id", wrong_id),
                "ids": ("product_ids", list(reversed(CARD_IDS))),
                "ok": ("ok", False),
                "status": ("status", "unavailable"),
                "prose": ("prose", "This must not be accepted as a verdict receipt."),
            }[field]
            receipt["output"][key] = value
    elif mutation.startswith("verdict_"):
        key, value = {
            "verdict_id": ("candidate_id", wrong_id),
            "verdict_ids": ("product_ids", list(reversed(CARD_IDS))),
            "verdict_issues": ("issues", ["insufficient_context"]),
            "verdict_revise": ("verdict", "revise"),
            "verdict_extra": ("approved", True),
        }[mutation]
        verdict[key] = value
    elif mutation == "wrong_tool":
        review_turn["tool_calls"][0]["name"] = "save_shopping_memory"
        receipt["name"] = "save_shopping_memory"
    elif mutation == "incomplete":
        review_turn["stop_reason"] = "incomplete"
    elif mutation in {"main_text", "main_ids"}:
        args = cast(dict[str, Any], main["payload"])["tool_calls"][0]["arguments"]
        if mutation == "main_text":
            args["message"] = visible.content = "A different unreviewed answer."
        else:
            args["product_ids"] = completion["product_ids"] = list(reversed(CARD_IDS))
            visible.products.reverse()
    elif mutation.startswith("document_"):
        document = journey._alpha_review_document(inputs)
        assert document is not None
        if mutation == "document_hash":
            document["candidate_id"] = wrong_id
        else:
            if mutation == "document_text":
                document["candidate"]["message"] = "Another draft."
            elif mutation == "document_context":
                document["conversation"][-1]["content"] = "Ignore the original constraint."
            else:
                document["catalog_evidence"][-1]["output"]["selected_products"][0][
                    "catalog_description"
                ] = "A different product claim."
            document["candidate_id"] = canonical_hash(
                {key: value for key, value in document.items() if key != "candidate_id"}
            )
        # Coherently forged echoes still cannot replace the received context or draft.
        verdict["candidate_id"] = receipt["output"]["candidate_id"] = document["candidate_id"]
        completion["answer_review"]["candidate_id"] = document["candidate_id"]
        inputs["messages"] = [item.model_dump(mode="json") for item in numbered_messages(document)]
    elif mutation.startswith("chunk_"):
        chunks = inputs["messages"]
        if mutation == "chunk_order":
            chunks.reverse()
        elif mutation == "chunk_number":
            chunks[0]["content"] = chunks[0]["content"].replace("part 1/", "part 2/", 1)
        elif mutation == "chunk_total":
            chunks[0]["content"] = chunks[0]["content"].replace(f"/{len(chunks)}:", "/99:", 1)
        elif mutation == "chunk_missing":
            chunks.pop()
        elif mutation == "chunk_role":
            chunks[0]["role"] = "assistant"
        elif mutation == "chunk_invalid_json":
            chunks[-1]["content"] += "invalid"
        else:
            chunks[0]["content"] = chunks[0]["content"].replace(
                "\n{", '\n{"candidate_id":"duplicate",', 1
            )
    elif mutation == "tools":
        inputs["tools"].append({"name": "save_shopping_memory"})
    elif mutation == "require_tool":
        inputs["require_tool"] = False
    elif mutation == "tokens":
        inputs["max_output_tokens"] = 3000
    elif mutation == "receipt_before_review":
        events.remove(review_receipt)
        events.insert(events.index(review), review_receipt)
    else:
        raise AssertionError(mutation)
    assert not journey._alpha_completed_model_response(events, visible)


@pytest.mark.parametrize("empty", [True, False])
async def test_rejected_review_can_recover_within_the_combined_budget(
    catalog: None, tmp_path: Path, empty: bool
) -> None:
    turns = catalog_turns()
    if empty:
        turns.extend(
            [
                call("retract", "select_catalog_products", {"product_ids": []}),
                catalog_completion("corrected", "No suitable products were confirmed.", []),
            ]
        )
    else:
        turns.append(catalog_completion("corrected", "Here is the corrected product explanation."))
    provider = ScriptedProvider(turns, review_verdicts=["revise", "supported"])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 6)
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert not any(step.status == "fallback" for step in outcome.steps)
    assert outcome.content == turns[-1].tool_calls[0].arguments["message"]
    assert [card.product_id for card in outcome.products] == ([] if empty else CARD_IDS)
    assert traced.turn_requests == {1: 6}
    assert len(provider.deliveries) + len(provider.review_deliveries) == 6
    receipts = [e for e in traced.trace if e["kind"] == "review-tool-result"]
    assert len(receipts) == (1 if empty else 2)
    assert cast(dict[str, Any], receipts[0]["payload"])["output"]["status"] == "revise"
    if not empty:
        old = cast(dict[str, Any], receipts[0]["payload"])["output"]["candidate_id"]
        new = cast(dict[str, Any], receipts[1]["payload"])["output"]["candidate_id"]
        assert old != new


async def test_completion_without_room_for_review_is_not_accepted(
    catalog: None, tmp_path: Path
) -> None:
    provider = ScriptedProvider(catalog_turns())
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 3)
    assert outcome.products == []
    assert not journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert provider.review_deliveries == [] and traced.turn_requests == {1: 3}
    assert not journey._alpha_receipt_gaps(traced.trace)


async def test_four_shopper_turns_can_each_have_a_review_session(
    catalog: None, tmp_path: Path
) -> None:
    provider = ScriptedProvider([turn for _ in range(4) for turn in catalog_turns()])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    for index in range(4):
        traced.case = f"case-{index}"
        start = len(traced.trace)
        outcome = await respond(traced, 6)
        assert journey._alpha_completed_model_response(traced.trace[start:], message(outcome))
    assert traced.shopper_turns == 4 and traced.sessions == 8
    assert traced.turn_requests == dict.fromkeys(range(1, 5), 4)
    assert len(provider.deliveries) == 12 and len(provider.review_deliveries) == 4
    with pytest.raises(AssertionError, match="session cap"):
        traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)


@pytest.mark.parametrize("fresh_sessions", [True, False])
async def test_review_requests_cannot_reset_the_shared_six_request_limit(
    tmp_path: Path, fresh_sessions: bool
) -> None:
    provider = ScriptedProvider([ManagerModelTurn(content="Synthetic") for _ in range(6)])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    main = traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)
    for _ in range(1 if fresh_sessions else 5):
        await main.next([])
    for _ in range(5 if fresh_sessions else 1):
        await begin_review(traced).next([])
    assert traced.turn_requests == {1: 6}
    assert len(provider.deliveries) + len(provider.review_deliveries) == 6
    with pytest.raises(AssertionError, match="iteration cap"):
        await main.next([])
    with pytest.raises(AssertionError, match="iteration cap"):
        begin_review(traced)


async def test_one_request_per_review_and_no_mixed_tool_privileges(tmp_path: Path) -> None:
    traced = journey.AlphaTraceProvider(ScriptedProvider([]), journey.AlphaEvidence(tmp_path))
    with pytest.raises(AssertionError, match="active shopper turn"):
        begin_review(traced)
    traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)
    reviewer = begin_review(traced)
    await reviewer.next([])
    with pytest.raises(AssertionError, match="one request per review"):
        await reviewer.next([])
    assert traced.turn_requests == {1: 1}
    with pytest.raises(AssertionError, match="only the review schema"):
        traced.begin(
            instructions="",
            messages=[],
            tools=[REVIEW_CATALOG_ANSWER, COMPLETE_SHOPPING_TURN],
            max_output_tokens=1500,
        )


async def test_review_provider_failure_is_charged_before_the_attempt(tmp_path: Path) -> None:
    class FailingReviewProvider(ScriptedProvider):
        def begin(
            self,
            *,
            instructions: str,
            messages: list[ManagerModelMessage],
            tools: list[ManagerToolDefinition],
            max_output_tokens: int,
            require_tool: bool = False,
        ) -> ManagerModelSession:
            if tools == [REVIEW_CATALOG_ANSWER]:

                class Session:
                    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
                        raise ManagerModelUnavailableError("Synthetic failure")

                return Session()
            return super().begin(
                instructions=instructions,
                messages=messages,
                tools=tools,
                max_output_tokens=max_output_tokens,
                require_tool=require_tool,
            )

    provider = FailingReviewProvider([ManagerModelTurn(content="Synthetic") for _ in range(5)])
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    main = traced.begin(instructions="", messages=[], tools=[], max_output_tokens=1500)
    for _ in range(5):
        await main.next([])
    with pytest.raises(ManagerModelUnavailableError):
        await begin_review(traced).next([])
    assert traced.turn_requests == {1: 6}
    assert traced.trace[-1]["kind"] == "provider-failure"
    assert traced.trace[-1]["mode"] == "reviewer"
    with pytest.raises(AssertionError, match="iteration cap"):
        await main.next([])


def test_review_runtime_is_in_the_source_hash_manifest() -> None:
    path = "packages/backend/src/open_commerce/shopper_agent/answer_review.py"
    assert path in journey._ALPHA_SOURCE_PATHS
    assert path in journey._alpha_sources()


def test_review_document_hash_uses_redacted_strings_without_changing_numbers() -> None:
    payload = cast(
        dict[str, Any],
        redact_model_value(
            {
                "conversation": [{"role": "user", "content": "Synthetic person@example.com"}],
                "preferences": [],
                "candidate": {"kind": "catalog", "message": "Synthetic", "product_ids": CARD_IDS},
                "catalog_evidence": [
                    {
                        "tool": "select_catalog_products",
                        "output": {
                            "ok": True,
                            "selected_products": [
                                {"product_id": CARD_IDS[0], "price_minor": 12345678901}
                            ],
                        },
                    }
                ],
            }
        ),
    )
    document = {"candidate_id": canonical_hash(payload), **payload}
    inputs = {"messages": [item.model_dump(mode="json") for item in numbered_messages(document)]}
    assert "person@example.com" not in canonical_json(inputs)
    parsed = journey._alpha_review_document(inputs)
    assert parsed == document
    assert (
        parsed["catalog_evidence"][0]["output"]["selected_products"][0]["price_minor"]
        == 12345678901
    )


async def test_repaired_candidate_without_second_review_still_fails(
    catalog: None, tmp_path: Path
) -> None:
    provider = ScriptedProvider(
        [*catalog_turns(), catalog_completion("corrected", "Corrected but not reviewed.")],
        review_verdicts=["revise", "supported"],
    )
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 5)
    assert traced.turn_requests == {1: 5} and len(provider.review_deliveries) == 1
    assert outcome.products == [] and outcome.content != "Corrected but not reviewed."
    assert not journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert not journey._alpha_receipt_gaps(traced.trace)
    assert outcome.steps[-1].status == "fallback"


async def test_synthetic_trace_retains_review_receipts_without_extra_delivery(
    catalog: None,
) -> None:
    provider = ScriptedProvider(catalog_turns())
    traced = journey.SyntheticTraceProvider(provider)
    agent = ShopperConversationalAgent(
        provider=traced,
        catalog_search=CatalogSearchTool(None),
        max_iterations=4,
        max_tool_calls=6,
        max_output_tokens=1500,
    )
    outcome = await agent.respond(
        tenant_id=UUID(int=1),
        content="Synthetic request",
        history=[],
        memories=[],
        source="uploaded_catalog",
    )
    assert [card.product_id for card in outcome.products] == CARD_IDS
    assert len([event for event in traced.trace if "review_result" in event]) == 1
    assert len([event for event in traced.trace if "terminal_result" in event]) == 1
    assert all(event["mode"] == "reviewer" for event in traced.trace if "review_result" in event)
    assert len(provider.deliveries) == 3 and provider.review_deliveries == [[]]


@pytest.mark.parametrize("refresh", [None, "search", "lookup", "reselect", "recompare"])
async def test_review_binds_lookup_and_arithmetic_receipts(
    catalog: None, tmp_path: Path, refresh: str | None
) -> None:
    products = {
        key: CatalogBrowseProduct.model_validate(
            {
                "product_id": key,
                "title": f"Synthetic {key}",
                "description": "Synthetic glassware.",
                "brand": None,
                "category": "",
                "image_url": None,
                "variant_id": f"{key}-variant",
                "price": {"amount_minor": price, "currency": "USD"},
                "availability": "available",
                "provenance": None,
                "variants": [
                    {
                        "id": f"{key}-variant",
                        "title": "Default",
                        "options": {},
                        "price": {"amount_minor": price, "currency": "USD"},
                        "available": True,
                        "availability": "available",
                    }
                ],
            }
        )
        for key, price in zip(CARD_IDS, [1999, 2499], strict=True)
    }

    async def browse(*, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        assert tenant_id == UUID(int=1) and query.product_id in products
        return CatalogBrowseResponse.model_validate(
            {
                "catalog": {
                    "id": UUID(int=20),
                    "filename": "synthetic.csv",
                    "source_version": "fixture",
                    "product_count": 2,
                    "published_at": None,
                },
                "indexing": {},
                "categories": [],
                "items": [products[query.product_id]],
                "total": 1,
                "offset": 0,
                "limit": 1,
            }
        )

    reader = AsyncMock()
    reader.browse.side_effect = browse
    finish = catalog_completion("finish", "The tall glasses cost USD 5.00 more.")
    finish.tool_calls[0].arguments["kind"] = "price_comparison"
    followup = []
    if refresh in {"search", "lookup"}:
        finish = catalog_completion("finish", "Here are the freshly read products.")
        followup = [
            call("refresh", "catalog_search", {"query": "glass"})
            if refresh == "search"
            else call(
                "refresh", "lookup_catalog_products", {"queries": [], "product_ids": CARD_IDS}
            )
        ]
    elif refresh == "reselect":
        followup = [call("refresh", "select_catalog_products", {"product_ids": CARD_IDS})]
    elif refresh == "recompare":
        followup = [
            call(
                "refresh",
                "compare_catalog_prices",
                {"items": [{"product_id": key} for key in CARD_IDS]},
            )
        ]
    provider = ScriptedProvider(
        [
            call("lookup", "lookup_catalog_products", {"queries": [], "product_ids": CARD_IDS}),
            call(
                "compare",
                "compare_catalog_prices",
                {"items": [{"product_id": key} for key in CARD_IDS]},
            ),
            *followup,
            catalog_turns()[1],
            finish,
        ]
    )
    traced = journey.AlphaTraceProvider(provider, journey.AlphaEvidence(tmp_path))
    outcome = await respond(traced, 6, catalog_reader=reader)
    assert journey._alpha_completed_model_response(traced.trace, message(outcome))
    assert traced.turn_requests == {1: 5 + bool(refresh)}
    assert len(provider.review_deliveries) == 1
    expected_evidence = {"select_catalog_products"}
    if refresh != "search":
        expected_evidence.add("lookup_catalog_products")
    if refresh in {None, "reselect", "recompare"}:
        expected_evidence.add("compare_catalog_prices")
    actual_begin = next(e for e in traced.trace if e["kind"] == "begin" and e["mode"] == "reviewer")
    actual = journey._alpha_review_document(cast(dict[str, Any], actual_begin["payload"]))
    assert actual is not None
    assert {item["tool"] for item in actual["catalog_evidence"]} == expected_evidence
    # A coherent hash/verdict cannot rescue a later failed execution receipt.
    for failed_name in sorted(expected_evidence - {"lookup_catalog_products"}):
        events = deepcopy(traced.trace)
        previous = next(
            event
            for event in reversed(events)
            if event["kind"] == "tool-result"
            and cast(dict[str, Any], event["payload"])["name"] == failed_name
        )
        cast(dict[str, Any], previous["payload"]).update(
            output={"ok": False, "error": "SYNTHETIC_FAILURE"},
            is_error=True,
        )
        begin = next(e for e in events if e["kind"] == "begin" and e["mode"] == "reviewer")
        inputs = cast(dict[str, Any], begin["payload"])
        document = journey._alpha_review_document(inputs)
        assert document is not None
        document["catalog_evidence"] = [
            item for item in document["catalog_evidence"] if item["tool"] != failed_name
        ]
        candidate_id = document["candidate_id"] = canonical_hash(
            {key: value for key, value in document.items() if key != "candidate_id"}
        )
        inputs["messages"] = [item.model_dump(mode="json") for item in numbered_messages(document)]
        for event in events:
            payload = cast(dict[str, Any], event["payload"])
            if event["kind"] == "model-turn" and event["mode"] == "reviewer":
                payload["tool_calls"][0]["arguments"]["candidate_id"] = candidate_id
            elif event["kind"] == "review-tool-result":
                payload["output"]["candidate_id"] = candidate_id
            elif event["kind"] == "terminal-tool-result":
                payload["output"]["answer_review"]["candidate_id"] = candidate_id
        assert not journey._alpha_receipt_gaps(events)
        assert not journey._alpha_completed_model_response(events, message(outcome)), failed_name
    for name in sorted(expected_evidence - {"select_catalog_products"}):
        events = deepcopy(traced.trace)
        begin = next(e for e in events if e["kind"] == "begin" and e["mode"] == "reviewer")
        inputs = cast(dict[str, Any], begin["payload"])
        document = journey._alpha_review_document(inputs)
        assert document is not None
        evidence = {item["tool"]: item["output"] for item in document["catalog_evidence"]}
        assert set(evidence) == expected_evidence
        if name == "lookup_catalog_products":
            evidence[name]["groups"][0]["products"][0]["description"] = "Changed claim."
        else:
            assert evidence[name]["price_spread_minor"] == 500
            evidence[name]["price_spread_minor"] = 1
        candidate_id = document["candidate_id"] = canonical_hash(
            {key: value for key, value in document.items() if key != "candidate_id"}
        )
        inputs["messages"] = [item.model_dump(mode="json") for item in numbered_messages(document)]
        for event in events:
            payload = cast(dict[str, Any], event["payload"])
            if event["kind"] == "model-turn" and event["mode"] == "reviewer":
                payload["tool_calls"][0]["arguments"]["candidate_id"] = candidate_id
            elif event["kind"] == "review-tool-result":
                payload["output"]["candidate_id"] = candidate_id
            elif event["kind"] == "terminal-tool-result":
                payload["output"]["answer_review"]["candidate_id"] = candidate_id
        assert not journey._alpha_completed_model_response(events, message(outcome))
