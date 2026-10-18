"""Worker health check entrypoint for local containers."""

import asyncio

from redis.asyncio import Redis
from sqlalchemy import text

from open_commerce.config import get_settings
from open_commerce.persistence.db import create_engine


async def check_worker_dependencies() -> None:
    """Check a live ARQ heartbeat and the authoritative database."""

    settings = get_settings()
    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.readiness_timeout_seconds,
        socket_timeout=settings.readiness_timeout_seconds,
    )
    try:
        await client.ping()
        if await client.get(f"{settings.worker_queue}:health-check") is None:
            raise RuntimeError("worker heartbeat is missing")
        engine = create_engine(settings)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
    finally:
        await client.aclose()


def main() -> None:
    """Exit non-zero when worker dependencies are unavailable."""

    asyncio.run(check_worker_dependencies())


if __name__ == "__main__":
    main()
