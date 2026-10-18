"""OpenAI Responses adapter contract tests with an in-process HTTP transport."""

import json

import httpx
import pytest
from pydantic import SecretStr

from open_commerce.config import Settings
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import (
    CheckpointedManagerSession,
    ManagerModelMessage,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.shopper_agent.completion import COMPLETE_SHOPPING_TURN
from open_commerce.shopper_agent.product_tools import PRODUCT_TOOLS


@pytest.mark.parametrize("required", [False, True])
async def test_required_completion_is_explicit_and_does_not_change_default(required: bool) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tool_choice"] == ("required" if required else "auto")
        assert payload["parallel_tool_calls"] is False
        assert payload["store"] is False
        assert payload["tools"][0]["strict"] is True
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "finish",
                        "name": "complete_shopping_turn",
                        "arguments": json.dumps({"kind": "conversation", "message": "Hello!"}),
                    }
                ],
            },
        )

    provider = OpenAIManagerProvider(
        api_key=SecretStr("synthetic"), model_id="test", transport=httpx.MockTransport(handle)
    )
    session = provider.begin(
        instructions="Synthetic",
        messages=[],
        tools=[COMPLETE_SHOPPING_TURN],
        max_output_tokens=400,
        require_tool=required,
    )
    turn = await session.next([])
    assert turn.tool_calls[0].name == "complete_shopping_turn"
    assert turn.tool_calls[0].arguments == {"kind": "conversation", "message": "Hello!"}


@pytest.mark.parametrize("item_type", ["function_call", "message"])
@pytest.mark.parametrize("status", ["incomplete", "in_progress", "unknown"])
async def test_unfinished_item_is_not_executable_or_checkpointed(
    status: str, item_type: str
) -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"),
        model_id="test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": item_type,
                            "status": status,
                            "call_id": "unfinished",
                            "name": "inspect_catalog",
                            "arguments": "{}",
                            "phase": "final_answer",
                            "content": [{"type": "output_text", "text": "Unfinished response"}],
                        }
                    ],
                },
            )
        ),
    )
    session = provider.begin(instructions="Test", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(session, CheckpointedManagerSession)
    with pytest.raises(ManagerModelUnavailableError):
        await session.next([])
    assert session.export_checkpoint()["output"] == []


@pytest.mark.parametrize(
    "status", ["incomplete", "failed", "cancelled", "in_progress", "queued", "unknown"]
)
async def test_unfinished_response_cannot_checkpoint_a_complete_looking_call(status: str) -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"),
        model_id="test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "status": status,
                    "output": [
                        {
                            "type": "function_call",
                            "status": "completed",
                            "call_id": "test",
                            "name": "inspect_catalog",
                            "arguments": "{}",
                        }
                    ],
                },
            )
        ),
    )
    session = provider.begin(instructions="Test", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(session, CheckpointedManagerSession)
    with pytest.raises(ManagerModelUnavailableError):
        await session.next([])
    assert session.export_checkpoint()["output"] == []


@pytest.mark.parametrize("status", [None, "completed"])
async def test_completed_response_tool_call_is_preserved(status: str | None) -> None:
    item = {
        "type": "function_call",
        "call_id": "test",
        "name": "inspect_catalog",
        "arguments": "{}",
    }
    if status is not None:
        item["status"] = status
    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"),
        model_id="test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [item],
                },
            )
        ),
    )
    session = provider.begin(instructions="Test", messages=[], tools=[], max_output_tokens=400)
    turn = await session.next([])
    assert turn.stop_reason == "completed"
    assert [call.name for call in turn.tool_calls] == ["inspect_catalog"]
    assert isinstance(session, CheckpointedManagerSession)
    assert session.export_checkpoint()["output"] == [item]


async def test_serialized_product_schemas_are_strict_at_every_nested_object() -> None:
    def check(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert set(node.get("required", [])) == set(node.get("properties", {}))
                assert node["additionalProperties"] is False
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        for tool in payload["tools"]:
            assert tool["strict"] is True
            check(tool["parameters"])
        variant = payload["tools"][1]["parameters"]["$defs"]["ProductVariantReference"]
        assert {"type": "null"} in variant["properties"]["variant_id"]["anyOf"]
        return httpx.Response(200, json={"status": "completed", "output": []})

    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"), model_id="test", transport=httpx.MockTransport(handler)
    )
    await provider.begin(
        instructions="Test", messages=[], tools=PRODUCT_TOOLS, max_output_tokens=400
    ).next([])


async def test_responses_checkpoint_preserves_encrypted_continuation_and_final_phase() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "reasoning",
                            "id": "r1",
                            "encrypted_content": "opaque-continuation",
                            "summary": [],
                            "content": [{"type": "reasoning_text", "text": "private trace"}],
                        },
                        {
                            "type": "function_call",
                            "call_id": "c1",
                            "name": "inspect_catalog",
                            "arguments": "{}",
                        },
                    ],
                },
            )
        payload = json.loads(request.content)
        assert "opaque-continuation" in json.dumps(payload["input"])
        assert "private trace" not in json.dumps(payload)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "phase": "commentary",
                        "content": [{"type": "output_text", "text": "Interim message"}],
                    },
                    {
                        "type": "message",
                        "phase": "final_answer",
                        "content": [{"type": "output_text", "text": "Verified final answer"}],
                    },
                ],
            },
        )

    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"), model_id="test", transport=httpx.MockTransport(handler)
    )
    first = provider.begin(
        instructions="Original context",
        messages=[ManagerModelMessage(role="user", content="Check")],
        tools=[],
        max_output_tokens=400,
    )
    assert isinstance(first, CheckpointedManagerSession)
    await first.next([])
    checkpoint = first.export_checkpoint()
    assert "private trace" not in json.dumps(checkpoint)
    second = provider.begin(instructions="Recreated", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(second, CheckpointedManagerSession)
    second.restore_checkpoint(checkpoint)
    result = await second.next(
        [ManagerToolResult(call_id="c1", name="inspect_catalog", output={"count": 3})]
    )
    assert result.content == "Verified final answer"
    assert result.phase == "final_answer"


async def test_commentary_continues_after_checkpoint_without_tool_results() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": f"msg-{len(payloads)}",
                        "role": "assistant",
                        "phase": "commentary" if len(payloads) == 1 else "final_answer",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Checking" if len(payloads) == 1 else "Done",
                            }
                        ],
                    }
                ],
            },
        )

    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"), model_id="test", transport=httpx.MockTransport(handler)
    )
    first = provider.begin(
        instructions="Test",
        messages=[
            ManagerModelMessage(role="assistant", content="Earlier answer"),
            ManagerModelMessage(role="user", content="Check"),
        ],
        tools=[],
        max_output_tokens=400,
    )
    assert (await first.next([])).phase == "commentary"
    assert isinstance(first, CheckpointedManagerSession)
    resumed = provider.begin(instructions="Test", messages=[], tools=[], max_output_tokens=400)
    assert isinstance(resumed, CheckpointedManagerSession)
    resumed.restore_checkpoint(first.export_checkpoint())
    result = await resumed.next([])
    assert result.phase == "final_answer"
    assert result.content == "Done"
    items = payloads[-1]["input"]
    assert isinstance(items, list)
    assert items[0]["phase"] == "final_answer"
    assert "phase" not in items[1]
    assert items[2]["phase"] == "commentary"
    assert items[2]["id"] == "msg-1"
    assert len(items) == 3
    await resumed.next([])
    items = payloads[-1]["input"]
    assert isinstance(items, list)
    assert [item.get("id") for item in items].count("msg-1") == 1


async def test_empty_explicit_final_does_not_promote_commentary() -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"),
        model_id="test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "phase": "commentary",
                            "content": [{"type": "output_text", "text": "I will look"}],
                        },
                        {"type": "message", "phase": "final_answer", "content": []},
                    ],
                },
            )
        ),
    )
    turn = await provider.begin(
        instructions="Test", messages=[], tools=[], max_output_tokens=400
    ).next([])
    assert turn.phase == "final_answer"
    assert turn.content is None


def test_openai_settings_report_missing_credentials_at_request_time_and_redact_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPEN_COMMERCE_OPENAI_API_KEY", raising=False)
    assert Settings(_env_file=None, manager_model_provider="openai").openai_api_key is None

    settings = Settings(
        _env_file=None,
        manager_model_provider="openai",
        openai_api_key="local-test-secret",
    )

    assert "local-test-secret" not in repr(settings)
    assert settings.openai_api_key == SecretStr("local-test-secret")


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_openai_environment_credentials_are_missing(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("OPEN_COMMERCE_OPENAI_API_KEY", value)
    settings = Settings(_env_file=None, manager_model_provider="openai")
    assert settings.openai_api_key is None


@pytest.mark.parametrize("value", [None, "", "  ", SecretStr(""), SecretStr(" \t")])
def test_blank_explicit_openai_credentials_are_missing(value: str | SecretStr | None) -> None:
    settings = Settings(_env_file=None, manager_model_provider="openai", openai_api_key=value)
    assert settings.openai_api_key is None


async def test_responses_adapter_replays_tool_call_and_disables_storage() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) == 1:
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "id": "fc_1",
                            "call_id": "call_1",
                            "name": "inspect_discovery_capabilities",
                            "arguments": "{}",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Semantic search is ready."}],
                    }
                ],
            },
        )

    provider = OpenAIManagerProvider(
        api_key=SecretStr("test-secret"),
        model_id="gpt-test",
        base_url="https://api.openai.test/v1",
        transport=httpx.MockTransport(handler),
    )
    session = provider.begin(
        instructions="Safe test instructions",
        messages=[ManagerModelMessage(role="user", content="Inspect search")],
        tools=[
            ManagerToolDefinition(
                name="inspect_discovery_capabilities",
                description="Inspect capabilities.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            )
        ],
        max_output_tokens=400,
    )

    first = await session.next([])
    second = await session.next(
        [
            ManagerToolResult(
                call_id="call_1",
                name="inspect_discovery_capabilities",
                output={"read_only": True},
            )
        ]
    )

    assert first.tool_calls[0].name == "inspect_discovery_capabilities"
    assert second.content == "Semantic search is ready."
    assert payloads[0]["store"] is False
    assert payloads[0]["parallel_tool_calls"] is False
    tools = payloads[0]["tools"]
    assert isinstance(tools, list) and tools[0]["strict"] is True
    second_input = payloads[1]["input"]
    assert isinstance(second_input, list)
    assert any(item.get("type") == "function_call" for item in second_input)
    assert any(item.get("type") == "function_call_output" for item in second_input)


async def test_provider_failure_is_redacted() -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("do-not-leak-this-secret"),
        model_id="gpt-test",
        base_url="https://api.openai.test/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"error": {}})),
    )
    session = provider.begin(
        instructions="Test",
        messages=[ManagerModelMessage(role="user", content="Hello")],
        tools=[],
        max_output_tokens=400,
    )

    with pytest.raises(ManagerModelUnavailableError) as captured:
        await session.next([])

    assert "401" in str(captured.value)
    assert "do-not-leak-this-secret" not in str(captured.value)
