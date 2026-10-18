"""Offline dispatched-attempt recovery through the real model loop and adapter."""

import asyncio
import json
from typing import cast
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from open_commerce.core.types import JsonObject
from open_commerce.manager_agent.model_agent import ModelBackedManagerAgent
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerAgentOutcome,
    ManagerWorkingMemory,
)
from open_commerce.manager_agent.run_hooks import RunCancelled
from open_commerce.providers.openai_manager import OpenAIManagerProvider


def clone(value: JsonObject) -> JsonObject:
    return cast(JsonObject, json.loads(json.dumps(value)))


class Journal:
    run_id = UUID(int=1)
    token = UUID(int=2)

    def __init__(self, checkpoint: JsonObject | None = None) -> None:
        self.checkpoint = clone(checkpoint or {})
        self.fail_save = False
        self.stopped = False
        self.events: list[tuple[str, str | None]] = []

    async def check(self) -> None:
        if self.stopped:
            raise RunCancelled

    async def save(self, checkpoint: JsonObject) -> None:
        await self.check()
        if self.fail_save:
            raise OSError("Synthetic checkpoint failure")
        self.checkpoint = clone(checkpoint)

    async def event(self, kind: str, title: str, detail: str, tool: str | None = None) -> None:
        self.events.append((kind, tool))


class Dispatches:
    def __init__(self, held: set[int], *, tool_first: bool = False) -> None:
        self.held, self.tool_first = held, tool_first
        self.entered: asyncio.Queue[int] = asyncio.Queue()
        self.requests: list[JsonObject] = []
        self.charges: list[tuple[int, int]] = []

    async def admit(self, input_bytes: int, output_tokens: int) -> None:
        self.charges.append((input_bytes, output_tokens))

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        number = len(self.requests)
        if number in self.held:
            self.entered.put_nowait(number)
            await asyncio.Event().wait()
        item: JsonObject = (
            {
                "type": "function_call",
                "call_id": "inspect-1",
                "name": "inspect_discovery_capabilities",
                "arguments": "{}",
            }
            if self.tool_first and number == 1
            else {
                "type": "message",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "Synthetic completion"}],
            }
        )
        return httpx.Response(200, json={"status": "completed", "output": [item]})

    async def respond(self, journal: Journal, limit: int) -> ManagerAgentOutcome:
        provider = OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="dispatch-test",
            base_url="http://dispatch-test.invalid/v1",
            max_input_bytes=100_000,
            transport=httpx.MockTransport(self.handle),
            usage_guard=self.admit,
        )
        return await ModelBackedManagerAgent(
            provider=provider,
            capabilities=ManagerAgentCapabilities(
                semantic_backend="test",
                learned_semantics=False,
                conversation_provider="openai",
                conversation_model="dispatch-test",
                model_backed=True,
            ),
            max_iterations=limit,
            max_tool_calls=1,
            max_output_tokens=128,
        ).respond(
            content="Inspect capabilities",
            working=ManagerWorkingMemory(),
            memories=[],
            recent_messages=[],
            journal=journal,
        )

    async def interrupt(self, journal: Journal, limit: int, number: int) -> None:
        task = asyncio.create_task(self.respond(journal, limit))
        try:
            assert await asyncio.wait_for(self.entered.get(), timeout=2) == number
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_cancelled_dispatch_cannot_replay_after_single_attempt_limit() -> None:
    calls, first = Dispatches({1}), Journal()
    await calls.interrupt(first, 1, 1)
    resumed = Journal(first.checkpoint)
    outcome = await calls.respond(resumed, 1)
    assert len(calls.requests) == 1, "The unresolved first dispatch already consumed the allowance"
    assert len(calls.charges) == 1
    assert resumed.checkpoint["iteration"] == 1
    assert "iteration limit" in outcome.content


async def test_each_interrupted_dispatch_consumes_the_remaining_allowance() -> None:
    calls, first = Dispatches({1, 2}), Journal()
    await calls.interrupt(first, 2, 1)
    second = Journal(first.checkpoint)
    await calls.interrupt(second, 2, 2)
    resumed = Journal(second.checkpoint)
    outcome = await calls.respond(resumed, 2)
    assert len(calls.requests) == 2, "Recovery must not reset the dispatched-attempt count"
    assert len(calls.charges) == 2
    assert resumed.checkpoint["iteration"] == 2
    assert "iteration limit" in outcome.content


async def test_failed_predispatch_checkpoint_prevents_admission_and_dispatch() -> None:
    calls, journal = Dispatches(set()), Journal()
    journal.fail_save = True
    with pytest.raises(OSError, match="Synthetic checkpoint failure"):
        await calls.respond(journal, 1)
    assert calls.requests == [] and calls.charges == []
    assert journal.checkpoint == {}


async def test_interrupted_followup_preserves_tool_receipt_and_valid_continuation() -> None:
    calls, journal = Dispatches({2}, tool_first=True), Journal()
    await calls.interrupt(journal, 3, 2)
    saved = clone(journal.checkpoint)
    resumed = Journal(saved)
    outcome = await calls.respond(resumed, 3)
    assert outcome.content == "Synthetic completion"
    assert len(calls.requests) == len(calls.charges) == 3
    assert calls.requests[2]["input"] == calls.requests[1]["input"]
    items = cast(list[JsonObject], calls.requests[2]["input"])
    assert sum(item.get("type") == "function_call_output" for item in items) == 1
    assert journal.events.count(("tool_result", "inspect_discovery_capabilities")) == 1
    assert not any(kind.startswith("tool_") for kind, _ in resumed.events)
    assert saved["call"] is None and len(cast(list[object], saved["results"])) == 1
    provider_state = cast(JsonObject, saved["provider"])
    assert cast(list[JsonObject], provider_state["output"])[0]["call_id"] == "inspect-1"
    assert saved["iteration"] == 2, "Pending response must consume an attempt, not its receipt"
    assert resumed.checkpoint["iteration"] == 3


async def test_explicit_stop_prevents_new_dispatch() -> None:
    calls, journal = Dispatches(set()), Journal()
    journal.stopped = True
    with pytest.raises(RunCancelled):
        await calls.respond(journal, 1)
    assert calls.requests == [] and calls.charges == []
