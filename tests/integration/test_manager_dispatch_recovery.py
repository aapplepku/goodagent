"""Real PostgreSQL run recovery must retain already-dispatched model allowances."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerThreadNotFoundError
from open_commerce.manager_agent.models import ManagerMessageRequest, ManagerThreadCreateRequest
from open_commerce.manager_agent.runs import ManagerRunService, PersistentRunJournal, run_row
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.model_usage import ModelUsageRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.stores.usage import admit_model_call

pytestmark = pytest.mark.integration


async def charges(db: RuntimeDatabase, tenant: UUID) -> list[tuple[UUID, int]]:
    async with db.transaction(tenant) as session:
        rows = await session.execute(
            select(ModelUsageRecord.id, ModelUsageRecord.reserved_tokens)
            .where(ModelUsageRecord.tenant_id == tenant)
            .order_by(ModelUsageRecord.created_at, ModelUsageRecord.id)
        )
        return [(row.id, row.reserved_tokens) for row in rows]


@pytest.mark.parametrize("allowance", [1, 2])
@pytest.mark.parametrize("ending", ["lease_recovery", "explicit_stop", "clear_history"])
async def test_cancelled_dispatch_is_counted_before_worker_recovery(
    integration_settings: Settings, allowance: int, ending: str
) -> None:
    db = RuntimeDatabase(
        integration_settings.model_copy(
            update={
                "runtime_profile": "self_hosted",
                "manager_model_max_iterations": allowance,
            }
        )
    )
    tenant, other = uuid4(), uuid4()
    entered: asyncio.Queue[int] = asyncio.Queue()
    requests: list[httpx.Request] = []
    checkpoints: list[int] = []
    tasks: list[asyncio.Task[bool]] = []

    async def response(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) <= allowance:
            entered.put_nowait(len(requests))
            await asyncio.Event().wait()
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "phase": "final_answer",
                        "content": [
                            {"type": "output_text", "text": "An extra dispatch must not happen."}
                        ],
                    }
                ],
            },
        )

    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        model = OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="synthetic-model",
            transport=httpx.MockTransport(response),
            max_input_bytes=128000,
            usage_guard=admit_model_call,
        )
        service = DurableManagerAgentService(db, model_provider=model)
        runs = ManagerRunService(db)
        thread = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(),
            idempotency_key="thread",
        )
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content="Synthetic setup question"),
            idempotency_key="run",
        )
        for attempt in range(1, allowance + 1):
            task = asyncio.create_task(
                runs.process(tenant_id=tenant, run_id=run.id, service=service)
            )
            tasks.append(task)
            assert await asyncio.wait_for(entered.get(), 5) == attempt
            assert len(await charges(db, tenant)) == attempt
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            async with db.transaction(tenant, write=True) as session:
                row = await run_row(session, tenant, run.id)
                assert row.status == "running" and row.lease_token is not None
                checkpoints.append(int(str(row.checkpoint.get("iteration", 0))))
                row.lease_until = utc_now() - timedelta(seconds=1)
        original_charges = await charges(db, tenant)
        with pytest.raises(ManagerThreadNotFoundError):
            await runs.process(tenant_id=other, run_id=run.id, service=service)
        assert await charges(db, other) == []
        if ending == "explicit_stop":
            await runs.cancel(tenant_id=tenant, run_id=run.id, idempotency_key="stop")
        elif ending == "clear_history":
            await service.clear_channel_history(
                tenant_id=tenant,
                thread_id=thread.thread.id,
                idempotency_key="clear",
            )
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert len(requests) == allowance
        assert checkpoints == list(range(1, allowance + 1))
        assert await charges(db, tenant) == original_charges
        detail = await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert "An extra dispatch" not in detail.model_dump_json()
        if ending == "lease_recovery":
            assert detail.messages[-1].content.startswith("I stopped at the iteration limit.")
            assert any(message.id == run.user_message_id for message in detail.messages)
        else:
            assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "cancelled"
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.close()


async def test_failed_predispatch_checkpoint_never_calls_or_charges_provider(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = RuntimeDatabase(integration_settings.model_copy(update={"runtime_profile": "self_hosted"}))
    tenant = uuid4()
    calls = 0

    async def response(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "phase": "final_answer",
                        "content": [{"type": "output_text", "text": "Must not dispatch."}],
                    }
                ],
            },
        )

    async def failed_save(self: PersistentRunJournal, checkpoint: object) -> None:
        raise RuntimeError("Synthetic checkpoint write failure")

    try:
        await db.initialize_tenant(tenant)
        provider = OpenAIManagerProvider(
            api_key=SecretStr("synthetic-test-only"),
            model_id="synthetic-model",
            transport=httpx.MockTransport(response),
            max_input_bytes=128000,
            usage_guard=admit_model_call,
        )
        service = DurableManagerAgentService(db, model_provider=provider)
        thread = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(),
            idempotency_key="thread",
        )
        runs = ManagerRunService(db)
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content="Synthetic setup question"),
            idempotency_key="run",
        )
        monkeypatch.setattr(PersistentRunJournal, "save", failed_save)
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert calls == 0
        assert await charges(db, tenant) == []
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "failed"
    finally:
        await db.close()
