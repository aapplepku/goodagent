"""Capture-only guards and evidence. Never imported by production entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import ipaddress
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from PIL import Image, UnidentifiedImageError
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from open_commerce.config import Settings

ROOT = Path(__file__).resolve().parents[2]
OPT_IN = "OPEN_COMMERCE_CAPTURE_CATALOG_DEMO"
DATABASE_NAME = re.compile(r"opencommerce_test_[a-f0-9]{32}\Z")
KINDS = {
    "network",
    "dns",
    "envfile",
    "model",
    "remote_image",
    "settings",
    "database",
    "credential_file",
}
PG_CREDENTIAL_FILES = ("PGPASSFILE", "PGSSLCERT", "PGSSLKEY", "PGSSLROOTCERT", "PGSSLCRL")
NEXT_DIST_DIR = ".next-self-service-qa"


class DemoSafetyError(RuntimeError):
    """A bounded, non-secret failure safe to put in a private result."""


def require(condition: object, code: str) -> None:
    if not condition:
        raise DemoSafetyError(code)


def private_path(path: Path, *, new: bool = False) -> Path:
    path = Path(os.path.abspath(path))
    require(path.is_relative_to(ROOT / ".opencommerce"), "output_outside_private_root")
    for item in (path, *path.parents):
        require(not item.is_symlink(), "symlink_output")
    if new:
        require(not path.exists(), "output_already_exists")
    return path


def private_json(path: Path, value: object) -> None:
    private_path(path, new=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def reject_next_envfiles(directory: Path) -> None:
    require(not any(directory.glob(".env*")), "next_envfile_present")


def verify_next_cache_idle(directory: Path) -> None:
    """Serial QA cache reuse, not a cold build or a cross-process scheduling lock."""
    reject_next_envfiles(directory)
    reference = f'/// <reference path="./{NEXT_DIST_DIR}/types/routes.d.ts" />'
    require(reference in (directory / "next-env.d.ts").read_text(), "next_cache_reference_changed")
    trace = directory / NEXT_DIST_DIR / "trace"
    require(not trace.is_symlink() and not trace.parent.is_symlink(), "symlink_next_cache")
    if not trace.exists():
        return
    lsof = shutil.which("lsof")
    require(lsof is not None, "cache_ownership_check_unavailable")
    assert lsof is not None
    checked = subprocess.run(
        [lsof, "-t", "--", str(trace)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    require(checked.returncode == 1 and not checked.stdout.strip(), "qa_cache_not_verified_idle")


def read_json(path: Path) -> dict[str, Any]:
    private_path(path)
    require(path.is_file() and path.stat().st_size <= 256_000, "invalid_receipt_file")
    with path.open() as stream:
        value = json.load(stream)
    require(isinstance(value, dict), "invalid_receipt")
    return dict(value)


def endpoint(host: str | None, port: int | None) -> tuple[str, int]:
    require(host is not None and port is not None and 0 < port < 65536, "endpoint_required")
    assert host is not None and port is not None
    if host == "localhost":
        host = "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise DemoSafetyError("numeric_loopback_required") from None
    require(address.is_loopback, "loopback_required")
    return str(address), port


def app_endpoints(env: Mapping[str, str]) -> frozenset[tuple[str, int]]:
    result = set()
    for key in ("PLAYWRIGHT_BASE_URL", "SHOPPER_PLAYWRIGHT_BASE_URL"):
        value = urlsplit(env[key])
        require(
            value.scheme == "http"
            and value.hostname == "127.0.0.1"
            and not value.path
            and not value.query
            and not value.fragment
            and not value.username
            and not value.password,
            "invalid_app_origin",
        )
        result.add(endpoint(value.hostname, value.port))
    return frozenset(result)


@dataclass(frozen=True)
class QaEndpoints:
    database: str = field(repr=False)
    redis: str = field(repr=False)
    qdrant: str = field(repr=False)
    allowed: frozenset[tuple[str, int]]

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> QaEndpoints:
        names = (
            "OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL",
            "OPEN_COMMERCE_REDIS_URL",
            "OPEN_COMMERCE_QDRANT_URL",
        )
        require(all(env.get(name) for name in names), "explicit_qa_endpoints_required")
        try:
            database = make_url(env[names[0]])
            require(database.drivername == "postgresql+asyncpg", "asyncpg_required")
            require(not database.query, "database_query_not_allowed")
            require(
                database.username and database.password, "explicit_database_credentials_required"
            )
            db_address = endpoint(database.host, database.port)
            database = database.set(host=db_address[0])
            values: list[str] = []
            addresses = {db_address}
            for name, scheme in ((names[1], "redis"), (names[2], "http")):
                raw = urlsplit(env[name])
                require(
                    raw.scheme == scheme and not raw.query and not raw.fragment,
                    "invalid_dependency_url",
                )
                require(not raw.username and not raw.password, "dependency_credentials_unsupported")
                address = endpoint(raw.hostname, raw.port)
                require(
                    raw.path in ("", "/", "/0") if scheme == "redis" else raw.path in ("", "/"),
                    "dependency_path_not_allowed",
                )
                host = f"[{address[0]}]" if ":" in address[0] else address[0]
                values.append(urlunsplit((scheme, f"{host}:{address[1]}", raw.path, "", "")))
                addresses.add(address)
            return cls(
                database.render_as_string(hide_password=False),
                values[0],
                values[1],
                frozenset(addresses),
            )
        except (ValueError, KeyError):
            raise DemoSafetyError("invalid_qa_endpoints") from None


def clean_environment(env: Mapping[str, str]) -> dict[str, str]:
    result = {key: env[key] for key in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT") if key in env}
    result.update(
        {
            "PYTHONPATH": f"{ROOT / 'packages/backend/src'}{os.pathsep}{ROOT}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "NEXT_TELEMETRY_DISABLED": "1",
            "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": "deterministic",
            "OPEN_COMMERCE_MODEL_ENABLED": "false",
            "OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND": "hash",
            "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": "false",
            "OPEN_COMMERCE_OPENAI_API_KEY": "",
            "OPEN_COMMERCE_RUNTIME_PROFILE": "self_hosted",
            OPT_IN: "1",
        }
    )
    return result


def settings_from_env(env: Mapping[str, str]) -> Settings:
    env = dict(env)
    require(env.get(OPT_IN) == "1", "explicit_opt_in_required")
    qa = QaEndpoints.from_env(env)
    database = make_url(env.get("OPEN_COMMERCE_DATABASE_URL", qa.database))
    admin = make_url(qa.database)
    require(
        endpoint(database.host, database.port) == endpoint(admin.host, admin.port),
        "database_endpoint_changed",
    )
    require(not database.query and database.drivername == "postgresql+asyncpg", "invalid_database")
    require(
        database.username == admin.username and database.password == admin.password,
        "database_identity_changed",
    )
    require(bool(DATABASE_NAME.fullmatch(database.database or "")), "disposable_database_required")
    require(env.get("OPEN_COMMERCE_MANAGER_MODEL_PROVIDER") == "deterministic", "model_selection")
    require(env.get("OPEN_COMMERCE_MODEL_ENABLED") == "false", "controller_model_enabled")
    require(env.get("OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND") == "hash", "embedding_selection")
    require(env.get("OPEN_COMMERCE_RUNTIME_PROFILE") == "self_hosted", "runtime_profile")
    require(env.get("OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED") == "false", "local_operations")
    require(not env.get("OPEN_COMMERCE_OPENAI_API_KEY"), "provider_key_present")
    require(not any("proxy" in key.lower() for key in env), "proxy_environment")
    runtime_id = UUID(env["OPEN_COMMERCE_LOCAL_RUNTIME_ID"])
    app_endpoints(env)
    assets = private_path(Path(env["OPEN_COMMERCE_ASSET_DIRECTORY"]))
    # Pydantic must not fill unspecified fields from the supervisor's ambient environment.
    with patch.dict(os.environ, {}, clear=True):
        return Settings(
            _env_file=None,
            environment="test",
            runtime_profile="self_hosted",
            database_url=database.render_as_string(hide_password=False),
            redis_url=qa.redis,
            qdrant_url=qa.qdrant,
            manager_model_provider="deterministic",
            model_enabled=False,
            search_embedding_backend="hash",
            search_model_directory=None,
            openai_api_key=None,
            local_operations_enabled=False,
            local_runtime_id=runtime_id,
            asset_directory=assets,
            encryption_key=SecretStr(env["OPEN_COMMERCE_ENCRYPTION_KEY"]),
            shopper_public_url=env["SHOPPER_PLAYWRIGHT_BASE_URL"],
            public_origins=[env["PLAYWRIGHT_BASE_URL"], env["SHOPPER_PLAYWRIGHT_BASE_URL"]],
            manager_web_health_url=env["PLAYWRIGHT_BASE_URL"] + "/health",
            shopper_web_health_url=env["SHOPPER_PLAYWRIGHT_BASE_URL"] + "/health",
        )


class RuntimeGuard:
    """Process-local Python audit barrier; not an OS sandbox or a Node guard."""

    def __init__(self, directory: Path, role: str, allowed: frozenset[tuple[str, int]]) -> None:
        require(role in {"supervisor", "api", "worker", "migrate"}, "invalid_guard_role")
        self.directory = private_path(directory)
        self.role, self.allowed = role, allowed
        self.counts = dict.fromkeys(sorted(KINDS), 0)
        self.active = False
        self.lock = threading.RLock()
        self.patches = contextlib.ExitStack()
        self.credential_files = {
            os.path.abspath(os.environ[key]) for key in PG_CREDENTIAL_FILES if os.environ.get(key)
        }
        self.log_path = directory / f"{role}.guard.jsonl"
        self.fd = os.open(
            self.log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        self._write({"event": "created", "role": role})

    def _write(self, value: object) -> None:
        data = (json.dumps(value, sort_keys=True) + "\n").encode()
        with self.lock:
            written = os.write(self.fd, data)
            require(written == len(data), "guard_evidence_write_failed")
            os.fsync(self.fd)

    def reject(self, kind: str) -> None:
        with self.lock:
            self.counts[kind] += 1
            self._write({"event": "denied", "kind": kind, "count": self.counts[kind]})
        raise DemoSafetyError(f"forbidden_{kind}")

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        if event == "open" and isinstance(args[0], str | bytes | os.PathLike):
            path = Path(os.fsdecode(args[0]))
            name = path.name
            if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
                self.reject("envfile")
            if (
                name in {".pgpass", "pgpass.conf"}
                or ".postgresql" in path.parts
                or os.path.abspath(path) in self.credential_files
            ):
                self.reject("credential_file")
        if event in {"socket.connect", "socket.sendto"}:
            address = args[1] if event == "socket.connect" else args[-1]
            if (
                event == "socket.sendto"
                or not isinstance(address, tuple)
                or len(address) < 2
                or (address[0], address[1]) not in self.allowed
            ):
                self.reject("network")
        if event == "socket.getaddrinfo":
            host, port = args[:2]
            if (host, port) not in self.allowed:
                self.reject("dns")
        elif event in {"socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo"}:
            self.reject("dns")
        elif event == "socket.sendmsg":
            # CPython audits (socket, explicit_address), not the buffers being sent.
            permitted = False
            if len(args) == 2 and args[1] is None:
                stream = args[0]
                if (
                    isinstance(stream, socket.socket)
                    and stream.family in {socket.AF_INET, socket.AF_INET6}
                    and stream.type == socket.SOCK_STREAM
                ):
                    try:
                        peer = stream.getpeername()
                    except OSError:
                        pass
                    else:
                        permitted = (
                            isinstance(peer, tuple)
                            and len(peer) == (2 if stream.family == socket.AF_INET else 4)
                            and peer[:2] in self.allowed
                            and (stream.family == socket.AF_INET or peer[2:] == (0, 0))
                        )
            if not permitted:
                self.reject("network")

    def install(self, settings: Settings) -> None:
        self.active = True
        sys.addaudithook(self.audit)
        import asyncpg  # type: ignore[import-untyped]

        from open_commerce import config
        from open_commerce.controller.ollama import OllamaBackend
        from open_commerce.providers.catalog_images import SafeCatalogImages
        from open_commerce.providers.openai_manager import (
            OpenAIManagerProvider,
            _OpenAIManagerSession,
        )

        database = make_url(settings.database_url)
        if (
            database.drivername != "postgresql+asyncpg"
            or database.query
            or not database.username
            or not database.password
            or not DATABASE_NAME.fullmatch(database.database or "")
            or (database.host, database.port) not in self.allowed
        ):
            self.reject("settings")
        identity = {
            "host": database.host,
            "port": database.port,
            "user": database.username,
            "password": database.password,
        }
        databases = {database.database}
        if self.role == "supervisor":
            databases.add("postgres")
        original_connect = asyncpg.connect

        async def connect(*args: object, **kwargs: Any) -> Any:
            require(self.active, "database_guard_closed")
            if (
                args
                or set(kwargs) != {*identity, "database"}
                or any(kwargs.get(key) != value for key, value in identity.items())
                or not isinstance(kwargs.get("database"), str)
                or kwargs["database"] not in databases
            ):
                self.reject("database")
            # Exact loopback QA only: no libpq environment, passfile or TLS home fallback.
            return await original_connect(
                **kwargs,
                ssl=False,
                passfile=os.devnull,
                direct_tls=False,
                target_session_attrs="any",
                krbsrvname="postgres",
                gsslib="gssapi",
            )

        self.patches.enter_context(patch.object(asyncpg, "connect", connect))

        def model(*args: object, **kwargs: object) -> Any:
            self.reject("model")

        async def model_async(*args: object, **kwargs: object) -> Any:
            self.reject("model")

        def image(*args: object, **kwargs: object) -> Any:
            self.reject("remote_image")

        for cls, method, replacement in (
            (OpenAIManagerProvider, "__init__", model),
            (OpenAIManagerProvider, "begin", model),
            (_OpenAIManagerSession, "next", model_async),
            (OllamaBackend, "complete", model_async),
            (SafeCatalogImages, "_fetch", image),
        ):
            self.patches.enter_context(patch.object(cls, method, replacement))
        self.patches.enter_context(patch.object(config, "get_settings", lambda: settings))
        self._write(
            {
                "event": "installed",
                "mode": "deterministic",
                "embedding": "hash",
                "database_credentials": "explicit",
                "database_tls": False,
            }
        )

    def close(self) -> None:
        if self.fd < 0:
            return
        self.active = False
        self.patches.close()
        self._write({"event": "closed", "counts": self.counts})
        os.close(self.fd)
        self.fd = -1


def verify_guard_logs(directory: Path, roles: tuple[str, ...]) -> None:
    for role in roles:
        path = private_path(directory / f"{role}.guard.jsonl")
        require(path.is_file(), "missing_guard_evidence")
        events = [json.loads(line) for line in path.read_text().splitlines()]
        require(any(event.get("event") == "installed" for event in events), "guard_not_installed")
        require(not any(event.get("event") == "denied" for event in events), "guard_violation")
        require(events[-1].get("event") == "closed", "guard_not_closed")
        require(all(value == 0 for value in events[-1]["counts"].values()), "guard_violation")


def wait_for_failed_capture(
    browser: subprocess.Popen[bytes], output: Path, *, timeout: float = 45
) -> dict[str, bool]:
    """No further workflow actions while the recorder closes its failed take."""
    try:
        browser.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"browser_exited": False, "failed_receipt": False, "timed_out": True}
    try:
        receipt = read_json(output / "receipt.json")
        failed = receipt.get("passed") is False
    except (OSError, ValueError, DemoSafetyError):
        failed = False
    return {"browser_exited": True, "failed_receipt": failed, "timed_out": False}


def reject_milestone(
    stage: str, directory: Path, browser: subprocess.Popen[bytes], output: Path
) -> None:
    require(stage in {"owner-ready", "preview-tested"}, "invalid_milestone")
    private_json(directory / f"{stage}.ack.json", {"passed": False, "stage": stage})
    finalized = wait_for_failed_capture(browser, output)
    private_json(directory / "failed-capture-finalization.json", finalized)


def validate_receipt(receipt: Mapping[str, Any]) -> tuple[UUID, UUID, UUID]:
    require(receipt.get("schema_version") == 1 and receipt.get("passed") is True, "capture_failed")
    require(receipt.get("model_mode") == "deterministic", "receipt_model_mode")
    require(receipt.get("browser_denied_requests") == 0, "browser_egress")
    product = receipt.get("preview_product", {})
    require(
        product.get("product_id") == "B0896LJNLH"
        and product.get("price_minor") == 1388
        and product.get("currency") == "USD",
        "preview_product_mismatch",
    )
    require(
        bool(re.fullmatch(r"sha256:[a-f0-9]{64}", str(receipt.get("review_fingerprint", "")))),
        "missing_review_fingerprint",
    )
    return UUID(receipt["store_id"]), UUID(receipt["import_id"]), UUID(receipt["catalog_id"])


def source_snapshot() -> dict[str, str]:
    paths = [
        "tests/integration/deterministic_demo_runtime.py",
        "tests/integration/test_deterministic_catalog_demo.py",
        "tests/contract/test_deterministic_demo_runtime.py",
        "apps/web/capture/catalog-demo.spec.ts",
        "apps/web/catalog-demo.config.ts",
        "apps/web/capture/catalog-demo-utils.ts",
        "apps/web/capture/catalog-demo-reporter.ts",
        "apps/web/capture/alpha-recording-utils.ts",
        "apps/web/next-env.d.ts",
        "apps/shopper/next-env.d.ts",
    ]
    for base, suffixes in (
        ("packages/backend/src", {".py", ".json", ".csv"}),
        ("apps/web/src", {".ts", ".tsx", ".css"}),
        ("apps/shopper/src", {".ts", ".tsx", ".css"}),
    ):
        paths.extend(
            str(path.relative_to(ROOT))
            for path in (ROOT / base).rglob("*")
            if path.is_file() and path.suffix in suffixes
        )
    result = {}
    for name in sorted(set(paths)):
        path = ROOT / name
        require(not path.is_symlink() and path.is_file(), "source_identity_missing")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def audit_png(path: Path, expected_sha256: str) -> dict[str, Any]:
    private_path(path)
    require(path.is_file() and path.stat().st_size <= 8_000_000, "invalid_asset_file")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    require(digest == expected_sha256, "asset_hash_mismatch")
    try:
        with Image.open(io.BytesIO(data), formats=("PNG",)) as source:
            require(
                source.format == "PNG"
                and source.mode == "RGB"
                and 0 < source.width <= 1600
                and 0 < source.height <= 1600,
                "asset_format_or_dimensions",
            )
            source.load()
            return {"sha256": digest, "width": source.width, "height": source.height}
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise DemoSafetyError("asset_decode_failed") from None


async def cleanup_scoped_dependencies(settings: Settings, tenant: UUID | None) -> None:
    """Delete only this runtime's queue and this tenant's exact catalog projections."""
    from qdrant_client import AsyncQdrantClient, models
    from redis.asyncio import Redis

    from open_commerce.persistence.models.catalog_import import CatalogImportRecord
    from open_commerce.persistence.runtime_db import RuntimeDatabase
    from open_commerce.search.qdrant_index import PRODUCT_COLLECTION, build_qdrant_filter

    require(settings.local_runtime_id is not None, "cleanup_runtime_required")
    require(
        settings.worker_queue == f"arq:stores:{settings.local_runtime_id}", "cleanup_queue_scope"
    )
    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.delete(
            settings.worker_queue,
            settings.worker_queue + ":health-check",
            f"opencommerce:worker:{settings.local_runtime_id}",
        )
    finally:
        await redis.aclose()
    if tenant is None:
        return
    database = RuntimeDatabase(settings)
    client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
    try:
        async with database.transaction(tenant) as session:
            catalogs = list(
                await session.scalars(
                    select(CatalogImportRecord.catalog_id).where(
                        CatalogImportRecord.tenant_id == tenant,
                        CatalogImportRecord.catalog_id.is_not(None),
                    )
                )
            )
        if catalogs and await client.collection_exists(PRODUCT_COLLECTION):
            for catalog in catalogs:
                assert catalog is not None
                await client.delete(
                    collection_name=PRODUCT_COLLECTION,
                    points_selector=models.FilterSelector(
                        filter=build_qdrant_filter(tenant, instance_id=catalog)
                    ),
                    wait=True,
                )
    finally:
        await client.close()
        await database.close()


async def audit_store(settings: Settings, message: Mapping[str, Any], stage: str) -> dict[str, Any]:
    from open_commerce.persistence.models.catalog import Product, ProductVariant
    from open_commerce.persistence.models.catalog_import import (
        CatalogAssetRecord,
        CatalogImportRecord,
    )
    from open_commerce.persistence.models.identity import Tenant
    from open_commerce.persistence.models.inference import InferenceCall
    from open_commerce.persistence.models.integrations import Integration
    from open_commerce.persistence.models.manager_runs import ManagerRunRecord
    from open_commerce.persistence.models.model_usage import ModelUsageRecord
    from open_commerce.persistence.models.search import CatalogIndexJob, SearchIndexVersion
    from open_commerce.persistence.models.store_setup import SetupEventRecord, StoreSetupRecord
    from open_commerce.persistence.runtime_db import RuntimeDatabase

    tenant = UUID(message["store_id"])
    database = RuntimeDatabase(settings)
    result: dict[str, Any] = {"stage": stage, "store_id": str(tenant)}
    try:
        async with database.transaction(tenant) as session:
            store = await session.scalar(
                select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == tenant)
            )
            owner = await session.scalar(select(Tenant).where(Tenant.id == tenant))
            require(store is not None and owner is not None, "store_missing")
            assert store is not None and owner is not None
            for model in (ModelUsageRecord, InferenceCall, ManagerRunRecord):
                count = await session.scalar(
                    select(func.count()).select_from(model).where(model.tenant_id == tenant)
                )
                require(count == 0, "unexpected_model_activity")
                result[model.__tablename__] = count
            require(store.readiness.get("ai_verified") is not True, "unexpected_ai_verified")
            if stage == "baseline":
                require(
                    not store.sharing_enabled and store.published_catalog_id is None,
                    "not_fresh_store",
                )
                count = await session.scalar(
                    select(func.count())
                    .select_from(CatalogImportRecord)
                    .where(CatalogImportRecord.tenant_id == tenant)
                )
                require(count == 0, "preexisting_import")
                return result
            catalog, import_id = UUID(message["catalog_id"]), UUID(message["import_id"])
            source = await session.scalar(
                select(CatalogImportRecord).where(
                    CatalogImportRecord.tenant_id == tenant, CatalogImportRecord.id == import_id
                )
            )
            integration = await session.scalar(
                select(Integration).where(
                    Integration.tenant_id == tenant, Integration.id == catalog
                )
            )
            job = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == tenant, CatalogIndexJob.integration_id == catalog
                )
            )
            require(
                source is not None and integration is not None and job is not None,
                "catalog_evidence_missing",
            )
            assert source is not None and integration is not None and job is not None
            require(
                source.status == "confirmed"
                and source.catalog_id == catalog
                and source.report.get("sample_data") is True,
                "import_mismatch",
            )
            if stage in {"published", "final"}:
                require(
                    source.report.get("review_fingerprint") == message["review_fingerprint"],
                    "review_mismatch",
                )
                require(owner.slug == message["store_slug"], "store_slug_mismatch")
            require(
                integration.status == "active"
                and integration.non_secret_config.get("sample_data") is True,
                "integration_mismatch",
            )
            require(
                job.status == "ready"
                and job.product_count == job.indexed_product_count == 48
                and job.attempts > 0
                and job.failures == 0,
                "index_not_ready",
            )
            require(
                integration.non_secret_config.get("source_version") == job.source_version,
                "source_version_mismatch",
            )
            version = await session.scalar(
                select(SearchIndexVersion).where(
                    SearchIndexVersion.tenant_id == tenant,
                    SearchIndexVersion.id
                    == uuid5(NAMESPACE_URL, f"{tenant}:{catalog}:{job.source_version}"),
                )
            )
            require(
                version is not None
                and version.status == "ready"
                and version.indexed_product_count == 48
                and version.embedding_model == "local-hash-embedding-v1",
                "projection_metadata_mismatch",
            )
            products = list(
                await session.scalars(
                    select(Product).where(
                        Product.tenant_id == tenant, Product.integration_id == catalog
                    )
                )
            )
            assets = list(
                await session.scalars(
                    select(CatalogAssetRecord).where(
                        CatalogAssetRecord.tenant_id == tenant,
                        CatalogAssetRecord.import_id == import_id,
                    )
                )
            )
            require(len(products) == len(assets) == 48, "sample_count_mismatch")
            image_urls = {
                f"/api/runtime/v1/shopper/assets/{asset.id}?store={owner.slug}" for asset in assets
            }
            require({p.primary_image_url for p in products} == image_urls, "asset_binding_mismatch")
            require(
                all(
                    p.primary_image_url in image_urls
                    and p.attributes.get("safe_image_pending") is False
                    and p.attributes.get("image_failed") is False
                    for p in products
                ),
                "sample_images_incomplete",
            )
            image_evidence = []
            for asset in assets:
                path = private_path(settings.asset_directory / str(tenant) / f"{asset.id}.png")
                image_evidence.append({"asset_id": str(asset.id), **audit_png(path, asset.sha256)})
            selected = [p for p in products if p.source_product_id == "B0896LJNLH"]
            require(len(selected) == 1, "expected_product_missing")
            variant = await session.scalar(
                select(ProductVariant).where(
                    ProductVariant.tenant_id == tenant,
                    ProductVariant.product_id == selected[0].id,
                    ProductVariant.source_variant_id == "B0896LJNLH-default",
                )
            )
            require(
                variant is not None and variant.price_minor == 1388 and variant.currency == "USD",
                "expected_variant_mismatch",
            )
            require(store.readiness.get("tested_catalog_id") == str(catalog), "preview_not_tested")
            if stage == "preview-tested":
                require(
                    not store.sharing_enabled and store.published_catalog_id is None,
                    "premature_publication",
                )
            else:
                require(
                    store.sharing_enabled
                    and store.published_catalog_id == catalog
                    and store.sample_data,
                    "publication_mismatch",
                )
                require(
                    store.readiness.get("images_reviewed") is True
                    and store.readiness.get("checkout_acknowledged") is True,
                    "acknowledgements_missing",
                )
                events = list(
                    await session.scalars(
                        select(SetupEventRecord).where(
                            SetupEventRecord.tenant_id == tenant,
                            SetupEventRecord.kind == "sharing_enabled",
                        )
                    )
                )
                require(
                    len(events) == 1 and events[0].details.get("catalog_id") == str(catalog),
                    "publication_event_mismatch",
                )
            result.update(
                catalog_id=str(catalog),
                import_id=str(import_id),
                products=48,
                assets=48,
                decoded_assets=image_evidence,
                source_version=job.source_version,
                index_attempts=job.attempts,
                sharing_enabled=store.sharing_enabled,
            )
        from qdrant_client import AsyncQdrantClient

        from open_commerce.search.qdrant_index import PRODUCT_COLLECTION, build_qdrant_filter

        client = AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)
        try:
            counted = await client.count(
                collection_name=PRODUCT_COLLECTION,
                count_filter=build_qdrant_filter(
                    tenant, instance_id=catalog, source_version=job.source_version
                ),
                exact=True,
            )
            require(counted.count == 48, "projection_count_mismatch")
            result["qdrant_count"] = counted.count
        finally:
            await client.close()
        return result
    finally:
        await database.close()


@dataclass
class OwnedProcesses:
    directory: Path
    processes: list[subprocess.Popen[bytes]] = field(default_factory=list)
    cleanup: list[dict[str, object]] = field(default_factory=list)

    def start(
        self, name: str, command: list[str], env: dict[str, str], cwd: Path
    ) -> subprocess.Popen[bytes]:
        path = private_path(self.directory / f"{name}.log", new=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
            )
        self.processes.append(process)
        return process

    def close(self) -> None:
        processes, self.processes = self.processes, []
        for process in reversed(processes):
            if process.poll() is not None:
                # A reaped leader's group ID can be reused. Never guess at leftover children.
                self.cleanup.append(
                    {
                        "pid": process.pid,
                        "action": "exited_leader_not_signalled",
                        "possible_leftovers_unverified": True,
                    }
                )
                continue
            # Every group was created by this object, never inferred from a port/name.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            self.cleanup.append({"pid": process.pid, "action": "live_owned_group_stopped"})


def _child() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("api", "worker", "migrate"))
    args = parser.parse_args()
    previous_umask = os.umask(0o077)
    directory = private_path(Path(os.environ["CATALOG_DEMO_RUNTIME_DIR"]))
    guard = RuntimeGuard(directory, args.role, frozenset())
    normal_api_shutdown = False
    try:
        try:
            qa = QaEndpoints.from_env(os.environ)
            guard.allowed = qa.allowed | app_endpoints(os.environ)
            settings = settings_from_env(os.environ)
        except Exception:
            guard.reject("settings")
        guard.install(settings)
        if args.role == "api":
            import uvicorn

            from open_commerce.api.main import create_app

            def exit_api(signum: int, frame: FrameType | None) -> None:
                nonlocal normal_api_shutdown
                normal_api_shutdown = True
                raise SystemExit(0)

            # Uvicorn restores and replays SIGTERM after its graceful shutdown.
            previous_handler = signal.signal(signal.SIGTERM, exit_api)
            try:
                uvicorn.run(
                    create_app(settings),
                    host="127.0.0.1",
                    port=int(os.environ["CATALOG_DEMO_API_PORT"]),
                    loop="asyncio",
                    access_log=False,
                    log_level="warning",
                )
            finally:
                signal.signal(signal.SIGTERM, previous_handler)
        elif args.role == "worker":
            from open_commerce.worker import main as worker

            with patch.object(worker, "get_settings", lambda: settings):
                asyncio.run(worker.run_worker())
        else:
            from alembic import command
            from alembic.config import Config

            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    except BaseException as exc:
        if not (normal_api_shutdown and isinstance(exc, SystemExit) and exc.code == 0):
            private_json(
                directory / f"{args.role}.failure.json", {"error_type": type(exc).__name__}
            )
            raise SystemExit(1) from None
    finally:
        guard.close()
        os.umask(previous_umask)


if __name__ == "__main__":
    _child()
