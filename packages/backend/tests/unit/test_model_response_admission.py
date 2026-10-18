"""An invalid provider response cannot authorize a tool or contaminate a checkpoint."""

import json

import httpx
import pytest
from pydantic import SecretStr

from open_commerce.core.types import JsonObject
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import CheckpointedManagerSession
from open_commerce.providers.openai_manager import OpenAIManagerProvider


def tool(**updates: object) -> dict[str, object]:
    return {
        "type": "function_call",
        "call_id": "synthetic-call",
        "name": "save_shopping_memory",
        "arguments": "{}",
        **updates,
    }


@pytest.mark.parametrize(
    "response",
    [
        {"output": [tool()]},
        {"status": None, "output": [tool()]},
        {"status": "completed", "output": [tool(arguments="{invalid")]},
        {"status": "completed", "output": [tool(arguments="[]")]},
        {"status": "completed", "output": [tool(call_id="")]},
        {"status": "completed", "output": [tool(), tool(call_id="second")]},
    ],
    ids=["missing-status", "null-status", "invalid-json", "non-object", "empty-id", "two-calls"],
)
async def test_invalid_turn_is_neither_executable_nor_checkpointed(response: JsonObject) -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("synthetic-test-only"),
        model_id="offline",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)),
    )
    session = provider.begin(instructions="Fixture", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(session, CheckpointedManagerSession)
    with pytest.raises(ManagerModelUnavailableError):
        await session.next([])
    assert session.export_checkpoint()["output"] == []


@pytest.mark.parametrize(
    "status", ["incomplete", "failed", "cancelled", "in_progress", "queued", "unknown"]
)
@pytest.mark.parametrize("item_type", ["message", "reasoning", "empty"])
async def test_unfinished_response_is_rejected_without_function_calls(
    status: str, item_type: str
) -> None:
    output: list[JsonObject] = []
    if item_type == "message":
        output.append(
            {
                "type": "message",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "Truncated answer"}],
            }
        )
    elif item_type == "reasoning":
        output.append({"type": "reasoning", "encrypted_content": "opaque", "summary": []})
    provider = OpenAIManagerProvider(
        api_key=SecretStr("synthetic-test-only"),
        model_id="offline",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"status": status, "output": output})
        ),
    )
    session = provider.begin(instructions="Fixture", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(session, CheckpointedManagerSession)
    with pytest.raises(ManagerModelUnavailableError):
        await session.next([])
    assert session.export_checkpoint()["output"] == []


async def test_rejected_output_stays_absent_after_restoring_checkpoint() -> None:
    requests: list[JsonObject] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 2:
            return httpx.Response(
                200, json={"status": "completed", "output": [tool(arguments="{invalid")]}
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "phase": "commentary" if len(requests) == 1 else "final_answer",
                        "content": [{"type": "output_text", "text": "Synthetic progress"}],
                    }
                ],
            },
        )

    provider = OpenAIManagerProvider(
        api_key=SecretStr("synthetic-test-only"),
        model_id="offline",
        transport=httpx.MockTransport(handle),
    )
    first = provider.begin(instructions="Fixture", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(first, CheckpointedManagerSession)
    await first.next([])
    with pytest.raises(ManagerModelUnavailableError):
        await first.next([])
    restored = provider.begin(instructions="Fixture", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(restored, CheckpointedManagerSession)
    restored.restore_checkpoint(first.export_checkpoint())
    assert (await restored.next([])).phase == "final_answer"
    assert len(requests) == 3
    assert "{invalid" not in json.dumps(requests[-1])
    assert "synthetic-call" not in json.dumps(requests[-1])
    items = requests[-1]["input"]
    assert isinstance(items, list)
    assert len(items) == 1
