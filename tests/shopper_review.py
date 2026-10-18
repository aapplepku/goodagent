"""Explicitly scripted reviewer for protocol tests; never a semantic-quality oracle."""

import json

from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.shopper_agent.answer_review import REVIEW_CATALOG_ANSWER


def supported_review_session(
    messages: list[ManagerModelMessage], tools: list[ManagerToolDefinition]
) -> ManagerModelSession | None:
    if [tool.name for tool in tools] != [REVIEW_CATALOG_ANSWER.name]:
        return None
    document = json.loads("".join(item.content.split("\n", 1)[1] for item in messages))

    class Session:
        called = False

        async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
            assert not self.called and not tool_results
            self.called = True
            return ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="scripted-review",
                        name=REVIEW_CATALOG_ANSWER.name,
                        arguments={
                            "candidate_id": document["candidate_id"],
                            "product_ids": document["candidate"]["product_ids"],
                            "verdict": "supported",
                            "issues": [],
                        },
                    )
                ]
            )

    return Session()
