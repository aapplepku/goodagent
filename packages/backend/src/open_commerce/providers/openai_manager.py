"""OpenAI Responses API adapter for the provider-neutral manager model boundary."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

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

logger = structlog.get_logger(__name__)


class _OpenAIOutputItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    status: str | None = None
    phase: Literal["commentary", "final_answer"] | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    content: list[dict[str, Any]] = Field(default_factory=list)


class _OpenAIResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    output: list[_OpenAIOutputItem]
    status: str


class OpenAIManagerProvider:
    """Create short-lived stateless Responses API sessions without logging secrets."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        model_id: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 45,
        max_input_bytes: int = 24000,
        transport: httpx.AsyncBaseTransport | None = None,
        usage_guard: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_input_bytes = max_input_bytes
        self._transport = transport
        self._usage_guard = usage_guard

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model_id

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        return _OpenAIManagerSession(
            provider=self,
            instructions=instructions,
            messages=messages,
            tools=tools,
            max_output_tokens=max_output_tokens,
            require_tool=require_tool,
        )


class _OpenAIManagerSession:
    def __init__(
        self,
        *,
        provider: OpenAIManagerProvider,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool,
    ) -> None:
        self.provider = provider
        self.instructions = instructions
        self.tools = tools
        self.max_output_tokens = max_output_tokens
        self.require_tool = require_tool
        self.input_items: list[JsonObject] = [
            {
                "role": item.role,
                "content": item.content,
                **({"phase": "final_answer"} if item.role == "assistant" else {}),
            }
            for item in messages
        ]
        self.previous_output: list[JsonObject] = []

    def export_checkpoint(self) -> JsonObject:
        return {
            "model": self.provider.model_id,
            "instructions": self.instructions,
            "input": self.input_items,
            "output": self.previous_output,
        }

    def restore_checkpoint(self, state: JsonObject) -> None:
        if state.get("model") != self.provider.model_id:
            raise ManagerModelUnavailableError("The saved run uses a different model")
        self.input_items = cast(list[JsonObject], state["input"])
        self.previous_output = cast(list[JsonObject], state["output"])
        if isinstance(state.get("instructions"), str):
            self.instructions = str(state["instructions"])

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        if not self.provider._api_key.get_secret_value():
            raise ManagerModelUnavailableError("No local OpenAI credential is configured")
        # Commentary can be a complete HTTP response without completing the task.
        # Replay its original phase and opaque continuation even without a tool receipt.
        self.input_items.extend(self.previous_output)
        self.previous_output = []
        if tool_results:
            self.input_items.extend(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": json.dumps(result.output, sort_keys=True, separators=(",", ":")),
                }
                for result in tool_results
            )
        payload: JsonObject = {
            "model": self.provider.model_id,
            "instructions": self.instructions,
            "input": self.input_items,
            "tools": [_openai_tool(tool) for tool in self.tools],
            "tool_choice": "required" if self.require_tool else "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": self.max_output_tokens,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        if len(encoded) > self.provider._max_input_bytes:
            raise ManagerModelUnavailableError("Manager model context exceeds its safe limit")
        if self.provider._usage_guard is not None:
            await self.provider._usage_guard(len(encoded), self.max_output_tokens)
        try:
            async with (
                asyncio.timeout(self.provider._timeout_seconds),
                httpx.AsyncClient(
                    base_url=self.provider._base_url,
                    timeout=self.provider._timeout_seconds,
                    transport=self.provider._transport,
                    headers={
                        "Authorization": f"Bearer {self.provider._api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                ) as client,
            ):
                response = await client.post("/responses", json=payload)
                response.raise_for_status()
                raw_response = response.json()
                parsed = _OpenAIResponse.model_validate(raw_response)
        except httpx.HTTPStatusError as exc:
            raise ManagerModelUnavailableError(
                f"Manager model provider returned HTTP {exc.response.status_code}"
            ) from None
        except (httpx.HTTPError, TimeoutError, ValidationError, ValueError, json.JSONDecodeError):
            raise ManagerModelUnavailableError(
                "Manager model provider is temporarily unavailable"
            ) from None

        logger.info(
            "model_response_received",
            **_response_metadata(parsed, raw_response, self.tools),
        )
        # Completeness belongs to the response, including message-only or empty output.
        if parsed.status != "completed":
            raise ManagerModelUnavailableError("Manager model did not complete its response")
        for item in parsed.output:
            if item.type in {"function_call", "message"} and item.status not in {None, "completed"}:
                raise ManagerModelUnavailableError("Manager model did not complete its response")
        raw_output = raw_response.get("output")
        if not isinstance(raw_output, list) or not all(
            isinstance(item, dict) for item in raw_output
        ):
            raise ManagerModelUnavailableError("Manager model returned an invalid response")
        content: list[str] = []
        final_content: list[str] = []
        phases: list[Literal["commentary", "final_answer"] | None] = []
        calls: list[ManagerToolCall] = []
        try:
            for item in parsed.output:
                if item.type == "function_call":
                    if item.call_id is None or item.name is None or item.arguments is None:
                        raise ValueError("incomplete function call")
                    arguments = json.loads(item.arguments)
                    if not isinstance(arguments, dict):
                        raise ValueError("function arguments must be an object")
                    calls.append(
                        ManagerToolCall(
                            call_id=item.call_id,
                            name=item.name,
                            arguments=cast(JsonObject, arguments),
                        )
                    )
                if item.type == "message":
                    phases.append(item.phase)
                    destination = final_content if item.phase == "final_answer" else content
                    destination.extend(
                        str(block["text"])
                        for block in item.content
                        if block.get("type") == "output_text" and isinstance(block.get("text"), str)
                    )
            turn = ManagerModelTurn(
                content="\n".join(final_content if "final_answer" in phases else content).strip()
                or None,
                tool_calls=calls,
                stop_reason=parsed.status,
                phase="final_answer"
                if "final_answer" in phases
                else "commentary"
                if phases and all(phase == "commentary" for phase in phases)
                else None,
            )
        except (ValidationError, ValueError, json.JSONDecodeError):
            raise ManagerModelUnavailableError(
                "Manager model returned an invalid response"
            ) from None
        # Retain continuation only after the entire sequential turn is validated.
        # A rejected call must not reappear through a later saved checkpoint.
        self.previous_output = cast(
            list[JsonObject],
            [
                {
                    key: value
                    for key, value in item.items()
                    if key in {"id", "type", "encrypted_content", "summary"}
                }
                if item.get("type") == "reasoning"
                else item
                for item in raw_output
            ],
        )
        return turn


def _openai_tool(tool: ManagerToolDefinition) -> JsonObject:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "strict": True,
    }


def _response_metadata(
    parsed: _OpenAIResponse,
    raw_response: dict[str, Any],
    tools: list[ManagerToolDefinition],
) -> JsonObject:
    """Allowlist diagnostics without logging model text, arguments or continuation."""
    known_tools = {tool.name for tool in tools}
    phases: dict[str, int] = {"commentary": 0, "final_answer": 0, "unspecified": 0}
    types: dict[str, int] = {"message": 0, "function_call": 0, "reasoning": 0, "other": 0}
    called: list[str] = []
    for item in parsed.output:
        types[item.type if item.type in types else "other"] += 1
        if item.type == "message":
            phases[item.phase or "unspecified"] += 1
        if item.type == "function_call" and len(called) < 16:
            called.append(item.name if item.name in known_tools else "unknown")
    usage = raw_response.get("usage")
    counts = (
        {
            key: value
            for key, value in usage.items()
            if key in {"input_tokens", "output_tokens", "total_tokens"}
            and type(value) is int
            and 0 <= value <= 1_000_000_000
        }
        if isinstance(usage, dict)
        else {}
    )
    return {
        "provider": "openai",
        "response_status": parsed.status
        if parsed.status in {"completed", "incomplete", "failed", "in_progress"}
        else "other",
        "output_types": types,
        "message_phases": phases,
        "tool_names": called,
        "usage_counts": counts,
    }
