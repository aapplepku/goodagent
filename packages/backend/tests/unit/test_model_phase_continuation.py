"""Offline phase-continuation regressions using only an in-process transport."""

import json
from typing import Literal, cast
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from open_commerce.core.types import JsonObject
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_agent import ModelBackedManagerAgent
from open_commerce.manager_agent.model_provider import (
    CheckpointedManagerSession,
    ManagerModelMessage,
    ManagerToolResult,
)
from open_commerce.manager_agent.models import ManagerAgentCapabilities, ManagerWorkingMemory
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.search.agent_tools import CatalogSearchTool
from open_commerce.shopper_agent.model_agent import ShopperConversationalAgent


def _message(phase: Literal["commentary", "final_answer"], text: str) -> JsonObject:
    return {
        "type": "message",
        "id": f"message-{phase}",
        "role": "assistant",
        "phase": phase,
        "content": [{"type": "output_text", "text": text}],
    }


def _tool_then_commentary() -> list[JsonObject]:
    return [
        {
            "output": [
                {
                    "type": "function_call",
                    "call_id": "inspect-1",
                    "name": "inspect_discovery_capabilities",
                    "arguments": "{}",
                }
            ]
        },
        {
            "output": [
                {
                    "type": "reasoning",
                    "id": "reasoning-1",
                    "encrypted_content": "synthetic-opaque-continuation",
                    "summary": [],
                    "content": [{"type": "reasoning_text", "text": "synthetic private trace"}],
                },
                _message("commentary", "I will explain the observed capabilities."),
            ]
        },
        {"output": [_message("final_answer", "The read-only inspection is complete.")]},
    ]


class ScriptedResponses:
    def __init__(self, responses: list[JsonObject]) -> None:
        self.responses = responses
        self.requests: list[JsonObject] = []
        self.admissions: list[tuple[int, int]] = []
        self.events: list[str] = []
        self.deny_call: int | None = None

    async def admit(self, input_bytes: int, output_tokens: int) -> None:
        self.admissions.append((input_bytes, output_tokens))
        self.events.append("admit")
        if len(self.admissions) == self.deny_call:
            raise ManagerModelUnavailableError("Synthetic admission limit")

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert self.events == ["admit", "request"] * len(self.requests) + ["admit"]
        self.events.append("request")
        self.requests.append(json.loads(request.content))
        assert len(self.requests) <= len(self.responses), "Unexpected continuation or retry"
        return httpx.Response(
            200, json={"status": "completed", **self.responses[len(self.requests) - 1]}
        )

    def provider(self) -> OpenAIManagerProvider:
        return OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="phase-test-model",
            base_url="https://phase-test.invalid/v1",
            max_input_bytes=100_000,
            transport=httpx.MockTransport(self.handle),
            usage_guard=self.admit,
        )


@pytest.mark.parametrize("restore", [False, True])
async def test_tool_result_then_commentary_replays_each_item_once(restore: bool) -> None:
    scripted = ScriptedResponses(_tool_then_commentary())
    provider = scripted.provider()
    session = provider.begin(
        instructions="Inspect only.",
        messages=[ManagerModelMessage(role="user", content="Check")],
        tools=[],
        max_output_tokens=800,
    )
    assert (await session.next([])).tool_calls[0].call_id == "inspect-1"
    receipt = ManagerToolResult(
        call_id="inspect-1", name="inspect_discovery_capabilities", output={"read_only": True}
    )
    assert (await session.next([receipt])).phase == "commentary"
    assert isinstance(session, CheckpointedManagerSession)
    saved = cast(JsonObject, json.loads(json.dumps(session.export_checkpoint())))
    assert "synthetic private trace" not in json.dumps(saved)
    if restore:
        session = provider.begin(
            instructions="Recreated context", messages=[], tools=[], max_output_tokens=800
        )
        assert isinstance(session, CheckpointedManagerSession)
        session.restore_checkpoint(saved)

    final = await session.next([])
    assert final.phase == "final_answer"
    assert final.content == "The read-only inspection is complete."
    original = [{"role": "user", "content": "Check"}]
    tool_output = cast(list[JsonObject], scripted.responses[0]["output"])
    expected_receipt = {
        "type": "function_call_output",
        "call_id": "inspect-1",
        "output": '{"read_only":true}',
    }
    after_tool = [*original, *tool_output, expected_receipt]
    assert scripted.requests[0]["input"] == original
    assert scripted.requests[1]["input"] == after_tool
    assert scripted.requests[2]["input"] == [
        *after_tool,
        {
            "type": "reasoning",
            "id": "reasoning-1",
            "encrypted_content": "synthetic-opaque-continuation",
            "summary": [],
        },
        _message("commentary", "I will explain the observed capabilities."),
    ]
    assert all(payload["instructions"] == "Inspect only." for payload in scripted.requests)
    assert scripted.admissions == [
        (len(json.dumps(payload, separators=(",", ":")).encode()), 800)
        for payload in scripted.requests
    ]
    assert scripted.events == ["admit", "request"] * 3


class WorkerInterrupted(Exception):
    """Simulate a worker stopping after its checkpoint is persisted."""


class MemoryJournal:
    run_id = UUID(int=1)
    token = UUID(int=2)

    def __init__(self, checkpoint: JsonObject | None = None) -> None:
        self.checkpoint = cast(JsonObject, json.loads(json.dumps(checkpoint or {})))
        self.interrupt_after_commentary = checkpoint is None
        self.interrupt_before_tool = False
        self.events: list[tuple[str, str | None]] = []

    async def check(self) -> None:
        pass

    async def save(self, checkpoint: JsonObject) -> None:
        # Match durable JSON storage, not mutable references to live session lists.
        self.checkpoint = cast(JsonObject, json.loads(json.dumps(checkpoint)))
        if self.interrupt_before_tool and checkpoint.get("call") is not None:
            raise WorkerInterrupted
        provider = cast(JsonObject, checkpoint["provider"])
        output = cast(list[JsonObject], provider["output"])
        if (
            self.interrupt_after_commentary
            and checkpoint["iteration"] == 2
            and any(item.get("phase") == "commentary" for item in output)
        ):
            raise WorkerInterrupted

    async def event(self, kind: str, title: str, detail: str, tool: str | None = None) -> None:
        self.events.append((kind, tool))


def _manager(provider: OpenAIManagerProvider, max_iterations: int) -> ModelBackedManagerAgent:
    return ModelBackedManagerAgent(
        provider=provider,
        capabilities=ManagerAgentCapabilities(
            semantic_backend="test",
            learned_semantics=False,
            conversation_provider=provider.provider_name,
            conversation_model=provider.model_id,
            model_backed=True,
        ),
        max_iterations=max_iterations,
        max_tool_calls=1,
        max_output_tokens=800,
    )


@pytest.mark.parametrize("alteration", ["none", "legacy", "status", "call", "hash", "extra"])
async def test_pending_tool_resume_requires_bound_completion_admission(alteration: str) -> None:
    responses = [_tool_then_commentary()[0], _tool_then_commentary()[2]]
    scripted = ScriptedResponses(responses)
    journal = MemoryJournal()
    journal.interrupt_after_commentary = False
    journal.interrupt_before_tool = True
    with pytest.raises(WorkerInterrupted):
        await _manager(scripted.provider(), 2).respond(
            content="Inspect capabilities",
            working=ManagerWorkingMemory(),
            memories=[],
            recent_messages=[],
            journal=journal,
        )
    saved = journal.checkpoint
    assert saved["call"] is not None and saved["call_admission"] is not None
    assert not any(kind.startswith("tool_") for kind, _ in journal.events)
    admission = cast(JsonObject, saved["call_admission"])
    call = cast(JsonObject, saved["call"])
    if alteration == "legacy":
        del saved["call_admission"]
    elif alteration == "status":
        admission["stop_reason"] = "incomplete"
    elif alteration == "call":
        call["call_id"] = "changed-call"
    elif alteration == "hash":
        admission["call_sha256"] = "sha256:" + "0" * 64
    elif alteration == "extra":
        admission["unvalidated"] = True
    resumed = MemoryJournal(saved)
    result = await _manager(scripted.provider(), 2).respond(
        content="Inspect capabilities",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        journal=resumed,
    )
    if alteration == "none":
        assert result.content == "The read-only inspection is complete."
        assert resumed.checkpoint["call"] is None
        assert resumed.checkpoint["call_admission"] is None
        assert [kind for kind, _ in resumed.events].count("tool_result") == 1
        assert len(scripted.requests) == 2
    else:
        assert "unverified saved tool request" in result.content
        assert not any(kind.startswith("tool_") for kind, _ in resumed.events)
        assert not any(step.stage == "act" for step in result.steps)
        assert len(scripted.requests) == 1
        assert resumed.checkpoint == saved


@pytest.mark.parametrize("resume_mode", ["finish", "exhausted", "denied"])
async def test_manager_commentary_checkpoint_resume_preserves_receipt_and_budget(
    resume_mode: Literal["finish", "exhausted", "denied"],
) -> None:
    scripted = ScriptedResponses(_tool_then_commentary())
    max_iterations = 2 if resume_mode == "exhausted" else 3
    first_journal = MemoryJournal()
    with pytest.raises(WorkerInterrupted):
        await _manager(scripted.provider(), max_iterations).respond(
            content="Inspect capabilities",
            working=ManagerWorkingMemory(),
            memories=[],
            recent_messages=[],
            journal=first_journal,
        )
    saved = first_journal.checkpoint
    assert saved["iteration"] == 2
    assert saved["tool_calls"] == 1
    assert saved["call"] is None
    assert saved["results"] == []
    provider_state = cast(JsonObject, saved["provider"])
    assert provider_state["input"] == scripted.requests[1]["input"]
    output = cast(list[JsonObject], provider_state["output"])
    assert output[-1]["phase"] == "commentary"
    assert "synthetic private trace" not in json.dumps(saved)
    assert first_journal.events.count(("tool_started", "inspect_discovery_capabilities")) == 1
    assert first_journal.events.count(("tool_result", "inspect_discovery_capabilities")) == 1

    resumed_journal = MemoryJournal(saved)
    resumed = _manager(scripted.provider(), max_iterations)
    if resume_mode == "denied":
        scripted.deny_call = 3
        with pytest.raises(ManagerModelUnavailableError, match="Synthetic admission limit"):
            await resumed.respond(
                content="Inspect capabilities",
                working=ManagerWorkingMemory(),
                memories=[],
                recent_messages=[],
                journal=resumed_journal,
            )
        assert len(scripted.requests) == 2
        assert scripted.events == ["admit", "request"] * 2 + ["admit"]
    else:
        result = await resumed.respond(
            content="Inspect capabilities",
            working=ManagerWorkingMemory(),
            memories=[],
            recent_messages=[],
            journal=resumed_journal,
        )
        assert len([step for step in result.steps if step.stage == "act"]) == 1
        if resume_mode == "exhausted":
            assert "iteration limit" in result.content
            assert scripted.events == ["admit", "request"] * 2
        else:
            assert result.content == "The read-only inspection is complete."
            assert scripted.requests[2]["input"] == [
                *cast(list[JsonObject], provider_state["input"]),
                *output,
            ]
            assert scripted.events == ["admit", "request"] * 3
    assert not any(kind.startswith("tool_") for kind, _ in resumed_journal.events)


@pytest.mark.parametrize("agent_kind", ["manager", "shopper"])
async def test_incomplete_commentary_stops_without_continuation(
    agent_kind: Literal["manager", "shopper"],
) -> None:
    scripted = ScriptedResponses(
        [{"status": "incomplete", "output": [_message("commentary", "I will look.")]}]
    )
    provider = scripted.provider()
    with pytest.raises(ManagerModelUnavailableError, match="did not complete its response"):
        if agent_kind == "manager":
            await _manager(provider, 3).respond(
                content="Hello", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
            )
        else:
            await ShopperConversationalAgent(
                provider=provider,
                catalog_search=CatalogSearchTool(None),
                max_iterations=3,
                max_tool_calls=0,
                max_output_tokens=800,
            ).respond(
                tenant_id=UUID(int=1),
                content="Hello",
                history=[],
                memories=[],
                source="uploaded_catalog",
            )
    assert scripted.events == ["admit", "request"]
