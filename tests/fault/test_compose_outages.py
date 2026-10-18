"""Opt-in destructive-to-availability drills against an explicitly named demo stack."""

import asyncio
import os
import re
import subprocess
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient, HTTPError

pytestmark = [
    pytest.mark.fault,
    pytest.mark.skipif(
        os.environ.get("OPEN_COMMERCE_RUN_FAULTS") != "1",
        reason="requires explicit opt-in and a disposable Compose demo stack",
    ),
]

ROOT = Path(__file__).resolve().parents[2]


async def compose(*args: str) -> None:
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    if not re.fullmatch(r"opencommerce-[a-z0-9][a-z0-9_-]*", project):
        raise AssertionError(
            "COMPOSE_PROJECT_NAME must explicitly name an opencommerce-* test stack"
        )
    result = await asyncio.to_thread(
        subprocess.run,
        ["docker", "compose", "--project-name", project, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr


async def wait_json(
    client: AsyncClient,
    path: str,
    accepts: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    deadline = time.monotonic() + 90
    last = "no response"
    while time.monotonic() < deadline:
        try:
            response = await client.get(path)
            last = response.text[:500]
            if response.status_code == 200:
                body: dict[str, Any] = response.json()
                if accepts(body):
                    return body
        except HTTPError as exc:
            last = type(exc).__name__
        await asyncio.sleep(0.5)
    raise AssertionError(f"{path} did not recover: {last}")


async def post(
    client: AsyncClient,
    path: str,
    payload: dict[str, Any] | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    response = await client.post(
        path,
        json=payload,
        headers={"Idempotency-Key": key or str(uuid4())},
    )
    assert response.status_code in {200, 201}, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        base_url=f"http://127.0.0.1:{os.environ.get('API_PORT', '8000')}",
        timeout=15,
    ) as api:
        await wait_json(api, "/health/ready", lambda body: body["status"] == "ready")
        yield api


async def pending_approval(client: AsyncClient) -> tuple[str, str, dict[str, Any]]:
    goal = await post(
        client,
        "/v1/goals",
        {
            "name": "Container recovery drill",
            "allowed_action_types": ["set_campaign_budget"],
        },
    )
    goal_id: str = goal["spec"]["id"]
    await post(client, f"/v1/goals/{goal_id}/activate")
    run = await post(client, f"/v1/goals/{goal_id}/run", {})
    run_id: str = run["id"]
    await wait_json(
        client, f"/v1/runs/{run_id}", lambda body: body["status"] == "awaiting_approval"
    )
    actions = await wait_json(
        client, f"/v1/actions?run_id={run_id}", lambda body: bool(body["items"])
    )
    action: dict[str, Any] = actions["items"][0]
    assert action["action"]["status"] == "awaiting_approval"
    return goal_id, run_id, action


async def test_redis_outage_retains_approved_work_and_resumes_without_api_retry(
    client: AsyncClient,
) -> None:
    goal_id, run_id, action = await pending_approval(client)
    action_id = action["action"]["id"]
    try:
        await compose("stop", "redis")
        assert (await client.get("/health/ready")).status_code == 503
        assert (await client.get("/health/live")).status_code == 200
        approved = await post(
            client,
            f"/v1/actions/{action_id}/approve",
            {
                "action_version_hash": action["action_version_hash"],
            },
        )
        assert approved["action"]["run_id"] == run_id
        assert approved["action"]["status"] == "approved"
    finally:
        await compose("start", "redis")
    completed = await wait_json(
        client, f"/v1/actions/{action_id}", lambda body: body["action"]["status"] == "succeeded"
    )
    replay = await post(client, f"/v1/actions/{action_id}/execute")
    assert replay["execution_result"] == completed["execution_result"]
    assert replay["action"]["run_id"] == run_id
    await post(client, f"/v1/goals/{goal_id}/archive")


async def test_qdrant_outage_fails_closed_then_reuses_durable_catalog(client: AsyncClient) -> None:
    goal = await post(client, "/v1/goals", {"name": "Qdrant recovery drill"})
    query = {"query": "SIM-FOO-0003-1", "goal_context_id": goal["spec"]["id"], "debug": True}
    # Preparation includes cold indexing, not the outage/recovery response-time assertion.
    # The large optional learned catalog can exceed the browser deadline under load.
    original_response = await client.post("/v1/search", json=query, timeout=300)
    assert original_response.status_code == 200, original_response.text
    original = original_response.json()
    assert original["results"]
    try:
        await compose("stop", "qdrant")
        assert (await client.get("/health/ready")).status_code == 503
        assert (await client.get("/health/live")).status_code == 200
        response = await client.post("/v1/search", json=query)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
        assert "Traceback" not in response.text and "qdrant:6333" not in response.text
    finally:
        await compose("start", "qdrant")
    await wait_json(client, "/health/ready", lambda body: body["status"] == "ready")
    restored = await post(client, "/v1/search", query)
    assert restored["results"] == original["results"]
    await post(client, f"/v1/goals/{goal['spec']['id']}/archive")


async def test_postgres_restart_retains_goal_approval_and_trace(client: AsyncClient) -> None:
    goal_id, run_id, action = await pending_approval(client)
    original = (await client.get(f"/v1/runs/{run_id}/events")).text
    try:
        await compose("stop", "postgres")
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/health/ready")).status_code == 503
        failed = await client.get(f"/v1/goals/{goal_id}")
        assert failed.status_code == 503
        assert "Traceback" not in failed.text
        assert "postgresql+asyncpg" not in failed.text
    finally:
        await compose("start", "postgres")
    await wait_json(client, "/health/ready", lambda body: body["status"] == "ready")
    restored = await wait_json(
        client, f"/v1/goals/{goal_id}", lambda body: body["spec"]["status"] == "active"
    )
    assert restored["spec"]["id"] == goal_id
    assert (await client.get(f"/v1/runs/{run_id}/events")).text == original
    await post(
        client,
        f"/v1/actions/{action['action']['id']}/approve",
        {
            "action_version_hash": action["action_version_hash"],
        },
    )
    await wait_json(client, f"/v1/runs/{run_id}", lambda body: body["status"] == "completed")
    await post(client, f"/v1/goals/{goal_id}/archive")


async def test_api_and_worker_container_restart_resume_same_approval_and_sse(
    client: AsyncClient,
) -> None:
    goal_id, run_id, action = await pending_approval(client)
    action_id = action["action"]["id"]
    before = (await client.get(f"/v1/runs/{run_id}/events")).text
    await compose("restart", "api", "worker")
    await wait_json(client, "/health/ready", lambda body: body["status"] == "ready")
    recovered = await wait_json(
        client,
        f"/v1/actions/{action_id}",
        lambda body: body["action"]["status"] == "awaiting_approval",
    )
    assert recovered["action_version_hash"] == action["action_version_hash"]
    assert (await client.get(f"/v1/runs/{run_id}/events")).text == before
    await post(
        client,
        f"/v1/actions/{action_id}/approve",
        {
            "action_version_hash": action["action_version_hash"],
        },
    )
    await wait_json(client, f"/v1/runs/{run_id}", lambda body: body["status"] == "completed")
    resumed = await client.get(f"/v1/runs/{run_id}/events", headers={"Last-Event-ID": "1"})
    ids = [int(line[4:]) for line in resumed.text.splitlines() if line.startswith("id: ")]
    assert ids and min(ids) == 2 and len(ids) == len(set(ids))
    await post(client, f"/v1/goals/{goal_id}/archive")
