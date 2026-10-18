import asyncio
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings

pytestmark = pytest.mark.integration


def _admin_url(database_url: str) -> URL:
    url = make_url(database_url)
    return url.set(database="postgres")


def _quote_database_name(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError("temporary database name contains unsupported characters")
    return f'"{name}"'


async def _create_empty_database(database_url: str) -> tuple[str, str]:
    source_url = make_url(database_url)
    base_name = source_url.database or "opencommerce"
    test_database = f"{base_name}_migration_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(_admin_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(f"CREATE DATABASE {_quote_database_name(test_database)} TEMPLATE template0"),
            )
    finally:
        await engine.dispose()
    return source_url.set(database=test_database).render_as_string(
        hide_password=False
    ), test_database


async def _drop_database(database_url: str, database_name: str) -> None:
    engine = create_async_engine(_admin_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name",
                ),
                {"name": database_name},
            )
            await connection.execute(
                text(f"DROP DATABASE IF EXISTS {_quote_database_name(database_name)}"),
            )
    finally:
        await engine.dispose()


def test_alembic_migration_from_empty_database() -> None:
    if os.getenv("OPEN_COMMERCE_RUN_INTEGRATION") != "1":
        pytest.skip("integration dependencies are not enabled")

    database_url = Settings().database_url
    test_database_url, test_database = asyncio.run(_create_empty_database(database_url))
    try:
        env = os.environ.copy()
        env["OPEN_COMMERCE_DATABASE_URL"] = test_database_url
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
        subprocess.run([sys.executable, "-m", "alembic", "downgrade", "base"], check=True, env=env)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    finally:
        asyncio.run(_drop_database(database_url, test_database))


async def _seed_legacy_manager_conversation(database_url: str) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    message_id = uuid.uuid4()
    now = datetime.now(UTC)
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO tenants "
                    "(id, slug, display_name, default_currency, timezone, status, created_at, "
                    "updated_at, version) VALUES "
                    "(:id, :slug, :name, 'USD', 'UTC', 'active', :now, :now, 1)"
                ),
                {"id": tenant_id, "slug": f"legacy-{tenant_id.hex}", "name": "Legacy", "now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO manager_threads "
                    "(id, tenant_id, title, status, working_memory, user_turn_count, created_at, "
                    "updated_at, version) VALUES "
                    "(:id, :tenant_id, 'Existing history', 'active', "
                    "CAST(:working AS jsonb), 0, :now, :now, 1)"
                ),
                {
                    "id": thread_id,
                    "tenant_id": tenant_id,
                    "working": json.dumps(
                        {
                            "current_topic": None,
                            "open_question": None,
                            "objective": None,
                            "recent_decisions": [],
                        }
                    ),
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO manager_messages "
                    "(id, tenant_id, thread_id, role, content, steps, created_at) VALUES "
                    "(:id, :tenant_id, :thread_id, 'assistant', 'Preserve this message', "
                    "CAST(:steps AS jsonb), :now)"
                ),
                {
                    "id": message_id,
                    "tenant_id": tenant_id,
                    "thread_id": thread_id,
                    "steps": "[]",
                    "now": now,
                },
            )
    finally:
        await engine.dispose()
    return thread_id, message_id


async def _read_upgraded_manager_conversation(
    database_url: str, thread_id: uuid.UUID, message_id: uuid.UUID
) -> tuple[str, str, str, str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT t.thread_type, t.channel_kind, t.slug, m.content "
                        "FROM manager_threads t JOIN manager_messages m ON m.thread_id = t.id "
                        "WHERE t.id = :thread_id AND m.id = :message_id"
                    ),
                    {"thread_id": thread_id, "message_id": message_id},
                )
            ).one()
            return str(row[0]), str(row[1]), str(row[2]), str(row[3])
    finally:
        await engine.dispose()


def test_workspace_migration_backfills_existing_conversations_without_history_loss() -> None:
    if os.getenv("OPEN_COMMERCE_RUN_INTEGRATION") != "1":
        pytest.skip("integration dependencies are not enabled")

    database_url = Settings().database_url
    test_database_url, test_database = asyncio.run(_create_empty_database(database_url))
    env = {**os.environ, "OPEN_COMMERCE_DATABASE_URL": test_database_url}
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "0010_manager_data_onboarding"],
            check=True,
            env=env,
        )
        thread_id, message_id = asyncio.run(_seed_legacy_manager_conversation(test_database_url))
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)

        thread_type, channel_kind, slug, content = asyncio.run(
            _read_upgraded_manager_conversation(test_database_url, thread_id, message_id)
        )
        assert (thread_type, channel_kind) == ("channel", "custom")
        assert slug == f"channel-{thread_id.hex}"
        assert content == "Preserve this message"
    finally:
        asyncio.run(_drop_database(database_url, test_database))
