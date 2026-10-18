"""Fault a disposable owned HTTP process, never the owner's running apps."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.local_runtime import LocalSupervisor
from open_commerce.manager_agent.models import ManagerMessageRequest, ManagerThreadCreateRequest
from open_commerce.manager_agent.runs import ManagerRunService, run_row
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.manager_runs import RuntimeOperationRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase

from .test_manager_runs import call, message, provider

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("cancel", [False, True])
async def test_owned_process_recovery_is_verified_idempotent_and_cancellable(
    integration_settings: Settings,
    tmp_path: Path,
    cancel: bool,
) -> None:
    tenant = uuid4()
    settings = integration_settings.model_copy(update={"local_tenant_id": tenant})
    supervisor = LocalSupervisor(tmp_path, settings)
    settings = settings.model_copy(
        update={"local_runtime_id": supervisor.runtime_id, "local_operations_enabled": True}
    )
    db = RuntimeDatabase(settings)
    # A synthetic /health file lets the real HTTP probe verify a disposable process.
    (tmp_path / "health").write_text("synthetic healthy response")
    name = "shopper_web"
    supervisor.working_directories[name] = tmp_path
    supervisor.commands[name] = [
        sys.executable,
        "-m",
        "http.server",
        str(supervisor.ports[name]),
        "--bind",
        "127.0.0.1",
        "--directory",
        str(tmp_path),
    ]
    try:
        await db.initialize_tenant(tenant)
        supervisor.start(name)
        for _ in range(30):
            if await supervisor.healthy(name):
                break
            await asyncio.sleep(0.1)
        assert await supervisor.healthy(name)
        previous_pid = supervisor.children[name].pid
        await supervisor.stop(name)
        assert not await supervisor.healthy(name)
        model = provider(
            [
                call("repair_local_service", {"service": name}, "repair"),
                message("The shopper connection was verified."),
            ]
        )
        service = DurableManagerAgentService(db, model_provider=model)
        thread = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title="Status"),
            idempotency_key="thread",
        )
        runs = ManagerRunService(db)
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content="can you fix it bro"),
            idempotency_key="repair",
        )
        assert not await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        async with db.transaction(tenant) as session:
            operation = await session.scalar(
                select(RuntimeOperationRecord).where(
                    RuntimeOperationRecord.tenant_id == tenant,
                    RuntimeOperationRecord.run_id == run.id,
                )
            )
            assert operation
            operation_id = operation.id
        if cancel:
            await runs.cancel(tenant_id=tenant, run_id=run.id, idempotency_key="stop")
        await supervisor.operation(operation_id)
        if cancel:
            assert not await supervisor.healthy(name)
            return
        assert await supervisor.healthy(name)
        assert supervisor.children[name].pid != previous_pid
        recovered_pid = supervisor.children[name].pid
        await supervisor.operation(operation_id)
        assert supervisor.children[name].pid == recovered_pid
        async with db.transaction(tenant, write=True) as session:
            operation = await session.scalar(
                select(RuntimeOperationRecord).where(
                    RuntimeOperationRecord.tenant_id == tenant,
                    RuntimeOperationRecord.id == operation_id,
                )
            )
            assert operation and operation.outcome and operation.outcome["verified"] is True
            row = await run_row(session, tenant, run.id)
            from open_commerce.core.types import utc_now

            row.available_at = utc_now()
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "completed"
    finally:
        if name in supervisor.children:
            await supervisor.stop(name)
        for log in supervisor.logs:
            log.close()
        await supervisor.database.close()
        await db.close()
