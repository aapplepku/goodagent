"""Readiness probes for the bootstrap infrastructure dependencies."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from time import perf_counter

import httpx
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.api.schemas import DependencyStatus, ServiceStatus
from open_commerce.config import Settings

DependencyProbe = Callable[[Settings], Awaitable[None]]


async def check_postgres(settings: Settings) -> None:
    """Verify PostgreSQL accepts a trivial query."""

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    finally:
        await engine.dispose()


async def check_redis(settings: Settings) -> None:
    """Verify Redis accepts a ping."""

    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    try:
        await client.ping()
    finally:
        await client.aclose()


async def check_qdrant(settings: Settings) -> None:
    """Verify Qdrant responds to the collections endpoint."""

    timeout_seconds = max(1, int(settings.readiness_timeout_seconds))
    client = AsyncQdrantClient(url=settings.qdrant_url, timeout=timeout_seconds)
    try:
        await client.get_collections()
    finally:
        await client.close()


async def check_manager_web(settings: Settings) -> None:
    async with httpx.AsyncClient(timeout=settings.readiness_timeout_seconds) as client:
        response = await client.get(settings.manager_web_health_url)
        response.raise_for_status()


async def check_shopper_web(settings: Settings) -> None:
    async with httpx.AsyncClient(timeout=settings.readiness_timeout_seconds) as client:
        response = await client.get(settings.shopper_web_health_url)
        response.raise_for_status()


async def check_local_worker(settings: Settings) -> None:
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    try:
        if not await client.exists(f"opencommerce:worker:{settings.local_runtime_id}"):
            raise ConnectionError("No current worker heartbeat")
    finally:
        await client.aclose()


async def _measure(
    name: str,
    settings: Settings,
    probe: DependencyProbe,
) -> DependencyStatus:
    start = perf_counter()
    try:
        await asyncio.wait_for(probe(settings), timeout=settings.readiness_timeout_seconds)
    except Exception as exc:
        latency_ms = round((perf_counter() - start) * 1000, 2)
        return DependencyStatus(
            name=name,
            ok=False,
            latency_ms=latency_ms,
            detail=type(exc).__name__,
        )
    latency_ms = round((perf_counter() - start) * 1000, 2)
    return DependencyStatus(name=name, ok=True, latency_ms=latency_ms)


async def run_readiness_checks(settings: Settings) -> list[DependencyStatus]:
    """Run all bootstrap readiness checks concurrently."""

    checks: tuple[tuple[str, DependencyProbe], ...] = (
        ("postgres", check_postgres),
        ("redis", check_redis),
        ("qdrant", check_qdrant),
    )
    return list(
        await asyncio.gather(
            *(_measure(name, settings, probe) for name, probe in checks),
        ),
    )


async def run_manager_status_checks(settings: Settings) -> list[DependencyStatus]:
    """Probe operator-visible surfaces without coupling them to API readiness."""

    dependencies = await run_readiness_checks(settings)
    surfaces: tuple[tuple[str, DependencyProbe], ...] = (
        ("manager_web", check_manager_web),
        ("shopper_web", check_shopper_web),
    )
    if settings.local_runtime_id:
        surfaces += (("worker", check_local_worker),)
    return [
        *dependencies,
        *(await asyncio.gather(*(_measure(name, settings, probe) for name, probe in surfaces))),
    ]


def aggregate_status(dependencies: Sequence[DependencyStatus]) -> ServiceStatus:
    """Return the aggregate readiness status."""

    return "ready" if all(dependency.ok for dependency in dependencies) else "not_ready"
