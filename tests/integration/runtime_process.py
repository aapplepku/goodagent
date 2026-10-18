"""Test-only child process that exits abruptly at a committed worker boundary."""

import argparse
import asyncio
import os
from uuid import UUID

from open_commerce.config import Settings
from open_commerce.controller.durable_executor import DurableExecutor
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner


async def run(boundary: str, tenant_id: UUID, job_id: UUID) -> None:
    class StoppedExecutor(DurableExecutor):
        async def _after_provider_commit(self, attempt_id: UUID) -> None:
            os._exit(86)

    class StoppedRunner(JobRunner):
        async def _dispatch(self, job: WorkflowJob) -> bool:
            if boundary == "leased":
                os._exit(85)
            assert job.action_id is not None
            await StoppedExecutor(self.database).execute(
                tenant_id=tenant_id,
                action_id=job.action_id,
                idempotency_key=f"workflow:{job.id}",
            )
            return True

    database = RuntimeDatabase(Settings())
    try:
        await StoppedRunner(database, tenant_id, lease_seconds=1).run(job_id)
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("boundary", choices=["leased", "provider_committed"])
    parser.add_argument("tenant_id", type=UUID)
    parser.add_argument("job_id", type=UUID)
    args = parser.parse_args()
    asyncio.run(run(args.boundary, args.tenant_id, args.job_id))
