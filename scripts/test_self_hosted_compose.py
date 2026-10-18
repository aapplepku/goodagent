"""Opt-in production-image owner/shopper QA, with no builds or dependency installs.

Run after building all eight services in an explicit image project:
    python scripts/test_self_hosted_compose.py --run --image-project opencommerce-ci

Requires a local Unix-socket Docker engine, Compose v2, installed web dependencies
and Chromium. Uses setup_self_hosted's fresh private configuration, never .env or
existing store volumes. Evidence is nested under apps/web/test-results/self-hosted-compose.
Only a sanitized receipt and successful, reviewed manual screenshots are exported;
raw browser output, error contexts and configuration are temporary and private.
SIGINT/SIGTERM and timeouts attempt owned cleanup. SIGKILL/engine loss cannot promise
cleanup; the receipt identifies the fixture for investigation. This is deterministic
QA of existing images, not a cold installation, model evaluation or CI-pass claim.
Both the owner/shopper journey and the isolated legacy sign-in rendering check
must pass; skipped or missing cases do not qualify the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Any

try:
    from scripts import setup_self_hosted as setup
except ModuleNotFoundError:  # Direct script invocation, without installing this repository.
    import setup_self_hosted as setup  # type: ignore[no-redef,import-not-found]

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("postgres", "redis", "qdrant", "migrate", "api", "worker", "web", "shopper")
VOLUMES = ("postgres-data", "redis-data", "qdrant-data", "catalog-assets")
OWNER_LABEL = "org.opencommerce.self-hosted-qa"
PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"
STATES = {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
TEST_STATES = {"passed", "failed", "timedOut", "skipped", "interrupted"}
EXPECTED_BROWSER_TESTS = 2
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
# Reviewed explicit captures in self-service.spec.ts: recovery codes have already
# been acknowledged. Never promote automatic screenshots or arbitrary attachments.
CAPTURES = {
    "owner": ("owner-products", "catalog-review-resumed", "owner-ready"),
    "shopper": (
        "private-preview",
        "empty-filter-recovery",
        "sign-in-disclosure",
        "memory-unverified",
        "account-controls",
        "shopper-browse",
        "demo-orders",
        "cart-choice",
        "sharing-disabled",
        "shopper-welcome",
        "shopper-sign-in",
    ),
}
RUNTIME_PROBE = """from open_commerce.config import Settings
s = Settings()
ok = (s.runtime_profile == 'self_hosted'
      and s.manager_model_provider == 'deterministic'
      and not s.openai_api_key and not s.model_enabled
      and not s.shopify_catalog_enabled and not s.shopify_admin_access_token
      and not s.local_operations_enabled)
raise SystemExit(0 if ok else 1)
"""
REPORTER = """const fs = require('node:fs');
module.exports = class {
  constructor() { this.data = { tests: [], steps: [], errors: 0 }; }
  save() { fs.writeFileSync(process.env.QA_REPORT, JSON.stringify(this.data), {mode: 0o600}); }
  onBegin() { this.save(); }
  onStdOut() {}
  onStdErr() {}
  onError() { this.data.errors++; this.save(); }
  onStepEnd(test, result, step) {
    // Titles, errors, arguments and attachments can contain authentication data.
    if (this.data.steps.length < 2000) this.data.steps.push({
      line: step.location?.line ?? 0, failed: Boolean(step.error)
    });
    this.save();
  }
  onTestEnd(test, result) {
    this.data.tests.push({status: result.status, duration_ms: result.duration}); this.save();
  }
  onEnd(result) { this.data.status = result.status; this.save(); }
};
"""


class FixtureError(RuntimeError):
    """Only fixed diagnostic codes, never subprocess output, belong in evidence."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def private_write(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        path.chmod(0o600)
        handle.write(content)


def clean_environment() -> dict[str, str]:
    """Keep local tool discovery only, excluding application/model/Node overrides."""
    return {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "DOCKER_CONTEXT", "DOCKER_HOST", "DOCKER_CONFIG")
        if key in os.environ
    }


def interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def stop_process(process: subprocess.Popen[str]) -> None:
    # Playwright has child workers/browsers. Reap the entire owned process group
    # before removing its private files or tearing down its Docker fixture.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
            # A parent can exit before a child that ignored SIGTERM.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        except subprocess.TimeoutExpired:
            continue
    raise FixtureError("child-shutdown-failed")


class Fixture:
    """One exclusively owned attempt; no caller-supplied cleanup target."""

    def __init__(self, directory: Path, image_project: str) -> None:
        self.directory = directory
        self.image_project = image_project
        self.nonce = secrets.token_hex(12)
        self.project = f"opencommerce-self-hosted-qa-{self.nonce}"
        self.environment = clean_environment()
        self.command: list[str] = []
        self.config: dict[str, Any] = {}
        self.images: dict[str, str] = {}
        self.started = False
        self.phase = "preflight"
        self.output = ROOT / "apps/web/test-results/self-hosted-compose" / self.project
        self.output.mkdir(parents=True, exist_ok=False)
        self.receipt: dict[str, Any] = {
            "schema_version": 1,
            "project": self.project,
            "started_at": now(),
            "result": "incomplete",
            "cleanup": "not-needed",
            "commands": [],
            "snapshots": [],
            "model": "deterministic",
            "runtime_profile": "self_hosted",
            "sources": {},
        }
        for name in (
            "docker-compose.yml",
            "scripts/setup_self_hosted.py",
            "scripts/test_self_hosted_compose.py",
            "apps/web/e2e/self-service.spec.ts",
        ):
            self.receipt["sources"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        self.save()

    def save(self) -> None:
        self.receipt["updated_at"] = now()
        path = self.output / "receipt.json"
        temporary = self.output / "receipt.tmp"
        temporary.write_text(json.dumps(self.receipt, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def run(
        self,
        command: list[str],
        *,
        timeout: int = 60,
        environment: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> str:
        event: dict[str, Any] = {"phase": self.phase, "started_at": now()}
        start = time.monotonic()
        self.receipt["commands"].append(event)
        try:
            with subprocess.Popen(
                command,
                cwd=cwd or ROOT,
                env=environment or self.environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            ) as process:
                try:
                    stdout, _ = process.communicate(timeout=timeout)
                except BaseException:
                    stop_process(process)
                    raise
                event["exit_code"] = process.returncode
                if process.returncode:
                    raise FixtureError("command-failed")
                return stdout
        except subprocess.TimeoutExpired:
            event["timed_out"] = True
            raise FixtureError("command-timeout") from None
        except OSError:
            raise FixtureError("command-unavailable") from None
        finally:
            event["duration_ms"] = round((time.monotonic() - start) * 1000)
            self.save()

    def local_engine(self) -> list[str]:
        if self.environment.get("DOCKER_HOST") and not self.environment.get("DOCKER_CONTEXT"):
            host = self.environment["DOCKER_HOST"]
        else:
            context = self.run(["docker", "context", "show"]).strip()
            row = json.loads(self.run(["docker", "context", "inspect", context]))[0]
            host = row["Endpoints"]["docker"]["Host"]
        if not isinstance(host, str) or not host.startswith("unix:///"):
            raise FixtureError("local-unix-engine-required")
        self.environment.pop("DOCKER_CONTEXT", None)
        self.environment["DOCKER_HOST"] = host
        try:
            compose = setup.compose_command(self.environment)
        except setup.SetupError:
            raise FixtureError("compose-unavailable") from None
        self.run(["docker", "info", "--format", "{{.ServerVersion}}"])
        return compose

    def prepare(self) -> None:
        compose = self.local_engine()
        env_file = self.directory / "fixture.env"
        if not setup.prepare_environment(env_file):
            raise FixtureError("fresh-environment-required")
        base = [
            *compose,
            "--project-directory",
            str(ROOT),
            "--project-name",
            self.project,
            "--env-file",
            str(env_file),
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]
        config = json.loads(self.run([*base, "config", "--format", "json"]))
        self.environment["POSTGRES_PASSWORD_URLENCODED"] = setup.encoded_database_password(config)
        config = json.loads(self.run([*base, "config", "--format", "json"]))
        ports = setup.validate_configuration(config)
        if set(config["services"]) != set(SERVICES) or set(config["volumes"]) != set(VOLUMES):
            raise FixtureError("eight-services-four-volumes-required")
        if set(config.get("networks", {})) != {"default"}:
            raise FixtureError("private-project-network-required")
        if config.get("secrets") or config.get("configs"):
            raise FixtureError("external-configuration-refused")
        self.receipt["urls"] = {name: f"http://localhost:{port}" for name, port in ports.items()}
        image_metadata: dict[str, dict[str, str]] = {}
        self.receipt["images"] = image_metadata
        for name, service in config["services"].items():
            row = json.loads(
                self.run(
                    [
                        "docker",
                        "image",
                        "inspect",
                        f"{self.image_project}-{name}:latest",
                    ]
                )
            )[0]
            identity = row["Id"]
            if not isinstance(identity, str) or not DIGEST.fullmatch(identity):
                raise FixtureError("invalid-image-identity")
            self.images[name] = identity
            image_metadata[name] = {
                "id": identity,
                "os": row["Os"] if row["Os"] == "linux" else "unsupported",
                "architecture": row["Architecture"]
                if row["Architecture"] in {"arm64", "amd64"}
                else "unsupported",
            }
            if "unsupported" in image_metadata[name].values():
                raise FixtureError("unsupported-image-platform")
            if any(
                service.get(key)
                for key in (
                    "container_name",
                    "network_mode",
                    "privileged",
                    "devices",
                    "env_file",
                    "secrets",
                    "configs",
                    "volumes_from",
                    "extends",
                    "develop",
                )
            ):
                raise FixtureError("unsafe-service-configuration")
            for mount in service.get("volumes", []):
                if mount.get("type") != "volume" or mount.get("source") not in VOLUMES:
                    raise FixtureError("fresh-named-volumes-required")
            service.pop("build", None)
            service["image"] = identity
            service["pull_policy"] = "never"
            service.setdefault("labels", {})[OWNER_LABEL] = self.nonce
            environment = service.setdefault("environment", {})
            if name in {"api", "worker"}:
                environment.update(
                    {
                        "OPEN_COMMERCE_MODEL_ENABLED": "false",
                        "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": "false",
                        "OPEN_COMMERCE_SHOPIFY_CATALOG_ENABLED": "false",
                        "OPEN_COMMERCE_SHOPIFY_ADMIN_ACCESS_TOKEN": "",
                    }
                )
                if environment.get(
                    "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER"
                ) != "deterministic" or environment.get("OPEN_COMMERCE_OPENAI_API_KEY"):
                    raise FixtureError("model-configuration-refused")
            if name == "web":
                environment["OPEN_COMMERCE_SHOPPER_PUBLIC_URL"] = self.receipt["urls"]["shopper"]
        for kind in ("volumes", "networks"):
            for name, resource in config[kind].items():
                if resource.get("external") or resource.get("driver_opts"):
                    raise FixtureError("external-resource-refused")
                resource["name"] = f"{self.project}_{name}"
                resource.setdefault("labels", {})[OWNER_LABEL] = self.nonce
        config["name"] = self.project
        path = self.directory / "compose.json"
        private_write(path, json.dumps(config))
        self.command = [*base[:-2], "-f", str(path)]
        self.config = config
        self.receipt["images"] = image_metadata
        self.inventory(require_empty=True)
        self.save()

    def inventory(self, *, require_empty: bool = False) -> dict[str, list[dict[str, Any]]]:
        """Refuse existing resources on entry, and foreign labels before teardown."""
        inventory: dict[str, list[dict[str, Any]]] = {}
        for kind in ("container", "volume", "network"):
            listing = ["ps", "--all"] if kind == "container" else [kind, "ls"]
            ids = self.run(
                [
                    "docker",
                    *listing,
                    "--quiet",
                    "--filter",
                    f"label={PROJECT_LABEL}={self.project}",
                ]
            ).split()
            if require_empty and ids:
                raise FixtureError("fixture-project-already-exists")
            rows = json.loads(self.run(["docker", kind, "inspect", *ids])) if ids else []
            for row in rows:
                labels = (
                    row.get("Config", {}).get("Labels", {})
                    if kind == "container"
                    else row.get("Labels", {})
                )
                if (
                    labels.get(PROJECT_LABEL) != self.project
                    or labels.get(OWNER_LABEL) != self.nonce
                ):
                    raise FixtureError("resource-ownership-mismatch")
                if kind == "container" and labels.get(SERVICE_LABEL) not in SERVICES:
                    raise FixtureError("unexpected-fixture-service")
                if kind != "container":
                    names = VOLUMES if kind == "volume" else ("default",)
                    if row["Name"] not in {f"{self.project}_{name}" for name in names}:
                        raise FixtureError("unexpected-fixture-resource")
            inventory[kind] = rows
            if kind != "container":
                # Names can collide even when a resource has no Compose project label.
                all_names = self.run(["docker", kind, "ls", "--format", "{{.Name}}"]).split()
                names = VOLUMES if kind == "volume" else ("default",)
                expected = {f"{self.project}_{name}" for name in names}
                owned = {row["Name"] for row in rows}
                if expected.intersection(all_names) - owned:
                    raise FixtureError("fixture-resource-name-collision")
        return inventory

    def snapshot(self, inventory: dict[str, list[dict[str, Any]]]) -> None:
        services = []
        for row in inventory["container"]:
            state = row.get("State", {})
            identity = row.get("Image", "")
            services.append(
                {
                    "service": row["Config"]["Labels"][SERVICE_LABEL],
                    "image": identity if DIGEST.fullmatch(identity) else "unknown",
                    "status": state.get("Status") if state.get("Status") in STATES else "unknown",
                    "exit_code": state.get("ExitCode")
                    if type(state.get("ExitCode")) is int
                    else None,
                    "health": state.get("Health", {}).get("Status")
                    if state.get("Health", {}).get("Status") in {"starting", "healthy", "unhealthy"}
                    else "none",
                }
            )
        self.receipt["snapshots"].append({"at": now(), "services": services})
        self.save()

    def verify_runtime(self) -> None:
        inventory = self.inventory()
        self.snapshot(inventory)
        rows = inventory["container"]
        if len(rows) != 8 or {r["Config"]["Labels"][SERVICE_LABEL] for r in rows} != set(SERVICES):
            raise FixtureError("runtime-eight-services-required")
        if len(inventory["volume"]) != 4 or len(inventory["network"]) != 1:
            raise FixtureError("runtime-fresh-storage-required")
        for row in rows:
            name = row["Config"]["Labels"][SERVICE_LABEL]
            state = row["State"]
            if row["Image"] != self.images[name]:
                raise FixtureError("runtime-image-mismatch")
            if name == "migrate":
                if state["Status"] != "exited" or state["ExitCode"] != 0:
                    raise FixtureError("migration-not-completed")
            elif state["Status"] != "running" or state.get("Health", {}).get("Status") != "healthy":
                raise FixtureError("runtime-not-healthy")
            environment = dict(item.split("=", 1) for item in row["Config"].get("Env", []))
            if name in {"api", "worker", "web", "shopper"}:
                if environment.get("OPEN_COMMERCE_RUNTIME_PROFILE") != "self_hosted":
                    raise FixtureError("runtime-profile-mismatch")
            for key, value in self.config["services"][name]["environment"].items():
                if environment.get(key) != str(value).replace("$$", "$"):
                    raise FixtureError("runtime-environment-mismatch")
            if name in {"web", "shopper"} and (
                environment.get("NODE_ENV") != "production"
                or row["Config"].get("Cmd") != ["node", f"apps/{name}/server.js"]
            ):
                raise FixtureError("production-web-runtime-required")
            for bindings in row.get("HostConfig", {}).get("PortBindings", {}).values():
                if any(binding.get("HostIp") not in {"127.0.0.1", "::1"} for binding in bindings):
                    raise FixtureError("runtime-public-port-refused")
            actual_ports = {
                (target.split("/")[0], binding["HostIp"], binding["HostPort"])
                for target, bindings in row.get("HostConfig", {}).get("PortBindings", {}).items()
                for binding in bindings
            }
            expected_ports = {
                (str(binding["target"]), binding["host_ip"], str(binding["published"]))
                for binding in self.config["services"][name].get("ports", [])
            }
            if actual_ports != expected_ports:
                raise FixtureError("runtime-port-mismatch")
            if set(row.get("NetworkSettings", {}).get("Networks", {})) != {
                f"{self.project}_default"
            }:
                raise FixtureError("runtime-network-mismatch")
            for mount in row.get("Mounts", []):
                if mount["Type"] == "tmpfs" and mount["Destination"] in {
                    entry.split(":", 1)[0]
                    for entry in self.config["services"][name].get("tmpfs", [])
                }:
                    continue
                if mount["Type"] != "volume" or mount["Name"] not in {
                    f"{self.project}_{volume}" for volume in VOLUMES
                }:
                    raise FixtureError("runtime-foreign-mount-refused")
            expected_mounts = {
                (
                    f"{self.project}_{mount['source']}",
                    mount["target"],
                    not mount.get("read_only", False),
                )
                for mount in self.config["services"][name].get("volumes", [])
            }
            actual_mounts = {
                (mount["Name"], mount["Destination"], mount["RW"])
                for mount in row.get("Mounts", [])
                if mount["Type"] == "volume"
            }
            if actual_mounts != expected_mounts:
                raise FixtureError("runtime-storage-mismatch")
        for service in ("api", "worker"):
            self.run([*self.command, "exec", "-T", service, "python", "-c", RUNTIME_PROBE])
        self.receipt["runtime_verified_at"] = now()
        self.save()

    def browser(self) -> None:
        self.phase = "bootstrap"
        token = self.run(
            [
                *self.command,
                "exec",
                "-T",
                "api",
                "python",
                "-m",
                "open_commerce.stores.console",
                "bootstrap",
            ]
        ).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            raise FixtureError("invalid-bootstrap-output")
        self.phase = "browser"
        raw = self.directory / "browser"
        reporter = self.directory / "reporter.cjs"
        report = self.directory / "browser.json"
        private_write(reporter, REPORTER)
        configuration = {
            "testDir": str(ROOT / "apps/web/e2e"),
            "testMatch": "self-service.spec.ts",
            "fullyParallel": False,
            "workers": 1,
            "retries": 0,
            "timeout": 300000,
            "expect": {"timeout": 30000},
            "outputDir": str(raw),
            "reporter": [[str(reporter)]],
            "use": {
                "baseURL": self.receipt["urls"]["web"],
                "browserName": "chromium",
                "trace": "off",
                "screenshot": "off",
                "video": "off",
                "viewport": {"width": 1280, "height": 720},
            },
        }
        config_path = self.directory / "playwright.config.cjs"
        private_write(config_path, "module.exports = " + json.dumps(configuration) + ";\n")
        environment = {
            key: value
            for key, value in self.environment.items()
            if key in {"PATH", "HOME", "TMPDIR"}
        }
        environment.update(
            {
                "CI": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
                "QA_REPORT": str(report),
                "OPEN_COMMERCE_E2E_SETUP_TOKEN": token,
                "PLAYWRIGHT_BASE_URL": self.receipt["urls"]["web"],
                "SHOPPER_PLAYWRIGHT_BASE_URL": self.receipt["urls"]["shopper"],
            }
        )
        try:
            self.run(
                [
                    "node",
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "self-service.spec.ts",
                    "--config",
                    str(config_path),
                    "--trace",
                    "off",
                ],
                timeout=420,
                environment=environment,
                cwd=ROOT / "apps/web",
            )
        finally:
            environment.pop("OPEN_COMMERCE_E2E_SETUP_TOKEN", None)
            if report.is_file():
                self.receipt["browser"] = sanitized_browser_report(json.loads(report.read_text()))
                self.save()
        result = self.receipt.get("browser", {})
        if (
            result.get("status") != "passed"
            or result.get("errors") != 0
            or len(result.get("tests", [])) != EXPECTED_BROWSER_TESTS
            or any(test["status"] != "passed" for test in result["tests"])
        ):
            raise FixtureError("browser-journey-not-passed")
        self.promote_captures(raw)

    def promote_captures(self, raw: Path) -> None:
        captures = []
        for audience, prefixes in CAPTURES.items():
            for prefix in prefixes:
                for size in ("1440x1000", "390x844"):
                    filename = f"{prefix}-{size}.png"
                    matches = list(raw.rglob(filename))
                    if len(matches) != 1:
                        raise FixtureError("manual-capture-missing")
                    source = matches[0]
                    if source.is_symlink() or not source.resolve().is_relative_to(raw.resolve()):
                        raise FixtureError("manual-capture-path-refused")
                    content = source.read_bytes()
                    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise FixtureError("manual-capture-format-refused")
                    destination = self.output / audience / filename
                    destination.parent.mkdir(exist_ok=True)
                    destination.write_bytes(content)
                    captures.append(
                        {
                            "path": str(destination.relative_to(self.output)),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
        self.receipt["captures"] = captures
        self.save()

    def cleanup(self) -> None:
        if not self.started:
            return
        self.phase = "cleanup"
        inventory = self.inventory()
        self.snapshot(inventory)
        self.run([*self.command, "down", "--volumes", "--timeout", "30"], timeout=120)
        self.inventory(require_empty=True)
        self.receipt["cleanup"] = "verified-empty"


def sanitized_browser_report(data: dict[str, Any]) -> dict[str, Any]:
    """Allowlisted values only; never copy exception messages, HTML or network data."""

    def number(value: Any) -> int:
        return value if type(value) is int and 0 <= value <= 10_000_000 else 0

    return {
        "status": data.get("status") if data.get("status") in TEST_STATES else "incomplete",
        "errors": number(data.get("errors")),
        "tests": [
            {
                "status": row.get("status") if row.get("status") in TEST_STATES else "unknown",
                "duration_ms": number(row.get("duration_ms")),
            }
            for row in data.get("tests", [])[:10]
        ],
        "steps": [
            {"line": number(row.get("line")), "failed": row.get("failed") is True}
            for row in data.get("steps", [])[:2000]
        ],
    }


def execute(image_project: str) -> int:
    previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with tempfile.TemporaryDirectory(
            prefix="opencommerce-self-hosted-qa-", dir="/tmp"
        ) as directory:
            fixture = Fixture(Path(directory), image_project)
            result = 1
            try:
                fixture.prepare()
                fixture.phase = "startup"
                fixture.inventory(require_empty=True)
                fixture.started = True  # Even a partial/timeout startup needs owned teardown.
                fixture.run(
                    [
                        *fixture.command,
                        "up",
                        "-d",
                        "--no-build",
                        "--pull",
                        "never",
                        "--wait",
                        "--wait-timeout",
                        "600",
                    ],
                    timeout=660,
                )
                fixture.phase = "runtime-verification"
                fixture.verify_runtime()
                fixture.browser()
                fixture.receipt["result"] = "passed"
                result = 0
            except KeyboardInterrupt:
                fixture.receipt["result"] = "interrupted"
                result = 130
            except FixtureError as error:
                fixture.receipt["result"] = "failed"
                fixture.receipt["reason"] = str(error)
            except Exception:
                # Third-party exceptions can embed config, tokens or raw stdout.
                fixture.receipt["result"] = "failed"
                fixture.receipt["reason"] = "unexpected-error"
            finally:
                fixture.receipt["last_phase"] = fixture.phase
                for sig in previous:
                    signal.signal(sig, signal.SIG_IGN)
                try:
                    fixture.cleanup()
                except Exception:
                    fixture.receipt["cleanup"] = "unverified-ownership-or-engine-failure"
                    fixture.receipt["result"] = "failed"
                    result = 1
                fixture.receipt["finished_at"] = now()
                fixture.receipt["exit_code"] = result
                fixture.save()
                print(
                    f"Self-hosted Compose QA: {fixture.receipt['result']}; "
                    f"cleanup: {fixture.receipt['cleanup']}. "
                    f"Receipt: {fixture.output / 'receipt.json'}"
                )
            return result
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Opt in to disposable Docker/browser QA")
    parser.add_argument("--image-project", help="Explicit Compose build project; images must exist")
    args = parser.parse_args()
    if not args.run:
        print("Not run. Supply --run and --image-project for isolated production-image QA.")
        return 0
    if not args.image_project or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,100}", args.image_project):
        parser.error("--image-project must explicitly name an existing Compose build project")
    try:
        return execute(args.image_project)
    except Exception:
        print("Self-hosted Compose QA could not create or finalize private evidence.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
