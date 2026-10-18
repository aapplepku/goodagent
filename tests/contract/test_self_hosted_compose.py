"""Production fixture contracts. Every subprocess is mocked; Docker never runs."""

from __future__ import annotations

import copy
import json
import os
import signal
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from scripts import setup_self_hosted as setup
from scripts import test_self_hosted_compose as qa

TOKEN = "synthetic-bootstrap-" + "t" * 32
PRIVATE = "private-cookie-recovery-secret"
PNG = b"\x89PNG\r\n\x1a\nsynthetic-test-image"


class FakeProcess:
    """Exercise the real runner, timeout and shutdown paths without child processes."""

    pid = 987654

    def __init__(self, docker: FakeDocker, command: list[str], kwargs: dict[str, Any]) -> None:
        self.docker = docker
        self.command = command
        self.kwargs = kwargs
        self.returncode = 0
        self.called = False

    def __enter__(self) -> FakeProcess:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def communicate(self, timeout: int) -> tuple[str, str]:
        if self.called:
            return "", ""
        self.called = True
        self.returncode, output = self.docker.respond(self.command, self.kwargs)
        return output, PRIVATE


class FakeDocker:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self.config: dict[str, Any] = {}
        self.active = False
        self.host = "unix:///synthetic/docker.sock"
        self.failure = ""
        self.drift = ""
        self.browser_status = "passed"
        self.browser_test_count = 2
        self.last_test_status: str | None = None
        self.private_directory: Path | None = None
        self.environments: list[bytes] = []
        self.killed: list[signal.Signals] = []
        self.generated: dict[str, Any] = {}
        self.compose_command = ["docker", "compose"]

    def run(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command in (["docker", "compose", "version"], ["docker-compose", "version"])
        assert kwargs == {
            "cwd": qa.ROOT,
            "env": kwargs["env"],
            "capture_output": True,
            "text": True,
            "timeout": 60,
        }
        assert kwargs["env"]["DOCKER_HOST"] == self.host
        assert "DOCKER_CONTEXT" not in kwargs["env"]
        assert PRIVATE not in kwargs["env"].values()
        self.calls.append((command, {**kwargs, "env": dict(kwargs["env"])}))
        return subprocess.CompletedProcess(
            command, 0 if command[:-1] == self.compose_command else 1, TOKEN, PRIVATE
        )

    def popen(self, command: list[str], **kwargs: Any) -> FakeProcess:
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE
        assert "shell" not in kwargs
        self.calls.append((command, {**kwargs, "env": dict(kwargs["env"])}))
        return FakeProcess(self, command, kwargs)

    def configuration(self, command: list[str]) -> dict[str, Any]:
        env_file = Path(command[command.index("--env-file") + 1])
        self.private_directory = env_file.parent
        assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(env_file.parent.stat().st_mode) == 0o700
        self.environments.append(env_file.read_bytes())
        env = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line)
        project = command[command.index("--project-name") + 1]
        store = {key: value for key, value in env.items() if key.startswith("OPEN_COMMERCE_")}
        services: dict[str, Any] = {
            name: {
                "build": {"context": "."},
                "environment": dict(store) if name in {"api", "worker", "web", "shopper"} else {},
                "networks": {"default": None},
            }
            for name in qa.SERVICES
        }
        services["postgres"]["environment"] = {"POSTGRES_PASSWORD": env["POSTGRES_PASSWORD"]}
        for service, key, target in (
            ("postgres", "POSTGRES_PORT", 5432),
            ("redis", "REDIS_PORT", 6379),
            ("qdrant", "QDRANT_PORT", 6333),
            ("qdrant", "QDRANT_GRPC_PORT", 6334),
            ("api", "API_PORT", 8000),
            ("web", "WEB_PORT", 3000),
            ("shopper", "SHOPPER_PORT", 3001),
        ):
            services[service].setdefault("ports", []).append(
                {
                    "host_ip": "127.0.0.1",
                    "published": env[key],
                    "target": target,
                }
            )
        for service, volume, destination in (
            ("postgres", "postgres-data", "/var/lib/postgresql/data"),
            ("redis", "redis-data", "/data"),
            ("qdrant", "qdrant-data", "/qdrant/storage"),
            ("api", "catalog-assets", "/app/.opencommerce/assets"),
            ("worker", "catalog-assets", "/app/.opencommerce/assets"),
        ):
            services[service]["volumes"] = [
                {
                    "type": "volume",
                    "source": volume,
                    "target": destination,
                    "read_only": service == "api",
                }
            ]
        config: dict[str, Any] = {
            "name": project,
            "services": services,
            "volumes": {name: {} for name in qa.VOLUMES},
            "networks": {"default": {}},
        }
        services["api"]["tmpfs"] = ["/tmp:rw,noexec,nosuid,size=64m"]
        if self.failure == "profile":
            services["api"]["environment"]["OPEN_COMMERCE_RUNTIME_PROFILE"] = "legacy_demo"
        if self.failure == "model":
            services["api"]["environment"]["OPEN_COMMERCE_OPENAI_API_KEY"] = PRIVATE
        if self.failure == "public-port":
            services["web"]["ports"][0]["host_ip"] = "0.0.0.0"
        if self.failure == "bind-mount":
            services["worker"]["volumes"][0]["type"] = "bind"
        if self.failure == "external-volume":
            config["volumes"]["postgres-data"]["external"] = True
        if self.failure == "missing-service":
            del services["shopper"]
        return config

    def resources(self, kind: str) -> list[dict[str, Any]]:
        if not self.active:
            return []
        project = self.config["name"]
        if kind != "container":
            resources = [
                {
                    "Name": resource["name"],
                    "Labels": {
                        **resource["labels"],
                        qa.PROJECT_LABEL: project,
                    },
                }
                for resource in self.config[kind + "s"].values()
            ]
            if self.drift == f"{kind}-ownership":
                resources[0]["Labels"][qa.OWNER_LABEL] = "other-owner"
            return resources
        rows: list[dict[str, Any]] = []
        for name, service in self.config["services"].items():
            environment = {**service["environment"], "NODE_ENV": "production"}
            row = {
                "Id": "id-" + name,
                "Image": service["image"],
                "Config": {
                    "Labels": {
                        **service["labels"],
                        qa.PROJECT_LABEL: project,
                        qa.SERVICE_LABEL: name,
                    },
                    "Env": [f"{key}={value}" for key, value in environment.items()],
                    "Cmd": ["node", f"apps/{name}/server.js"],
                },
                "State": {
                    "Status": "exited" if name == "migrate" else "running",
                    "ExitCode": 0,
                    "Health": {"Status": "healthy", "Log": [{"Output": TOKEN + PRIVATE}]},
                    "Error": PRIVATE,
                },
                "HostConfig": {
                    "PortBindings": {
                        f"{binding['target']}/tcp": [
                            {
                                "HostIp": binding["host_ip"],
                                "HostPort": binding["published"],
                            }
                        ]
                        for binding in service.get("ports", [])
                    }
                },
                "NetworkSettings": {"Networks": {f"{project}_default": {}}},
                "Mounts": [
                    {
                        "Type": "volume",
                        "Name": f"{project}_{mount['source']}",
                        "Destination": mount["target"],
                        "RW": not mount.get("read_only", False),
                    }
                    for mount in service.get("volumes", [])
                ],
            }
            if self.drift == "health" and name == "api":
                row["State"]["Health"]["Status"] = "unhealthy"
            if name == "api":
                row["Mounts"].append({"Type": "tmpfs", "Destination": "/tmp"})
            if self.drift == "migration" and name == "migrate":
                row["State"]["ExitCode"] = 1
            if self.drift == "profile" and name == "api":
                row["Config"]["Env"] = ["OPEN_COMMERCE_RUNTIME_PROFILE=legacy_demo"]
            if self.drift == "development" and name == "web":
                row["Config"]["Cmd"] = ["next", "dev"]
            if self.drift == "public-port" and name == "web":
                row["HostConfig"]["PortBindings"]["3000/tcp"][0]["HostIp"] = "0.0.0.0"
            if self.drift == "wrong-port" and name == "web":
                row["HostConfig"]["PortBindings"]["3000/tcp"][0]["HostPort"] = "3000"
            if self.drift == "image" and name == "api":
                row["Image"] = "sha256:" + "f" * 64
            if self.drift == "mount" and name == "api":
                row["Mounts"][0]["Name"] = "real-user-store"
            if self.drift == "missing-mount" and name == "api":
                row["Mounts"] = []
            if self.drift == "network" and name == "api":
                row["NetworkSettings"]["Networks"]["user-store-network"] = {}
            if self.drift == "ownership" and name == "api":
                row["Config"]["Labels"][qa.OWNER_LABEL] = "other-owner"
            rows.append(row)
        if self.drift == "seven-services":
            rows.pop()
        if self.drift == "duplicate-service":
            rows[-1] = copy.deepcopy(rows[-2])
        return rows

    def respond(self, command: list[str], kwargs: dict[str, Any]) -> tuple[int, str]:
        if command[:3] == ["docker", "context", "show"]:
            return 0, "local-context"
        if command[:3] == ["docker", "context", "inspect"]:
            return 0, json.dumps([{"Endpoints": {"docker": {"Host": self.host}}}])
        if command[:2] == ["docker", "info"] or command[-1] == "version":
            return 0, "synthetic-version"
        if command[-3:] == ["config", "--format", "json"]:
            return 0, json.dumps(self.configuration(command))
        if command[:3] == ["docker", "image", "inspect"]:
            if self.failure == "missing-image":
                return 1, PRIVATE
            name = command[-1].removeprefix("already-built-").removesuffix(":latest")
            return 0, json.dumps(
                [
                    {
                        "Id": "sha256:" + str(qa.SERVICES.index(name) + 1) * 64,
                        "Os": "linux",
                        "Architecture": "arm64",
                        "Config": {"Env": [PRIVATE]},
                    }
                ]
            )
        if command[:2] == ["docker", "ps"]:
            if self.failure == "project-collision":
                return 0, "existing-user-container"
            return 0, "\n".join(row["Id"] for row in self.resources("container"))
        if command[1:3] in (["volume", "ls"], ["network", "ls"]):
            if self.failure == "name-collision" and "--format" in command:
                project = next(
                    c[c.index("--project-name") + 1] for c, _ in self.calls if "--project-name" in c
                )
                return 0, f"{project}_postgres-data"
            return 0, "\n".join(row["Name"] for row in self.resources(command[1]))
        if command[1:3] in (
            ["container", "inspect"],
            ["volume", "inspect"],
            ["network", "inspect"],
        ):
            return 0, json.dumps(self.resources(command[1]))
        if "up" in command:
            self.config = json.loads(Path(command[command.index("-f") + 1]).read_text())
            self.active = True
            if self.failure == "startup":
                return 1, PRIVATE
            if self.failure == "startup-timeout":
                raise subprocess.TimeoutExpired(command, 660, output=PRIVATE, stderr=TOKEN)
            if self.failure == "interrupt":
                qa.interrupt(signal.SIGTERM, None)
            return 0, PRIVATE
        if "down" in command:
            assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
            if self.failure == "cleanup":
                return 1, PRIVATE
            self.active = False
            return 0, ""
        if "exec" in command and command[-1] == qa.RUNTIME_PROBE:
            return (1, PRIVATE) if self.failure == "effective-settings" else (0, "")
        if command[-1] == "bootstrap":
            return 0, (PRIVATE + "\n" + TOKEN) if self.failure == "bootstrap" else TOKEN
        if command[0] == "node":
            return self.browser(command, kwargs)
        raise AssertionError("Unexpected mocked subprocess")

    def browser(self, command: list[str], kwargs: dict[str, Any]) -> tuple[int, str]:
        config_file = Path(command[command.index("--config") + 1])
        config = json.loads(
            config_file.read_text().removeprefix("module.exports = ").removesuffix(";\n")
        )
        self.generated = config
        raw = Path(config["outputDir"]) / "nested-test-output"
        raw.mkdir(parents=True)
        for name in ("error-context.md", "trace.zip", "report.html", "test-failed-1.png"):
            (raw / name).write_text(TOKEN + PRIVATE)
        for prefixes in qa.CAPTURES.values():
            for prefix in prefixes:
                for size in ("1440x1000", "390x844"):
                    (raw / f"{prefix}-{size}.png").write_bytes(PNG)
        if self.failure == "missing-capture":
            (raw / "sharing-disabled-390x844.png").unlink()
        report: dict[str, Any] = {
            "status": self.browser_status,
            "errors": 0,
            "raw": TOKEN + PRIVATE,
            "tests": [
                {"status": self.browser_status, "duration_ms": 321, "message": PRIVATE}
                for _ in range(self.browser_test_count)
            ],
            "steps": [{"line": 123, "failed": self.failure == "browser", "title": TOKEN}],
        }
        if report["tests"] and self.last_test_status is not None:
            report["tests"][-1]["status"] = self.last_test_status
        Path(kwargs["env"]["QA_REPORT"]).write_text(json.dumps(report))
        if self.failure == "browser-timeout":
            raise subprocess.TimeoutExpired(command, 420, output=TOKEN, stderr=PRIVATE)
        if self.failure == "browser":
            return 1, TOKEN + PRIVATE
        if self.failure == "foreign-before-cleanup":
            self.drift = "ownership"
        return 0, TOKEN + PRIVATE


@pytest.fixture
def docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeDocker:
    root = tmp_path / "checkout"
    for name in (
        "docker-compose.yml",
        "scripts/setup_self_hosted.py",
        "scripts/test_self_hosted_compose.py",
        "apps/web/e2e/self-service.spec.ts",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((qa.ROOT / name).read_bytes())
    (root / ".env").write_text("real-user-configuration-do-not-read-or-replace")
    (root / "data").mkdir()
    (root / "data/store").write_text("real-user-data")
    monkeypatch.setattr(qa, "ROOT", root)
    monkeypatch.setattr(setup, "ROOT", root)
    monkeypatch.setattr(
        setup,
        "available_ports",
        lambda: {key: 41000 + index for index, key in enumerate(setup.PORTS)},
    )
    for key in (
        "OPEN_COMMERCE_RUNTIME_PROFILE",
        "OPEN_COMMERCE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "OPEN_COMMERCE_E2E_SETUP_TOKEN",
        "OPEN_COMMERCE_DATABASE_URL",
        "COMPOSE_FILE",
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_ENV_FILES",
        "WEB_PORT",
        "POSTGRES_PASSWORD",
        "POSTGRES_PASSWORD_URLENCODED",
        "NODE_OPTIONS",
        "PW_TEST_CONNECT_WS_ENDPOINT",
        "PLAYWRIGHT_BASE_URL",
        "HTTP_PROXY",
        "DOCKER_AUTH_CONFIG",
    ):
        monkeypatch.setenv(key, PRIVATE)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    fake = FakeDocker()
    monkeypatch.setattr(subprocess, "run", fake.run)
    monkeypatch.setattr(subprocess, "Popen", fake.popen)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: fake.killed.append(sig))
    return fake


def receipt() -> dict[str, Any]:
    paths = list((qa.ROOT / "apps/web/test-results/self-hosted-compose").glob("*/receipt.json"))
    assert len(paths) == 1
    return json.loads(paths[0].read_text())  # type: ignore[no-any-return]


def test_without_opt_in_never_invokes_subprocess(
    docker: FakeDocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["fixture"])
    assert qa.main() == 0
    assert docker.calls == []
    monkeypatch.setattr("sys.argv", ["fixture", "--run"])
    with pytest.raises(SystemExit) as error:
        qa.main()
    assert error.value.code == 2
    assert docker.calls == []


@pytest.mark.parametrize("compose", [["docker", "compose"], ["docker-compose"]])
def test_existing_images_fresh_private_project_and_complete_safe_evidence(
    docker: FakeDocker,
    capsys: pytest.CaptureFixture[str],
    compose: list[str],
) -> None:
    docker.compose_command = compose
    assert qa.execute("already-built") == 0
    report = receipt()
    assert report["result"] == "passed"
    assert report["cleanup"] == "verified-empty"
    assert report["runtime_verified_at"] <= report["finished_at"]
    assert set(report["images"]) == set(qa.SERVICES)
    assert len(report["snapshots"][0]["services"]) == 8
    assert len(report["captures"]) == 28
    assert len(report["browser"]["tests"]) == 2
    assert {
        f"shopper/{prefix}-{size}.png"
        for prefix in ("shopper-welcome", "shopper-sign-in")
        for size in ("1440x1000", "390x844")
    } <= {item["path"] for item in report["captures"]}
    assert {p["path"].split("/")[0] for p in report["captures"]} == {"owner", "shopper"}
    assert docker.config["name"] == report["project"]
    assert docker.private_directory is not None and not docker.private_directory.exists()
    assert (qa.ROOT / ".env").read_text() == "real-user-configuration-do-not-read-or-replace"
    assert (qa.ROOT / "data/store").read_text() == "real-user-data"
    assert (
        docker.config["services"]["web"]["environment"]["OPEN_COMMERCE_SHOPPER_PUBLIC_URL"]
        == report["urls"]["shopper"]
    )
    assert report["urls"] == {"web": "http://localhost:41005", "shopper": "http://localhost:41006"}
    for service in docker.config["services"].values():
        assert "build" not in service
        assert service["pull_policy"] == "never"
        assert qa.DIGEST.fullmatch(service["image"])
    commands = [command for command, _ in docker.calls]
    assert [c for c in commands if c[-1] == "version"] == (
        [["docker", "compose", "version"]]
        if compose == ["docker", "compose"]
        else [["docker", "compose", "version"], ["docker-compose", "version"]]
    )
    assert all(c[: len(compose)] == compose for c in commands if "--project-name" in c)
    up = next(command for command in commands if "up" in command)
    assert up[-8:] == [
        "up",
        "-d",
        "--no-build",
        "--pull",
        "never",
        "--wait",
        "--wait-timeout",
        "600",
    ]
    assert not any(
        "build" in c or "install" in c or "prune" in c or "--remove-orphans" in c for c in commands
    )
    assert all(
        "--project-name" in c and report["project"] in c
        for c in commands
        if ("compose" in c or c[0] == "docker-compose") and c[-1] != "version"
    )
    assert commands.index(next(c for c in commands if c[-1] == qa.RUNTIME_PROBE)) < commands.index(
        next(c for c in commands if c[-1] == "bootstrap")
    )
    assert len([c for c in commands if c[-1] == qa.RUNTIME_PROBE]) == 2
    browser_command, browser_kwargs = next((c, k) for c, k in docker.calls if c[0] == "node")
    assert browser_command[-2:] == ["--trace", "off"]
    assert browser_kwargs["env"]["OPEN_COMMERCE_E2E_SETUP_TOKEN"] == TOKEN
    assert browser_kwargs["env"]["SHOPPER_PLAYWRIGHT_BASE_URL"] == report["urls"]["shopper"]
    assert docker.generated["retries"] == 0
    assert all(docker.generated["use"][key] == "off" for key in ("trace", "video", "screenshot"))
    for command, kwargs in docker.calls:
        assert PRIVATE not in kwargs["env"].values()
        assert TOKEN not in command
        if command[0] != "node":
            assert "OPEN_COMMERCE_E2E_SETUP_TOKEN" not in kwargs["env"]
    for path in (qa.ROOT / "apps/web/test-results").rglob("*"):
        if path.is_file():
            assert path.suffix in {".png", ".json"}
            assert TOKEN.encode() not in path.read_bytes()
            assert PRIVATE.encode() not in path.read_bytes()
            for line in docker.environments[0].decode().splitlines():
                if line.startswith(("POSTGRES_PASSWORD=", "OPEN_COMMERCE_ENCRYPTION_KEY=")):
                    assert line.split("=", 1)[1].encode() not in path.read_bytes()
    assert TOKEN not in capsys.readouterr().out


def test_missing_compose_fails_before_configuration_or_resources(
    docker: FakeDocker,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docker.compose_command = []
    assert qa.execute("already-built") == 1
    report = receipt()
    assert report["reason"] == "compose-unavailable"
    assert report["result"] == "failed"
    assert report["cleanup"] == "not-needed"
    assert [c for c, _ in docker.calls if c[-1] == "version"] == [
        ["docker", "compose", "version"],
        ["docker-compose", "version"],
    ]
    assert docker.private_directory is None
    assert not any("--project-name" in c or "image" in c or "node" in c for c, _ in docker.calls)
    serialized = json.dumps(report) + capsys.readouterr().out
    assert TOKEN not in serialized and PRIVATE not in serialized


@pytest.mark.parametrize(
    "failure",
    [
        "profile",
        "model",
        "public-port",
        "bind-mount",
        "external-volume",
        "missing-service",
        "missing-image",
        "project-collision",
        "name-collision",
    ],
)
def test_preflight_failures_do_not_start_or_clean_other_projects(
    docker: FakeDocker, failure: str
) -> None:
    docker.failure = failure
    assert qa.execute("already-built") == 1
    assert receipt()["result"] == "failed"
    assert receipt()["cleanup"] == "not-needed"
    assert not any("up" in command or "down" in command for command, _ in docker.calls)
    assert docker.private_directory is not None and not docker.private_directory.exists()


@pytest.mark.parametrize("host", ["tcp://127.0.0.1:2375", "ssh://remote", "tcp://remote:2375"])
def test_remote_or_unverified_engine_rejected(docker: FakeDocker, host: str) -> None:
    docker.host = host
    assert qa.execute("already-built") == 1
    assert receipt()["reason"] == "local-unix-engine-required"
    assert not any("up" in command or "down" in command for command, _ in docker.calls)


@pytest.mark.parametrize(
    "drift",
    [
        "health",
        "migration",
        "profile",
        "development",
        "public-port",
        "wrong-port",
        "image",
        "mount",
        "missing-mount",
        "network",
        "seven-services",
        "duplicate-service",
    ],
)
def test_runtime_must_be_verified_before_any_token_or_browser(
    docker: FakeDocker, drift: str
) -> None:
    docker.drift = drift
    assert qa.execute("already-built") == 1
    assert receipt()["last_phase"] == "runtime-verification"
    assert receipt()["cleanup"] == "verified-empty"
    assert not any(
        command[-1] == "bootstrap" or command[0] == "node" for command, _ in docker.calls
    )


@pytest.mark.parametrize("failure", ["startup", "effective-settings", "bootstrap", "browser"])
def test_failures_keep_sanitized_metadata_and_clean_owned_fixture(
    docker: FakeDocker,
    failure: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docker.failure = failure
    assert qa.execute("already-built") == 1
    report = receipt()
    assert report["cleanup"] == "verified-empty"
    assert report["snapshots"]
    assert "captures" not in report
    assert not list((qa.ROOT / "apps/web/test-results").rglob("*.png"))
    serialized = json.dumps(report) + capsys.readouterr().out
    assert TOKEN not in serialized and PRIVATE not in serialized
    if failure == "browser":
        assert report["browser"]["steps"] == [{"line": 123, "failed": True}]


@pytest.mark.parametrize("failure", ["startup-timeout", "browser-timeout", "interrupt"])
def test_timeouts_and_signals_stop_child_group_then_cleanup(
    docker: FakeDocker, failure: str
) -> None:
    old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    docker.failure = failure
    assert qa.execute("already-built") == (130 if failure == "interrupt" else 1)
    assert receipt()["cleanup"] == "verified-empty"
    assert signal.SIGTERM in docker.killed and signal.SIGKILL in docker.killed
    assert all(signal.getsignal(sig) == handler for sig, handler in old_handlers.items())
    assert not list((qa.ROOT / "apps/web/test-results").rglob("*.png"))


@pytest.mark.parametrize(
    "failure", ["ownership", "volume-ownership", "network-ownership", "foreign-before-cleanup"]
)
def test_teardown_refuses_foreign_ownership_even_in_fixture_project(
    docker: FakeDocker, failure: str
) -> None:
    if failure != "foreign-before-cleanup":
        docker.drift = failure
    else:
        docker.failure = failure
    assert qa.execute("already-built") == 1
    assert receipt()["cleanup"] == "unverified-ownership-or-engine-failure"
    assert receipt()["result"] == "failed"
    assert not any("down" in command for command, _ in docker.calls)


def test_cleanup_failure_cannot_report_success(docker: FakeDocker) -> None:
    docker.failure = "cleanup"
    assert qa.execute("already-built") == 1
    assert receipt()["result"] == "failed"
    assert receipt()["browser"]["status"] == "passed"
    assert receipt()["cleanup"] == "unverified-ownership-or-engine-failure"


@pytest.mark.parametrize("status", ["skipped", "failed", "interrupted"])
def test_zero_browser_exit_without_all_passes_is_failure(docker: FakeDocker, status: str) -> None:
    docker.browser_status = status
    assert qa.execute("already-built") == 1
    assert receipt()["reason"] == "browser-journey-not-passed"
    assert "captures" not in receipt()


@pytest.mark.parametrize("count", [0, 1, 3])
def test_browser_requires_exactly_both_cases(docker: FakeDocker, count: int) -> None:
    docker.browser_test_count = count
    assert qa.execute("already-built") == 1
    assert receipt()["reason"] == "browser-journey-not-passed"
    assert "captures" not in receipt()


@pytest.mark.parametrize("status", ["skipped", "failed", "interrupted"])
def test_passing_main_journey_cannot_mask_failed_sign_in(docker: FakeDocker, status: str) -> None:
    docker.last_test_status = status
    assert qa.execute("already-built") == 1
    assert receipt()["reason"] == "browser-journey-not-passed"
    assert "captures" not in receipt()


def test_browser_report_does_not_copy_untrusted_fields() -> None:
    assert qa.sanitized_browser_report(
        {
            "status": PRIVATE,
            "errors": 1,
            "cookie": PRIVATE,
            "tests": [{"status": PRIVATE, "duration_ms": PRIVATE, "error": PRIVATE}],
            "steps": [{"line": PRIVATE, "failed": PRIVATE, "title": PRIVATE}],
        }
    ) == {
        "status": "incomplete",
        "errors": 1,
        "tests": [{"status": "unknown", "duration_ms": 0}],
        "steps": [{"line": 0, "failed": False}],
    }


def test_workflow_preserves_native_journey_and_runs_fixture_after_successful_build() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/qualification.yml").read_text())
    steps = workflow["jobs"]["verify"]["steps"]
    index = next(
        i for i, step in enumerate(steps) if "test_self_hosted_compose.py" in step.get("run", "")
    )
    assert "test_self_service_browser.py" in steps[index - 1]["run"]
    assert steps[index - 1]["env"]["OPEN_COMMERCE_SELF_SERVICE_BROWSER"] == "1"
    assert steps[index]["if"] == "${{ !cancelled() && steps.images.outcome == 'success' }}"
    assert "--run --image-project opencommerce-ci" in steps[index]["run"]
    assert not steps[index].get("continue-on-error")
    assert next(i for i, step in enumerate(steps) if step.get("id") == "images") < index
    assert any("make test-e2e" in step.get("run", "") for step in steps)
    assert any("make test-fault" in step.get("run", "") for step in steps)
    upload = next(step for step in steps if "upload-artifact@" in step.get("uses", ""))
    assert upload["with"]["path"] == ".opencommerce/ci-upload/qualification/upload/"
    from scripts.stage_ci_artifacts import selected

    assert selected(
        "apps/web/test-results/self-hosted-compose/fixture/receipt.json", "qualification"
    )
    assert not selected(
        "apps/web/test-results/self-hosted-compose/fixture/browser.png", "qualification"
    )


def test_workflow_installs_chromium_after_check_failure_before_browser_journeys() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/qualification.yml").read_text())
    steps = workflow["jobs"]["verify"]["steps"]
    installers = [
        i
        for i, step in enumerate(steps)
        if "playwright install --with-deps chromium" in step.get("run", "")
    ]
    assert len(installers) == 1
    install = installers[0]
    dependencies = next(i for i, step in enumerate(steps) if step.get("id") == "dependencies")
    check = next(i for i, step in enumerate(steps) if step.get("run") == "make check")
    smoke = next(
        i for i, step in enumerate(steps) if step.get("name") == "Production browser smoke"
    )
    fixture = next(
        i for i, step in enumerate(steps) if "test_self_hosted_compose.py" in step.get("run", "")
    )
    assert dependencies < check < install < smoke < fixture
    assert steps[install]["if"] == "${{ !cancelled() && steps.dependencies.outcome == 'success' }}"
    assert not steps[install].get("continue-on-error")
    assert steps[smoke]["run"] == "make test-e2e"
    assert "if" not in steps[smoke]
    assert not steps[smoke].get("continue-on-error")
    assert "if" not in steps[check]
    assert not steps[check].get("continue-on-error")
