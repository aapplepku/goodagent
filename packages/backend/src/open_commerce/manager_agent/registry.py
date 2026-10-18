"""One registry owns tool contracts, permissions, handlers and verification policy."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from open_commerce.manager_agent.model_provider import ManagerToolCall, ManagerToolDefinition


@dataclass(frozen=True)
class ToolSpec:
    definition: ManagerToolDefinition
    input_model: type[BaseModel]
    permission: Literal["read", "draft", "local_recovery", "local_training", "local_import"]
    verification: str
    handler: Callable[..., Awaitable[object]]
    output_model: type[BaseModel]


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self.specs = {spec.definition.name: spec for spec in specs}
        if len(self.specs) != len(specs):
            raise ValueError("Duplicate tool name")

    @property
    def definitions(self) -> list[ManagerToolDefinition]:
        return [spec.definition for spec in self.specs.values()]

    async def execute(self, call: ManagerToolCall, **context: object) -> object:
        spec = self.specs[call.name]
        spec.input_model.model_validate(call.arguments)
        return spec.output_model.model_validate(await spec.handler(call, **context))
