"""Owner legal decisions and redistributed attribution cannot silently drift."""

import gzip
import hashlib
import io
import json
import re
import runpy
import tarfile
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

APACHE_SHA = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
DCO_SHA = "f7ac75b443f4ca16b503241344b41aeff9503b0c30bedc2b119551d83cb0fa90"
NOTICE = (
    b"Open Commerce Agent\nCopyright 2026 Han Chen\n\n"
    b"This product includes software developed by Han Chen and contributors.\n"
)
STUMPALO_EXCEPTION = "Verified SHA-256 of the preserved stumpalo allocator source, not a credential"
TOKENIZER_EXCEPTION = "Verified public pinned MiniLM tokenizer SHA-256, not an access token"
VERIFIER_EXCEPTION = (
    "Verified MiniLM tokenizer file checksum in the exact offline runtime verifier field"
)
IDEMPOTENCY_EXCEPTION = "Two reproducible synthetic action idempotency hashes, not credentials"
ARCHIVE_EXCEPTION = (
    "Verified archive SHA-256 values in the public retention manifest, not credentials"
)
IMAGE_EXCEPTION = (
    "Published Python release-signing fingerprint in exact Python image metadata fields"
)


def secret_scan_exception(description: str) -> dict[str, Any]:
    config = tomllib.loads(Path(".gitleaks.toml").read_text())
    assert config["extend"] == {"useDefault": True}
    assert len(config["rules"]) == 1 and "allowlists" not in config
    rule = config["rules"][0]
    assert rule["id"] == "generic-api-key"
    allowances = rule["allowlists"]
    assert len(allowances) == 6
    assert {row["description"] for row in allowances} == {
        STUMPALO_EXCEPTION,
        TOKENIZER_EXCEPTION,
        VERIFIER_EXCEPTION,
        IDEMPOTENCY_EXCEPTION,
        ARCHIVE_EXCEPTION,
        IMAGE_EXCEPTION,
    }
    return cast(
        dict[str, Any], next(row for row in allowances if row["description"] == description)
    )


def test_canonical_legal_texts_and_exact_owner_notice() -> None:
    assert hashlib.sha256(Path("LICENSE").read_bytes()).hexdigest() == APACHE_SHA
    assert hashlib.sha256(Path("DCO.md").read_bytes()).hexdigest() == DCO_SHA
    assert Path("NOTICE").read_bytes() == NOTICE


@pytest.mark.parametrize(
    "package", ["packages/backend", "packages/sdk-typescript", "apps/web", "apps/shopper"]
)
def test_package_legal_files_are_exact_canonical_copies(package: str) -> None:
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        assert (Path(package) / name).read_bytes() == Path(name).read_bytes()


def test_first_party_package_and_openapi_license_metadata() -> None:
    for name in ("pyproject.toml", "packages/backend/pyproject.toml"):
        metadata = tomllib.loads(Path(name).read_text())
        assert metadata["project"]["license"] == {"text": "Apache-2.0"}
    for name in (
        "package.json",
        "apps/web/package.json",
        "apps/shopper/package.json",
        "packages/sdk-typescript/package.json",
    ):
        assert json.loads(Path(name).read_text())["license"] == "Apache-2.0"
    assert json.loads(Path("openapi/openapi.json").read_text())["info"]["license"] == {
        "name": "Apache-2.0",
        "identifier": "Apache-2.0",
    }


def test_qdrant_notices_cover_complete_recorded_inventory_with_unchanged_hashes() -> None:
    root = Path("security/third-party/qdrant-1.19.1")
    manifest = json.loads((root / "manifest.json").read_bytes())
    sbom_raw = gzip.decompress((root / "upstream.spdx.json.gz").read_bytes())
    assert hashlib.sha256(sbom_raw).hexdigest() == manifest["sbom_sha256"]
    sbom = json.loads(sbom_raw)
    assert manifest["complete"]
    expected = {(p["name"], p["versionInfo"]) for p in sbom["packages"]}
    assert {(p["name"], p["version"]) for p in manifest["packages"]} == expected
    assert len(expected) == 782
    data = (root / "notices.tar.gz").read_bytes()
    assert hashlib.sha256(data).hexdigest() == manifest["bundle_sha256"]
    expected_files = {k: v for p in manifest["packages"] for k, v in p["files"].items()}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        actual = set()
        for member in archive:
            assert member.isfile() and member.mtime == 0
            assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            actual.add(member.name)
            stream = archive.extractfile(member)
            assert stream is not None
            assert hashlib.sha256(stream.read()).hexdigest() == expected_files[member.name]
    assert actual == set(expected_files)


def test_notice_source_archive_cannot_traverse_or_execute_links() -> None:
    archive_files = runpy.run_path("scripts/collect_qdrant_legal.py")["archive_files"]
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        member = tarfile.TarInfo("source/../../LICENSE")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"evil"))
    with pytest.raises(ValueError, match="unsafe source"):
        archive_files(data.getvalue())


def test_private_security_channel_and_contribution_decisions_are_explicit() -> None:
    security = Path("SECURITY.md").read_text()
    assert "hc414t@gmail.com" in security and "[Open Commerce Agent Security]" in security
    assert "non-admin account" in security and "security-alert notifications" in security
    assert "Only the most recent released minor version" in security
    contribution = Path("CONTRIBUTING.md").read_text()
    assert "git commit -s" in contribution and "does not transfer" in contribution
    assert "There is no CLA" in contribution and "required status check" in contribution


def test_secret_scan_exception_is_one_verified_checksum_in_one_manifest() -> None:
    allow = secret_scan_exception(STUMPALO_EXCEPTION)
    assert allow["condition"] == "AND" and allow["regexTarget"] == "secret"
    assert len(allow["regexes"]) == len(allow["paths"]) == 1
    root = Path("security/third-party/qdrant-1.19.1")
    manifest = json.loads((root / "manifest.json").read_bytes())
    with tarfile.open(root / "notices.tar.gz", "r:gz") as archive:
        name = "stumpalo@1.0.0/src/arena/allocator_api.rs"
        if "source_distribution" in manifest:
            from scripts.source_only_notices import verify_public_collections

            verify_public_collections(Path.cwd())
            assert name not in archive.getnames()
            package = next(p for p in manifest["packages"] if p["name"] == "stumpalo")
            checksum = package["excluded_files"][name]
        else:
            stream = archive.extractfile(name)
            assert stream is not None
            checksum = hashlib.sha256(stream.read()).hexdigest()
    assert re.fullmatch(allow["regexes"][0], checksum)
    assert not re.fullmatch(allow["regexes"][0], checksum[:-1] + "0")
    assert re.search(allow["paths"][0], str(root / "manifest.json"))
    for other in ("secrets.json", str(root / "different.json"), str(root / "manifest.json.bak")):
        assert not re.search(allow["paths"][0], other)


def test_tokenizer_checksum_exception_is_exact_and_scoped() -> None:
    allow = secret_scan_exception(TOKENIZER_EXCEPTION)
    assert allow["condition"] == "AND" and allow["regexTarget"] == "secret"
    checksum = "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037"
    assert re.fullmatch(allow["regexes"][0], checksum)
    assert not re.fullmatch(allow["regexes"][0], checksum[:-1] + "0")
    for name in ("development", "held-out", "post-fix-regression"):
        path = Path(f"examples/eval/search-merchandising-v1/{name}.json")
        assert json.loads(path.read_text())["model_files"]["tokenizer.json"] == checksum
        assert re.search(allow["paths"][0], str(path))
        assert not re.search(allow["paths"][0], str(path) + ".bak")
    assert not re.search(allow["paths"][0], "secrets.json")


def test_synthetic_idempotency_exceptions_are_content_derived_not_credentials() -> None:
    from datetime import timedelta

    from open_commerce.core.actions import CompiledAction, build_action_idempotency_key
    from open_commerce.core.enums import ActionType
    from open_commerce.core.types import TimeWindow

    allow = secret_scan_exception(IDEMPOTENCY_EXCEPTION)
    assert allow["condition"] == "AND" and allow["regexTarget"] == "secret"
    path = Path("examples/eval/merchandising-v1/summary.json")
    records = json.loads(path.read_text())["trajectory"]["actions"]
    assert len(records) == 2
    for record in records:
        action = CompiledAction.model_validate(record["action"])
        start = action.intent.proposed_at
        expected = build_action_idempotency_key(
            tenant_id=action.tenant_id,
            goal_id=action.goal_id,
            action_type=ActionType(action.intent.type),
            target_provider=action.target_provider,
            normalized_parameters=action.normalized_parameters,
            decision_window=TimeWindow(start_at=start, end_at=start + timedelta(days=7)),
        )
        assert action.idempotency_key == expected
        assert re.fullmatch(allow["regexes"][0], expected)
        assert not re.fullmatch(allow["regexes"][0], expected[:-1] + "0")
    assert re.search(allow["paths"][0], str(path))
    assert not re.search(allow["paths"][0], str(path) + ".bak")
    assert not re.search(allow["paths"][0], "secrets.json")


@pytest.mark.parametrize("version", ["1.3.3", "1.3.4"])
def test_web_native_notices_cover_libraries_and_locked_rust_packages(version: str) -> None:
    from scripts.collect_web_native_legal import SOURCES

    root = Path(f"security/third-party/sharp-libvips-{version}")
    manifest = json.loads((root / "native-manifest.json").read_bytes())
    assert manifest["complete"] and set(manifest["versions"]) == set(SOURCES)
    raw = (root / "native-notices.tar.gz").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["bundle_sha256"]
    expected = {k: v for p in manifest["packages"] for k, v in p["files"].items()}
    identities = {(p["name"], p["version"]) for p in manifest["packages"]}
    assert set(manifest["versions"].items()) <= identities
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive:
            assert member.isfile() and member.mtime == 0
            assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
            stream = archive.extractfile(member)
            assert stream is not None
            content = stream.read()
            actual[member.name] = hashlib.sha256(content).hexdigest()
            if Path(member.name).name == "Cargo.lock":
                for package in tomllib.loads(content.decode())["package"]:
                    if package.get("source"):
                        assert (package["name"], package["version"]) in identities
    assert actual == expected
    assert any("FTL.TXT" in name for name in actual)
    assert any("COPYING" in name and name.startswith("vips@") for name in actual)


def test_native_source_archive_rejects_unsafe_paths() -> None:
    from scripts.collect_web_native_legal import source_files

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        member = tarfile.TarInfo("../../LICENSE")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"test"))
    with pytest.raises(ValueError, match="unsafe native"):
        source_files(buffer.getvalue())
