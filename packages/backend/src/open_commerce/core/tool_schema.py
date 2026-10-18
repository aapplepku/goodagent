"""Strict tool contracts require every object property, including nullable values."""

from pydantic import BaseModel

from open_commerce.core.types import JsonObject


def strict_tool_schema(model: type[BaseModel]) -> JsonObject:
    schema = model.model_json_schema()

    def visit(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["required"] = list(node.get("properties", {}))
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema
