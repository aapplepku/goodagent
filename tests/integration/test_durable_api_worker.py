"""Real PostgreSQL and Redis API-to-worker delivery, replay and resume tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker
from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.worker.jobs import (
    JobRunner,
    deserialize_job,
    process_workflow_job,
    serialize_job,
)

pytestmark = pytest.mark.integration


async def test_default_api_delivers_durable_run_through_real_redis_worker(
    integration_settings: Settings,
) -> None:
    tenant_id = uuid4()
    settings = integration_settings.model_copy(update={"local_tenant_id": tenant_id})
    queue = f"test:workflow:{uuid4()}"
    redis = await create_pool(
        RedisSettings.from_dsn(settings.redis_url),
        default_queue_name=queue,
        job_serializer=serialize_job,
        job_deserializer=deserialize_job,
    )
    app = create_app(settings)
    try:
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/v1/goals", json={"seed": 42}, headers={"Idempotency-Key": "same-goal"}
                    )
                    for _ in range(4)
                ]
            )
            assert all(item.status_code == 201 for item in responses)
            goal_id = responses[0].json()["spec"]["id"]
            assert all(item.json()["spec"]["id"] == goal_id for item in responses)
            conflict = await client.post(
                "/v1/goals", json={"seed": 99}, headers={"Idempotency-Key": "same-goal"}
            )
            assert conflict.status_code == 409
            await client.post(
                f"/v1/goals/{goal_id}/activate", headers={"Idempotency-Key": "activate"}
            )
            queued = await client.post(
                f"/v1/goals/{goal_id}/run", json={}, headers={"Idempotency-Key": "run"}
            )
            assert queued.status_code == 200
            assert queued.json()["status"] == "queued"
            run_id = queued.json()["id"]
            runner = JobRunner(app.state.database, tenant_id)
            assert await runner.publish_due(redis) == 1
            worker = Worker(
                functions=[process_workflow_job],
                redis_pool=redis,
                queue_name=queue,
                ctx={"runner": runner},
                handle_signals=False,
                burst=True,
                keep_result=0,
                job_serializer=serialize_job,
                job_deserializer=deserialize_job,
                log_results=False,
            )
            try:
                await worker.async_run()
                assert worker.jobs_complete == 1
                assert worker.jobs_failed == 0
            finally:
                await worker.close()
            planned = await client.get(f"/v1/runs/{run_id}")
            assert planned.json()["status"] == "awaiting_approval"
            assert len(planned.json()["action_ids"]) > 0
            events = await client.get(f"/v1/runs/{run_id}/events")
            assert "id: 1\n" in events.text
        restarted = create_app(settings)
        async with (
            restarted.router.lifespan_context(restarted),
            AsyncClient(transport=ASGITransport(app=restarted), base_url="http://test") as client,
        ):
            restored = await client.get(f"/v1/runs/{run_id}")
            assert restored.json() == planned.json()
            resumed = await client.get(f"/v1/runs/{run_id}/events", headers={"Last-Event-ID": "2"})
            assert "id: 1\n" not in resumed.text and "id: 2\n" not in resumed.text
            assert "id: 3\n" in resumed.text
            assert UUID(restored.json()["tenant_id"]) == tenant_id
    finally:
        await redis.aclose()
