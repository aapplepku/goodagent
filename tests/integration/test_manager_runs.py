"""Durable operator runs, replay fences, and projection recovery using real dependencies."""

import asyncio
import json
import subprocess
import sys
from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.catalog.persistence import active_catalog_integration
from open_commerce.config import Settings
from open_commerce.core.types import JsonObject, utc_now
from open_commerce.manager_agent.errors import ManagerThreadBusyError, ManagerThreadNotFoundError
from open_commerce.manager_agent.models import (
    ManagerDatasetProfileRequest,
    ManagerMessageRequest,
    ManagerThreadCreateRequest,
)
from open_commerce.manager_agent.runs import ManagerRunService, run_row
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import SearchRequest
from open_commerce.worker.jobs import JobRunner

from .test_process_recovery import process_env

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("cause", ["age", "active", "elapsed", "dependency"])
async def test_run_time_limit_is_honest_and_does_not_start_exhausted_work(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    settings = integration_settings.model_copy(update={"manager_run_active_seconds": 1})
    db = RuntimeDatabase(settings)
    tenant = uuid4()

    async def execute(**_: object) -> None:
        if cause == "dependency":
            raise TimeoutError("Synthetic dependency timeout")
        await asyncio.sleep(2)

    try:
        await db.initialize_tenant(tenant)
        service = DurableManagerAgentService(db)
        thread = await service.create_thread(
            tenant_id=tenant, request=ManagerThreadCreateRequest(), idempotency_key="thread"
        )
        runs = ManagerRunService(db)
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content="Inspect the catalog"),
            idempotency_key="run",
        )
        async with db.transaction(tenant, write=True) as session:
            row = await run_row(session, tenant, run.id)
            if cause == "age":
                row.created_at = utc_now() - timedelta(minutes=16)
            if cause == "active":
                row.active_seconds = 1
        execution = AsyncMock(side_effect=execute)
        monkeypatch.setattr(service, "_execute_message", execution)
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        events = await runs.events(tenant_id=tenant, run_id=run.id)
        assert events.run.status == "failed"
        assert events.run.error_code == (
            "TimeoutError" if cause == "dependency" else "RUN_TIME_BUDGET_EXCEEDED"
        )
        if cause in {"age", "active"}:
            execution.assert_not_awaited()
        else:
            execution.assert_awaited_once()
        if cause != "dependency":
            assert events.items[-1].title == "Time limit reached"
            assert "smaller next step" in events.items[-1].detail
            assert "service is available" not in events.items[-1].detail
        else:
            assert events.items[-1].title == "Agent needs attention"
            assert "retry when the underlying service is available" in events.items[-1].detail
            assert "time limit" not in events.items[-1].detail
        detail = await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert any(item.id == run.user_message_id for item in detail.messages)
        assert detail.messages[-1].content.startswith(events.items[-1].detail)
    finally:
        await db.close()


def provider(outputs: list[JsonObject]) -> OpenAIManagerProvider:
    def reply(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        count = sum(item.get("type") == "function_call_output" for item in payload["input"])
        return httpx.Response(200, json={"status": "completed", "output": [outputs[count]]})

    return OpenAIManagerProvider(
        api_key=SecretStr("synthetic-test-only"),
        model_id="test-model",
        transport=httpx.MockTransport(reply),
        max_input_bytes=128000,
    )


def message(text: str) -> JsonObject:
    return {
        "type": "message",
        "role": "assistant",
        "phase": "final_answer",
        "content": [{"type": "output_text", "text": text}],
    }


def call(name: str, arguments: JsonObject, key: str) -> JsonObject:
    return {
        "type": "function_call",
        "name": name,
        "arguments": json.dumps(arguments),
        "call_id": key,
        "id": key,
    }


async def test_run_saved_immediately_replayed_scoped_and_cancelled(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        service = DurableManagerAgentService(
            db, model_provider=provider([message("A useful reply.")])
        )
        thread = await service.create_thread(
            tenant_id=tenant, request=ManagerThreadCreateRequest(), idempotency_key="thread"
        )
        runs = ManagerRunService(db)
        request = ManagerMessageRequest(content="Help with initial setup")
        run = await runs.submit(
            tenant_id=tenant, thread_id=thread.thread.id, request=request, idempotency_key="run"
        )
        assert (
            await runs.submit(
                tenant_id=tenant, thread_id=thread.thread.id, request=request, idempotency_key="run"
            )
            == run
        )
        detail = await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert detail.messages[-1].id == run.user_message_id
        assert detail.active_run == run
        with pytest.raises(ManagerThreadBusyError):
            await runs.submit(
                tenant_id=tenant,
                thread_id=thread.thread.id,
                request=request,
                idempotency_key="another",
            )
        with pytest.raises(ManagerThreadNotFoundError):
            await runs.events(tenant_id=other, run_id=run.id)
        with pytest.raises(ManagerThreadNotFoundError):
            await runs.cancel(tenant_id=other, run_id=run.id, idempotency_key="deny")
        stopped = await runs.cancel(tenant_id=tenant, run_id=run.id, idempotency_key="stop")
        assert stopped.status == "cancelled"
        assert await runs.cancel(tenant_id=tenant, run_id=run.id, idempotency_key="stop") == stopped
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert (
            len((await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)).messages)
            == 3
        )
        events = await runs.events(tenant_id=tenant, run_id=run.id)
        assert [event.sequence for event in events.items] == [1, 2]
        assert (
            await runs.events(tenant_id=tenant, run_id=run.id, after=events.next_cursor)
        ).items == []
    finally:
        await db.close()


async def test_cleared_run_cannot_commit_after_model_returns(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    entered, release = asyncio.Event(), asyncio.Event()

    async def reply(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"output": [message("Must never appear after clear")]})

    try:
        await db.initialize_tenant(tenant)
        model = OpenAIManagerProvider(
            api_key=SecretStr("test"),
            model_id="test",
            transport=httpx.MockTransport(reply),
            max_input_bytes=128000,
        )
        service = DurableManagerAgentService(db, model_provider=model)
        thread = await service.create_thread(
            tenant_id=tenant, request=ManagerThreadCreateRequest(), idempotency_key="thread"
        )
        runs = ManagerRunService(db)
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content="Start"),
            idempotency_key="run",
        )
        task = asyncio.create_task(runs.process(tenant_id=tenant, run_id=run.id, service=service))
        await asyncio.wait_for(entered.wait(), 5)
        await service.clear_channel_history(
            tenant_id=tenant, thread_id=thread.thread.id, idempotency_key="clear"
        )
        release.set()
        await task
        detail = await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert len(detail.messages) == 1
        assert "Must never appear" not in detail.model_dump_json()
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "cancelled"
    finally:
        release.set()
        await db.close()


@pytest.mark.parametrize("action", ["retry_failed", "rebuild_active"])
async def test_index_recovery_suspends_resumes_and_preserves_active_projection(
    integration_settings: Settings,
    action: str,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    collection = f"flexible_runs_{uuid4().hex}"
    search = DurableSearchService(db, collection_name=collection)
    try:
        await db.initialize_tenant(tenant)
        model = provider(
            [
                call("inspect_catalog", {}, "inspect"),
                call("recover_catalog_index", {"action": action}, "repair"),
                call(
                    "test_catalog_search", {"query": "lamp", "mode": "hybrid", "top_k": 3}, "search"
                ),
                message(
                    "The catalog was verified and I tested lamp search. No sales lift is claimed."
                ),
            ]
        )
        service = DurableManagerAgentService(db, model_provider=model, search_service=search)
        thread = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(
                title="Analysis", description="Cross-domain investigation"
            ),
            idempotency_key="thread",
        )
        upload = await service.profile_dataset(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="synthetic.csv",
                csv_text="product_id,title,description,price,currency,updated_at\n"
                "lamp,Desk lamp,Reading light,20,USD,2026-09-01T00:00:00Z\n",
            ),
            idempotency_key="upload",
        )
        job_id = upload.catalog_index.job_id
        assert job_id
        runner = JobRunner(db, tenant, search_service=search)
        await runner.run_catalog_index(job_id)
        old_version = upload.catalog_index.source_version
        if action == "retry_failed":
            async with db.transaction(tenant, write=True) as session:
                job = await session.scalar(
                    select(CatalogIndexJob).where(
                        CatalogIndexJob.tenant_id == tenant, CatalogIndexJob.id == job_id
                    )
                )
                assert job
                job.status = "failed"
                job.failures = 3
        runs = ManagerRunService(db)
        run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(
                content="Inspect catalog readiness, repair the index, then test lamp search."
            ),
            idempotency_key="recover",
        )
        if action == "rebuild_active":
            crashed = await asyncio.to_thread(
                subprocess.run,
                [
                    sys.executable,
                    "tests/integration/manager_run_process.py",
                    str(tenant),
                    str(run.id),
                ],
                env=process_env(integration_settings, tenant),
                capture_output=True,
                timeout=30,
            )
            assert crashed.returncode == 85, crashed.stderr.decode()
            async with db.transaction(tenant, write=True) as session:
                saved = await run_row(session, tenant, run.id)
                assert saved.status == "running"
                # The interrupted second dispatch consumes its allowance too.
                assert saved.checkpoint["iteration"] == 2
                saved.lease_until = utc_now() - timedelta(seconds=1)
        assert not await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "waiting"
        async with db.transaction(tenant) as session:
            active = await active_catalog_integration(session, tenant_id=tenant)
            assert active and active.non_secret_config["source_version"] == old_version
            saved = await run_row(session, tenant, run.id)
            assert saved.checkpoint["iteration"] == (3 if action == "rebuild_active" else 2)
        assert (await search.search(tenant_id=tenant, request=SearchRequest(query="lamp"))).results
        assert await runner.run_catalog_index(job_id)
        async with db.transaction(tenant, write=True) as session:
            saved = await run_row(session, tenant, run.id)
            saved.available_at = utc_now()
        # New service and provider instances simulate losing worker process memory.
        restarted = DurableManagerAgentService(db, model_provider=model, search_service=search)
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=restarted)
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "completed"
        detail = await restarted.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert "catalog was verified" in detail.messages[-1].content
        events = await runs.events(tenant_id=tenant, run_id=run.id)
        assert (
            sum(
                event.kind == "tool_started" and event.tool == "recover_catalog_index"
                for event in events.items
            )
            == 1
        )
        assert "synthetic-test-only" not in events.model_dump_json()
        assert (
            sum(
                event.tool == "inspect_catalog" and event.kind == "tool_started"
                for event in events.items
            )
            == 1
        )
    finally:
        await search.client.delete_collection(collection)
        await search.close()
        await db.close()
