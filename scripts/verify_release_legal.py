"""Verify legal text bytes in actual built package archives and Compose images."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dependency_attribution import attribution_gaps, require_attribution
from scripts.setup_self_hosted import compose_command

NAMES = ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md")
IMAGE_DOCKERFILES = {
    "api": "apps/api/Dockerfile",
    "migrate": "apps/api/Dockerfile",
    "worker": "apps/worker/Dockerfile",
    "web": "apps/web/Dockerfile",
    "shopper": "apps/shopper/Dockerfile",
    "postgres": "infra/docker/postgres/Dockerfile",
    "qdrant": "infra/docker/qdrant/Dockerfile",
    "redis": "infra/docker/redis/Dockerfile",
}
REDIS_VERSION = "7.4.11"
REDIS_NOTICES = Path(f"security/third-party/redis-{REDIS_VERSION}")
REDIS_LICENSE = "RSAL-2.0 OR SSPL-1.0"
REDIS_IMAGE_NOTICES = "/usr/share/doc/redis"
MAX_LEGAL_BYTES = 64 * 1024 * 1024
MAX_LEGAL_MEMBERS = 10000
SOURCE_COLLECTIONS = {
    "security/third-party/qdrant-1.19.1": ("manifest.json", "notices.tar.gz"),
    "security/third-party/sharp-libvips-1.3.3": ("native-manifest.json", "native-notices.tar.gz"),
    "security/third-party/sharp-libvips-1.3.4": ("native-manifest.json", "native-notices.tar.gz"),
}


def relative_notice_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("unsafe legal notice path")
    if path.as_posix() != value or value == ".":
        raise ValueError("noncanonical legal notice path")
    return value


def tar_contents(raw: bytes) -> dict[str, bytes]:
    files = {}
    expanded = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
        for index, member in enumerate(archive):
            path = PurePosixPath(member.name)
            if index >= MAX_LEGAL_MEMBERS:
                raise ValueError("legal archive member limit exceeded")
            if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError("archive contains an unsafe path")
            if member.isdir():
                continue
            if not member.isfile() or str(path) in files:
                raise ValueError("legal archive contains a linked, duplicate or nonregular file")
            expanded += member.size
            if member.size < 0 or expanded > MAX_LEGAL_BYTES:
                raise ValueError("legal archive byte limit exceeded")
            stream = archive.extractfile(member)
            assert stream is not None
            files[str(path)] = stream.read()
    return files


def verify_packages(directory: Path) -> list[dict[str, str]]:
    records = []
    paths = sorted(p for p in directory.iterdir() if p.suffix in {".whl", ".gz", ".tgz"})
    if len(paths) != 5:
        raise ValueError("expect exactly one wheel, one sdist and SDK/web/shopper npm tarballs")
    for path in paths:
        raw = path.read_bytes()
        if path.suffix == ".whl":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                files = {n: archive.read(n) for n in archive.namelist() if not n.endswith("/")}
            metadata = BytesParser().parsebytes(
                next(b for n, b in files.items() if n.endswith("/METADATA"))
            )
            name, license_name = metadata["Name"], metadata["License"]
        elif path.suffix == ".tgz":
            files = tar_contents(raw)
            package = json.loads(files["package/package.json"])
            name, license_name = package["name"], package["license"]
        else:
            files = tar_contents(raw)
            metadata = BytesParser().parsebytes(
                next(b for n, b in files.items() if n.count("/") == 1 and n.endswith("/PKG-INFO"))
            )
            name, license_name = metadata["Name"], metadata["License"]
        if license_name != "Apache-2.0":
            raise ValueError(f"{path.name}: incorrect package license metadata")
        for legal in NAMES:
            matches = [b for n, b in files.items() if PurePosixPath(n).name == legal]
            if not matches or any(data != Path(legal).read_bytes() for data in matches):
                raise ValueError(f"{path.name}: missing or changed {legal}")
        records.append(
            {
                "file": path.name,
                "package": str(name),
                "license": license_name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    identities = {(Path(r["file"]).suffix, r["package"]) for r in records}
    if identities != {
        (".whl", "open-commerce-backend"),
        (".gz", "open-commerce-backend"),
        (".tgz", "@open-commerce/web"),
        (".tgz", "@open-commerce/shopper"),
        (".tgz", "@open-commerce/sdk-typescript"),
    }:
        raise ValueError("unexpected package archive identities")
    return records


def verify_collection_files(packages: list[dict[str, Any]], files: dict[str, bytes]) -> set[str]:
    expected = {}
    identities = set()
    for package in packages:
        identity = relative_notice_path(f"{package['name']}@{package['version']}")
        if identity in identities or not package["files"]:
            raise ValueError(f"duplicate or empty notice package: {identity}")
        identities.add(identity)
        for name, checksum in package["files"].items():
            relative_notice_path(name)
            if name in expected or not name.startswith(f"{identity}/"):
                raise ValueError(f"conflicting notice ownership: {identity}")
            expected[name] = checksum
    if not expected or {n: hashlib.sha256(b).hexdigest() for n, b in files.items()} != expected:
        raise ValueError("notice manifest and archive differ")
    return identities


def native_inventory(versions: dict[str, str], files: dict[str, bytes]) -> set[str]:
    expected = {f"{n}@{v}" for n, v in versions.items()}
    locks = [b for n, b in files.items() if PurePosixPath(n).name == "Cargo.lock"]
    if not versions or not locks:
        raise ValueError("native attribution dependency lock or version inventory is missing")
    for raw in locks:
        expected.update(
            f"{p['name']}@{p['version']}"
            for p in tomllib.loads(raw.decode())["package"]
            if p.get("source")
        )
    return expected


def audit_source_notices(root: Path) -> dict[str, Any]:
    """Audit preserved collections without network access or changing historical evidence."""
    collections: list[dict[str, Any]] = []
    for directory, (manifest_name, archive_name) in SOURCE_COLLECTIONS.items():
        manifest_raw = (root / directory / manifest_name).read_bytes()
        manifest = json.loads(manifest_raw)
        archive_raw = (root / directory / archive_name).read_bytes()
        if hashlib.sha256(archive_raw).hexdigest() != manifest["bundle_sha256"]:
            raise ValueError(f"notice archive hash differs: {directory}")
        files = tar_contents(archive_raw)
        identities = verify_collection_files(manifest["packages"], files)
        if manifest_name == "manifest.json":
            sbom_raw = gzip.decompress((root / directory / "upstream.spdx.json.gz").read_bytes())
            if hashlib.sha256(sbom_raw).hexdigest() != manifest["sbom_sha256"]:
                raise ValueError("Qdrant attribution inventory hash differs")
            expected_identities = {
                f"{p['name']}@{p['versionInfo']}" for p in json.loads(sbom_raw)["packages"]
            }
        else:
            expected_identities = native_inventory(manifest["versions"], files)
        if identities != expected_identities:
            raise ValueError(f"notice package coverage differs: {directory}")
        collections.append(
            {
                "collection": directory,
                "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
                "archive_sha256": hashlib.sha256(archive_raw).hexdigest(),
                "packages": len(identities),
                "files": len(files),
                "gaps": attribution_gaps(manifest["packages"], files),
            }
        )
    unique = sorted({gap["package"] for c in collections for gap in c["gaps"]})
    return {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "complete": not unique,
        "archive_integrity_verified": True,
        "attribution_complete": not unique,
        "unique_blocked_packages": unique,
        "blocked_occurrences": sum(len(c["gaps"]) for c in collections),
        "collections": collections,
        "scope": (
            "Known omissions and MIT/BSD standard-template fallbacks "
            "in the three retained collections"
        ),
        "limitations": (
            "Not a complete dependency license audit, proof of rights, "
            "security qualification, or publication approval"
        ),
    }


def docker(*args: str) -> bytes:
    if args and args[0] == "compose":
        environment = dict(os.environ)
        command = compose_command(environment)
        return subprocess.check_output([*command, *args[1:]], env=environment)
    return subprocess.check_output(["docker", *args])


def container_files(image: str, directory: str) -> dict[str, bytes]:
    container = (
        docker("create", "--network", "none", "--entrypoint", "true", image).decode().strip()
    )
    try:
        return tar_contents(docker("cp", f"{container}:{directory}/.", "-"))
    finally:
        subprocess.run(["docker", "rm", container], check=True, stdout=subprocess.DEVNULL)


def redis_notices(info: dict[str, Any]) -> dict[str, bytes]:
    """Require reviewed upstream text in the wrapper; an image label is not legal text.

    The source collection manifest declares version, license and nonempty files mapped
    to SHA-256. The wrapper must copy those same files to REDIS_IMAGE_NOTICES.
    """
    if f"REDIS_VERSION={REDIS_VERSION}" not in info["Config"].get("Env", []):
        raise ValueError("redis: unexpected upstream version")
    try:
        manifest = json.loads((REDIS_NOTICES / "manifest.json").read_bytes())
    except FileNotFoundError:
        raise ValueError("redis: reviewed upstream notice collection is missing") from None
    expected = manifest.get("files")
    if (
        manifest.get("version") != REDIS_VERSION
        or manifest.get("license") != REDIS_LICENSE
        or not isinstance(expected, dict)
        or "LICENSE.txt" not in expected
        or len(expected) > MAX_LEGAL_MEMBERS
    ):
        raise ValueError("redis: invalid reviewed upstream notice manifest")
    files = container_files(info["Id"], REDIS_IMAGE_NOTICES)
    total = 0
    for name, checksum in expected.items():
        relative_notice_path(name)
        reference = (REDIS_NOTICES / name).read_bytes()
        total += len(reference)
        if (
            not reference.strip()
            or total > MAX_LEGAL_BYTES
            or hashlib.sha256(reference).hexdigest() != checksum
            or files.get(name) != reference
        ):
            raise ValueError(f"redis: upstream notice missing or changed: {name}")
    return files


def verify_frontend_notices(service: str, files: dict[str, bytes]) -> None:
    """Check the same bounded standalone notice collection for each frontend."""
    manifest = json.loads(files[f"{service}/manifest.json"])
    packages = manifest["packages"]
    if not packages or len(packages) > MAX_LEGAL_MEMBERS:
        raise ValueError(f"{service}: invalid frontend legal collection")
    if not any(p["name"] == "next" for p in packages):
        raise ValueError(f"{service}: legal collection does not cover Next.js")
    # The reviewed Linux standalone apps ship sharp/libvips. Presence is required
    # independently of the collector's own list; omission must not skip its audit.
    native_packages = [p for p in packages if p["name"].startswith("@img/sharp-libvips-")]
    if len(native_packages) != 1 or native_packages[0]["name"] not in {
        "@img/sharp-libvips-linux-arm64",
        "@img/sharp-libvips-linux-x64",
    }:
        raise ValueError(
            f"{service}: required Linux native attribution collection is missing or ambiguous"
        )
    seen: set[str] = set()
    for package in packages:
        identity = relative_notice_path(f"{package['name']}@{package['version']}")
        if identity in seen or not package["files"]:
            raise ValueError(f"{service}: duplicate package or missing upstream notice text")
        seen.add(identity)
        prefix = f"{service}/third-party/{identity}/"
        for record in package["files"]:
            name = prefix + relative_notice_path(record["path"])
            if not files.get(name) or hashlib.sha256(files[name]).hexdigest() != record["sha256"]:
                raise ValueError(f"{service}: upstream notice missing or changed: {name}")
        if package["name"].startswith("@img/sharp-libvips-"):
            native = json.loads(files[prefix + "native-manifest.json"])
            raw = files[prefix + "native-notices.tar.gz"]
            if hashlib.sha256(raw).hexdigest() != native["bundle_sha256"]:
                raise ValueError("native legal archive hash differs")
            contents = tar_contents(raw)
            expected_native = {k: v for p in native["packages"] for k, v in p["files"].items()}
            if {k: hashlib.sha256(v).hexdigest() for k, v in contents.items()} != expected_native:
                raise ValueError("native legal text differs or is missing")
            if native["versions"] != json.loads(files[prefix + "versions.json"]):
                raise ValueError("native legal versions differ from the shipped inventory")
            identities = verify_collection_files(native["packages"], contents)
            if identities != native_inventory(native["versions"], contents):
                raise ValueError("native notice package coverage differs")
            require_attribution(native["packages"], contents)


def verify_images(env_file: Path | None = None) -> list[dict[str, Any]]:
    scope = ["--env-file", str(env_file.resolve())] if env_file is not None else []
    config = json.loads(docker("compose", *scope, "config", "--format", "json"))
    if set(config["services"]) != set(IMAGE_DOCKERFILES):
        raise ValueError("exactly the eight reviewed Compose services are required")
    for service, definition in config["services"].items():
        build = definition.get("build")
        if (
            not isinstance(build, dict)
            or build.get("dockerfile") != IMAGE_DOCKERFILES[service]
            or not isinstance(build.get("context"), str)
            or not build["context"]
            or Path(build["context"]).resolve() != Path.cwd()
            or "dockerfile_inline" in build
            or definition.get("image", f"{config['name']}-{service}")
            != f"{config['name']}-{service}"
        ):
            raise ValueError(f"{service}: unexpected or missing reviewed image build")
    records = []
    for service, definition in sorted(config["services"].items()):
        reference = definition.get("image", f"{config['name']}-{service}")
        inspected = json.loads(docker("image", "inspect", reference))
        if (
            not isinstance(inspected, list)
            or len(inspected) != 1
            or not isinstance(inspected[0], dict)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", inspected[0].get("Id", ""))
        ):
            raise ValueError(f"{service}: missing or ambiguous image identity")
        info = inspected[0]
        if service == "redis":
            files = redis_notices(info)
            records.append(
                {
                    "service": service,
                    "image_id": info["Id"],
                    "first_party_license": None,
                    "upstream_license": REDIS_LICENSE,
                    "notice_directory": REDIS_IMAGE_NOTICES,
                    "files": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())},
                }
            )
            continue
        labels = info["Config"].get("Labels") or {}
        if labels.get("org.opencontainers.image.licenses") != "Apache-2.0":
            raise ValueError(f"{service}: first-party license label missing")
        files = container_files(info["Id"], "/usr/share/doc/open-commerce-agent")
        for name in NAMES:
            if files.get(name) != Path(name).read_bytes():
                raise ValueError(f"{service}: canonical {name} missing or changed")
        if service in {"api", "worker", "migrate"}:
            manifest = json.loads(files["learned-search/manifest.json"])
            raw_notices = files["learned-search/notices.tar.gz"]
            if hashlib.sha256(raw_notices).hexdigest() != manifest["archive_sha256"]:
                raise ValueError("learned-search notice archive hash differs")
            if {
                name: hashlib.sha256(data).hexdigest()
                for name, data in tar_contents(raw_notices).items()
            } != manifest["files"]:
                raise ValueError("learned-search upstream notice text differs")
        if service in {"web", "shopper"}:
            verify_frontend_notices(service, files)
        if service == "qdrant":
            manifest = json.loads(files["qdrant/manifest.json"])
            raw = docker(
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "cat",
                info["Id"],
                "/qdrant/qdrant.spdx.json",
            )
            if hashlib.sha256(raw).hexdigest() != manifest["sbom_sha256"]:
                raise ValueError("Qdrant legal inventory differs from the shipped binary inventory")
            for package in manifest["packages"]:
                for name, expected in package["files"].items():
                    if hashlib.sha256(files[f"qdrant/notices/{name}"]).hexdigest() != expected:
                        raise ValueError(f"Qdrant upstream notice changed: {name}")
            notices = {
                n.removeprefix("qdrant/notices/"): b
                for n, b in files.items()
                if n.startswith("qdrant/notices/")
            }
            identities = verify_collection_files(manifest["packages"], notices)
            expected_identities = {
                f"{p['name']}@{p['versionInfo']}" for p in json.loads(raw)["packages"]
            }
            if identities != expected_identities:
                raise ValueError("Qdrant notice package coverage differs")
            require_attribution(manifest["packages"], notices)
        if service == "postgres":
            upstream = container_files(info["Id"], "/usr/share/doc/postgresql")
            if (
                upstream["COPYRIGHT"]
                != Path("security/third-party/postgresql-16.15/COPYRIGHT").read_bytes()
            ):
                raise ValueError("PostgreSQL copyright differs")
        records.append(
            {
                "service": service,
                "image_id": info["Id"],
                "first_party_license": "Apache-2.0",
                "files": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())},
            }
        )
    if {r["service"] for r in records} != set(IMAGE_DOCKERFILES):
        raise ValueError("not all project-built images were verified")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--images", action="store_true")
    parser.add_argument(
        "--source-notices",
        action="store_true",
        help="Offline attribution audit; exits nonzero for missing notices",
    )
    parser.add_argument("--env-file", type=Path, help="Selected isolated Compose environment")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.source_notices:
        if args.images or args.artifacts or args.env_file:
            parser.error("--source-notices is a separate offline check")
        source_report = audit_source_notices(Path.cwd())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            handle.write(json.dumps(source_report, sort_keys=True, indent=2) + "\n")
        print(
            f"Attribution audit: {len(source_report['unique_blocked_packages'])} blocked packages; "
            f"{source_report['blocked_occurrences']} collection occurrences"
        )
        raise SystemExit(0 if source_report["attribution_complete"] else 1)
    if not args.artifacts and not args.images:
        parser.error("select --artifacts or --images")
    report: dict[str, Any] = {
        "complete": True,
        "packages": verify_packages(args.artifacts) if args.artifacts else [],
        "images": verify_images(args.env_file) if args.images else [],
        "external_image_scope": (
            "Eight local Compose builds; Redis retains its upstream license and reviewed notices. "
            "No dependency is relicensed by first-party Apache-2.0 metadata."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(
        f"Verified {len(report['packages'])} package archives "
        f"and {len(report['images'])} built images"
    )


if __name__ == "__main__":
    main()
