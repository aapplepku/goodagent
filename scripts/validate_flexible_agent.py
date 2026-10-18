"""Synthetic live-model conversation check against the owner-started local runtime."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["conversation", "status"], default="conversation")
    selected = parser.parse_args().case
    manifest = json.loads(Path(".opencommerce/runtime/manifest.json").read_text())
    url = manifest["services"]["api"]["url"]
    async with httpx.AsyncClient(base_url=url, timeout=30) as client:
        response = await client.post(
            "/v1/manager/threads",
            json={
                "title": "Status" if selected == "status" else "Agent validation",
                "description": "Synthetic initial-store setup and tool checks.",
            },
            headers={"Idempotency-Key": f"flexible-validation-{uuid4()}"},
        )
        response.raise_for_status()
        thread_id = response.json()["thread"]["id"]
        prompts = (
            [
                "I'm setting up a new store. Help me decide a useful first step.",
                "just drive more sales",
                "it's initial set up, not a change",
                "not sure I understand",
            ]
            if selected == "conversation"
            else [
                "Check current service health. Can you fix it bro? Repair only a verified "
                "supported local failure, otherwise explain what is healthy and what is unchecked.",
                "not sure I understand",
            ]
        )
        for content in prompts:
            response = await client.post(
                f"/v1/manager/threads/{thread_id}/runs",
                json={"content": content},
                headers={"Idempotency-Key": str(uuid4())},
            )
            response.raise_for_status()
            run_id = response.json()["id"]
            for _ in range(180):
                await asyncio.sleep(1)
                response = await client.get(f"/v1/manager/runs/{run_id}/events")
                response.raise_for_status()
                result = response.json()
                if result["run"]["status"] in {"completed", "failed", "cancelled"}:
                    break
            print(
                json.dumps({"request": content, "run": result["run"], "events": result["items"]}),
                flush=True,
            )
            if result["run"]["status"] != "completed":
                raise RuntimeError("Live model validation did not complete")
            detail = (await client.get(f"/v1/manager/threads/{thread_id}")).json()
            print(detail["messages"][-1]["content"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
