"""Test-only worker execution process killed after a durable tool receipt."""

import argparse
import asyncio
import json
import os
from uuid import UUID

import httpx
from pydantic import SecretStr

from open_commerce.config import Settings
from open_commerce.manager_agent.runs import ManagerRunService
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.openai_manager import OpenAIManagerProvider


async def run(tenant_id: UUID, run_id: UUID) -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content)["input"]
        if any(item.get("type") == "function_call_output" for item in inputs):
            os._exit(85)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "name": "inspect_catalog",
                        "arguments": "{}",
                        "call_id": "inspect",
                        "id": "inspect",
                    }
                ],
            },
        )

    database = RuntimeDatabase(Settings())
    model = OpenAIManagerProvider(
        api_key=SecretStr("synthetic-test-only"),
        model_id="test-model",
        transport=httpx.MockTransport(reply),
        max_input_bytes=128000,
    )
    try:
        await ManagerRunService(database).process(
            tenant_id=tenant_id,
            run_id=run_id,
            service=DurableManagerAgentService(database, model_provider=model),
        )
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tenant_id", type=UUID)
    parser.add_argument("run_id", type=UUID)
    args = parser.parse_args()
    asyncio.run(run(args.tenant_id, args.run_id))
