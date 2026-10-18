"""Docker-first local setup. Standard library only; never replace existing configuration."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import secrets
import shlex
import socket
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PORTS = {
    "POSTGRES_PORT": 5432,
    "REDIS_PORT": 6379,
    "QDRANT_PORT": 6333,
    "QDRANT_GRPC_PORT": 6334,
    "API_PORT": 8000,
    "WEB_PORT": 3000,
    "SHOPPER_PORT": 3001,
}


class SetupError(RuntimeError):
    """An actionable error safe to print without environment values."""


def available_ports() -> dict[str, int]:
    held: list[socket.socket] = []
    ports: dict[str, int] = {}
    try:
        for key, preferred in PORTS.items():
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            held.append(connection)
            try:
                connection.bind(("127.0.0.1", preferred))
            except OSError:
                connection.bind(("127.0.0.1", 0))
            ports[key] = connection.getsockname()[1]
        return ports
    finally:
        for connection in held:
            connection.close()


def prepare_environment(path: Path) -> bool:
    if path.is_symlink():
        raise SetupError("Refusing a symlink environment file. Choose a regular private file.")
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved.is_relative_to(root) and not (
        resolved == root / ".env" or resolved.is_relative_to(root / ".opencommerce")
    ):
        raise SetupError(
            "Keep private configuration in the root .env, inside .opencommerce, or outside "
            "this checkout. Other paths can enter container images or source control."
        )
    if path.exists():
        if not path.is_file():
            raise SetupError("The environment path must be a regular file.")
        if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise SetupError("Existing environment is unchanged. Restrict its permissions to 600.")
        return False
    ports = available_ports()
    content = [
        "# Private local configuration. Back up this file separately; never commit it.",
        "# Re-running setup reuses this project, ports, secrets and data volumes.",
        f"COMPOSE_PROJECT_NAME=opencommerce-{secrets.token_hex(4)}",
        "OPEN_COMMERCE_RUNTIME_PROFILE=self_hosted",
        f"OPEN_COMMERCE_ENCRYPTION_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}",
        f"POSTGRES_PASSWORD={secrets.token_hex(24)}",
        "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER=deterministic",
        "OPEN_COMMERCE_MANAGER_MODEL_ID=gpt-5.4-mini",
        "OPEN_COMMERCE_OPENAI_API_KEY=",
        f"OPEN_COMMERCE_SHOPPER_PUBLIC_URL=http://localhost:{ports['SHOPPER_PORT']}",
        *[f"{key}={value}" for key, value in ports.items()],
        "",
    ]
    # Keep incomplete secrets private and ignored; linking publishes without ever
    # replacing a file created by a concurrent setup process.
    with tempfile.TemporaryDirectory(prefix=".env.setup-", dir=path.parent) as staging:
        staged = Path(staging) / "environment"
        descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(content))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(staged, path)
        except FileExistsError:
            raise SetupError(
                "Environment appeared during setup. It was not changed; run setup again."
            ) from None
        except OSError:
            raise SetupError(
                "Could not publish private configuration. Check free space, directory "
                "permissions and filesystem hard-link support, then run setup again. "
                "No existing configuration was replaced."
            ) from None
    return True


def compose_environment() -> dict[str, str]:
    # Compose, not shell evaluation, parses the selected file. Ambient demo settings
    # must not redirect a new installation or inject a model credential into it.
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("OPEN_COMMERCE_", "COMPOSE_"))
        and key not in PORTS
        and key not in {"POSTGRES_PASSWORD", "POSTGRES_PASSWORD_URLENCODED"}
    }


def captured(command: list[str], environment: dict[str, str]) -> str:
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError(
            "Docker/Compose could not run. Install it and start the Docker engine."
        ) from None
    if result.returncode != 0:
        raise SetupError(
            "Docker/Compose preflight failed. Check the engine and the selected environment. "
            "Configuration was preserved; private diagnostics were not printed."
        )
    return result.stdout


def compose_command(environment: dict[str, str]) -> list[str]:
    for command in (["docker", "compose"], ["docker-compose"]):
        try:
            captured([*command, "version"], environment)
            return command
        except SetupError:
            continue
    raise SetupError("Install Docker Engine with Compose v2 or later, then run setup again.")


def validate_configuration(config: dict[str, Any]) -> dict[str, int]:
    try:
        services = config["services"]
        for name in ("api", "worker", "web", "shopper"):
            if services[name]["environment"]["OPEN_COMMERCE_RUNTIME_PROFILE"] != "self_hosted":
                raise SetupError(
                    "This setup command is only for self_hosted installations. Existing demo "
                    "or hosted settings were not changed. Use a separate checkout for a new store."
                )
        key = services["api"]["environment"]["OPEN_COMMERCE_ENCRYPTION_KEY"]
        if (
            not isinstance(key, str)
            or len(base64.b64decode(key, altchars=b"-_", validate=True)) != 32
        ):
            raise SetupError("Set a valid private 32-byte base64 encryption key before starting.")
        if services["worker"]["environment"]["OPEN_COMMERCE_ENCRYPTION_KEY"] != key:
            raise SetupError("API and worker encryption keys must match. No services were started.")
        ports: dict[str, int] = {}
        for name, service in services.items():
            for binding in service.get("ports", []):
                if binding.get("host_ip") not in {"127.0.0.1", "::1"}:
                    raise SetupError("Local setup requires loopback-only port bindings.")
                if name in {"web", "shopper"}:
                    ports[name] = int(binding["published"])
        if set(ports) != {"web", "shopper"}:
            raise SetupError("Both application ports must be configured.")
        return ports
    except (KeyError, TypeError, ValueError, binascii.Error):
        raise SetupError(
            "Invalid Compose configuration or encryption key. No services were started."
        ) from None


def encoded_database_password(config: dict[str, Any]) -> str:
    password = (
        config.get("services", {})
        .get("postgres", {})
        .get("environment", {})
        .get("POSTGRES_PASSWORD")
    )
    if not isinstance(password, str) or not password:
        raise SetupError("Configure the database password before starting.")
    # Compose's serialized config escapes literal dollars for a later Compose parse.
    # Undo exactly that serialization layer, not environment-variable interpolation.
    return quote(password.replace("$$", "$"), safe="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--configure-only", action="store_true", help="Create missing config; do not start Docker"
    )
    args = parser.parse_args()
    path = args.env_file.absolute()
    try:
        created = prepare_environment(path)
        print(
            "Created private configuration."
            if created
            else "Keeping existing configuration unchanged."
        )
        if args.configure_only:
            print("No services started. Existing files were not validated or modified.")
            return 0
        environment = compose_environment()
        command = [
            *compose_command(environment),
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(path),
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]
        config = json.loads(captured([*command, "config", "--format", "json"], environment))
        environment["POSTGRES_PASSWORD_URLENCODED"] = encoded_database_password(config)
        config = json.loads(captured([*command, "config", "--format", "json"], environment))
        ports = validate_configuration(config)
        project = config.get("name")
        if not isinstance(project, str) or not project:
            raise SetupError("Compose did not resolve an installation project name.")
        command.extend(["--project-name", project])
        captured(["docker", "info", "--format", "{{.ServerVersion}}"], environment)
        result = subprocess.run(
            [*command, "up", "-d", "--build", "--wait", "--wait-timeout", "600"],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        if result.returncode:
            raise SetupError(
                "Startup did not become healthy. Configuration and volumes are retained. "
                "Inspect Compose status/logs, fix the failure, and run setup again. "
                "Do not delete volumes to retry."
            )
        print(f"Owner: http://localhost:{ports['web']}/manager")
        print(f"Shopper: http://localhost:{ports['shopper']} (use the store link after sharing)")
        print("For the first owner only, issue a private one-time token in your own terminal:")
        print(
            shlex.join(
                [
                    "env",
                    *[
                        part
                        for key in os.environ
                        if key not in compose_environment()
                        for part in ("-u", key)
                    ],
                    *(
                        [f"DOCKER_CONTEXT={environment['DOCKER_CONTEXT']}"]
                        if environment.get("DOCKER_CONTEXT")
                        else []
                    ),
                    *command,
                    "exec",
                    "api",
                    "python",
                    "-m",
                    "open_commerce.stores.console",
                    "bootstrap",
                ]
            )
        )
        print(
            "Browsing needs no model key. Agent conversation requires an optional server-side key."
        )
        return 0
    except (SetupError, OSError, json.JSONDecodeError) as error:
        message = (
            str(error)
            if isinstance(error, SetupError)
            else "Could not complete local setup. Existing data was retained."
        )
        print(f"Setup stopped: {message}")
        return 1
    except KeyboardInterrupt:
        print("Setup interrupted. Configuration and volumes are retained; run it again to resume.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
