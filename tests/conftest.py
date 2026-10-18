"""Disposable real PostgreSQL databases for integration and fault tests."""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings


@pytest.fixture(scope="session")
def integration_settings() -> Iterator[Settings]:
    if os.getenv("OPEN_COMMERCE_RUN_INTEGRATION") != "1":
        pytest.skip("set OPEN_COMMERCE_RUN_INTEGRATION=1 for real database tests")
    source = Settings()
    url = make_url(os.getenv("OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL", source.database_url))
    name = f"opencommerce_test_{uuid4().hex}"

    async def change_database(*, create: bool) -> None:
        engine = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                statement = (
                    f'CREATE DATABASE "{name}" TEMPLATE template0'
                    if create
                    else f'DROP DATABASE "{name}" WITH (FORCE)'
                )
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    asyncio.run(change_database(create=True))
    database_url = url.set(database=name).render_as_string(hide_password=False)
    try:
        env = {**os.environ, "OPEN_COMMERCE_DATABASE_URL": database_url}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
        yield source.model_copy(update={"database_url": database_url, "environment": "test"})
    finally:
        asyncio.run(change_database(create=False))
