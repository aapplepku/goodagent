"""Scan exact local Compose images and retain per-image CycloneDX inventories."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.setup_self_hosted import compose_command

TRIVY = (
    "aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
)
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_TOTAL_METADATA_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_READ_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
MAX_MANIFEST_IMAGES = 128


class ArchiveValidationError(ValueError):
    """Locally generated validation reasons that contain no archive values."""


class BoundedArchiveReader:
    """Also bound tarfile's implicit PAX/long-name header reads, not just JSON."""

    def __init__(self, handle: BinaryIO) -> None:
        self.handle = handle
        self.read_bytes = 0

    def read(self, size: int = -1) -> bytes:
        if not 0 <= size <= MAX_METADATA_BYTES + tarfile.BLOCKSIZE:
            raise ArchiveValidationError("image archive read size limit exceeded")
        self.read_bytes += size
        if self.read_bytes > MAX_ARCHIVE_READ_BYTES:
            raise ArchiveValidationError("image archive read budget exceeded")
        return self.handle.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.handle.seek(offset, whence)

    def tell(self) -> int:
        return self.handle.tell()


def write_private_new(path: Path, raw: bytes) -> None:
    """Exclusive creation also refuses dangling symlinks; never replace evidence."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def docker_json(*args: str) -> Any:
    return json.loads(subprocess.check_output(["docker", *args], text=True))


def initialize_output(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output.chmod(0o700)
    write_private_new(output / "inventory.json", b'{"complete": false, "images": []}\n')


def validate_service(service: str) -> None:
    if (
        not isinstance(service, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", service) is None
    ):
        raise ValueError("unsafe service evidence filename")


def inspection_identity(info: dict[str, Any]) -> dict[str, Any]:
    """Select identity fields only, never live Config/Env/Cmd/Entrypoint data."""
    try:
        rootfs = info["RootFS"]
        if not isinstance(rootfs, dict) or rootfs.get("Type") != "layers":
            raise ValueError
        layers = rootfs["Layers"]
        if not isinstance(layers, list) or len(layers) > 4096:
            raise ValueError
        for digest in [info["Id"], *layers]:
            if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
                raise ValueError
        for key in ("Architecture", "Os"):
            if (
                not isinstance(info[key], str)
                or re.fullmatch(r"[a-z0-9_.-]{1,64}", info[key]) is None
            ):
                raise ValueError
        return {
            "Id": info["Id"],
            "Architecture": info["Architecture"],
            "Os": info["Os"],
            "RootFS": {"Type": "layers", "Layers": list(layers)},
        }
    except (KeyError, TypeError, ValueError):
        raise ArchiveValidationError("malformed Docker inspection identity") from None


def metadata_json(raw: bytes) -> Any:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ValueError("non-JSON constant")

    try:
        return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ArchiveValidationError("malformed image archive metadata") from None


def archive_path(name: Any) -> str:
    if (
        not isinstance(name, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,511}", name) is None
        or str(PurePosixPath(name)) != name
        or ".." in PurePosixPath(name).parts
    ):
        raise ArchiveValidationError("unsafe image metadata member name")
    return name


def selected_archive_metadata(archive: Path, info: dict[str, Any]) -> tuple[bytes, bytes, str]:
    """Match filesystem/platform, not a signed or complete OCI-index proof.

    Read only regular metadata members; never extract or materialize layer payloads.
    Docker save produces an uncompressed tar; compressed archives are unsupported.
    """
    identity = inspection_identity(info)
    try:
        with (
            archive.open("rb") as handle,
            tarfile.open(fileobj=cast(BinaryIO, BoundedArchiveReader(handle)), mode="r:") as saved,
        ):
            members: dict[str, list[tarfile.TarInfo]] = {}
            for count, member in enumerate(saved, 1):
                if count > MAX_ARCHIVE_MEMBERS:
                    raise ArchiveValidationError("image archive member limit exceeded")
                members.setdefault(str(PurePosixPath(member.name)), []).append(member)
            total = 0

            def read_json(name: str) -> tuple[bytes, Any]:
                nonlocal total
                candidates = members.get(name, [])
                if len(candidates) != 1 or candidates[0].name != name:
                    raise ArchiveValidationError(
                        "missing, duplicate or aliased image metadata member"
                    )
                member = candidates[0]
                if (
                    member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE}
                    or member.sparse is not None
                    or not 0 < member.size <= MAX_METADATA_BYTES
                ):
                    raise ArchiveValidationError("unexpected image manifest/config entry")
                total += member.size
                if total > MAX_TOTAL_METADATA_BYTES:
                    raise ArchiveValidationError("image metadata byte limit exceeded")
                stream = saved.extractfile(member)
                if stream is None:
                    raise ArchiveValidationError("unreadable image metadata member")
                with stream:
                    raw = stream.read(member.size + 1)
                if len(raw) != member.size:
                    raise ArchiveValidationError("truncated image metadata member")
                return raw, metadata_json(raw)

            manifest_raw, manifest = read_json("manifest.json")
            if not isinstance(manifest, list) or not 0 < len(manifest) <= MAX_MANIFEST_IMAGES:
                raise ArchiveValidationError("malformed image manifest list")
            seen: set[str] = set()
            matches: list[tuple[bytes, str]] = []
            for image in manifest:
                if not isinstance(image, dict):
                    raise ArchiveValidationError("malformed image manifest record")
                name = archive_path(image.get("Config"))
                if name in seen or name == "manifest.json":
                    raise ArchiveValidationError("duplicate image manifest config reference")
                seen.add(name)
                layers = image.get("Layers")
                if not isinstance(layers, list) or len(layers) > 4096:
                    raise ArchiveValidationError("malformed image manifest layers")
                for layer in layers:
                    archive_path(layer)
                raw, config = read_json(name)
                if not isinstance(config, dict) or not isinstance(config.get("rootfs"), dict):
                    raise ArchiveValidationError("malformed image config identity fields")
                config_identity = inspection_identity(
                    {
                        "Id": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "Architecture": config.get("architecture"),
                        "Os": config.get("os"),
                        "RootFS": {
                            "Type": config["rootfs"].get("type"),
                            "Layers": config["rootfs"].get("diff_ids"),
                        },
                    }
                )
                if len(layers) != len(config_identity["RootFS"]["Layers"]):
                    raise ArchiveValidationError("image manifest/config layer count mismatch")
                if all(
                    config_identity[key] == identity[key]
                    for key in ("Architecture", "Os", "RootFS")
                ):
                    matches.append((raw, name))
            if len(matches) != 1:
                raise ArchiveValidationError(
                    "export does not uniquely match the inspected image filesystem"
                )
            config_raw, config_name = matches[0]
            return manifest_raw, config_raw, config_name
    except ArchiveValidationError:
        raise
    except (tarfile.TarError, OSError, ValueError, OverflowError, RecursionError):
        raise ValueError("cannot read image archive metadata") from None


def image_config_identity(archive: Path, info: dict[str, Any]) -> str:
    """Docker may identify an OCI index; Trivy identifies the selected image config."""
    _, raw, _ = selected_archive_metadata(archive, info)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def retain_image_identity(
    archive: Path, info: dict[str, Any], output: Path, service: str
) -> dict[str, Any]:
    """Retain private, byte-exact selected inputs; never log their contents."""
    validate_service(service)
    manifest, config, config_name = selected_archive_metadata(archive, info)
    inspected = (json.dumps(inspection_identity(info), sort_keys=True, indent=2) + "\n").encode()
    inputs = {
        "manifest": (f"{service}.image-manifest.json", manifest),
        "config": (f"{service}.image-config.json", config),
        "inspection": (f"{service}.image-inspection.json", inspected),
    }
    for filename, _ in inputs.values():
        path = output / filename
        if path.exists() or path.is_symlink():
            raise FileExistsError("image identity evidence already exists")
    references: dict[str, Any] = {}
    for kind, (filename, raw) in inputs.items():
        write_private_new(output / filename, raw)
        references[kind] = {"file": filename, "sha256": hashlib.sha256(raw).hexdigest()}
    references["config"]["archive_member"] = config_name
    return {
        "image_config_id": "sha256:" + references["config"]["sha256"],
        "identity_inputs": references,
        "identity_match_fields": ["Architecture", "Os", "RootFS"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".opencommerce/security-scans/final"))
    parser.add_argument("--service", action="append", help="Only these Compose services")
    parser.add_argument("--env-file", type=Path, help="Selected isolated Compose environment")
    args = parser.parse_args()
    output = args.output.resolve()
    initialize_output(output)
    started_at = datetime.now(UTC).isoformat()
    command = compose_command(dict(os.environ))
    if args.env_file is not None:
        command.extend(["--env-file", str(args.env_file.resolve())])
    config = json.loads(
        subprocess.check_output([*command, "config", "--format", "json"], text=True)
    )
    services = args.service or sorted(config["services"])
    if len(services) != len(set(services)):
        raise ValueError("duplicate scan service")
    for service in services:
        validate_service(service)
        if service not in config["services"]:
            raise ValueError("unknown scan service")
    records = []
    scanner = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{output}:/scans",
        TRIVY,
    ]
    for service in services:
        reference = config["services"][service].get("image", f"{config['name']}-{service}")
        info = docker_json("image", "inspect", reference)[0]
        archive = output / f"{service}.tar"
        write_private_new(archive, b"")
        identity_retained = False
        try:
            run("docker", "image", "save", "--output", str(archive), info["Id"])
            identity = retain_image_identity(archive, info, output, service)
            config_id = identity["image_config_id"]
            record = {
                "service": service,
                "reference": reference,
                "image_id": info["Id"],
                **identity,
                "repo_digests": info.get("RepoDigests", []),
                "architecture": info["Architecture"],
                "user": info["Config"].get("User"),
                "scanner": TRIVY,
                "scan": f"{service}.scan.json",
                "sbom": f"{service}.cdx.json",
                "complete": False,
            }
            records.append(record)
            (output / "inventory.json").write_text(
                json.dumps({"complete": False, "images": records}, sort_keys=True, indent=2) + "\n"
            )
            identity_retained = True
            # Reserve only new report files; the scanner may populate these placeholders.
            write_private_new(output / record["scan"], b"")
            write_private_new(output / record["sbom"], b"")
            base = [
                *scanner,
                "image",
                "--cache-dir",
                "/scans/cache",
                "--input",
                f"/scans/{service}.tar",
            ]
            run(
                *base,
                "--scanners",
                "vuln",
                "--format",
                "json",
                "--output",
                f"/scans/{service}.scan.json",
            )
            run(*base, "--format", "cyclonedx", "--output", f"/scans/{service}.cdx.json")
        finally:
            # Keep the original if validation or compact-proof persistence failed.
            if identity_retained:
                archive.unlink(missing_ok=True)
        report_path = output / f"{service}.scan.json"
        report_path.chmod(0o600)
        (output / f"{service}.cdx.json").chmod(0o600)
        report = json.loads(report_path.read_text())
        if report.get("Metadata", {}).get("ImageID") != config_id:
            raise ValueError(f"{service}: scanner did not inspect the exported image config")
        findings = [
            v
            for result in report.get("Results", [])
            for v in result.get("Vulnerabilities", []) or []
        ]
        record.update(
            {
                "complete": True,
                "scan_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                "sbom_sha256": hashlib.sha256(
                    (output / f"{service}.cdx.json").read_bytes()
                ).hexdigest(),
                "counts": dict(sorted(Counter(v["Severity"] for v in findings).items())),
                "fix_available_count": sum(bool(v.get("FixedVersion")) for v in findings),
                "untriaged_high_critical_count": sum(
                    v["Severity"] in {"HIGH", "CRITICAL"} for v in findings
                ),
            }
        )
        print(json.dumps(records[-1], sort_keys=True), flush=True)
        (output / "inventory.json").write_text(
            json.dumps({"complete": False, "images": records}, sort_keys=True, indent=2) + "\n"
        )
    (output / "inventory.json").write_text(
        json.dumps(
            {
                "complete": True,
                "images": records,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
