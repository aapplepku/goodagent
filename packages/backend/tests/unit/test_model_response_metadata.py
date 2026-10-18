"""Provider diagnostics expose only bounded structural facts, not model content."""

import json

import httpx
import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.manager_agent.model_provider import ManagerToolDefinition
from open_commerce.providers.openai_manager import OpenAIManagerProvider


@pytest.mark.parametrize("phase", [None, "commentary", "final_answer"])
async def test_response_log_is_content_free(phase: str | None) -> None:
    raw = {
        "status": "completed",
        "usage": {
            "input_tokens": 123,
            "output_tokens": 45,
            "total_tokens": 168,
            "private_usage_field": "do-not-log-usage",
        },
        "output": [
            {
                "type": "reasoning",
                "encrypted_content": "do-not-log-continuation",
                "summary": [{"text": "do-not-log-summary"}],
            },
            {
                "type": "message",
                "phase": phase,
                "content": [{"type": "output_text", "text": "do-not-log-answer"}],
            },
            {
                "type": "function_call",
                "call_id": "do-not-log-call-id",
                "name": "catalog_search",
                "arguments": '{"query":"do-not-log-arguments"}',
            },
            {"type": "do-not-log-unknown-item"},
        ],
    }
    provider = OpenAIManagerProvider(
        api_key=SecretStr("do-not-log-credential"),
        model_id="do-not-log-model-id",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    with capture_logs() as logs:
        await provider.begin(
            instructions="do-not-log-instructions",
            messages=[],
            tools=[ManagerToolDefinition(name="catalog_search", description="Test", parameters={})],
            max_output_tokens=400,
        ).next([])
    [event] = [item for item in logs if item.get("event") == "model_response_received"]
    assert "do-not-log" not in json.dumps(event)
    assert event["response_status"] == "completed"
    assert event["output_types"] == {"message": 1, "function_call": 1, "reasoning": 1, "other": 1}
    assert event["message_phases"][phase or "unspecified"] == 1
    assert event["tool_names"] == ["catalog_search"]
    assert event["usage_counts"] == {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168}


@pytest.mark.parametrize(
    "usage",
    [None, {"input_tokens": -1, "output_tokens": True, "total_tokens": 10**30}, "do-not-log-usage"],
)
async def test_unknown_metadata_is_not_logged_verbatim(usage: object) -> None:
    provider = OpenAIManagerProvider(
        api_key=SecretStr("test"),
        model_id="test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "status": "do-not-log-status",
                    "usage": usage,
                    "output": [
                        {
                            "type": "function_call",
                            "name": "do-not-log-tool",
                            "call_id": "test",
                            "arguments": "{}",
                        }
                    ],
                },
            )
        ),
    )
    with capture_logs() as logs, pytest.raises(ManagerModelUnavailableError) as caught:
        await provider.begin(
            instructions="Test", messages=[], tools=[], max_output_tokens=400
        ).next([])
    assert "do-not-log" not in str(caught.value)
    [event] = [item for item in logs if item.get("event") == "model_response_received"]
    assert "do-not-log" not in json.dumps(event)
    assert event["response_status"] == "other"
    assert event["tool_names"] == ["unknown"]
    assert event["usage_counts"] == {}
