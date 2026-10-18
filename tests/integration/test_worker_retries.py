"""Real PostgreSQL retry accounting; fault injection does not replace storage."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner

pytestmark = pytest.mark.integration


async def make_due(database: RuntimeDatabase, tenant_id: UUID, job_id: UUID) -> None:
    async with database.transaction(tenant_id, write=True) as session:
        job = await session.scalar(
            select(WorkflowJob).where(
                WorkflowJob.tenant_id == tenant_id,
                WorkflowJob.id == job_id,
            )
        )
        assert job is not None
        job.available_at = utc_now()


async def test_measurement_polls_do_not_consume_failure_budget(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, job_id = uuid4(), uuid4()

    class InjectedRunner(JobRunner):
        response: str = "waiting"

        async def _dispatch(self, job: WorkflowJob) -> bool:
            if self.response == "error":
                raise TimeoutError("injected transient dependency failure")
            return self.response == "done"

    try:
        await database.initialize_tenant(tenant)
        async with database.transaction(tenant, write=True) as session:
            session.add(
                WorkflowJob(
                    id=job_id,
                    tenant_id=tenant,
                    kind="measure",
                    status="pending",
                    available_at=utc_now(),
                    attempts=0,
                )
            )
        runner = InjectedRunner(database, tenant)
        for _ in range(15):
            await make_due(database, tenant, job_id)
            assert not await runner.run(job_id)
        runner.response = "error"
        await make_due(database, tenant, job_id)
        with pytest.raises(TimeoutError):
            await runner.run(job_id)
        await database.close()
        database = RuntimeDatabase(integration_settings)
        async with database.transaction(tenant) as session:
            job = await session.scalar(
                select(WorkflowJob).where(WorkflowJob.tenant_id == tenant, WorkflowJob.id == job_id)
            )
            assert job is not None
            assert job.attempts == 16 and job.failures == 1 and job.status == "pending"
        runner = InjectedRunner(database, tenant)
        runner.response = "done"
        await make_due(database, tenant, job_id)
        assert await runner.run(job_id)
        assert not await runner.run(job_id)
    finally:
        await database.close()


async def test_repeated_actual_failures_are_bounded_across_restart(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant, job_id = uuid4(), uuid4()

    class FailingRunner(JobRunner):
        async def _dispatch(self, job: WorkflowJob) -> bool:
            raise TimeoutError("injected transient dependency failure")

    try:
        await database.initialize_tenant(tenant)
        async with database.transaction(tenant, write=True) as session:
            session.add(
                WorkflowJob(
                    id=job_id,
                    tenant_id=tenant,
                    kind="plan",
                    status="pending",
                    available_at=utc_now(),
                    attempts=0,
                )
            )
        for _ in range(10):
            await make_due(database, tenant, job_id)
            with pytest.raises(TimeoutError):
                await FailingRunner(database, tenant).run(job_id)
            await database.close()
            database = RuntimeDatabase(integration_settings)
        async with database.transaction(tenant) as session:
            job = await session.scalar(
                select(WorkflowJob).where(WorkflowJob.tenant_id == tenant, WorkflowJob.id == job_id)
            )
            assert job is not None and job.status == "dead_letter" and job.failures == 10
            assert job.error_code == "TimeoutError"
        assert not await FailingRunner(database, tenant).run(job_id)
    finally:
        await database.close()
