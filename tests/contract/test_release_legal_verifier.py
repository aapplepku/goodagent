"""Exercise the real eight-service policy without Docker or external downloads."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from scripts import verify_release_legal as legal

ROOT = Path(__file__).resolve().parents[2]
QDRANT_SBOM = json.dumps({"packages": [{"name": "qdrant", "versionInfo": "fixture"}]}).encode()


def checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tar_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, raw in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return buffer.getvalue()


def frontend_files(app: str) -> dict[str, bytes]:
    notice = b"Synthetic Next.js notice fixture\n"
    native_files = {
        "vips@fixture/COPYING": b"Synthetic native notice fixture\n",
        "vips@fixture/Cargo.lock": b"version = 3\npackage = []\n",
    }
    native_archive = tar_bytes(native_files)
    native = {
        "bundle_sha256": checksum(native_archive),
        "versions": {"vips": "fixture"},
        "packages": [
            {
                "name": "vips",
                "version": "fixture",
                "files": {name: checksum(raw) for name, raw in native_files.items()},
            }
        ],
    }
    entries = {
        ("next", "15.5.27"): {"license.md": notice},
        ("@img/sharp-libvips-linux-arm64", "1.3.4"): {
            "native-manifest.json": json.dumps(native).encode(),
            "native-notices.tar.gz": native_archive,
            "versions.json": json.dumps(native["versions"]).encode(),
        },
    }
    files = {}
    packages = []
    for (name, version), notices in entries.items():
        packages.append(
            {
                "name": name,
                "version": version,
                "files": [{"path": path, "sha256": checksum(raw)} for path, raw in notices.items()],
            }
        )
        files.update(
            {f"{app}/third-party/{name}@{version}/{path}": raw for path, raw in notices.items()}
        )
    files[f"{app}/manifest.json"] = json.dumps({"packages": packages}).encode()
    return files


@dataclass
class ImageFixture:
    config: dict[str, Any]
    inspections: dict[str, dict[str, Any]]
    contents: dict[tuple[str, str], dict[str, bytes]]
    calls: list[tuple[str, ...]] = field(default_factory=list)
    sbom: bytes = QDRANT_SBOM

    def docker(self, *args: str) -> bytes:
        self.calls.append(args)
        if args == ("compose", "config", "--format", "json"):
            return json.dumps(self.config).encode()
        if args[:2] == ("image", "inspect"):
            return json.dumps([self.inspections[args[2]]]).encode()
        if args[0] == "run" and args[-1] == "/qdrant/qdrant.spdx.json":
            return self.sbom
        raise AssertionError(f"unmocked Docker call: {args}")

    def container_files(self, image: str, directory: str) -> dict[str, bytes]:
        return self.contents[image, directory]


@pytest.fixture
def images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ImageFixture:
    config = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    config["name"] = "fixture"
    canonical = {name: (ROOT / name).read_bytes() for name in legal.NAMES}
    for name, raw in canonical.items():
        (tmp_path / name).write_bytes(raw)
    monkeypatch.chdir(tmp_path)
    redis_source = legal.REDIS_NOTICES
    redis_source.mkdir(parents=True)
    redis_files = {
        "LICENSE.txt": b"Synthetic Redis dual-license fixture, not upstream legal text\n",
        "NOTICE": b"Synthetic Redis attribution fixture\n",
    }
    for name, raw in redis_files.items():
        (redis_source / name).write_bytes(raw)
    (redis_source / "manifest.json").write_text(
        json.dumps(
            {
                "version": legal.REDIS_VERSION,
                "license": legal.REDIS_LICENSE,
                "files": {name: checksum(raw) for name, raw in redis_files.items()},
            }
        )
    )
    fixture = ImageFixture(config, {}, {})
    learned = {"LICENSE": b"synthetic learned-search notice"}
    archive = tar_bytes(learned)
    for service, definition in config["services"].items():
        definition["build"]["context"] = str(tmp_path)
        image = "sha256:" + checksum(service.encode())
        fixture.inspections[f"fixture-{service}"] = {
            "Id": image,
            "Config": {
                "Labels": None
                if service == "redis"
                else {"org.opencontainers.image.licenses": "Apache-2.0"},
                "Env": [f"REDIS_VERSION={legal.REDIS_VERSION}"] if service == "redis" else [],
            },
        }
        if service == "redis":
            fixture.contents[image, legal.REDIS_IMAGE_NOTICES] = redis_files
            continue
        files = {
            **canonical,
            "learned-search/manifest.json": json.dumps(
                {
                    "archive_sha256": checksum(archive),
                    "files": {name: checksum(raw) for name, raw in learned.items()},
                }
            ).encode(),
            "learned-search/notices.tar.gz": archive,
        }
        if service in {"web", "shopper"}:
            files.update(frontend_files(service))
        if service == "qdrant":
            notice = b"Synthetic Qdrant license fixture\n"
            files["qdrant/notices/qdrant@fixture/LICENSE"] = notice
            files["qdrant/manifest.json"] = json.dumps(
                {
                    "sbom_sha256": checksum(QDRANT_SBOM),
                    "packages": [
                        {
                            "name": "qdrant",
                            "version": "fixture",
                            "files": {"qdrant@fixture/LICENSE": checksum(notice)},
                        }
                    ],
                }
            ).encode()
        if service == "postgres":
            upstream = (ROOT / "security/third-party/postgresql-16.15/COPYRIGHT").read_bytes()
            source = Path("security/third-party/postgresql-16.15/COPYRIGHT")
            source.parent.mkdir(parents=True)
            source.write_bytes(upstream)
            fixture.contents[image, "/usr/share/doc/postgresql"] = {"COPYRIGHT": upstream}
        fixture.contents[image, "/usr/share/doc/open-commerce-agent"] = files
    monkeypatch.setattr(legal, "docker", fixture.docker)
    monkeypatch.setattr(legal, "container_files", fixture.container_files)
    return fixture


def test_all_eight_actual_compose_services_have_explicit_legal_policies(
    images: ImageFixture,
) -> None:
    records = legal.verify_images()
    assert (
        {row["service"] for row in records}
        == set(images.config["services"])
        == set(legal.IMAGE_DOCKERFILES)
    )
    assert len(records) == 8
    redis = next(row for row in records if row["service"] == "redis")
    assert redis["first_party_license"] is None
    assert redis["upstream_license"] == "RSAL-2.0 OR SSPL-1.0"
    assert set(redis["files"]) == {"LICENSE.txt", "NOTICE"}
    assert all(
        row["first_party_license"] == "Apache-2.0" for row in records if row["service"] != "redis"
    )


def test_qdrant_image_rejects_template_only_source_despite_matching_hashes(
    images: ImageFixture,
) -> None:
    image = images.inspections["fixture-qdrant"]["Id"]
    files = images.contents[image, "/usr/share/doc/open-commerce-agent"]
    name = "stumpalo@1.0.0/BSD-3-Clause-standard-template.txt"
    template = b"Copyright (c) <year> <owner>\n"
    files[f"qdrant/notices/{name}"] = template
    manifest = json.loads(files["qdrant/manifest.json"])
    manifest["packages"] += [
        {"name": "stumpalo", "version": "1.0.0", "files": {name: checksum(template)}}
    ]
    sbom = json.loads(images.sbom)
    sbom["packages"].append({"name": "stumpalo", "versionInfo": "1.0.0"})
    images.sbom = json.dumps(sbom).encode()
    manifest["sbom_sha256"] = checksum(images.sbom)
    files["qdrant/manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="stumpalo@1.0.0"):
        legal.verify_images()


def test_qdrant_image_cannot_drop_a_package_from_the_actual_inventory(images: ImageFixture) -> None:
    image = images.inspections["fixture-qdrant"]["Id"]
    files = images.contents[image, "/usr/share/doc/open-commerce-agent"]
    sbom = json.loads(images.sbom)
    sbom["packages"].append({"name": "stumpalo", "versionInfo": "1.0.0"})
    images.sbom = json.dumps(sbom).encode()
    manifest = json.loads(files["qdrant/manifest.json"])
    manifest["sbom_sha256"] = checksum(images.sbom)
    files["qdrant/manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="coverage differs"):
        legal.verify_images()


@pytest.mark.parametrize("app", ["web", "shopper"])
@pytest.mark.parametrize("remove_files", [False, True])
def test_frontend_cannot_skip_native_attribution_by_dropping_outer_entry(
    app: str, remove_files: bool
) -> None:
    files = frontend_files(app)
    manifest = json.loads(files[f"{app}/manifest.json"])
    manifest["packages"] = [p for p in manifest["packages"] if p["name"] == "next"]
    files[f"{app}/manifest.json"] = json.dumps(manifest).encode()
    if remove_files:
        files = {n: b for n, b in files.items() if "@img/sharp-libvips-" not in n}
    with pytest.raises(ValueError, match="required Linux native attribution"):
        legal.verify_frontend_notices(app, files)


@pytest.mark.parametrize("service", sorted(legal.IMAGE_DOCKERFILES))
def test_missing_service_never_silently_skips_verification(
    images: ImageFixture, service: str
) -> None:
    del images.config["services"][service]
    with pytest.raises(ValueError, match="eight"):
        legal.verify_images()
    assert len(images.calls) == 1


@pytest.mark.parametrize(
    "problem",
    [
        "unknown-service",
        "image-only",
        "wrong-dockerfile",
        "wrong-context",
        "missing-context",
        "unknown-image",
    ],
)
def test_unreviewed_images_are_rejected_before_inspection(
    images: ImageFixture, problem: str
) -> None:
    if problem == "unknown-service":
        images.config["services"]["unexpected"] = {"image": "example.invalid/image"}
    elif problem == "image-only":
        images.config["services"]["redis"] = {"image": "example.invalid/redis"}
    elif problem == "wrong-dockerfile":
        images.config["services"]["shopper"]["build"]["dockerfile"] = "apps/web/Dockerfile"
    elif problem == "wrong-context":
        images.config["services"]["api"]["build"]["context"] = "/elsewhere"
    elif problem == "missing-context":
        del images.config["services"]["api"]["build"]["context"]
    else:
        images.config["services"]["api"]["image"] = "example.invalid/unreviewed"
    with pytest.raises(ValueError):
        legal.verify_images()
    assert len(images.calls) == 1


def test_inspected_images_need_exact_ids(images: ImageFixture) -> None:
    images.inspections["fixture-api"]["Id"] = "unidentified"
    with pytest.raises(ValueError, match="image identity"):
        legal.verify_images()


@pytest.mark.parametrize("service", ["web", "shopper"])
@pytest.mark.parametrize(
    "problem", ["missing", "tampered", "empty", "missing-next", "empty-records", "native"]
)
def test_both_frontends_require_real_notice_bytes(
    images: ImageFixture, service: str, problem: str
) -> None:
    image = images.inspections[f"fixture-{service}"]["Id"]
    files = images.contents[image, "/usr/share/doc/open-commerce-agent"]
    notice = f"{service}/third-party/next@15.5.27/license.md"
    if problem == "missing":
        del files[notice]
    elif problem in {"tampered", "empty"}:
        files[notice] = b"changed" if problem == "tampered" else b""
    elif problem == "native":
        files[
            f"{service}/third-party/@img/sharp-libvips-linux-arm64@1.3.4/native-notices.tar.gz"
        ] = b"changed"
    else:
        manifest = json.loads(files[f"{service}/manifest.json"])
        if problem == "missing-next":
            manifest["packages"] = manifest["packages"][1:]
        else:
            manifest["packages"][0]["files"] = []
        files[f"{service}/manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError):
        legal.verify_images()


@pytest.mark.parametrize(
    "problem", ["collection", "license", "empty", "tampered", "version", "manifest"]
)
def test_redis_requires_upstream_text_not_an_apache_label(
    images: ImageFixture, problem: str
) -> None:
    info = images.inspections["fixture-redis"]
    info["Config"]["Labels"] = {"org.opencontainers.image.licenses": "Apache-2.0"}
    files = images.contents[info["Id"], legal.REDIS_IMAGE_NOTICES]
    if problem == "collection":
        (legal.REDIS_NOTICES / "manifest.json").unlink()
    elif problem == "license":
        del files["LICENSE.txt"]
    elif problem in {"empty", "tampered"}:
        files["LICENSE.txt"] = b"" if problem == "empty" else b"changed"
    elif problem == "version":
        info["Config"]["Env"] = ["REDIS_VERSION=unknown"]
    else:
        manifest = json.loads((legal.REDIS_NOTICES / "manifest.json").read_bytes())
        manifest["license"] = "Apache-2.0"
        (legal.REDIS_NOTICES / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="redis"):
        legal.verify_images()


@pytest.fixture
def packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    canonical = {name: (ROOT / name).read_bytes() for name in legal.NAMES}
    for name, raw in canonical.items():
        (tmp_path / name).write_bytes(raw)
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "packages"
    directory.mkdir()
    metadata = b"Name: open-commerce-backend\nLicense: Apache-2.0\n"
    with zipfile.ZipFile(directory / "backend.whl", "w") as archive:
        archive.writestr("backend.dist-info/METADATA", metadata)
        for name, raw in canonical.items():
            archive.writestr(f"backend.dist-info/{name}", raw)
    (directory / "backend.tar.gz").write_bytes(
        tar_bytes(
            {
                "backend/PKG-INFO": metadata,
                **{f"backend/{name}": raw for name, raw in canonical.items()},
            }
        )
    )
    for package in ("web", "shopper", "sdk-typescript"):
        (directory / f"{package}.tgz").write_bytes(
            tar_bytes(
                {
                    "package/package.json": json.dumps(
                        {"name": f"@open-commerce/{package}", "license": "Apache-2.0"}
                    ).encode(),
                    **{f"package/{name}": raw for name, raw in canonical.items()},
                }
            )
        )
    return directory


def test_five_package_archives_include_shopper(packages: Path) -> None:
    assert {record["package"] for record in legal.verify_packages(packages)} == {
        "open-commerce-backend",
        "@open-commerce/sdk-typescript",
        "@open-commerce/web",
        "@open-commerce/shopper",
    }


def test_workflow_builds_shopper_archive_before_verification() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/qualification.yml").read_text())
    step = next(
        step
        for step in workflow["jobs"]["verify"]["steps"]
        if step.get("name") == "Verify legal files in local package archives"
    )
    command = step["run"]
    shopper = (
        '--dir apps/shopper pack --pack-destination "$PWD/.opencommerce/distribution-artifacts"'
    )
    assert command.index(shopper) < command.index("scripts/verify_release_legal.py --artifacts")


@pytest.mark.parametrize("problem", ["missing", "wrong-name", "missing-notice", "changed-license"])
def test_shopper_archive_is_mandatory_and_checked(packages: Path, problem: str) -> None:
    path = packages / "shopper.tgz"
    if problem == "missing":
        path.unlink()
    else:
        files = legal.tar_contents(path.read_bytes())
        if problem == "wrong-name":
            files["package/package.json"] = b'{"name":"@open-commerce/web","license":"Apache-2.0"}'
        elif problem == "missing-notice":
            del files["package/NOTICE"]
        else:
            files["package/LICENSE"] = b"changed"
        path.write_bytes(tar_bytes(files))
    with pytest.raises(ValueError):
        legal.verify_packages(packages)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_legal_tar_rejects_nonregular_members(kind: bytes) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member = tarfile.TarInfo("LICENSE")
        member.type = kind
        member.linkname = "elsewhere"
        archive.addfile(member)
    with pytest.raises(ValueError, match="nonregular"):
        legal.tar_contents(buffer.getvalue())


def test_legal_tar_expansion_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(legal, "MAX_LEGAL_BYTES", 10)
    with pytest.raises(ValueError, match="byte limit"):
        legal.tar_contents(tar_bytes({"LICENSE": b"x" * 11}))


@pytest.mark.parametrize("plugin_available", [True, False])
def test_compose_fallback_preserves_explicit_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, plugin_available: bool
) -> None:
    scope = {
        "DOCKER_CONTEXT": "colima-opencommerce-release",
        "COMPOSE_PROJECT_NAME": "opencommerce-cloud-reviewed-20261017",
        "COMPOSE_FILE": str(tmp_path / "docker-compose.yml"),
    }
    for key, value in scope.items():
        monkeypatch.setenv(key, value)
    calls = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert command in (["docker", "compose", "version"], ["docker-compose", "version"])
        assert all(kwargs["env"][key] == value for key, value in scope.items())
        failed = command == ["docker", "compose", "version"] and not plugin_available
        return subprocess.CompletedProcess(command, int(failed), "version", "")

    arguments = ["--env-file", str(tmp_path / "isolated.env"), "config", "--format", "json"]
    expected = ["docker", "compose"] if plugin_available else ["docker-compose"]

    def check_output(command: list[str], **kwargs: Any) -> bytes:
        calls.append(command)
        assert command == [*expected, *arguments]
        assert all(kwargs["env"][key] == value for key, value in scope.items())
        return b'{"services": {}}'

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "check_output", check_output)
    assert legal.docker("compose", *arguments) == b'{"services": {}}'
    assert calls == [
        ["docker", "compose", "version"],
        *([] if plugin_available else [["docker-compose", "version"]]),
        [*expected, *arguments],
    ]


def test_image_cli_forwards_selected_env_file_and_keeps_eight_image_gate(
    images: ImageFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / "isolated.env"
    expected = ("compose", "--env-file", str(env_file), "config", "--format", "json")
    calls = []

    def docker(*args: str) -> bytes:
        calls.append(args)
        if args[0] == "compose":
            assert args == expected
            return images.docker("compose", "config", "--format", "json")
        return images.docker(*args)

    monkeypatch.setattr(legal, "docker", docker)
    output = tmp_path / "legal.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_release_legal.py",
            "--images",
            "--env-file",
            str(env_file),
            "--output",
            str(output),
        ],
    )
    legal.main()
    report = json.loads(output.read_bytes())
    assert report["complete"]
    assert {row["service"] for row in report["images"]} == set(legal.IMAGE_DOCKERFILES)
    assert calls[0] == expected
    assert all(call[0] != "compose" for call in calls[1:])
