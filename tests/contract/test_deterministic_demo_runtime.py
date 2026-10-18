"""Offline controls for the opt-in capture; no sockets, SQL or child processes."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, create_autospec
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.engine import make_url

from tests.integration import deterministic_demo_runtime as runtime


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    private = tmp_path / ".opencommerce"
    private.mkdir()
    return {
        runtime.OPT_IN: "1",
        "OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL": "postgresql+asyncpg://fixture:synthetic@127.0.0.1:15432/postgres",
        "OPEN_COMMERCE_DATABASE_URL": f"postgresql+asyncpg://fixture:synthetic@127.0.0.1:15432/opencommerce_test_{uuid4().hex}",
        "OPEN_COMMERCE_REDIS_URL": "redis://127.0.0.1:16379/0",
        "OPEN_COMMERCE_QDRANT_URL": "http://127.0.0.1:16333",
        "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": "deterministic",
        "OPEN_COMMERCE_MODEL_ENABLED": "false",
        "OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND": "hash",
        "OPEN_COMMERCE_RUNTIME_PROFILE": "self_hosted",
        "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": "false",
        "OPEN_COMMERCE_LOCAL_RUNTIME_ID": str(uuid4()),
        "OPEN_COMMERCE_ASSET_DIRECTORY": str(private / "assets"),
        "OPEN_COMMERCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"t" * 32).decode(),
        "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:13000",
        "SHOPPER_PLAYWRIGHT_BASE_URL": "http://127.0.0.1:13001",
    }


def test_explicit_settings_ignore_existing_envfile(
    environment: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=openai\n")
    monkeypatch.setenv("OPEN_COMMERCE_MANAGER_MODEL_ID", "ambient-must-not-survive")
    settings = runtime.settings_from_env(environment)
    assert settings.manager_model_provider == "deterministic"
    assert settings.search_embedding_backend == "hash" and settings.openai_api_key is None
    assert settings.worker_queue == "arq:stores:" + environment["OPEN_COMMERCE_LOCAL_RUNTIME_ID"]
    assert settings.manager_web_health_url == environment["PLAYWRIGHT_BASE_URL"] + "/health"
    assert settings.manager_model_id != "ambient-must-not-survive"
    assert os.environ["OPEN_COMMERCE_MANAGER_MODEL_ID"] == "ambient-must-not-survive"


def test_settings_can_snapshot_process_environment(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    for key in list(os.environ):
        if "proxy" in key.lower():
            monkeypatch.delenv(key)
    assert runtime.settings_from_env(os.environ).manager_model_provider == "deterministic"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (runtime.OPT_IN, "0"),
        ("OPEN_COMMERCE_MANAGER_MODEL_PROVIDER", "openai"),
        ("OPEN_COMMERCE_MODEL_ENABLED", "true"),
        ("OPEN_COMMERCE_SEARCH_EMBEDDING_BACKEND", "minilm"),
        ("OPEN_COMMERCE_RUNTIME_PROFILE", "legacy_demo"),
        ("OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED", "true"),
        ("OPEN_COMMERCE_OPENAI_API_KEY", "synthetic-not-a-credential"),
        ("HTTPS_PROXY", "http://127.0.0.1:18080"),
        (
            "OPEN_COMMERCE_DATABASE_URL",
            "postgresql+asyncpg://fixture:synthetic@127.0.0.1:15432/original",
        ),
        ("OPEN_COMMERCE_QDRANT_URL", "http://example.invalid:16333"),
        ("OPEN_COMMERCE_REDIS_URL", "redis://127.0.0.1:16379/0?host=example.invalid"),
        ("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:13000/path"),
    ],
)
def test_unsafe_configuration_rejected(environment: dict[str, str], key: str, value: str) -> None:
    with pytest.raises(runtime.DemoSafetyError):
        runtime.settings_from_env({**environment, key: value})


@pytest.mark.parametrize(
    "key",
    [
        "OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL",
        "OPEN_COMMERCE_REDIS_URL",
        "OPEN_COMMERCE_QDRANT_URL",
    ],
)
def test_no_default_dependency_endpoints(environment: dict[str, str], key: str) -> None:
    environment.pop(key)
    with pytest.raises(runtime.DemoSafetyError, match="explicit_qa"):
        runtime.settings_from_env(environment)


@pytest.mark.parametrize("credentials", ["", "fixture@", "fixture:@", ":synthetic@"])
def test_qa_requires_explicit_nonempty_database_credentials(
    environment: dict[str, str], credentials: str
) -> None:
    environment["OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL"] = (
        f"postgresql+asyncpg://{credentials}127.0.0.1:15432/postgres"
    )
    with pytest.raises(runtime.DemoSafetyError, match="explicit_database_credentials_required"):
        runtime.settings_from_env(environment)


@pytest.mark.parametrize("change", [{"username": "other"}, {"password": "other"}, {"password": ""}])
def test_disposable_database_preserves_explicit_qa_identity(
    environment: dict[str, str], change: dict[str, str]
) -> None:
    url = make_url(environment["OPEN_COMMERCE_DATABASE_URL"])
    environment["OPEN_COMMERCE_DATABASE_URL"] = url.set(
        username=change.get("username", url.username),
        password=change.get("password", url.password),
    ).render_as_string(hide_password=False)
    with pytest.raises(runtime.DemoSafetyError, match="database_identity_changed"):
        runtime.settings_from_env(environment)


@pytest.mark.parametrize("role", ["supervisor", "migrate", "api", "worker"])
def test_real_driver_parser_cannot_use_ambient_credentials_and_guard_restores_patches(
    environment: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    import asyncpg  # type: ignore[import-untyped]
    from asyncpg import connect_utils
    from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

    from open_commerce import config
    from open_commerce.providers.catalog_images import SafeCatalogImages
    from open_commerce.providers.openai_manager import OpenAIManagerProvider

    settings = runtime.settings_from_env(environment)
    home = tmp_path / "synthetic-home"
    home.mkdir()
    (home / ".pgpass").write_text("127.0.0.1:15432:*:fixture:wrong-home-password\n")
    (home / ".pgpass").chmod(0o600)
    (home / ".postgresql").mkdir()
    for name in ("postgresql.crt", "postgresql.key", "root.crt", "root.crl"):
        (home / ".postgresql" / name).write_text("synthetic-not-a-certificate")
    monkeypatch.setattr(
        os,
        "environ",
        {
            "HOME": str(home),
            "PGHOST": "example.invalid",
            "PGPORT": "9",
            "PGUSER": "wrong-user",
            "PGPASSWORD": "wrong-environment-password",
            "PGDATABASE": "original",
            "PGPASSFILE": str(home / ".pgpass"),
            "PGSSLMODE": "verify-full",
            "PGSSLNEGOTIATION": "direct",
            "PGTARGETSESSIONATTRS": "read-only",
            "PGKRBSRVNAME": "wrong-service",
            "PGGSSLIB": "wrong-library",
            **{
                key: str(home / ".postgresql" / "postgresql.crt")
                for key in runtime.PG_CREDENTIAL_FILES
                if key != "PGPASSFILE"
            },
        },
    )
    parsed: list[Any] = []

    async def parse_only(**kwargs: Any) -> object:
        addresses, parameters = connect_utils._parse_connect_dsn_and_args(
            dsn=None,
            server_settings=None,
            **kwargs,
        )
        parsed.append(parameters)
        assert addresses == [("127.0.0.1", 15432)]
        assert parameters.user == "fixture" and parameters.password == "synthetic"
        assert parameters.ssl is False and parameters.sslmode == connect_utils.SSLMode.disable
        assert parameters.target_session_attrs == connect_utils.SessionAttribute.any
        assert parameters.krbsrvname == "postgres" and parameters.gsslib == "gssapi"
        return parameters

    monkeypatch.setattr(asyncpg, "connect", parse_only)
    originals = (config.get_settings, OpenAIManagerProvider.__init__, SafeCatalogImages._fetch)
    directory = runtime.ROOT / ".opencommerce"
    guard = runtime.RuntimeGuard(directory, role, runtime.QaEndpoints.from_env(environment).allowed)
    guard.install(settings)
    guarded_connect = asyncpg.connect
    forbidden = Mock(side_effect=AssertionError("unexpected credential/TLS fallback"))
    monkeypatch.setattr(connect_utils, "_read_password_from_pgpass", forbidden)
    monkeypatch.setattr(connect_utils.compat, "get_pg_home_directory", forbidden)
    monkeypatch.setattr(connect_utils, "_dot_postgresql_path", forbidden)
    monkeypatch.setattr(connect_utils.ssl_module, "SSLContext", forbidden)
    try:
        assert config.get_settings() is settings
        url = make_url(settings.database_url)
        assert url.database is not None
        names = [url.database, "postgres"] if role == "supervisor" else [url.database]
        for database_name in names:
            args, kwargs = PGDialect_asyncpg().create_connect_args(  # type: ignore[no-untyped-call]
                url.set(database=database_name)
            )
            asyncio.run(asyncpg.connect(*args, **kwargs))
            assert parsed[-1].database == database_name
        forbidden.assert_not_called()
        assert not any(guard.counts.values())
    finally:
        guard.close()
    assert asyncpg.connect is parse_only
    assert originals == (
        config.get_settings,
        OpenAIManagerProvider.__init__,
        SafeCatalogImages._fetch,
    )
    with pytest.raises(runtime.DemoSafetyError, match="database_guard_closed"):
        asyncio.run(guarded_connect())
    runtime.verify_guard_logs(directory, (role,))
    installed = json.loads(guard.log_path.read_text().splitlines()[1])
    assert installed["database_credentials"] == "explicit" and installed["database_tls"] is False


@pytest.mark.parametrize("role", ["supervisor", "migrate", "api", "worker"])
def test_database_wrapper_rejects_overrides_before_dispatch_and_keeps_denial_evidence(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    import asyncpg

    settings = runtime.settings_from_env(environment)
    url = make_url(settings.database_url)
    connect = AsyncMock()
    monkeypatch.setattr(asyncpg, "connect", connect)
    directory = runtime.ROOT / ".opencommerce"
    guard = runtime.RuntimeGuard(directory, role, runtime.QaEndpoints.from_env(environment).allowed)
    args: dict[str, Any] = {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "password": url.password,
        "database": url.database,
    }
    changes: list[dict[str, Any]] = [
        {"host": "localhost"},
        {"host": [url.host]},
        {"port": 15433},
        {"user": "other"},
        {"password": None},
        {"password": "other"},
        {"password": lambda: "synthetic"},
        {"database": "opencommerce_test_" + "a" * 32},
        {"database": "original"},
        {"ssl": False},
        {"passfile": os.devnull},
        {
            "dsn": url.set(drivername="postgresql", database="original").render_as_string(
                hide_password=False
            )
        },
        {"server_settings": {}},
    ]
    if role != "supervisor":
        changes.append({"database": "postgres"})
    guard.install(settings)
    try:
        for change in changes:
            with pytest.raises(runtime.DemoSafetyError, match="forbidden_database"):
                asyncio.run(asyncpg.connect(**{**args, **change}))
        with pytest.raises(runtime.DemoSafetyError, match="forbidden_database"):
            asyncio.run(asyncpg.connect("postgresql://synthetic", **args))
        with pytest.raises(runtime.DemoSafetyError, match="forbidden_database"):
            asyncio.run(
                asyncpg.connect(**{key: value for key, value in args.items() if key != "password"})
            )
        connect.assert_not_awaited()
        assert guard.counts["database"] == len(changes) + 2
    finally:
        guard.close()
    assert asyncpg.connect is connect
    with pytest.raises(runtime.DemoSafetyError, match="guard_violation"):
        runtime.verify_guard_logs(directory, (role,))
    journal = guard.log_path.read_text()
    assert "synthetic" not in journal and "original" not in journal


@pytest.mark.parametrize("role", ["supervisor", "migrate", "api", "worker"])
def test_unexpected_pg_credential_reads_are_counted_and_guard_close_restores_access(
    environment: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    home = tmp_path / "synthetic-home"
    (home / ".postgresql").mkdir(parents=True)
    files = [home / ".pgpass", home / "pgpass.conf", home / ".postgresql" / "postgresql.key"]
    for key in runtime.PG_CREDENTIAL_FILES:
        custom = home / f"custom-{key}"
        monkeypatch.setenv(key, str(custom))
        files.append(custom)
    for path in files:
        path.write_text("synthetic")
    directory = runtime.ROOT / ".opencommerce"
    guard = runtime.RuntimeGuard(directory, role, runtime.QaEndpoints.from_env(environment).allowed)
    try:
        guard.install(runtime.settings_from_env(environment))
        for path in files:
            with pytest.raises(runtime.DemoSafetyError, match="forbidden_credential_file"):
                path.read_bytes()
        assert guard.counts["credential_file"] == len(files)
    finally:
        guard.close()
    assert all(path.read_text() == "synthetic" for path in files)
    with pytest.raises(runtime.DemoSafetyError, match="guard_violation"):
        runtime.verify_guard_logs(directory, (role,))
    assert str(home) not in guard.log_path.read_text()


def test_clean_environment_does_not_copy_provider_or_proxy_values() -> None:
    clean = runtime.clean_environment(
        {
            "PATH": "/synthetic/bin",
            "HTTPS_PROXY": "private",
            "OPENAI_API_KEY": "private",
            "AWS_SECRET_ACCESS_KEY": "private",
        }
    )
    assert clean["PATH"] == "/synthetic/bin"
    assert not any(value == "private" for value in clean.values())


def test_private_json_is_new_only_atomic_and_private(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = runtime.ROOT / ".opencommerce" / "ack.json"
    original = os.link
    observed = []

    def link(source: Path, target: Path, **kwargs: object) -> None:
        assert not target.exists()
        assert json.loads(source.read_text()) == {"passed": True}
        observed.append(True)
        original(source, target, follow_symlinks=False)

    monkeypatch.setattr(os, "link", link)
    runtime.private_json(path, {"passed": True})
    assert observed and path.stat().st_mode & 0o777 == 0o600
    assert not list(path.parent.glob("*.tmp"))
    with pytest.raises(runtime.DemoSafetyError):
        runtime.private_json(path, {"passed": False})
    assert runtime.read_json(path) == {"passed": True}


def test_private_paths_reject_symlinks_and_outside(
    environment: dict[str, str], tmp_path: Path
) -> None:
    link = runtime.ROOT / ".opencommerce" / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    for path in (link / "receipt.json", tmp_path / "receipt.json"):
        with pytest.raises(runtime.DemoSafetyError):
            runtime.private_path(path)


@pytest.mark.parametrize(
    ("event", "args", "kind"),
    [
        ("socket.connect", (None, ("127.0.0.1", 15433)), "network"),
        ("socket.connect", (None, ("203.0.113.1", 443)), "network"),
        ("socket.connect", (None, "/tmp/unowned.sock"), "network"),
        ("socket.sendto", (None, b"synthetic", ("127.0.0.1", 15432)), "network"),
        ("socket.getaddrinfo", ("example.invalid", 443, 0, 0, 0), "dns"),
        ("socket.getaddrinfo", ("localhost", 15432, 0, 0, 0), "dns"),
        ("socket.gethostbyname", ("example.invalid",), "dns"),
        ("open", ("/synthetic/.env.local", "r", 0), "envfile"),
    ],
)
def test_audit_rejects_and_persists_before_raise(
    environment: dict[str, str], event: str, args: tuple[object, ...], kind: str
) -> None:
    guard = runtime.RuntimeGuard(
        runtime.ROOT / ".opencommerce", "api", frozenset({("127.0.0.1", 15432)})
    )
    guard.active = True
    try:
        guard.audit("socket.connect", (None, ("127.0.0.1", 15432)))
        with pytest.raises(runtime.DemoSafetyError):
            guard.audit(event, args)
        records = [json.loads(line) for line in guard.log_path.read_text().splitlines()]
        assert records[-1] == {"event": "denied", "kind": kind, "count": 1}
    finally:
        guard.close()


@pytest.mark.parametrize(
    ("family", "peer"),
    [(socket.AF_INET, ("127.0.0.1", 15432)), (socket.AF_INET6, ("::1", 15432, 0, 0))],
)
def test_sendmsg_accepts_only_connected_allowlisted_tcp_without_address(
    environment: dict[str, str], family: int, peer: tuple[object, ...]
) -> None:
    stream = Mock(spec=socket.socket, family=family, type=socket.SOCK_STREAM)
    stream.getpeername.return_value = peer
    guard = runtime.RuntimeGuard(
        runtime.ROOT / ".opencommerce",
        "worker",
        frozenset({("127.0.0.1", 15432), ("::1", 15432)}),
    )
    guard.active = True
    try:
        guard.audit("socket.sendmsg", (stream, None))
        stream.getpeername.assert_called_once_with()
        assert not any(guard.counts.values())
    finally:
        guard.close()


@pytest.mark.parametrize(
    "case",
    [
        "not_socket",
        "unix",
        "datagram",
        "raw",
        "unknown_peer",
        "closed",
        "wrong_host",
        "wrong_port",
        "override",
        "empty_override",
        "missing_address",
        "extra_argument",
        "ipv4_bad_shape",
        "ipv6_scope",
        "ipv6_bad_shape",
    ],
)
def test_sendmsg_rejections_are_counted_without_destination_or_payload(
    environment: dict[str, str], case: str
) -> None:
    stream: Any = Mock(spec=socket.socket, family=socket.AF_INET, type=socket.SOCK_STREAM)
    stream.getpeername.return_value = ("127.0.0.1", 15432)
    address: object = None
    if case == "not_socket":
        stream = SimpleNamespace(family=socket.AF_INET, type=socket.SOCK_STREAM)
    elif case == "unix":
        stream.family = socket.AF_UNIX
    elif case in {"datagram", "raw"}:
        stream.type = socket.SOCK_DGRAM if case == "datagram" else socket.SOCK_RAW
    elif case == "unknown_peer":
        stream.getpeername.return_value = None
    elif case == "closed":
        stream.getpeername.side_effect = OSError("synthetic")
    elif case == "wrong_host":
        stream.getpeername.return_value = ("127.0.0.2", 15432)
    elif case == "wrong_port":
        stream.getpeername.return_value = ("127.0.0.1", 15433)
    elif case in {"override", "empty_override"}:
        address = ("127.0.0.1", 15432) if case == "override" else ()
    elif case == "ipv4_bad_shape":
        stream.getpeername.return_value = ("127.0.0.1", 15432, 0, 0)
    elif case in {"ipv6_scope", "ipv6_bad_shape"}:
        stream.family = socket.AF_INET6
        stream.getpeername.return_value = (
            ("::1", 15432, 0, 1) if case == "ipv6_scope" else ("::1", 15432)
        )
    args = (stream,) if case == "missing_address" else (stream, address)
    if case == "extra_argument":
        args = (*args, b"synthetic-payload")
    guard = runtime.RuntimeGuard(
        runtime.ROOT / ".opencommerce",
        "supervisor",
        frozenset({("127.0.0.1", 15432), ("::1", 15432)}),
    )
    guard.active = True
    try:
        with pytest.raises(runtime.DemoSafetyError, match="forbidden_network"):
            guard.audit("socket.sendmsg", args)
        assert guard.counts["network"] == 1
        records = [json.loads(line) for line in guard.log_path.read_text().splitlines()]
        assert records[-1] == {"event": "denied", "kind": "network", "count": 1}
    finally:
        guard.close()
    journal = guard.log_path.read_text()
    assert (
        "15432" not in journal and "127.0.0" not in journal and "synthetic-payload" not in journal
    )


def test_installed_guards_block_models_images_envfiles(environment: dict[str, str]) -> None:
    from open_commerce.providers.catalog_images import SafeCatalogImages
    from open_commerce.providers.openai_manager import OpenAIManagerProvider

    settings = runtime.settings_from_env(environment)
    directory = runtime.ROOT / ".opencommerce"
    guard = runtime.RuntimeGuard(
        directory, "worker", runtime.QaEndpoints.from_env(environment).allowed
    )
    try:
        guard.install(settings)
        with pytest.raises(runtime.DemoSafetyError):
            OpenAIManagerProvider()  # type: ignore[call-arg]
        with pytest.raises(runtime.DemoSafetyError):
            asyncio.run(SafeCatalogImages().fetch("https://example.invalid/image.png"))
        with pytest.raises(runtime.DemoSafetyError):
            Path("/synthetic/.env").read_text()
        assert guard.counts["model"] == guard.counts["remote_image"] == guard.counts["envfile"] == 1
    finally:
        guard.close()
    with pytest.raises(runtime.DemoSafetyError, match="guard_violation"):
        runtime.verify_guard_logs(directory, ("worker",))


def test_guard_requires_complete_evidence(environment: dict[str, str]) -> None:
    directory = runtime.ROOT / ".opencommerce"
    guard = runtime.RuntimeGuard(
        directory, "api", runtime.QaEndpoints.from_env(environment).allowed
    )
    try:
        guard.install(runtime.settings_from_env(environment))
        with pytest.raises(runtime.DemoSafetyError, match="guard_not_closed"):
            runtime.verify_guard_logs(directory, ("api",))
    finally:
        guard.close()
    runtime.verify_guard_logs(directory, ("api",))


def test_next_environment_files_are_rejected(tmp_path: Path) -> None:
    runtime.reject_next_envfiles(tmp_path)
    (tmp_path / ".env.production.local").write_text("synthetic")
    with pytest.raises(runtime.DemoSafetyError, match="next_envfile"):
        runtime.reject_next_envfiles(tmp_path)


@pytest.mark.parametrize("occupied", [False, True])
def test_serial_next_cache_reuse_checks_reference_and_existing_open_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, occupied: bool
) -> None:
    (tmp_path / "next-env.d.ts").write_text(
        '/// <reference path="./.next-self-service-qa/types/routes.d.ts" />\n'
    )
    cache = tmp_path / runtime.NEXT_DIST_DIR
    cache.mkdir()
    (cache / "trace").touch()
    monkeypatch.setattr("shutil.which", lambda _: "/synthetic/lsof")
    checked = Mock(
        return_value=SimpleNamespace(
            returncode=0 if occupied else 1, stdout=b"12345\n" if occupied else b""
        )
    )
    monkeypatch.setattr(subprocess, "run", checked)
    if occupied:
        with pytest.raises(runtime.DemoSafetyError, match="qa_cache_not_verified_idle"):
            runtime.verify_next_cache_idle(tmp_path)
    else:
        runtime.verify_next_cache_idle(tmp_path)
    assert checked.call_args.args[0] == ["/synthetic/lsof", "-t", "--", str(cache / "trace")]


def test_next_cache_requires_matching_selected_reference(tmp_path: Path) -> None:
    (tmp_path / "next-env.d.ts").write_text('/// <reference path="./.next/types/routes.d.ts" />')
    with pytest.raises(runtime.DemoSafetyError, match="next_cache_reference_changed"):
        runtime.verify_next_cache_idle(tmp_path)


def test_source_snapshot_includes_reporter_and_selected_next_references() -> None:
    snapshot = runtime.source_snapshot()
    for name in (
        "apps/web/capture/catalog-demo-reporter.ts",
        "apps/web/next-env.d.ts",
        "apps/shopper/next-env.d.ts",
    ):
        assert len(snapshot[name]) == 64


@pytest.mark.parametrize("case", ["valid", "truncated", "jpeg", "rgba", "oversize", "hash"])
def test_asset_audit_decodes_png_rgb_and_dimensions(environment: dict[str, str], case: str) -> None:
    path = runtime.ROOT / ".opencommerce" / "sample.png"
    source = Image.new(
        "RGBA" if case == "rgba" else "RGB", (1601 if case == "oversize" else 16, 12)
    )
    source.save(path, format="JPEG" if case == "jpeg" else "PNG")
    if case == "truncated":
        path.write_bytes(path.read_bytes()[:40])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if case == "valid":
        assert runtime.audit_png(path, digest) == {"sha256": digest, "width": 16, "height": 12}
    else:
        with pytest.raises(runtime.DemoSafetyError):
            runtime.audit_png(path, "0" * 64 if case == "hash" else digest)


@pytest.mark.parametrize("outcome", ["replayed_sigterm", "exit_failure", "exception"])
def test_owned_api_signal_replay_closes_real_guard_without_masking_failures(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    directory = runtime.ROOT / ".opencommerce"
    monkeypatch.setattr(sys, "argv", ["capture-only", "api"])
    monkeypatch.setattr(
        os,
        "environ",
        {
            **environment,
            "CATALOG_DEMO_RUNTIME_DIR": str(directory),
            "CATALOG_DEMO_API_PORT": "18000",
        },
    )
    monkeypatch.setattr("open_commerce.api.main.create_app", Mock(return_value=object()))
    handlers: dict[int, object] = {signal.SIGTERM: signal.SIG_DFL}

    def install(signum: int, handler: object) -> object:
        previous = handlers[signum]
        handlers[signum] = handler
        return previous

    def fake_uvicorn(*args: object, **kwargs: object) -> None:
        if outcome == "replayed_sigterm":
            restored = handlers[signal.SIGTERM]
            assert callable(restored)
            restored(signal.SIGTERM, None)
        if outcome == "exit_failure":
            raise SystemExit(1)
        raise RuntimeError("synthetic")

    monkeypatch.setattr(signal, "signal", install)
    monkeypatch.setattr("uvicorn.run", fake_uvicorn)
    if outcome == "replayed_sigterm":
        runtime._child()
        assert not (directory / "api.failure.json").exists()
    else:
        with pytest.raises(SystemExit) as raised:
            runtime._child()
        assert raised.value.code == 1
        assert runtime.read_json(directory / "api.failure.json")["error_type"] in {
            "SystemExit",
            "RuntimeError",
        }
    assert handlers[signal.SIGTERM] == signal.SIG_DFL
    runtime.verify_guard_logs(directory, ("api",))


def test_owned_groups_cleaned_once_without_name_or_port_kills(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = Mock(pid=11001), Mock(pid=11002)
    first.poll.return_value = second.poll.return_value = None
    kill = Mock()
    monkeypatch.setattr(os, "killpg", kill)
    owned = runtime.OwnedProcesses(runtime.ROOT / ".opencommerce", [first, second])
    owned.close()
    owned.close()
    assert [call.args[0] for call in kill.call_args_list] == [11002, 11001]
    first.wait.assert_called_once()
    second.wait.assert_called_once()


def test_reaped_owned_leader_is_not_signalled_and_leftovers_are_not_guessed(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    leader = Mock(pid=11001)
    leader.poll.return_value = 0
    kill = Mock()
    monkeypatch.setattr(os, "killpg", kill)
    owned = runtime.OwnedProcesses(runtime.ROOT / ".opencommerce", [leader])
    owned.close()
    kill.assert_not_called()
    leader.wait.assert_not_called()
    assert owned.cleanup == [
        {
            "pid": 11001,
            "action": "exited_leader_not_signalled",
            "possible_leftovers_unverified": True,
        }
    ]


def test_group_escalation_does_not_signal_a_newly_exited_leader(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    leader = Mock(pid=11001)
    leader.poll.side_effect = [None, 0]
    leader.wait.side_effect = [subprocess.TimeoutExpired("synthetic", 15), 0]
    kill = Mock()
    monkeypatch.setattr(os, "killpg", kill)
    runtime.OwnedProcesses(runtime.ROOT / ".opencommerce", [leader]).close()
    kill.assert_called_once_with(11001, signal.SIGTERM)


def test_receipt_requires_known_literal_result_without_variant_field() -> None:
    value = {
        "schema_version": 1,
        "passed": True,
        "model_mode": "deterministic",
        "store_id": str(uuid4()),
        "import_id": str(uuid4()),
        "catalog_id": str(uuid4()),
        "review_fingerprint": "sha256:" + "a" * 64,
        "browser_denied_requests": 0,
        "preview_product": {"product_id": "B0896LJNLH", "price_minor": 1388, "currency": "USD"},
    }
    assert len(runtime.validate_receipt(value)) == 3
    changes: list[dict[str, object]] = [
        {"passed": False},
        {"browser_denied_requests": 1},
        {"preview_product": {}},
        {"model_mode": "openai"},
        {"review_fingerprint": ""},
    ]
    for change in changes:
        with pytest.raises(runtime.DemoSafetyError):
            runtime.validate_receipt({**value, **change})


def test_negative_ack_allows_failed_media_finalization_before_group_cleanup(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = runtime.ROOT / ".opencommerce"
    output = directory / "take"
    output.mkdir()
    events: list[str] = []
    browser = Mock(pid=11999)
    browser.poll.return_value = 1

    def wait(*, timeout: float) -> int:
        assert runtime.read_json(directory / "preview-tested.ack.json")["passed"] is False
        assert timeout == 45
        events.append("finalize")
        runtime.private_json(output / "receipt.json", {"passed": False, "clips": []})
        return 1

    browser.wait.side_effect = wait
    monkeypatch.setattr(os, "killpg", lambda *args: events.append("terminate"))
    runtime.reject_milestone("preview-tested", directory, browser, output)
    assert events == ["finalize"]
    assert runtime.read_json(directory / "failed-capture-finalization.json") == {
        "browser_exited": True,
        "failed_receipt": True,
        "timed_out": False,
    }
    browser.wait.side_effect = None
    runtime.OwnedProcesses(directory, [browser]).close()
    assert events == ["finalize"]


def test_failed_capture_finalization_has_a_hard_deadline(environment: dict[str, str]) -> None:
    directory = runtime.ROOT / ".opencommerce"
    browser = Mock()
    browser.wait.side_effect = subprocess.TimeoutExpired("synthetic", 45)
    runtime.reject_milestone("owner-ready", directory, browser, directory / "missing-take")
    browser.wait.assert_called_once_with(timeout=45)
    assert runtime.read_json(directory / "failed-capture-finalization.json")["timed_out"] is True


@pytest.mark.parametrize("counts", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)])
def test_baseline_durable_audit_requires_zero_rows_and_scopes_tenant(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, counts: tuple[int, int, int]
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from open_commerce.persistence.runtime_db import RuntimeDatabase

    tenant = uuid4()
    session = create_autospec(AsyncSession, instance=True)
    session.scalar.side_effect = [
        SimpleNamespace(readiness={}, sharing_enabled=False, published_catalog_id=None),
        SimpleNamespace(id=tenant),
        *counts,
        0,
    ]
    database = create_autospec(RuntimeDatabase, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    monkeypatch.setattr("open_commerce.persistence.runtime_db.RuntimeDatabase", lambda _: database)
    coroutine = runtime.audit_store(
        runtime.settings_from_env(environment), {"store_id": str(tenant)}, "baseline"
    )
    if any(counts):
        with pytest.raises(runtime.DemoSafetyError, match="unexpected_model_activity"):
            asyncio.run(coroutine)
    else:
        facts = asyncio.run(coroutine)
        assert facts["model_usage"] == facts["inference_calls"] == facts["manager_runs"] == 0
    for call in session.scalar.await_args_list:
        assert tenant in call.args[0].compile().params.values()
    database.close.assert_awaited_once()


def test_cleanup_filters_exact_tenant_catalog_and_runtime_queue(
    environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from open_commerce.persistence.runtime_db import RuntimeDatabase

    settings = runtime.settings_from_env(environment)
    tenant, catalog = uuid4(), uuid4()
    session = create_autospec(AsyncSession, instance=True)
    session.scalars.return_value = [catalog]
    database = create_autospec(RuntimeDatabase, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    client = Mock(
        collection_exists=AsyncMock(return_value=True), delete=AsyncMock(), close=AsyncMock()
    )
    redis = Mock(delete=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr("open_commerce.persistence.runtime_db.RuntimeDatabase", lambda _: database)
    monkeypatch.setattr("qdrant_client.AsyncQdrantClient", lambda **_: client)
    monkeypatch.setattr("redis.asyncio.Redis.from_url", lambda _: redis)
    asyncio.run(runtime.cleanup_scoped_dependencies(settings, tenant))
    redis.delete.assert_awaited_once_with(
        settings.worker_queue,
        settings.worker_queue + ":health-check",
        f"opencommerce:worker:{settings.local_runtime_id}",
    )
    params = session.scalars.await_args.args[0].compile().params
    assert tenant in params.values()
    query = client.delete.await_args.kwargs["points_selector"].filter.model_dump()
    assert {item["key"]: item["match"]["value"] for item in query["must"]} == {
        "tenant_id": str(tenant),
        "instance_id": str(catalog),
    }
    client.delete_collection.assert_not_called()
    redis.flushdb.assert_not_called()
    redis.flushall.assert_not_called()
