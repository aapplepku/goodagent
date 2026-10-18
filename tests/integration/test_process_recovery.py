"""Abrupt OS-process failure tests with real PostgreSQL authority and HTTP sockets."""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, ConnectError
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.core.enums import ActionStatus
from open_commerce.persistence.models.actions import ActionExecution
from open_commerce.persistence.models.simulator import SimulatorCommandRecordModel
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner

from .test_durable_controller import approve, prepared_goal
from .test_durable_cycles import jobs_of_kind

pytestmark = pytest.mark.integration


def process_env(settings: Settings, tenant_id: UUID) -> dict[str, str]:
    return {
        **os.environ,
        "OPEN_COMMERCE_ENVIRONMENT": "test",
        "OPEN_COMMERCE_DATABASE_URL": settings.database_url,
        "OPEN_COMMERCE_REDIS_URL": settings.redis_url,
        "OPEN_COMMERCE_QDRANT_URL": settings.qdrant_url,
        "OPEN_COMMERCE_LOCAL_TENANT_ID": str(tenant_id),
        "PYTHONPATH": str(Path("packages/backend/src").resolve()),
    }


@pytest.mark.parametrize("boundary", ["leased", "provider_committed"])
async def test_worker_process_dies_and_restarted_worker_replays_only_durable_ids(
    integration_settings: Settings,
    boundary: str,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant_id, _, action_id = await prepared_goal(database)
        await approve(database, tenant_id, action_id)
        jobs = await jobs_of_kind(database, tenant_id, "execute")
        assert len(jobs) == 1
        result = await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "tests/integration/runtime_process.py",
                boundary,
                str(tenant_id),
                str(jobs[0]),
            ],
            env=process_env(integration_settings, tenant_id),
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == (85 if boundary == "leased" else 86), result.stderr.decode()
        async with database.transaction(tenant_id) as session:
            before = list(
                await session.scalars(
                    select(SimulatorCommandRecordModel).where(
                        SimulatorCommandRecordModel.tenant_id == tenant_id,
                    )
                )
            )
            assert len(before) == (0 if boundary == "leased" else 1)
        await database.close()
        await asyncio.sleep(1.1)
        database = RuntimeDatabase(integration_settings)
        runner = JobRunner(database, tenant_id)
        assert await runner.run(jobs[0])
        assert not await runner.run(jobs[0])
        action = await DurableControllerService(database).get_action(
            tenant_id=tenant_id,
            action_id=action_id,
        )
        assert action.action.status == ActionStatus.SUCCEEDED
        async with database.transaction(tenant_id) as session:
            receipts = list(
                await session.scalars(
                    select(SimulatorCommandRecordModel).where(
                        SimulatorCommandRecordModel.tenant_id == tenant_id,
                    )
                )
            )
            attempts = list(
                await session.scalars(
                    select(ActionExecution).where(
                        ActionExecution.tenant_id == tenant_id,
                    )
                )
            )
            assert len(receipts) == len(attempts) == 1
    finally:
        await database.close()


async def _wait_live(client: AsyncClient, process: asyncio.subprocess.Process) -> None:
    for _ in range(100):
        assert process.returncode is None, "API exited before it became live"
        try:
            if (await client.get("/health/live")).status_code == 200:
                return
        except ConnectError:
            pass
        await asyncio.sleep(0.1)
    raise AssertionError("API did not become live")


async def _wait_run(client: AsyncClient, run_id: str, status: str) -> None:
    for _ in range(150):
        response = await client.get(f"/v1/runs/{run_id}")
        if response.status_code == 200 and response.json()["status"] == status:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"Run did not reach {status}: {response.text}")


async def test_active_goal_approval_and_sse_survive_actual_api_process_restart(
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    tenant_id = uuid4()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "open_commerce.api.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]
    environment = process_env(integration_settings, tenant_id)
    log = (tmp_path / "api-recovery.log").open("wb")
    worker_log = (tmp_path / "worker-recovery.log").open("wb")
    worker: asyncio.subprocess.Process | None = None
    process = await asyncio.create_subprocess_exec(
        *command,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    database = RuntimeDatabase(integration_settings)
    try:
        async with AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
            await _wait_live(client, process)
            created = await client.post(
                "/v1/goals",
                json={"allowed_action_types": ["set_campaign_budget"]},
                headers={"Idempotency-Key": "create"},
            )
            assert created.status_code == 201, created.text
            goal_id = created.json()["spec"]["id"]
            activated = await client.post(
                f"/v1/goals/{goal_id}/activate",
                headers={"Idempotency-Key": "activate"},
            )
            assert activated.status_code == 200
            queued = await client.post(
                f"/v1/goals/{goal_id}/run",
                json={},
                headers={"Idempotency-Key": "run"},
            )
            assert queued.status_code == 200
            run_id = queued.json()["id"]
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=10)
            process = await asyncio.create_subprocess_exec(
                *command, env=environment, stdout=log, stderr=subprocess.STDOUT
            )
            await _wait_live(client, process)
            restored = await client.get(f"/v1/runs/{run_id}")
            assert restored.json()["status"] == "queued"
            worker = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "open_commerce.worker.main",
                env=environment,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
            )
            await _wait_run(client, run_id, "awaiting_approval")
            health = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "open_commerce.worker.health"],
                env=environment,
                capture_output=True,
                timeout=10,
            )
            assert health.returncode == 0, health.stderr.decode()
            worker.kill()
            await asyncio.wait_for(worker.wait(), timeout=10)
            listed = await client.get(f"/v1/actions?run_id={run_id}")
            action = next(
                item
                for item in listed.json()["items"]
                if item["action"]["status"] == "awaiting_approval"
            )
            cursor = 0
            async with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("id: "):
                        cursor = int(line[4:])
                        break
            assert cursor == 1
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=10)
            process = await asyncio.create_subprocess_exec(
                *command, env=environment, stdout=log, stderr=subprocess.STDOUT
            )
            await _wait_live(client, process)
            approval = await client.post(
                f"/v1/actions/{action['action']['id']}/approve",
                json={"action_version_hash": action["action_version_hash"]},
                headers={"Idempotency-Key": "approve"},
            )
            assert approval.status_code == 200, approval.text
            assert approval.json()["action"]["run_id"] == run_id
            # The worker is still stopped: persist the decision, kill the API,
            # and prove recovery before any execution consumer can run.
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=10)
            process = await asyncio.create_subprocess_exec(
                *command, env=environment, stdout=log, stderr=subprocess.STDOUT
            )
            await _wait_live(client, process)
            restored_approval = await client.get(f"/v1/actions/{action['action']['id']}")
            assert restored_approval.status_code == 200
            saved = restored_approval.json()
            assert saved["action"]["run_id"] == run_id
            assert saved["action"]["status"] == "approved"
            assert saved["approval"]["id"] == approval.json()["approval"]["id"]
            assert saved["approval"]["action_version_hash"] == action["action_version_hash"]
            worker = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "open_commerce.worker.main",
                env=environment,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
            )
            await _wait_run(client, run_id, "completed")
            completed = await client.get(f"/v1/runs/{run_id}")
            assert completed.json()["status"] == "completed"
            events = await client.get(
                f"/v1/runs/{run_id}/events",
                headers={"Last-Event-ID": str(cursor)},
            )
            ids = [int(line[4:]) for line in events.text.splitlines() if line.startswith("id: ")]
            assert ids and min(ids) == cursor + 1 and len(ids) == len(set(ids))
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), timeout=10)
        if worker is not None:
            if worker.returncode is None:
                worker.kill()
            await asyncio.wait_for(worker.wait(), timeout=10)
        log.close()
        worker_log.close()
        await database.close()
