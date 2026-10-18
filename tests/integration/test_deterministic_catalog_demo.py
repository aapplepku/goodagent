"""Opt-in first-only catalog capture. No services are started during collection."""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import shutil
import socket
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from tests.integration.deterministic_demo_runtime import (
    NEXT_DIST_DIR,
    OPT_IN,
    ROOT,
    DemoSafetyError,
    OwnedProcesses,
    QaEndpoints,
    RuntimeGuard,
    audit_store,
    clean_environment,
    cleanup_scoped_dependencies,
    private_json,
    private_path,
    read_json,
    reject_milestone,
    require,
    settings_from_env,
    source_snapshot,
    validate_receipt,
    verify_guard_logs,
    verify_next_cache_idle,
)

pytestmark = pytest.mark.integration


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture(scope="session")
def catalog_demo_database() -> Iterator[tuple[Settings, dict[str, str], Path]]:
    if os.getenv(OPT_IN) != "1" or os.getenv("OPEN_COMMERCE_RUN_INTEGRATION") != "1":
        pytest.skip("Explicit catalog-demo and integration opt-ins are both required")
    qa = QaEndpoints.from_env(os.environ)
    for app in ("web", "shopper"):
        verify_next_cache_idle(ROOT / "apps" / app)
    output = private_path(Path(os.environ["CATALOG_DEMO_OUTPUT"]), new=True)
    test_output = private_path(Path(os.environ["CATALOG_DEMO_TEST_OUTPUT"]), new=True)
    require(
        output != test_output
        and not output.is_relative_to(test_output)
        and not test_output.is_relative_to(output),
        "overlapping_output",
    )
    directory = private_path(output.with_name(output.name + "-runtime"), new=True)
    require(directory.parent.is_dir(), "output_parent_missing")
    directory.mkdir(mode=0o700)
    runtime_id = uuid4()
    ports: set[int] = set()
    while len(ports) < 3:
        ports.add(free_port())
    api_port, web_port, shopper_port = sorted(ports)
    env = clean_environment(os.environ)
    env.update(
        {
            "OPEN_COMMERCE_RUN_INTEGRATION": "1",
            "OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL": qa.database,
            "OPEN_COMMERCE_DATABASE_URL": make_url(qa.database)
            .set(database=f"opencommerce_test_{uuid4().hex}")
            .render_as_string(hide_password=False),
            "OPEN_COMMERCE_REDIS_URL": qa.redis,
            "OPEN_COMMERCE_QDRANT_URL": qa.qdrant,
            "OPEN_COMMERCE_LOCAL_RUNTIME_ID": str(runtime_id),
            "OPEN_COMMERCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(
                secrets.token_bytes(32)
            ).decode(),
            "OPEN_COMMERCE_ASSET_DIRECTORY": str(directory / "assets"),
            "CATALOG_DEMO_OUTPUT": str(output),
            "CATALOG_DEMO_TEST_OUTPUT": str(test_output),
            "CATALOG_DEMO_RUNTIME_DIR": str(directory),
            "CATALOG_DEMO_API_PORT": str(api_port),
            "OPEN_COMMERCE_API_BASE_URL": f"http://127.0.0.1:{api_port}",
            "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{web_port}",
            "SHOPPER_PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{shopper_port}",
            "OPEN_COMMERCE_SHOPPER_PUBLIC_URL": f"http://127.0.0.1:{shopper_port}",
            "OPEN_COMMERCE_NEXT_DIST_DIR": NEXT_DIST_DIR,
        }
    )
    source = settings_from_env(env)
    private_json(
        directory / "runtime-identity.json",
        {
            "runtime_id": str(runtime_id),
            "database_name": make_url(source.database_url).database,
            "worker_queue": source.worker_queue,
            "owned_app_origins": [
                env["OPEN_COMMERCE_API_BASE_URL"],
                env["PLAYWRIGHT_BASE_URL"],
                env["SHOPPER_PLAYWRIGHT_BASE_URL"],
            ],
        },
    )
    allowed = qa.allowed | frozenset(("127.0.0.1", port) for port in ports)
    guard = RuntimeGuard(directory, "supervisor", allowed)
    guard.install(source)
    created = False
    dropped = False
    migration = OwnedProcesses(directory)

    async def change_database(*, create: bool) -> None:
        name = make_url(source.database_url).database
        engine = create_async_engine(
            make_url(qa.database).set(database="postgres"), isolation_level="AUTOCOMMIT"
        )
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

    old_umask = os.umask(0o077)
    try:
        asyncio.run(change_database(create=True))
        created = True
        child = migration.start(
            "migration",
            [sys.executable, "-m", "tests.integration.deterministic_demo_runtime", "migrate"],
            env,
            ROOT,
        )
        require(child.wait(timeout=90) == 0, "migration_failed")
        yield source, env, directory
    finally:
        migration.close()
        try:
            if created:
                asyncio.run(change_database(create=False))
                dropped = True
        finally:
            guard.close()
            os.umask(old_umask)
            private_json(directory / "migration-cleanup.json", migration.cleanup)
            private_json(
                directory / "database-cleanup.json",
                {"created": created, "drop_completed": dropped},
            )
        verify_guard_logs(directory, ("supervisor", "migrate"))


def test_deterministic_catalog_demo(
    catalog_demo_database: tuple[Settings, dict[str, str], Path],
) -> None:
    settings, env, directory = catalog_demo_database
    owned = OwnedProcesses(directory)
    output = Path(env["CATALOG_DEMO_OUTPUT"])
    result: dict[str, Any] = {"passed": False, "mode": "deterministic", "schema_version": 1}
    completed: set[str] = set()
    tenant_id: str | None = None
    before = source_snapshot()
    private_json(directory / "source-before.json", before)

    async def bootstrap() -> str:
        database = RuntimeDatabase(settings)
        try:
            return await MerchantAuthService(database).issue_bootstrap()
        finally:
            await database.close()

    try:
        token = asyncio.run(bootstrap())
        for role in ("api", "worker"):
            owned.start(
                role,
                [sys.executable, "-m", "tests.integration.deterministic_demo_runtime", role],
                env,
                ROOT,
            )
        node = shutil.which("node")
        require(node is not None, "installed_node_required")
        assert node is not None
        # Only the API/worker need database/key settings; browser/app children do not.
        app_env = {
            key: value
            for key, value in env.items()
            if key
            in {
                "PATH",
                "HOME",
                "TMPDIR",
                "SYSTEMROOT",
                "NEXT_TELEMETRY_DISABLED",
                "OPEN_COMMERCE_API_BASE_URL",
                "OPEN_COMMERCE_SHOPPER_PUBLIC_URL",
                "OPEN_COMMERCE_NEXT_DIST_DIR",
                "PLAYWRIGHT_BASE_URL",
                "SHOPPER_PLAYWRIGHT_BASE_URL",
            }
        }
        from urllib.parse import urlsplit

        for app, key in (
            ("web", "PLAYWRIGHT_BASE_URL"),
            ("shopper", "SHOPPER_PLAYWRIGHT_BASE_URL"),
        ):
            verify_next_cache_idle(ROOT / "apps" / app)
            port = urlsplit(env[key]).port
            owned.start(
                app,
                [
                    node,
                    "node_modules/next/dist/bin/next",
                    "dev",
                    "--hostname",
                    "127.0.0.1",
                    "-p",
                    str(port),
                ],
                app_env,
                ROOT / "apps" / app,
            )
        for url in (
            env["OPEN_COMMERCE_API_BASE_URL"] + "/health/live",
            env["PLAYWRIGHT_BASE_URL"] + "/health",
            env["SHOPPER_PLAYWRIGHT_BASE_URL"] + "/health",
        ):
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                require(all(p.poll() is None for p in owned.processes), "owned_process_exited")
                try:
                    if httpx.get(url, timeout=2, trust_env=False).is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise DemoSafetyError("owned_service_timeout")
        browser_env = {
            **app_env,
            OPT_IN: "1",
            "CATALOG_DEMO_OUTPUT": str(output),
            "CATALOG_DEMO_TEST_OUTPUT": env["CATALOG_DEMO_TEST_OUTPUT"],
            "CATALOG_DEMO_RUNTIME_DIR": str(directory),
            "OPEN_COMMERCE_E2E_SETUP_TOKEN": token,
        }
        browser = owned.start(
            "browser",
            [
                node,
                "node_modules/@playwright/test/cli.js",
                "test",
                "--config",
                "catalog-demo.config.ts",
            ],
            browser_env,
            ROOT / "apps/web",
        )
        deadline = time.monotonic() + 600
        while browser.poll() is None:
            require(time.monotonic() < deadline, "capture_timeout")
            for stage in ("owner-ready", "preview-tested"):
                milestone = directory / f"{stage}.json"
                if stage in completed or not milestone.exists():
                    continue
                require(stage == "owner-ready" or "owner-ready" in completed, "milestone_order")
                message = read_json(milestone)
                if tenant_id is None:
                    tenant_id = str(message["store_id"])
                require(message["store_id"] == tenant_id, "milestone_tenant_changed")
                try:
                    facts = asyncio.run(
                        audit_store(
                            settings, message, "baseline" if stage == "owner-ready" else stage
                        )
                    )
                except Exception:
                    reject_milestone(stage, directory, browser, output)
                    raise
                private_json(directory / f"{stage}.audit.json", facts)
                private_json(directory / f"{stage}.ack.json", {"passed": True, "stage": stage})
                completed.add(stage)
            require(all(p.poll() is None for p in owned.processes[:-1]), "owned_process_exited")
            time.sleep(0.1)
        require(browser.returncode == 0, "browser_failed")
        require(completed == {"owner-ready", "preview-tested"}, "missing_milestone")
        receipt = read_json(output / "receipt.json")
        tenant, _, _ = validate_receipt(receipt)
        require(str(tenant) == tenant_id, "receipt_tenant_changed")
        # Stop writers before the final durable snapshot. No service is restarted.
        owned.close()
        facts = asyncio.run(audit_store(settings, receipt, "final"))
        verify_guard_logs(directory, ("migrate", "api", "worker"))
        require(source_snapshot() == before, "source_changed")
        result.update(passed=True, audit=facts)
    except BaseException as exc:
        result["error_type"] = type(exc).__name__
        raise DemoSafetyError("deterministic_capture_incomplete_see_private_summary") from None
    finally:
        try:
            owned.close()
            asyncio.run(
                cleanup_scoped_dependencies(settings, UUID(tenant_id) if tenant_id else None)
            )
        except Exception as exc:
            result.update(passed=False, cleanup_error_type=type(exc).__name__)
            raise DemoSafetyError("owned_cleanup_incomplete") from None
        finally:
            result["owned_process_cleanup"] = owned.cleanup
            private_json(directory / "source-after.json", source_snapshot())
            private_json(directory / "runtime-receipt.json", result)
