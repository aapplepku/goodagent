"""Provider-neutral contracts for model-backed manager conversation turns."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field

from open_commerce.core.types import JsonObject, StrictDomainModel


class ManagerModelMessage(StrictDomainModel):
    """One redacted conversation message sent to a model provider."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ManagerToolDefinition(StrictDomainModel):
    """Allowlisted client tool exposed to a model."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=1, max_length=1000)
    parameters: JsonObject
    simulated: bool = False


class ManagerToolCall(StrictDomainModel):
    """Untrusted model request to invoke one named client tool."""

    call_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    arguments: JsonObject


class ManagerToolResult(StrictDomainModel):
    """Validated tool result returned to the model for observation."""

    call_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    output: JsonObject
    is_error: bool = False


class ManagerModelTurn(StrictDomainModel):
    """One provider response containing prose or a single sequential tool call."""

    content: str | None = Field(default=None, max_length=4000)
    tool_calls: list[ManagerToolCall] = Field(default_factory=list, max_length=1)
    stop_reason: str = Field(default="completed", min_length=1, max_length=100)
    phase: Literal["commentary", "final_answer"] | None = None


class ManagerModelSession(Protocol):
    """A short-lived provider session scoped to one manager request."""

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn: ...


@runtime_checkable
class ToolResultObserver(Protocol):
    """Optional local execution observer; observing does not request another model turn."""

    def observe_tool_result(self, result: ManagerToolResult) -> None: ...


@runtime_checkable
class CheckpointedManagerSession(Protocol):
    def export_checkpoint(self) -> JsonObject: ...
    def restore_checkpoint(self, state: JsonObject) -> None: ...


class ManagerModelProvider(Protocol):
    """Model boundary; provider SDKs and HTTP remain outside this module."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession: ...
