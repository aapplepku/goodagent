"""Cold recovery must preserve data and fail before touching an existing installation."""

import base64
import copy
import io
import json
import secrets
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest
from scripts import backup_self_hosted as backup
from scripts import setup_self_hosted as setup


def config() -> dict[str, Any]:
    settings = {
        "OPEN_COMMERCE_RUNTIME_PROFILE": "self_hosted",
        "OPEN_COMMERCE_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"x" * 32).decode(),
        "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": "openai",
        "OPEN_COMMERCE_OPENAI_API_KEY": "synthetic-not-a-real-key",
    }
    services: dict[str, Any] = {
        name: {"environment": dict(settings), "image": "sha256:" + "1" * 64}
        for name in backup.SERVICES
    }
    services["web"]["environment"]["OPEN_COMMERCE_SHOPPER_PUBLIC_URL"] = "http://localhost:3001"
    for name, port in (("web", 3000), ("shopper", 3001)):
        services[name]["ports"] = [{"host_ip": "127.0.0.1", "target": port, "published": str(port)}]
    return {
        "name": "source-store",
        "services": services,
        "volumes": {name: {"name": f"source-store_{name}"} for name in backup.DATA},
        "networks": {"default": {"name": "source-store_default"}},
    }


def archive(path: Path, *, name: str = "./file", kind: bytes = tarfile.REGTYPE) -> None:
    with tarfile.open(path, "w") as handle:
        root = tarfile.TarInfo(".")
        root.type = tarfile.DIRTYPE
        root.mode = 0o700
        root.uid = root.gid = 999
        handle.addfile(root)
        item = tarfile.TarInfo(name)
        item.type = kind
        item.linkname = "/outside"
        item.mode = 0o600
        item.uid = item.gid = 999
        data = b"private fixture data"
        item.size = len(data) if kind == tarfile.REGTYPE else 0
        handle.addfile(item, io.BytesIO(data) if item.size else None)
    path.chmod(0o600)


def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    (root / "docker-compose.yml").write_text("synthetic source identity")
    monkeypatch.setattr(setup, "ROOT", root)
    monkeypatch.setattr(backup, "validate_layout", lambda value: None)
    directory = backup.safe_destination(tmp_path / "bundle")
    backup.private_json(directory / "configuration.json", config())
    for name in backup.DATA:
        archive(directory / f"{name}.tar")
    names = ["configuration.json", *(f"{name}.tar" for name in backup.DATA)]
    backup.private_json(
        directory / "manifest.json",
        {
            "schema": 1,
            "complete": True,
            "project": "source-store",
            "compose_sha256": backup.digest(root / "docker-compose.yml"),
            "files": {
                name: {
                    "sha256": backup.digest(directory / name),
                    "bytes": (directory / name).stat().st_size,
                }
                for name in names
            },
            "images": {name: "sha256:" + "1" * 64 for name in backup.SERVICES},
        },
    )
    return directory


def test_private_outputs_never_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path / "source")
    directory = backup.safe_destination(tmp_path / "backup")
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    path = directory / "private.json"
    backup.private_json(path, {"synthetic": "secret"})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        backup.private_json(path, {})
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.safe_destination(directory)
    assert path.read_bytes() == original


def test_missing_parent_requires_explicit_private_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    parent = tmp_path / ".opencommerce"
    destination = parent / "private-backup-name"
    with pytest.raises(backup.BackupError, match="parent directory is missing") as error:
        backup.safe_destination(destination)
    assert "mode 700" in str(error.value)
    assert "leave the final destination directory absent" in str(error.value)
    assert str(tmp_path) not in str(error.value)
    assert destination.name not in str(error.value)
    assert not parent.exists()

    parent.mkdir(mode=0o700)
    assert backup.safe_destination(destination) == destination
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.safe_destination(destination)


def test_missing_parent_cli_fails_before_stop_copy_or_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    destination = tmp_path / ".opencommerce" / "private-backup-name"
    current: dict[str, Any] = {
        name: {
            "Image": "sha256:" + "1" * 64,
            "State": {"Running": name != "migrate"},
        }
        for name in backup.SERVICES
    }
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backup_self_hosted.py",
            "backup",
            "--env-file",
            str(tmp_path / "never-read.env"),
            "--confirm-project",
            "source-store",
            "--output",
            str(destination),
        ],
    )
    monkeypatch.setattr(backup, "source_configuration", lambda path: config())
    monkeypatch.setattr(backup, "containers", lambda project: current)
    monkeypatch.setattr(backup, "validate_owned", lambda config, rows: None)
    monkeypatch.setattr(backup, "local_images", lambda identities: {})
    for name in ("run", "private_json", "restart_original"):
        monkeypatch.setattr(
            backup, name, lambda *args, **kwargs: pytest.fail("No service or receipt actions")
        )
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("No real subprocesses")
    )

    assert backup.main() == 1
    output = capsys.readouterr()
    assert "Recovery stopped: Destination parent directory is missing." in output.out
    assert "mode 700" in output.out
    assert "leave the final destination directory absent" in output.out
    assert str(tmp_path) not in output.out
    assert destination.name not in output.out
    assert not output.err
    assert not destination.parent.exists()
    assert all(row["State"]["Running"] for name, row in current.items() if name != "migrate")


def test_dangling_destination_symlink_still_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    parent = tmp_path / ".opencommerce"
    parent.mkdir(mode=0o700)
    destination = parent / "backup"
    target = tmp_path / "missing-parent" / "missing-target"
    destination.symlink_to(target)
    with pytest.raises(backup.BackupError, match="non-symlink"):
        backup.safe_destination(destination)
    assert destination.is_symlink()
    assert not target.parent.exists()


def test_source_and_symlink_destinations_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    with pytest.raises(backup.BackupError, match="outside source"):
        backup.safe_destination(tmp_path / "docs")
    (tmp_path / "linked").symlink_to(tmp_path)
    with pytest.raises(backup.BackupError, match="symlink"):
        backup.safe_destination(tmp_path / "linked" / "backup")


@pytest.mark.parametrize("name", ["../escape", "/outside", "x/../../escape", "x\\escape"])
def test_unsafe_archive_paths_reject(tmp_path: Path, name: str) -> None:
    path = tmp_path / "volume.tar"
    archive(path, name=name)
    with pytest.raises(backup.BackupError, match="unsafe"):
        backup.validate_archive(path)


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_archive_links_and_special_files_reject(tmp_path: Path, kind: bytes) -> None:
    path = tmp_path / "volume.tar"
    archive(path, kind=kind)
    with pytest.raises(backup.BackupError, match="unsupported"):
        backup.validate_archive(path)


def test_archive_content_identity_includes_ownership(tmp_path: Path) -> None:
    path = tmp_path / "volume.tar"
    archive(path)
    original = backup.validate_archive(path)
    with tarfile.open(path, "a") as handle:
        duplicate = tarfile.TarInfo("./file")
        handle.addfile(duplicate)
    with pytest.raises(backup.BackupError, match="unsafe"):
        backup.validate_archive(path)
    assert len(original) == 64


def test_restore_archive_carries_the_volume_root_permissions(tmp_path: Path) -> None:
    source = tmp_path / "source.tar"
    target = tmp_path / "named.tar"
    archive(source)
    backup.named_volume_archive(source, target, "data")
    with tarfile.open(target, "r:") as handle:
        root = handle.getmember("data")
        assert (root.uid, root.gid, root.mode) == (999, 999, 0o700)
        member = handle.getmember("data/file")
        assert member.uid == 999 and member.mode == 0o600
        stream = handle.extractfile(member)
        assert stream and stream.read() == b"private fixture data"
    with pytest.raises(FileExistsError):
        backup.named_volume_archive(source, target, "data")


@pytest.mark.parametrize(
    "mutation", ["missing", "bytes", "permission", "symlink", "manifest", "source"]
)
def test_incomplete_or_changed_bundle_is_rejected_before_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    directory = bundle(tmp_path, monkeypatch)
    assert backup.verified_backup(directory)[0]["complete"]
    path = directory / "postgres-data.tar"
    if mutation == "missing":
        path.unlink()
    elif mutation == "bytes":
        path.write_bytes(b"corrupted")
    elif mutation == "permission":
        path.chmod(0o644)
    elif mutation == "symlink":
        path.unlink()
        path.symlink_to(directory / "redis-data.tar")
    elif mutation == "source":
        (setup.ROOT / "docker-compose.yml").write_text("different source")
    else:
        (directory / "manifest.json").unlink()
    with pytest.raises(backup.BackupError):
        backup.verified_backup(directory)


def test_restored_configuration_keeps_identity_but_disables_external_models() -> None:
    original = config()
    restored = backup.restored_configuration(original, "recovered", dict(setup.PORTS))
    assert original == config()
    assert restored["name"] == "recovered"
    assert restored["networks"]["default"]["internal"] is True
    for name in backup.DATA:
        assert restored["volumes"][name]["name"] == f"recovered_{name}"
    for service in restored["services"].values():
        env = service["environment"]
        assert (
            env["OPEN_COMMERCE_ENCRYPTION_KEY"]
            == original["services"]["api"]["environment"]["OPEN_COMMERCE_ENCRYPTION_KEY"]
        )
        assert env["OPEN_COMMERCE_OPENAI_API_KEY"] == ""
        assert env["OPEN_COMMERCE_MANAGER_MODEL_PROVIDER"] == "deterministic"


def test_layout_keeps_execution_and_mount_security_in_scope() -> None:
    reference = config()
    assert backup.layout(
        backup.restored_configuration(reference, "new", dict(setup.PORTS))
    ) == backup.layout(reference)
    for key, value in (
        ("command", ["malicious"]),
        ("privileged", True),
        ("volumes", [{"type": "bind", "source": "/"}]),
    ):
        changed = copy.deepcopy(reference)
        changed["services"]["api"][key] = value
        assert backup.layout(changed) != backup.layout(reference)


@pytest.mark.parametrize(
    "existing", ["containers", "labelled-volume", "network", "unlabelled-volume"]
)
def test_restore_cannot_overwrite_any_existing_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: str,
) -> None:
    directory = bundle(tmp_path, monkeypatch)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> str:
        commands.append(command)
        if (
            (existing == "containers" and "ps" in command)
            or (existing == "labelled-volume" and "-q" in command and "volume" in command)
            or (existing == "network" and "network" in command)
        ):
            return "existing"
        if existing == "unlabelled-volume" and "--format" in command:
            return "recovered_postgres-data"
        return ""

    monkeypatch.setattr(backup, "run", run)
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.restore(directory, tmp_path / "out", "recovered")
    assert not (tmp_path / "out").exists()
    assert all("create" not in command and "cp" not in command for command in commands)


def test_docker_failure_never_echoes_private_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args[0], 1, b"secret config", b"private password")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(backup.BackupError) as error:
        backup.run(["docker", "inspect", "fixture"])
    assert "secret" not in str(error.value) and "password" not in str(error.value)


def test_forced_or_running_service_cannot_complete_backup() -> None:
    for state in ({"Running": True, "ExitCode": 0}, {"Running": False, "ExitCode": 137}):
        with pytest.raises(backup.BackupError, match="stop cleanly"):
            backup.stopped({"postgres": {"State": state}})


def test_start_rejects_changed_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "configuration.json"
    path.write_text("changed")
    (tmp_path / "restore.json").write_text(
        json.dumps({"complete": True, "project": "recovered", "configuration_sha256": "old"})
    )
    monkeypatch.setattr(backup, "run", lambda *args, **kwargs: pytest.fail("must not reach Docker"))
    with pytest.raises(backup.BackupError, match="unchanged"):
        backup.start(tmp_path, "recovered")


def test_restart_uses_only_original_container_ids_not_compose_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {name: {"Id": f"id-{name}"} for name in backup.SERVICES}
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> str:
        calls.append(command)
        if command[1] == "inspect":
            return json.dumps(
                [
                    {"Id": identifier, "State": {"Running": True, "Health": {"Status": "healthy"}}}
                    for identifier in command[2:]
                ]
            )
        return ""

    monkeypatch.setattr(backup, "run", run)
    backup.restart_original(current, ["postgres", "api", "web"])
    assert [call for call in calls if call[1] == "start"] == [
        ["docker", "start", "id-postgres"],
        ["docker", "start", "id-api"],
        ["docker", "start", "id-web"],
    ]
    assert not any("migrate" in " ".join(call) or "compose" in call for call in calls)


def test_qdrant_receives_shutdown_directly() -> None:
    dockerfile = Path("infra/docker/qdrant/Dockerfile").read_text()
    assert 'CMD ["./qdrant"]' in dockerfile
    with pytest.raises(backup.BackupError, match="stop cleanly"):
        backup.stopped({"qdrant": {"State": {"Running": False, "ExitCode": 143}}})


@pytest.mark.parametrize(
    "host,architecture", [("tcp://remote:2375", "arm64"), ("unix:///local", "amd64")]
)
def test_remote_engine_or_wrong_image_architecture_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    architecture: str,
) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    def run(command: list[str], **kwargs: Any) -> str:
        if command[1:3] == ["context", "show"]:
            return "local"
        if command[1:3] == ["context", "inspect"]:
            return json.dumps([{"Endpoints": {"docker": {"Host": host}}}])
        if command[1] == "info":
            return json.dumps({"Architecture": "aarch64", "OSType": "linux"})
        return json.dumps([{"Architecture": architecture, "Os": "linux"}])

    monkeypatch.setattr(backup, "run", run)
    with pytest.raises(backup.BackupError, match="local Unix|original image platform"):
        backup.local_images(["sha256:" + "1" * 64])


def test_failed_copy_retains_incomplete_evidence_and_restarts_originals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current: dict[str, Any] = {
        name: {
            "Id": "id-" + name,
            "Image": "sha256:" + "1" * 64,
            "State": {"Running": name != "migrate", "ExitCode": 0},
        }
        for name in backup.SERVICES
    }
    calls: list[list[str]] = []
    resumed: list[list[str]] = []
    monkeypatch.setattr(setup, "ROOT", tmp_path / "source")
    monkeypatch.setattr(backup, "source_configuration", lambda path: config())
    monkeypatch.setattr(backup, "containers", lambda project: copy.deepcopy(current))
    monkeypatch.setattr(backup, "validate_owned", lambda config, rows: None)
    monkeypatch.setattr(backup, "local_images", lambda identities: {})
    monkeypatch.setattr(backup, "restart_original", lambda rows, active: resumed.append(active))

    def run(command: list[str], **kwargs: Any) -> str:
        calls.append(command)
        if command[1] == "stop":
            for row in current.values():
                if row["Id"] in command:
                    row["State"]["Running"] = False
        if command[1] == "exec":
            assert not any(current[name]["State"]["Running"] for name in backup.WRITERS)
            return "OK"
        if command[1] == "cp":
            assert not any(row["State"]["Running"] for row in current.values())
            raise backup.BackupError("Synthetic interrupted copy")
        return ""

    monkeypatch.setattr(backup, "run", run)
    output = tmp_path / "backup"
    with pytest.raises(backup.BackupError, match="interrupted copy"):
        backup.backup(tmp_path / "unused.env", output, "source-store")
    assert (output / "INCOMPLETE.json").exists()
    assert not (output / "manifest.json").exists()
    assert resumed == [[name for name in backup.SERVICES if name != "migrate"]]
    assert not any("rm" in call or "down" in call for call in calls)


@pytest.mark.parametrize(
    "change", ["none", "pgdata", "redis-command", "api-assets", "extra-network", "network-egress"]
)
def test_actual_storage_and_network_drift_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    configuration = config()
    image = {
        "Env": [],
        "Cmd": ["safe-server"],
        "Entrypoint": None,
        "WorkingDir": "/app",
        "User": "1000",
    }
    rows: dict[str, Any] = {}
    for name in backup.SERVICES:
        rows[name] = {
            "Id": "id-" + name,
            "Image": "sha256:" + "1" * 64,
            "Config": {
                **image,
                "Env": [
                    f"{key}={value}"
                    for key, value in configuration["services"][name]["environment"].items()
                ],
            },
            "State": {},
            "Mounts": [],
            "HostConfig": {"NetworkMode": "source-store_default"},
            "NetworkSettings": {"Networks": {"source-store_default": {}}},
        }
    for volume, (name, target) in backup.DATA.items():
        configuration["services"][name]["volumes"] = [{"source": volume, "target": target}]
        rows[name]["Mounts"] = [
            {"Destination": target, "Name": "source-store_" + volume, "RW": True, "Type": "volume"}
        ]
    configuration["services"]["api"]["volumes"] = [
        {"source": "catalog-assets", "target": "/app/.opencommerce/assets", "read_only": True}
    ]
    rows["api"]["Mounts"] = [
        {
            "Destination": "/app/.opencommerce/assets",
            "Name": "source-store_catalog-assets",
            "RW": False,
            "Type": "volume",
        }
    ]
    if change == "pgdata":
        rows["postgres"]["Config"]["Env"].append("PGDATA=/not-copied")
    elif change == "redis-command":
        rows["redis"]["Config"]["Cmd"] = ["redis-server", "--dir", "/not-copied"]
    elif change == "api-assets":
        rows["api"]["Mounts"][0]["Name"] = "uncaptured-assets"
    elif change == "extra-network":
        rows["api"]["NetworkSettings"]["Networks"]["external-egress"] = {}

    def run(command: list[str], **kwargs: Any) -> str:
        if command[1] == "image":
            return json.dumps([{"Config": image}])
        if command[1] == "network":
            return json.dumps(
                [
                    {
                        "Internal": change == "network-egress",
                        "Labels": {"com.docker.compose.project": "source-store"},
                    }
                ]
            )
        if command[1] == "volume":
            return json.dumps([{"Labels": {"com.docker.compose.project": "source-store"}}])
        return "\n".join(row["Id"] for row in rows.values())

    monkeypatch.setattr(backup, "run", run)
    if change == "none":
        backup.validate_owned(configuration, rows)
    else:
        with pytest.raises(backup.BackupError):
            backup.validate_owned(configuration, rows)


def test_a_volume_created_during_restore_preflight_is_not_adopted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = bundle(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    monkeypatch.setattr(backup, "local_images", lambda identities: {})
    monkeypatch.setattr(setup, "available_ports", lambda: dict(setup.PORTS))
    monkeypatch.setattr(backup, "command_for", lambda path, project: ["docker-compose"])

    def run(command: list[str], **kwargs: Any) -> str:
        calls.append(command)
        if command[1:3] == ["volume", "inspect"]:
            return json.dumps([{"Labels": {backup.ATTEMPT_LABEL: "other-attempt"}}])
        return ""

    monkeypatch.setattr(backup, "run", run)
    with pytest.raises(backup.BackupError, match="appeared concurrently"):
        backup.restore(directory, tmp_path / "target", "recovered")
    assert not any("cp" in call or "up" in call for call in calls)
    assert not (tmp_path / "target" / "restore.json").exists()


def test_stale_health_cannot_report_a_stopped_container_as_restarted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backup,
        "run",
        lambda command, **kwargs: json.dumps(
            [
                {
                    "Id": "id-api",
                    "State": {"Running": False, "Health": {"Status": "healthy"}},
                }
            ]
        ),
    )
    with pytest.raises(backup.BackupError, match="restart failed"):
        backup.restart_original({"api": {"Id": "id-api"}}, ["api"])


@pytest.mark.parametrize("resource", ["volume", "network"])
def test_replaced_resource_after_container_creation_rejects_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resource: str
) -> None:
    directory = bundle(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    attempt = "a" * 48
    created = False
    monkeypatch.setattr(secrets, "token_hex", lambda count: attempt)
    monkeypatch.setattr(backup, "local_images", lambda identities: {})
    monkeypatch.setattr(setup, "available_ports", lambda: dict(setup.PORTS))
    monkeypatch.setattr(backup, "command_for", lambda path, project: ["docker-compose"])
    monkeypatch.setattr(backup, "validate_owned", lambda config, rows: None)
    monkeypatch.setattr(
        backup,
        "containers",
        lambda project: {
            name: {"Config": {"Labels": {backup.ATTEMPT_LABEL: attempt}}}
            for name in backup.SERVICES
        },
    )

    def run(command: list[str], **kwargs: Any) -> str:
        nonlocal created
        calls.append(command)
        if command[:2] == ["docker-compose", "create"]:
            created = True
        if command[1:3] in (["volume", "inspect"], ["network", "inspect"]):
            nonce = "foreign" if created and command[1] == resource else attempt
            return json.dumps([{"Labels": {backup.ATTEMPT_LABEL: nonce}}])
        return ""

    monkeypatch.setattr(backup, "run", run)
    with pytest.raises(backup.BackupError, match=f"{resource} has been replaced"):
        backup.restore(directory, tmp_path / "target", "recovered")
    assert created
    assert not any("cp" in call or "up" in call for call in calls)
    assert not (tmp_path / "target" / "restore.json").exists()
