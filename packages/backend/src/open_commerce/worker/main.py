"""ARQ delivery with PostgreSQL outbox replay after Redis or process failure."""

import asyncio
import contextlib
import signal
from uuid import UUID

import structlog
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker
from sqlalchemy import select

from open_commerce.config import get_settings
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.logging import configure_logging
from open_commerce.worker.jobs import (
    JobRunner,
    deserialize_job,
    process_catalog_index_job,
    process_manager_run,
    process_ranking_job,
    process_workflow_job,
    serialize_job,
)


async def run_worker() -> None:
    """Recover delivery from durable IDs until interrupted."""

    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger(__name__)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    database = RuntimeDatabase(settings)
    runner = JobRunner(database, settings.local_tenant_id)
    activity = ActivityService(database)
    next_activity_check = 0.0
    logger.info("worker.started", framework="arq", durable_queue="postgresql", codec="json")
    try:
        while not stop_event.is_set():
            worker: Worker | None = None
            task: asyncio.Task[None] | None = None
            try:
                if settings.runtime_profile == "legacy_demo":
                    await database.initialize_tenant(settings.local_tenant_id)
                redis = await create_pool(
                    RedisSettings.from_dsn(settings.redis_url),
                    default_queue_name=settings.worker_queue,
                    job_serializer=serialize_job,
                    job_deserializer=deserialize_job,
                )
                worker = Worker(
                    functions=[
                        process_workflow_job,
                        process_catalog_index_job,
                        process_manager_run,
                        process_ranking_job,
                    ],
                    redis_pool=redis,
                    queue_name=settings.worker_queue,
                    ctx={"runner": runner},
                    handle_signals=False,
                    max_jobs=4,
                    keep_result=0,
                    job_timeout=settings.worker_job_timeout_seconds,
                    health_check_interval=15,
                    job_serializer=serialize_job,
                    job_deserializer=deserialize_job,
                    log_results=False,
                )
                task = asyncio.create_task(worker.async_run())
                cursor: UUID | None = None
                while not stop_event.is_set() and not task.done():
                    if settings.local_runtime_id:
                        await redis.set(
                            f"opencommerce:worker:{settings.local_runtime_id}", "alive", ex=10
                        )
                    tenants = [settings.local_tenant_id]
                    if settings.runtime_profile != "legacy_demo":
                        # Enumerate only registered stores, in bounded round-robin batches.
                        async with database.sessions() as session:
                            query = (
                                select(StoreSetupRecord.tenant_id)
                                .join(Tenant)
                                .where(Tenant.status == "active")
                            )
                            if cursor is not None:
                                query = query.where(StoreSetupRecord.tenant_id > cursor)
                            tenants = list(
                                await session.scalars(
                                    query.order_by(StoreSetupRecord.tenant_id).limit(25)
                                )
                            )
                        cursor = tenants[-1] if tenants else None
                    for tenant_id in tenants:
                        try:
                            await JobRunner(database, tenant_id).publish_due(redis)
                            if (
                                settings.runtime_profile != "legacy_demo"
                                or loop.time() >= next_activity_check
                            ):
                                await activity.evaluate_due(tenant_id)
                                if settings.runtime_profile != "legacy_demo":
                                    from open_commerce.stores.imports import CatalogImportService
                                    from open_commerce.stores.shoppers import ShopperAccounts

                                    await CatalogImportService(database).cleanup(tenant_id)
                                    await ShopperAccounts(database).cleanup(tenant_id)
                                    from open_commerce.stores.measurement import check_monitors

                                    await check_monitors(database, tenant_id)
                        except Exception as exc:
                            logger.warning(
                                "store.background_unavailable", error_type=type(exc).__name__
                            )
                    if loop.time() >= next_activity_check:
                        next_activity_check = loop.time() + 30
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), timeout=1)
                if task.done():
                    await task
            except Exception as exc:
                logger.warning("worker.delivery_unavailable", error_type=type(exc).__name__)
            finally:
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
                if worker is not None:
                    with contextlib.suppress(Exception):
                        await worker.close()
            if not stop_event.is_set():
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=2)
    finally:
        await database.close()
        logger.info("worker.stopped")


def main() -> None:
    """Process entrypoint."""

    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
