"""Private cold backups and non-destructive local recovery of one self-hosted installation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tarfile
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import setup_self_hosted as setup

SERVICES = ("postgres", "redis", "qdrant", "migrate", "api", "worker", "web", "shopper")
WRITERS = ("web", "shopper", "api", "worker")
DATA = {
    "postgres-data": ("postgres", "/var/lib/postgresql/data"),
    "redis-data": ("redis", "/data"),
    "qdrant-data": ("qdrant", "/qdrant/storage"),
    "catalog-assets": ("worker", "/app/.opencommerce/assets"),
}
MAX_ARCHIVE_BYTES = 32 * 1024**3
PROJECT = re.compile(r"[a-z0-9][a-z0-9_-]{2,62}\Z")
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
ATTEMPT_LABEL = "org.opencommerce.recovery-attempt"


class BackupError(RuntimeError):
    """Safe diagnostic; private subprocess output is never printed."""


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def private_file(path: Path, data: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def private_json(path: Path, value: Any) -> None:
    private_file(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def safe_destination(path: Path) -> Path:
    path = path.absolute()
    if path.is_symlink() or path.resolve() != path:
        raise BackupError("Choose a non-symlink destination.")
    root = setup.ROOT.resolve()
    if path.is_relative_to(root) and not path.is_relative_to(root / ".opencommerce"):
        raise BackupError(
            "Private backup/recovery files must stay outside source or in .opencommerce."
        )
    if path.exists():
        raise BackupError(
            "Destination already exists. Choose a new directory; nothing was overwritten."
        )
    try:
        path.mkdir(mode=0o700, parents=False)
    except FileNotFoundError:
        raise BackupError(
            "Destination parent directory is missing. Create that parent privately (mode 700), "
            "then retry; leave the final destination directory absent."
        ) from None
    return path


def run(command: list[str], *, input_file: Path | None = None, output: Path | None = None) -> str:
    environment = setup.compose_environment()
    try:
        with ExitStack() as files:
            source = (
                files.enter_context(input_file.open("rb")) if input_file else subprocess.DEVNULL
            )
            target = (
                files.enter_context(
                    os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")
                )
                if output
                else subprocess.PIPE
            )
            result = subprocess.run(
                command,
                cwd=setup.ROOT,
                env=environment,
                stdin=source,
                stdout=target,
                stderr=subprocess.PIPE,
                timeout=900,
                check=False,
            )
        if result.returncode:
            raise BackupError("Docker operation failed; private diagnostics were not printed.")
        return "" if output else result.stdout.decode()
    except (OSError, subprocess.TimeoutExpired):
        raise BackupError(
            "Docker operation interrupted or timed out; retained data was not deleted."
        ) from None


def command_for(config_path: Path, project: str) -> list[str]:
    return [
        *setup.compose_command(setup.compose_environment()),
        "--env-file",
        "/dev/null",
        "--project-directory",
        str(setup.ROOT),
        "--project-name",
        project,
        "-f",
        str(config_path),
    ]


def validate_project(project: str) -> None:
    if not PROJECT.fullmatch(project):
        raise BackupError(
            "Use a lowercase project name of 3-63 letters, numbers, dashes or underscores."
        )


def local_images(identities: list[str]) -> dict[str, dict[str, str]]:
    if os.environ.get("DOCKER_HOST") and not os.environ["DOCKER_HOST"].startswith("unix://"):
        raise BackupError("Recovery supports a local Unix-socket Docker engine only.")
    context = run(["docker", "context", "show"]).strip()
    endpoint = json.loads(run(["docker", "context", "inspect", context]))[0]
    if not endpoint["Endpoints"]["docker"]["Host"].startswith("unix://"):
        raise BackupError("Recovery supports a local Unix-socket Docker context only.")
    engine = json.loads(run(["docker", "info", "--format", "{{json .}} "]))
    architecture = {"aarch64": "arm64", "x86_64": "amd64"}.get(
        engine["Architecture"], engine["Architecture"]
    )
    result: dict[str, dict[str, str]] = {}
    for identity in set(identities):
        if not IMAGE.fullmatch(identity):
            raise BackupError("Expected an exact image ID, never a mutable tag.")
        image = json.loads(run(["docker", "image", "inspect", identity]))[0]
        if image["Architecture"] != architecture or image["Os"] != engine["OSType"]:
            raise BackupError(
                "Restore requires the original image platform; emulation is unverified."
            )
        result[identity] = {"architecture": image["Architecture"], "os": image["Os"]}
    return result


def source_configuration(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise BackupError("The existing environment must be a regular private (600) file.")
    environment = setup.compose_environment()
    command = [
        *setup.compose_command(environment),
        "--project-directory",
        str(setup.ROOT),
        "--env-file",
        str(path.absolute()),
        "-f",
        str(setup.ROOT / "docker-compose.yml"),
        "config",
        "--format",
        "json",
    ]
    config: dict[str, Any] = json.loads(setup.captured(command, environment))
    environment["POSTGRES_PASSWORD_URLENCODED"] = setup.encoded_database_password(config)
    config = json.loads(setup.captured(command, environment))
    setup.validate_configuration(config)
    validate_project(config["name"])
    if set(config["services"]) != set(SERVICES) or set(config["volumes"]) != set(DATA):
        raise BackupError("Only the standard self-hosted service and volume layout is supported.")
    return config


def containers(project: str) -> dict[str, dict[str, Any]]:
    ids = run(
        [
            "docker",
            "ps",
            "-aq",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={project}",
        ]
    ).split()
    if not ids:
        raise BackupError("No installation containers found. Check the project and Docker context.")
    result: dict[str, dict[str, Any]] = {}
    for item in json.loads(run(["docker", "inspect", *ids])):
        labels = item["Config"].get("Labels", {})
        name = labels.get("com.docker.compose.service")
        if (
            name not in SERVICES
            or name in result
            or labels.get("com.docker.compose.oneoff") == "True"
        ):
            raise BackupError(
                "Unexpected or duplicate project containers; stop and inspect the installation."
            )
        result[name] = item
    if set(result) != set(SERVICES):
        raise BackupError(
            "All eight standard service containers must exist before backup/recovery."
        )
    return result


def validate_owned(config: dict[str, Any], current: dict[str, Any]) -> None:
    project = config["name"]
    owned = {row["Id"] for row in current.values()}
    for name, row in current.items():
        service = config["services"][name]
        image = json.loads(run(["docker", "image", "inspect", row["Image"]]))[0]["Config"]
        expected = dict(value.split("=", 1) for value in image.get("Env", []))
        expected.update(
            {
                key: str(value).replace("$$", "$")
                for key, value in service.get("environment", {}).items()
            }
        )
        actual = dict(value.split("=", 1) for value in row["Config"].get("Env", []))
        if actual != expected:
            raise BackupError(
                "Running configuration differs from the selected file; reconcile it before backup."
            )
        for key, compose_key in (
            ("Cmd", "command"),
            ("Entrypoint", "entrypoint"),
            ("WorkingDir", "working_dir"),
            ("User", "user"),
        ):
            expected_value = service.get(compose_key)
            if expected_value is None:
                expected_value = image.get(key)
            if row["Config"].get(key) != expected_value:
                raise BackupError(
                    "Container command, user or working directory differs from the supported setup."
                )
        expected_mounts = {
            mount["target"]: (
                config["volumes"][mount["source"]]["name"],
                not mount.get("read_only", False),
            )
            for mount in service.get("volumes", [])
        }
        actual_mounts = {
            mount["Destination"]: (mount.get("Name"), mount.get("RW")) for mount in row["Mounts"]
        }
        if actual_mounts != expected_mounts or any(
            mount["Type"] != "volume" for mount in row["Mounts"]
        ):
            raise BackupError(
                "Every persistent mount must match, including the API's read-only assets."
            )
        if service.get("image") and row["Image"] != service["image"]:
            raise BackupError("Container image differs from the frozen recovery configuration.")
        if row["State"].get("Paused") or row["State"].get("Restarting"):
            raise BackupError("A container is paused/restarting; resolve it before backup.")
    network_name = config["networks"]["default"]["name"]
    network = json.loads(run(["docker", "network", "inspect", network_name]))[0]
    if (
        network.get("Internal") != config["networks"]["default"].get("internal", False)
        or (network.get("Labels") or {}).get("com.docker.compose.project") != project
    ):
        raise BackupError("Actual network isolation or ownership does not match the configuration.")
    for row in current.values():
        if (
            set(row["NetworkSettings"]["Networks"]) != {network_name}
            or row["HostConfig"]["NetworkMode"] != network_name
        ):
            raise BackupError("A container has an unexpected network attachment.")
    for volume, (service, target) in DATA.items():
        name = config["volumes"][volume].get("name")
        if name != f"{project}_{volume}":
            raise BackupError("External/shared or custom volume names are not supported.")
        mounts = [mount for mount in current[service]["Mounts"] if mount["Destination"] == target]
        if len(mounts) != 1 or mounts[0].get("Name") != name or mounts[0]["Type"] != "volume":
            raise BackupError("Persistent storage does not match the selected installation.")
        info = json.loads(run(["docker", "volume", "inspect", name]))[0]
        if (info.get("Labels") or {}).get("com.docker.compose.project") != project:
            raise BackupError("Volume ownership could not be verified.")
        users = set(
            run(["docker", "ps", "-aq", "--no-trunc", "--filter", f"volume={name}"]).split()
        )
        if not users <= owned:
            raise BackupError(
                "Another container shares this volume; a consistent backup cannot be proven."
            )


def validate_attempt(config: dict[str, Any], current: dict[str, Any], attempt: Any) -> None:
    if not isinstance(attempt, str) or not re.fullmatch(r"[a-f0-9]{48}", attempt):
        raise BackupError("A valid recovery-attempt receipt is required.")
    for row in current.values():
        if row["Config"].get("Labels", {}).get(ATTEMPT_LABEL) != attempt:
            raise BackupError("A recovery container has been replaced since verification.")
    for volume in DATA:
        info = json.loads(run(["docker", "volume", "inspect", config["volumes"][volume]["name"]]))[
            0
        ]
        if (info.get("Labels") or {}).get(ATTEMPT_LABEL) != attempt:
            raise BackupError("A recovery volume has been replaced since verification.")
    network = json.loads(
        run(["docker", "network", "inspect", config["networks"]["default"]["name"]])
    )[0]
    if (network.get("Labels") or {}).get(ATTEMPT_LABEL) != attempt:
        raise BackupError("A recovery network has been replaced since verification.")


def validate_archive(path: Path) -> str:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise BackupError("Archive exceeds the supported 32 GiB cold-backup limit.")
    seen: set[str] = set()
    contents: dict[str, Any] = {}
    expanded = 0
    with tarfile.open(path, "r:") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in member.name
                or not (member.isfile() or member.isdir())
                or str(name) in seen
                or member.mode & 0o7000
                or member.size < 0
            ):
                raise BackupError(
                    "Backup contains unsupported links, special files or unsafe paths/modes."
                )
            seen.add(str(name))
            expanded += member.size
            if len(seen) > 1_000_000 or expanded > MAX_ARCHIVE_BYTES:
                raise BackupError("Archive exceeds supported entry/expanded-size limits.")
            stream = archive.extractfile(member) if member.isfile() else None
            try:
                checksum = hashlib.sha256()
                if stream:
                    while chunk := stream.read(1024 * 1024):
                        checksum.update(chunk)
                contents[str(name)] = {
                    "mode": member.mode,
                    "uid": member.uid,
                    "gid": member.gid,
                    "directory": member.isdir(),
                    "size": member.size,
                    "sha256": checksum.hexdigest() if stream else None,
                }
            finally:
                if stream:
                    stream.close()
    if not seen:
        raise BackupError("An empty archive cannot prove the volume was copied.")
    return hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()


def layout(config: dict[str, Any]) -> dict[str, Any]:
    """Ignore deployment values, never executable settings or storage boundaries."""
    result = copy.deepcopy(config)
    result.pop("name", None)
    for key in list(result):
        if key.startswith("x-"):
            del result[key]
    for service in result["services"].values():
        for key in ("build", "image"):
            service.pop(key, None)
        service["environment"] = sorted(service.get("environment", {}))
        if ATTEMPT_LABEL in service.get("labels", {}):
            service["labels"].pop(ATTEMPT_LABEL)
            if not service["labels"]:
                service.pop("labels")
        for binding in service.get("ports", []):
            binding.pop("published", None)
    for volume in result["volumes"].values():
        volume.pop("name", None)
    for network in result["networks"].values():
        network.pop("name", None)
        network.pop("internal", None)
        if network.get("ipam") == {}:
            network.pop("ipam")
    return result


def validate_layout(config: dict[str, Any]) -> None:
    reference = json.loads(
        run(
            [
                *command_for(setup.ROOT / "docker-compose.yml", "backup-layout-check"),
                "config",
                "--format",
                "json",
            ]
        )
    )
    if layout(config) != layout(reference):
        raise BackupError(
            "Backup commands, mounts or security settings differ from the trusted Compose source."
        )


def named_volume_archive(source: Path, output: Path, basename: str) -> None:
    """Copy the mount directory itself so Docker also restores its owner and mode."""
    validate_archive(source)
    if PurePosixPath(basename).name != basename or basename in {".", ".."}:
        raise BackupError("Invalid fixed volume directory name.")
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as file:
        with tarfile.open(source, "r:") as old, tarfile.open(fileobj=file, mode="w") as new:
            for item in old:
                name = PurePosixPath(item.name)
                renamed = item.replace(name=str(PurePosixPath(basename) / name))
                renamed.pax_headers = {
                    key: value for key, value in item.pax_headers.items() if key != "path"
                }
                stream = old.extractfile(item) if item.isfile() else None
                try:
                    new.addfile(renamed, stream)
                finally:
                    if stream:
                        stream.close()


def stopped(current: dict[str, Any]) -> None:
    if any(row["State"]["Running"] or row["State"]["ExitCode"] != 0 for row in current.values()):
        raise BackupError(
            "Every service must stop cleanly. No backup is marked complete after a forced exit."
        )


def restart_original(current: dict[str, Any], active: list[str]) -> None:
    for group in (("postgres", "redis", "qdrant"), ("api", "worker"), ("web", "shopper")):
        ids = [current[name]["Id"] for name in group if name in active]
        if not ids:
            continue
        run(["docker", "start", *ids])
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            rows = json.loads(run(["docker", "inspect", *ids]))
            if {row["Id"] for row in rows} != set(ids):
                raise BackupError(
                    "Restart inspection did not return the exact original containers."
                )
            if all(
                row["State"]["Running"]
                and row["State"].get("Health", {}).get("Status") == "healthy"
                for row in rows
            ):
                break
            if any(not row["State"]["Running"] for row in rows):
                raise BackupError(
                    "Original service restart failed; inspect the retained installation."
                )
            time.sleep(1)
        else:
            raise BackupError(
                "Original service health timed out; inspect the retained installation."
            )


def backup(env_file: Path, output: Path, confirmation: str) -> None:
    config = source_configuration(env_file)
    project = config["name"]
    if confirmation != project:
        raise BackupError("Confirm the exact source project name before stopping it.")
    current = containers(project)
    validate_owned(config, current)
    platforms = local_images([row["Image"] for row in current.values()])
    if current["migrate"]["State"]["Running"]:
        raise BackupError("Wait for the active migration to finish before taking a backup.")
    destination = safe_destination(output)
    private_json(
        destination / "INCOMPLETE.json",
        {"project": project, "started_at": datetime.now(UTC).isoformat()},
    )
    active = [name for name in SERVICES if current[name]["State"]["Running"]]
    frozen = copy.deepcopy(config)
    for key in list(frozen):
        if key.startswith("x-"):
            del frozen[key]
    for name in SERVICES:
        frozen["services"][name].pop("build", None)
        frozen["services"][name]["image"] = current[name]["Image"]
    private_json(destination / "configuration.json", frozen)
    try:
        print("Stopping the selected installation for a consistent cold backup.")
        for group in (WRITERS[:2], WRITERS[2:]):
            ids = [current[name]["Id"] for name in group if name in active]
            if ids:
                run(["docker", "stop", "--time", "360", *ids])
        # Redis must persist queues and quota state even when its periodic RDB save
        # has not yet run. No application writer remains at this point.
        if "redis" in active:
            if run(["docker", "exec", current["redis"]["Id"], "redis-cli", "SAVE"]).strip() != "OK":
                raise BackupError("Redis did not confirm a durable save.")
        ids = [current[name]["Id"] for name in ("postgres", "redis", "qdrant") if name in active]
        if ids:
            run(["docker", "stop", "--time", "120", *ids])
        shutdown = containers(project)
        private_json(
            destination / "shutdown.json",
            {
                name: {"running": row["State"]["Running"], "exit_code": row["State"]["ExitCode"]}
                for name, row in shutdown.items()
            },
        )
        stopped(shutdown)
        for volume, (service, path) in DATA.items():
            stopped(containers(project))
            archive = destination / f"{volume}.tar"
            run(["docker", "cp", f"{current[service]['Id']}:{path}/.", "-"], output=archive)
            validate_archive(archive)
        stopped(containers(project))
        files = ["configuration.json", *(f"{name}.tar" for name in DATA)]
        private_json(
            destination / "manifest.json",
            {
                "schema": 1,
                "complete": True,
                "created_at": datetime.now(UTC).isoformat(),
                "project": project,
                "compose_sha256": digest(setup.ROOT / "docker-compose.yml"),
                "files": {
                    name: {
                        "sha256": digest(destination / name),
                        "bytes": (destination / name).stat().st_size,
                    }
                    for name in files
                },
                "images": {name: current[name]["Image"] for name in SERVICES},
                "platforms": platforms,
                "requires": "Trusted backup; retain exact images; same CPU architecture.",
            },
        )
        print("Cold backup completed. It contains credentials and personal data; keep it private.")
    finally:
        if active:
            restart_original(current, active)
            print("Previously running containers restarted and passed their health checks.")


def verified_backup(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise BackupError("Backup directory must be private (700), regular and trusted.")
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BackupError(
            "No completed backup manifest. Retain the incomplete attempt for diagnosis."
        )
    manifest = json.loads(manifest_path.read_bytes())
    required = {"configuration.json", *(f"{name}.tar" for name in DATA)}
    if (
        manifest.get("schema") != 1
        or manifest.get("complete") is not True
        or set(manifest["files"]) != required
    ):
        raise BackupError("Unsupported or incomplete backup manifest.")
    if manifest["compose_sha256"] != digest(setup.ROOT / "docker-compose.yml"):
        raise BackupError("Restore from the same Compose source version, then upgrade separately.")
    for name in required:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise BackupError("Backup members must be regular private files.")
        if manifest["files"][name] != {"sha256": digest(path), "bytes": path.stat().st_size}:
            raise BackupError("Backup checksum/size mismatch. No restore was attempted.")
        if name.endswith(".tar"):
            validate_archive(path)
    config = json.loads((directory / "configuration.json").read_bytes())
    setup.validate_configuration(config)
    validate_layout(config)
    if set(config["services"]) != set(SERVICES) or set(config["volumes"]) != set(DATA):
        raise BackupError("Unsupported service/volume layout.")
    if config["name"] != manifest["project"] or set(manifest["images"]) != set(SERVICES):
        raise BackupError("Backup installation identity mismatch.")
    for name, identity in manifest["images"].items():
        if not IMAGE.fullmatch(identity) or config["services"][name].get("image") != identity:
            raise BackupError("Backup images must match exact recorded local image IDs.")
    return manifest, config


def restored_configuration(
    config: dict[str, Any], project: str, ports: dict[str, int]
) -> dict[str, Any]:
    config = copy.deepcopy(config)
    config["name"] = project
    for volume in DATA:
        config["volumes"][volume] = {"name": f"{project}_{volume}"}
    config["networks"] = {"default": {"name": f"{project}_default", "internal": True}}
    port_keys = dict(
        zip(
            ("postgres", "redis", "qdrant", "api", "web", "shopper"),
            ("POSTGRES_PORT", "REDIS_PORT", "QDRANT_PORT", "API_PORT", "WEB_PORT", "SHOPPER_PORT"),
            strict=True,
        )
    )
    for name, service in config["services"].items():
        service.pop("build", None)
        service.pop("container_name", None)
        for binding in service.get("ports", []):
            key = (
                "QDRANT_GRPC_PORT"
                if name == "qdrant" and binding["target"] == 6334
                else port_keys[name]
            )
            binding["published"] = str(ports[key])
        environment = service.get("environment", {})
        for key in ("OPEN_COMMERCE_OPENAI_API_KEY", "OPEN_COMMERCE_OIDC_CLIENT_SECRET"):
            if key in environment:
                environment[key] = ""
        if "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER" in environment:
            environment["OPEN_COMMERCE_MANAGER_MODEL_PROVIDER"] = "deterministic"
        if "OPEN_COMMERCE_SHOPPER_PUBLIC_URL" in environment:
            environment["OPEN_COMMERCE_SHOPPER_PUBLIC_URL"] = (
                f"http://localhost:{ports['SHOPPER_PORT']}"
            )
    return config


def restore(directory: Path, output: Path, project: str, *, local_preview: bool = False) -> None:
    validate_project(project)
    manifest, config = verified_backup(directory)
    if project == manifest["project"]:
        raise BackupError(
            "Restore requires a different project; never overwrite the source installation."
        )
    for command in (
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"],
        ["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"],
        ["docker", "network", "ls", "-q", "--filter", f"name=^{project}_default$"],
    ):
        if run(command).strip():
            raise BackupError(
                "Restore project already exists. Choose a new name; no data was overwritten."
            )
    existing = set(run(["docker", "volume", "ls", "--format", "{{.Name}}"]).split())
    if existing & {f"{project}_{name}" for name in DATA}:
        raise BackupError(
            "A target volume already exists, including unlabelled volumes. Choose a new project."
        )
    local_images(list(manifest["images"].values()))
    destination = safe_destination(output)
    config = restored_configuration(config, project, setup.available_ports())
    config["networks"]["default"]["internal"] = not local_preview
    attempt = secrets.token_hex(24)
    for service in config["services"].values():
        service.setdefault("labels", {})[ATTEMPT_LABEL] = attempt
    private_json(destination / "configuration.json", config)
    private_json(
        destination / "INCOMPLETE.json",
        {"project": project, "started_at": datetime.now(UTC).isoformat()},
    )
    command = command_for(destination / "configuration.json", project)
    # Docker does not change existing volume labels on create. An unguessable
    # attempt label distinguishes newly created storage from a racing operation.
    for volume in DATA:
        name = config["volumes"][volume]["name"]
        run(
            [
                "docker",
                "volume",
                "create",
                "--label",
                f"com.docker.compose.project={project}",
                "--label",
                f"com.docker.compose.volume={volume}",
                "--label",
                f"{ATTEMPT_LABEL}={attempt}",
                name,
            ]
        )
        info = json.loads(run(["docker", "volume", "inspect", name]))[0]
        if (info.get("Labels") or {}).get(ATTEMPT_LABEL) != attempt:
            raise BackupError("A target volume appeared concurrently; it was not overwritten.")
    run(
        [
            "docker",
            "network",
            "create",
            *([] if local_preview else ["--internal"]),
            "--label",
            f"com.docker.compose.project={project}",
            "--label",
            "com.docker.compose.network=default",
            "--label",
            f"{ATTEMPT_LABEL}={attempt}",
            f"{project}_default",
        ]
    )
    run([*command, "create", "--no-recreate", "--no-build", "--pull", "never"])
    current = containers(project)
    if any(
        row["Config"].get("Labels", {}).get(ATTEMPT_LABEL) != attempt for row in current.values()
    ):
        raise BackupError(
            "A target container appeared concurrently; it was not replaced or written."
        )
    validate_owned(config, current)
    # Volumes can be replaced while still unattached after their initial create.
    # Recheck ownership once containers hold them, before the first data write.
    validate_attempt(config, current, attempt)
    stopped(current)
    content_hashes: dict[str, str] = {}
    for volume, (service, path) in DATA.items():
        stopped(containers(project))
        prepared: Path | None = None
        copy_source = directory / f"{volume}.tar"
        copy_target = path
        if not config["services"][service].get("read_only"):
            prepared = destination / f"restore-{volume}.tar"
            named_volume_archive(copy_source, prepared, PurePosixPath(path).name)
            copy_source = prepared
            copy_target = str(PurePosixPath(path).parent)
        # On a read-only root filesystem Docker permits copy into the mounted
        # volume, not its parent. Exact-image volume initialization supplies the
        # root attributes; the subsequent comparison must still prove equality.
        run(
            ["docker", "cp", "-a", "-", f"{current[service]['Id']}:{copy_target}"],
            input_file=copy_source,
        )
        verified = destination / f"verified-{volume}.tar"
        run(["docker", "cp", f"{current[service]['Id']}:{path}/.", "-"], output=verified)
        content_hashes[volume] = validate_archive(verified)
        if content_hashes[volume] != validate_archive(directory / f"{volume}.tar"):
            raise BackupError("Restored volume bytes or numeric ownership do not match the backup.")
        if prepared:
            prepared.unlink()
    stopped(containers(project))
    private_json(
        destination / "restore.json",
        {
            "schema": 1,
            "complete": True,
            "project": project,
            "source_manifest_sha256": digest(directory / "manifest.json"),
            "configuration_sha256": digest(destination / "configuration.json"),
            "attempt": attempt,
            "local_preview": local_preview,
            "volume_content_sha256": content_hashes,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    print(
        f"Restored project {project}; all services remain stopped. Model credentials are disabled."
    )
    print("Run the explicit start operation only after checking the recovery runbook.")


def start(directory: Path, project: str) -> None:
    validate_project(project)
    receipt = json.loads((directory / "restore.json").read_bytes())
    path = directory / "configuration.json"
    if (
        receipt.get("complete") is not True
        or receipt.get("project") != project
        or receipt.get("configuration_sha256") != digest(path)
    ):
        raise BackupError(
            "A completed, unchanged restore receipt and exact project confirmation are required."
        )
    config = json.loads(path.read_bytes())
    setup.validate_configuration(config)
    validate_layout(config)
    local_images([row["image"] for row in config["services"].values()])
    if config["name"] != project or config["networks"]["default"].get("internal") != (
        not receipt.get("local_preview", False)
    ):
        raise BackupError("Recovery project or network mode differs from the completed receipt.")
    current = containers(project)
    validate_owned(config, current)
    validate_attempt(config, current, receipt.get("attempt"))
    run(
        [
            *command_for(path, project),
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "600",
        ]
    )
    if receipt.get("local_preview"):
        ports = setup.validate_configuration(config)
        print("Local preview permits outbound networking. Model credentials remain disabled.")
        print(f"Recovered owner app: http://localhost:{ports['web']}/manager")
        print(f"Recovered shopper app: http://localhost:{ports['shopper']}")
    else:
        print(
            "Offline recovery started. Host port forwarding is unavailable on an internal network."
        )
        print("Run verification through docker exec; see the recovery runbook for local preview.")
    print(
        "Verify login, catalog/search, images, memory and demo orders before considering cutover."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    capture = sub.add_parser("backup")
    capture.add_argument("--env-file", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--confirm-project", required=True)
    recovery = sub.add_parser("restore")
    recovery.add_argument("--backup", type=Path, required=True)
    recovery.add_argument("--output", type=Path, required=True)
    recovery.add_argument("--project", required=True)
    recovery.add_argument(
        "--local-preview",
        action="store_true",
        help="Permit outbound networking and loopback app access after start; models stay disabled",
    )
    launch = sub.add_parser("start")
    launch.add_argument("--directory", type=Path, required=True)
    launch.add_argument("--confirm-project", required=True)
    args = parser.parse_args()
    try:
        if args.action == "backup":
            backup(args.env_file, args.output, args.confirm_project)
        elif args.action == "restore":
            restore(
                args.backup.absolute(), args.output, args.project, local_preview=args.local_preview
            )
        else:
            start(args.directory.absolute(), args.confirm_project)
        return 0
    except (
        BackupError,
        setup.SetupError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        tarfile.TarError,
    ) as error:
        message = (
            str(error)
            if isinstance(error, BackupError | setup.SetupError)
            else ("Invalid or unavailable local recovery input.")
        )
        print(f"Recovery stopped: {message}")
        print(
            "Existing data and incomplete evidence were retained. Do not delete volumes to retry."
        )
        return 1
    except KeyboardInterrupt:
        print("Interrupted; retain incomplete evidence and inspect service state before retrying.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
