"""Local-only process owner. Models submit service IDs, never process commands."""

import asyncio
import contextlib
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import IO
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.manager_runs import ManagerRunRecord, RuntimeOperationRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase

SERVICES = ("api", "manager_web", "shopper_web", "worker")


def available_port(start: int) -> int:
    for port in range(start, start + 200):
        with socket.socket() as connection:
            # Match application listeners: a closed connection's TIME_WAIT is not a live service.
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                connection.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No local application port is available")


class LocalSupervisor:
    def __init__(self, root: Path, settings: Settings) -> None:
        self.root, self.settings = root, settings
        self.runtime_id = uuid4()
        self.directory = root / ".opencommerce" / "runtime"
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.manifest_path = self.directory / "manifest.json"
        self.ports = {
            "api": available_port(58024),
            "manager_web": available_port(53025),
            "shopper_web": available_port(53225),
        }
        self.database = RuntimeDatabase(settings)
        self.children: dict[str, subprocess.Popen[bytes]] = {}
        self.logs: list[IO[bytes]] = []
        self.env = dict(os.environ)
        self.env.update(
            {
                "OPEN_COMMERCE_DATABASE_URL": settings.database_url,
                "OPEN_COMMERCE_REDIS_URL": settings.redis_url,
                "OPEN_COMMERCE_QDRANT_URL": settings.qdrant_url,
                "OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND": settings.search_embedding_backend,
                "OPEN_COMMERCE_RUNTIME_PROFILE": settings.runtime_profile,
                "OPEN_COMMERCE_LOCAL_RUNTIME_ID": str(self.runtime_id),
                "OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST": str(self.manifest_path),
                "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": str(
                    settings.runtime_profile == "legacy_demo"
                ).lower(),
                "OPEN_COMMERCE_API_BASE_URL": self.origin("api"),
                "OPEN_COMMERCE_MANAGER_WEB_HEALTH_URL": self.origin("manager_web") + "/health",
                "OPEN_COMMERCE_SHOPPER_WEB_HEALTH_URL": self.origin("shopper_web") + "/health",
                "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": settings.manager_model_provider,
                "OPEN_COMMERCE_MANAGER_MODEL_ID": settings.manager_model_id,
                "OPEN_COMMERCE_OPENAI_API_BASE_URL": settings.openai_api_base_url,
                "OPEN_COMMERCE_OPENAI_API_KEY": settings.openai_api_key.get_secret_value()
                if settings.openai_api_key
                else "",
                "OPEN_COMMERCE_LOCAL_TENANT_ID": str(settings.local_tenant_id),
                "NEXT_TELEMETRY_DISABLED": "1",
                "OPEN_COMMERCE_NEXT_DIST_DIR": ".next-local",
            }
        )
        for field in (
            "manager_model_timeout_seconds",
            "manager_model_max_iterations",
            "manager_model_max_tool_calls",
            "manager_model_max_output_tokens",
            "manager_model_max_input_bytes",
            "manager_run_active_seconds",
        ):
            self.env[f"OPEN_COMMERCE_{field.upper()}"] = str(getattr(settings, field))
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node.js is required for the local apps")
        self.commands = {
            "api": [
                sys.executable,
                "-m",
                "uvicorn",
                "open_commerce.api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports["api"]),
            ],
            "worker": [sys.executable, "-m", "open_commerce.worker.main"],
            "manager_web": [
                node,
                str(root / "apps/web/node_modules/next/dist/bin/next"),
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(self.ports["manager_web"]),
            ],
            "shopper_web": [
                node,
                str(root / "apps/shopper/node_modules/next/dist/bin/next"),
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(self.ports["shopper_web"]),
            ],
        }
        self.working_directories = {
            "api": root,
            "worker": root,
            "manager_web": root / "apps/web",
            "shopper_web": root / "apps/shopper",
        }

    def origin(self, service: str) -> str:
        return f"http://127.0.0.1:{self.ports[service]}"

    def write_manifest(self) -> None:
        data = {
            "runtime_id": str(self.runtime_id),
            "supervisor_pid": os.getpid(),
            "created_at": utc_now().isoformat(),
            "provider": self.settings.manager_model_provider,
            "model": self.settings.manager_model_id,
            "credential_configured": self.settings.openai_api_key is not None,
            "services": {
                name: {
                    "pid": child.pid,
                    "owned": True,
                    "url": self.origin(name) if name in self.ports else None,
                    "cwd": str(self.working_directories[name]),
                    "command": self.commands[name],
                    "alive": child.poll() is None,
                }
                for name, child in self.children.items()
            },
        }
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n")
        temporary.chmod(0o600)
        temporary.replace(self.manifest_path)

    def start(self, name: str) -> None:
        if name not in SERVICES:
            raise ValueError("Unknown service")
        log = (self.directory / f"{name}.log").open("ab")
        self.logs.append(log)
        self.children[name] = subprocess.Popen(
            self.commands[name],
            cwd=self.working_directories[name],
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.write_manifest()

    async def stop(self, name: str) -> None:
        child = self.children[name]
        if child.poll() is None:
            # Only the process group we created, never a PID supplied by a tool or manifest.
            os.killpg(child.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(asyncio.to_thread(child.wait), timeout=15)
            except TimeoutError:
                os.killpg(child.pid, signal.SIGKILL)
                await asyncio.to_thread(child.wait)

    async def healthy(self, name: str) -> bool:
        if name not in self.children or self.children[name].poll() is not None:
            return False
        try:
            if name == "worker":
                client = Redis.from_url(self.settings.redis_url)
                try:
                    return bool(await client.exists(f"opencommerce:worker:{self.runtime_id}"))
                finally:
                    await client.aclose()
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    self.origin(name) + ("/health/live" if name == "api" else "/health")
                )
                return bool(response.is_success)
        except (httpx.HTTPError, OSError):
            return False

    async def operation(self, operation_id: UUID) -> None:
        if self.settings.runtime_profile != "legacy_demo":
            raise RuntimeError("Automatic process recovery is disabled outside legacy demo")
        tenant_id = self.settings.local_tenant_id
        async with self.database.transaction(tenant_id, write=True) as session:
            row = await session.scalar(
                select(RuntimeOperationRecord).where(
                    RuntimeOperationRecord.tenant_id == tenant_id,
                    RuntimeOperationRecord.id == operation_id,
                    RuntimeOperationRecord.runtime_id == self.runtime_id,
                    RuntimeOperationRecord.status == "queued",
                )
            )
            if row is None:
                return
            run = await session.scalar(
                select(ManagerRunRecord).where(
                    ManagerRunRecord.tenant_id == tenant_id, ManagerRunRecord.id == row.run_id
                )
            )
            if run is None or run.status in {"cancelled", "failed", "completed"}:
                row.status = "cancelled"
                return
            if run.status != "waiting":
                return
            if row.service not in SERVICES:
                row.status = "failed"
                return
            name = row.service
            row.status = "running"
            row.evidence = {
                **row.evidence,
                "owned_pid": self.children[name].pid,
                "checked_at": utc_now().isoformat(),
                "runtime_id": str(self.runtime_id),
            }
        was_healthy = await self.healthy(name)
        if not was_healthy:
            # Serialize the last cancellation fence with the external process operation.
            async with self.database.transaction(tenant_id, write=True) as session:
                run = await session.scalar(
                    select(ManagerRunRecord).where(
                        ManagerRunRecord.tenant_id == tenant_id, ManagerRunRecord.id == row.run_id
                    )
                )
                operation = await session.scalar(
                    select(RuntimeOperationRecord).where(
                        RuntimeOperationRecord.tenant_id == tenant_id,
                        RuntimeOperationRecord.id == operation_id,
                    )
                )
                if run is None or run.status != "waiting":
                    if operation is not None:
                        operation.status = "cancelled"
                    return
                await self.stop(name)
                self.start(name)
        verified = False
        for _ in range(60):
            if await self.healthy(name):
                verified = True
                break
            await asyncio.sleep(1)
        async with self.database.transaction(tenant_id, write=True) as session:
            row = await session.scalar(
                select(RuntimeOperationRecord).where(
                    RuntimeOperationRecord.tenant_id == tenant_id,
                    RuntimeOperationRecord.id == operation_id,
                    RuntimeOperationRecord.runtime_id == self.runtime_id,
                )
            )
            if row is not None:
                row.status = "completed" if verified else "failed"
                row.updated_at = utc_now()
                row.evidence = {**row.evidence, "healthy_before": was_healthy}
                row.outcome = {
                    "verified": verified,
                    "restarted": not was_healthy,
                    "checked_at": utc_now().isoformat(),
                    "error": None if verified else "HEALTH_VERIFICATION_FAILED",
                }

    async def run(self) -> None:
        stop = asyncio.Event()
        for signum in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(signum, stop.set)
        lock = (self.directory / "supervisor.lock").open("w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for name in SERVICES:
                self.start(name)
            print(
                f"Operator: {self.origin('manager_web')}/manager\n"
                f"Shopper: {self.origin('shopper_web')}",
                flush=True,
            )
            while not stop.is_set():
                if self.settings.runtime_profile != "legacy_demo":
                    await stop.wait()
                    continue
                try:
                    async with self.database.transaction(self.settings.local_tenant_id) as session:
                        ids = list(
                            await session.scalars(
                                select(RuntimeOperationRecord.id)
                                .where(
                                    RuntimeOperationRecord.tenant_id
                                    == self.settings.local_tenant_id,
                                    RuntimeOperationRecord.runtime_id == self.runtime_id,
                                    RuntimeOperationRecord.status == "queued",
                                )
                                .limit(10)
                            )
                        )
                    for operation_id in ids:
                        await self.operation(operation_id)
                except Exception as exc:
                    print(f"Local recovery unavailable: {type(exc).__name__}", flush=True)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=1)
        finally:
            for name in self.children:
                await self.stop(name)
            for log in self.logs:
                log.close()
            await self.database.close()
            lock.close()


def main() -> None:
    root = Path.cwd()
    if not (root / "apps/web").is_dir() or not (root / "Makefile").exists():
        raise RuntimeError("Start the local runtime from the repository root")
    settings = Settings(_env_file=(root / ".env", root / ".opencommerce/local-runtime.env"))
    asyncio.run(LocalSupervisor(root, settings).run())


if __name__ == "__main__":
    main()
