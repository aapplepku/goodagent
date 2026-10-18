"""Inventory coverage must not be mistaken for complete dependency attribution."""

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import collect_qdrant_legal as qdrant
from scripts import collect_web_native_legal as native
from scripts import dependency_attribution as attribution
from scripts import verify_release_legal as legal
from scripts.dependency_attribution import attribution_gaps, require_attribution
from scripts.verify_release_legal import audit_source_notices, verify_frontend_notices

from tests.contract.test_release_legal_verifier import frontend_files, tar_bytes

ROOT = Path(__file__).resolve().parents[2]
# Deliberately synthetic fixtures, never a substitute for upstream legal evidence.
MIT = (
    b"Copyright (c) 2026 Synthetic Fixture Authors\n"
    b"Permission is hereby granted ...\nTHE SOFTWARE IS PROVIDED ...\n"
)
TEMPLATE = MIT.replace(b"2026 Synthetic Fixture Authors", b"<year> <copyright holders>")


def package(name: str = "block", version: str = "0.1.6") -> dict[str, Any]:
    return {"name": name, "version": version, "files": {}, "license_selection": None}


def attach(record: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    record["files"] = {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}
    return record


@pytest.mark.parametrize(
    "identity",
    [("block", "0.1.6"), ("objc-foundation", "0.1.1"), ("objc_id", "0.1.1"), ("stumpalo", "1.0.0")],
)
def test_known_omission_cannot_hide_by_removing_template_or_selection(
    identity: tuple[str, str],
) -> None:
    record = package(*identity)
    prefix = f"{identity[0]}@{identity[1]}"
    files = {f"{prefix}/Cargo.toml": b'authors = ["Some Author"]\nlicense = "MIT"\n'}
    with pytest.raises(ValueError, match="Missing upstream attribution"):
        require_attribution([attach(record, files)], files)


@pytest.mark.parametrize(
    "notice",
    [
        TEMPLATE,
        TEMPLATE.replace(b"<year> <copyright holders>", b"2026 <owner>"),
        b"Copyright 2026 Somebody\n",
        b"Permission is hereby granted\nTHE SOFTWARE IS PROVIDED\n",
    ],
)
def test_renamed_template_or_incomplete_notice_does_not_resolve_gap(notice: bytes) -> None:
    files = {"block@0.1.6/LICENSE": notice}
    assert attribution_gaps([attach(package(), files)], files)


def test_notice_for_another_package_does_not_cover_omission() -> None:
    files = {"other@1/LICENSE": MIT}
    assert attribution_gaps([attach(package(), files)], files)


def test_new_template_only_fallback_is_blocked() -> None:
    files = {"new-crate@1/MIT-standard-template.txt": TEMPLATE}
    with pytest.raises(ValueError, match="new-crate@1"):
        require_attribution([attach(package("new-crate", "1"), files)], files)


def test_unreviewed_notice_text_cannot_resolve_a_gap() -> None:
    files = {
        "block@0.1.6/MIT-standard-template.txt": TEMPLATE,
        "block@0.1.6/upstream-notices/LICENSE": MIT,
    }
    assert attribution_gaps([attach(package(), files)], files)


def test_cargo_authors_and_source_are_not_an_original_notice() -> None:
    files = {
        "block@0.1.6/src/lib.rs": MIT,
        "block@0.1.6/Cargo.toml": b'authors = ["Synthetic Fixture Authors"]',
    }
    assert attribution_gaps([attach(package(), files)], files)


def test_bsd_fallback_requires_its_own_clauses() -> None:
    record = package("stumpalo", "1.0.0")
    files = {"stumpalo@1.0.0/LICENSE": MIT}
    assert attribution_gaps([attach(record, files)], files)
    files["stumpalo@1.0.0/LICENSE"] = (
        b"Copyright (c) 2026 Synthetic Fixture Authors\n"
        b"Redistribution and use in source and binary forms ...\n"
        b"Neither the name ...\nTHIS SOFTWARE IS PROVIDED ...\n"
    )
    assert attribution.original_notice_candidate(files["stumpalo@1.0.0/LICENSE"], "BSD-3-Clause")
    assert attribution_gaps([attach(record, files)], files)


@pytest.mark.parametrize(
    "change", [None, "notice", "source", "crate", "path", "identity", "removed-review"]
)
def test_resolution_requires_exact_reviewed_provenance(
    monkeypatch: pytest.MonkeyPatch, change: str | None
) -> None:
    path = "block@0.1.6/upstream-notices/LICENSE"
    files = {path: MIT}
    evidence = {
        "license": "MIT",
        "path": path,
        "sha256": hashlib.sha256(MIT).hexdigest(),
        "source_url": "https://example.invalid/upstream/revision",
        "source_sha256": "a" * 64,
        "crate_sha256": "b" * 64,
    }
    monkeypatch.setattr(attribution, "REVIEWED_NOTICES", {("block", "0.1.6"): evidence})
    record = attach(package(), files)
    record["sources"] = [
        {"url": evidence["source_url"], "sha256": evidence["source_sha256"]},
        {
            "url": "https://static.crates.io/crates/block/block-0.1.6.crate",
            "sha256": evidence["crate_sha256"],
        },
    ]
    if change == "notice":
        files[path] += b"changed"
        attach(record, files)  # Updated manifest alone cannot approve different bytes.
    elif change == "source":
        record["sources"][0]["url"] += "changed"
    elif change == "crate":
        record["sources"][1]["sha256"] = "c" * 64
    elif change == "path":
        files[path + ".txt"] = files.pop(path)
        attach(record, files)
    elif change == "identity":
        record["version"] = "1.0"
        files["block@1.0/MIT-standard-template.txt"] = TEMPLATE
        attach(record, files)
    elif change == "removed-review":
        monkeypatch.setattr(attribution, "REVIEWED_NOTICES", {})
    assert bool(attribution_gaps([record], files)) == (change is not None)


@pytest.mark.parametrize(
    "template", ["GPL-standard-template.txt", "BSD-3-Clause-standard-template.txt"]
)
def test_unknown_or_conflicting_template_license_requires_review(template: str) -> None:
    files = {f"block@0.1.6/{template}": TEMPLATE}
    with pytest.raises(ValueError, match="attribution"):
        attribution_gaps([attach(package(), files)], files)


def test_source_audit_binds_exact_preserved_evidence_and_reports_all_omissions() -> None:
    report = audit_source_notices(ROOT)
    assert report["archive_integrity_verified"]
    assert not report["complete"] and not report["attribution_complete"]
    assert report["unique_blocked_packages"] == [
        "block@0.1.6",
        "objc-foundation@0.1.1",
        "objc_id@0.1.1",
        "stumpalo@1.0.0",
    ]
    assert report["blocked_occurrences"] == 7
    for collection in report["collections"]:
        assert len(collection["archive_sha256"]) == len(collection["manifest_sha256"]) == 64
        assert collection["packages"] > 0 and collection["files"] > 0
        assert all(g["decision"] == "blocked" and g["sources"] for g in collection["gaps"])


def test_dependency_runtime_attribution_release_gate() -> None:
    report = audit_source_notices(ROOT)
    assert report["attribution_complete"], (
        "Dependency runtime/image redistribution remains blocked by missing original notices: "
        + ", ".join(report["unique_blocked_packages"])
    )


@pytest.mark.parametrize(
    "corruption",
    ["archive-hash", "file-hash", "extra-file", "duplicate-package", "removed-package"],
)
def test_audit_rejects_changed_or_incomplete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    folder = tmp_path / "fixture"
    folder.mkdir()
    contents = {"block@0.1.6/LICENSE": MIT}
    record = attach(package(), contents)
    raw = tar_bytes(contents)
    sbom = json.dumps({"packages": [{"name": "block", "versionInfo": "0.1.6"}]}).encode()
    manifest = {
        "packages": [record],
        "bundle_sha256": hashlib.sha256(raw).hexdigest(),
        "sbom_sha256": hashlib.sha256(sbom).hexdigest(),
    }
    if corruption == "archive-hash":
        manifest["bundle_sha256"] = "0" * 64
    elif corruption == "file-hash":
        record["files"]["block@0.1.6/LICENSE"] = "0" * 64
    elif corruption == "extra-file":
        raw = tar_bytes({**contents, "unreviewed/LICENSE": MIT})
        manifest["bundle_sha256"] = hashlib.sha256(raw).hexdigest()
    elif corruption == "duplicate-package":
        manifest["packages"] = [record, record]
    else:
        # Self-consistent archive/manifest hashes still cannot drop an inventory member.
        contents = {"other@1/LICENSE": MIT}
        manifest["packages"] = [attach(package("other", "1"), contents)]
        raw = tar_bytes(contents)
        manifest["bundle_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    (folder / "notices.tar.gz").write_bytes(raw)
    (folder / "upstream.spdx.json.gz").write_bytes(gzip.compress(sbom))
    monkeypatch.setattr(
        legal, "SOURCE_COLLECTIONS", {"fixture": ("manifest.json", "notices.tar.gz")}
    )
    with pytest.raises(ValueError):
        audit_source_notices(tmp_path)


def test_offline_cli_retains_blocked_report_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/verify_release_legal.py"),
        "--source-notices",
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 1 and "4 blocked packages" in result.stdout
    before = output.read_bytes()
    assert not json.loads(before)["complete"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode != 0 and output.read_bytes() == before


def test_native_collector_refuses_success_for_template_only_crate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tar_bytes(
        {
            "block-0.1.6/Cargo.toml": (
                b'[package]\nname="block"\nversion="0.1.6"\nlicense="MIT"\n'
                b'authors=["Synthetic Fixture Authors"]\n'
            )
        }
    )
    monkeypatch.setattr(
        native, "download", lambda url: TEMPLATE if url.endswith(".txt") else source
    )
    with pytest.raises(ValueError, match="block@0.1.6"):
        native.collect_locked_crate({"name": "block", "versionInfo": "0.1.6"})


def test_qdrant_collector_refuses_success_for_template_only_crate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tar_bytes(
        {
            "stumpalo-1.0.0/Cargo.toml": b'[package]\nname="stumpalo"\nversion="1.0.0"\nlicense="BSD-3-Clause"\nrepository="https://codeberg.org/fixture/stumpalo"\n',
            "stumpalo-1.0.0/.cargo_vcs_info.json": json.dumps({"git": {"sha1": "a" * 40}}).encode(),
        }
    )
    monkeypatch.setattr(
        qdrant, "download", lambda url: TEMPLATE if url.endswith(".txt") else source
    )
    with pytest.raises(ValueError, match="stumpalo@1.0.0"):
        qdrant.collect_package(
            {
                "name": "stumpalo",
                "versionInfo": "1.0.0",
                "downloadLocation": "registry+https://github.com/rust-lang/crates.io-index",
            }
        )


@pytest.mark.parametrize("app", ["web", "shopper"])
@pytest.mark.parametrize("omit", [False, True])
def test_actual_frontend_notice_check_rejects_template_only_even_with_correct_hashes(
    app: str,
    omit: bool,
) -> None:
    files = frontend_files(app)
    prefix = f"{app}/third-party/@img/sharp-libvips-linux-arm64@1.3.4/"
    contents = legal.tar_contents(files[prefix + "native-notices.tar.gz"])
    contents["vips@fixture/Cargo.lock"] = (
        b'version = 3\n[[package]]\nname = "block"\nversion = "0.1.6"\n'
        b'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
    )
    manifest = json.loads(files[prefix + "native-manifest.json"])
    manifest["packages"] = [attach(package("vips", "fixture"), contents)]
    if not omit:
        extra = {"block@0.1.6/MIT-standard-template.txt": TEMPLATE}
        contents.update(extra)
        manifest["packages"].append(attach(package(), extra))
    raw = tar_bytes(contents)
    manifest["bundle_sha256"] = hashlib.sha256(raw).hexdigest()
    files[prefix + "native-manifest.json"] = json.dumps(manifest).encode()
    files[prefix + "native-notices.tar.gz"] = raw
    top = json.loads(files[f"{app}/manifest.json"])
    for p in top["packages"]:
        for entry in p["files"]:
            location = f"{app}/third-party/{p['name']}@{p['version']}/{entry['path']}"
            entry["sha256"] = hashlib.sha256(files[location]).hexdigest()
    files[f"{app}/manifest.json"] = json.dumps(top).encode()
    with pytest.raises(ValueError, match="coverage differs" if omit else "block@0.1.6"):
        verify_frontend_notices(app, files)
