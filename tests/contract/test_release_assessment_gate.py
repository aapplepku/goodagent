"""Synthetic current-artifact bundles only; never adopt private release assessments."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from scripts import check_release_assessments as gate

NOW = datetime.now(UTC).replace(microsecond=0)
START = NOW - timedelta(hours=1)
SOURCE_TIME = START - timedelta(days=1)
REVIEW = START + timedelta(minutes=5)
EXPIRES = NOW + timedelta(days=7)
REJECTED = (
    gate.GateError,
    ValidationError,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
)


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class Bundle:
    def __init__(self, root: Path, *, high: bool = True, fixed: str = "") -> None:
        self.root = root
        self.source = b"# frozen synthetic build payload\n"
        self.put("source/app.py", self.source)
        source_files = [
            {
                "path": "app.py",
                "source": "app.py",
                "bytes": len(self.source),
                "sha256": checksum(self.source),
                "mode": 0o644,
            }
        ]
        self.source_sha = checksum(encoded(source_files))
        snapshot = {
            "schema_version": 1,
            "created_at": SOURCE_TIME.isoformat(),
            "purpose": "test",
            "provenance": "synthetic",
            "files": source_files,
            "source_tree_sha256": self.source_sha,
        }
        source_ref = self.put("source/SOURCE_SNAPSHOT.json", snapshot)
        self.inventory: dict[str, Any] = {
            "complete": True,
            "started_at": START.isoformat(),
            "completed_at": (START + timedelta(minutes=2)).isoformat(),
            "images": [],
        }
        self.images: list[dict[str, Any]] = []
        self.scans: dict[str, dict[str, Any]] = {}
        self.sboms: dict[str, dict[str, Any]] = {}
        for service in sorted(gate.SERVICES):
            self.add_image(service, high=high and service == "api", fixed=fixed)
        self.manifest: dict[str, Any] = {
            "schema_version": 1,
            "hash_format": "trivy-full-finding-json-v1",
            "review_owner": "Synthetic fixture; no real approval",
            "review_method": "automated",
            "reviewed_at": REVIEW.isoformat(),
            "expires_at": EXPIRES.isoformat(),
            "source": {
                "manifest": source_ref,
                "directory": "source",
                "source_tree_sha256": self.source_sha,
            },
            "inventory": self.put("scans/inventory.json", self.inventory),
            "images": self.images,
            "assessments": [],
            "residual_policy": "retain-low-medium-unknown-without-approval",
            "limitations": ["Synthetic input does not establish human applicability judgment"],
        }
        self.proofs: dict[str, Any] = {"proofs": []}
        if high:
            self.add_assessment(fixed)

    def put(self, name: str, value: Any) -> dict[str, Any]:
        raw = value if isinstance(value, bytes) else encoded(value)
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        return {"path": name, "sha256": checksum(raw), "size": len(raw)}

    def add_image(self, service: str, *, high: bool, fixed: str) -> None:
        layers = ["sha256:" + "a" * 64]
        config = {
            "architecture": "arm64",
            "os": "linux",
            "rootfs": {"type": "layers", "diff_ids": layers},
            "config": {"Labels": {"fixture-service": service}},
        }
        config_ref = self.put(f"scans/{service}.image-config.json", config)
        cid = "sha256:" + config_ref["sha256"]
        iid = "sha256:" + checksum(("live-index-" + service).encode())
        inspection = {
            "Id": iid,
            "Architecture": "arm64",
            "Os": "linux",
            "RootFS": {"Type": "layers", "Layers": layers},
        }
        inspection_ref = self.put(f"scans/{service}.image-inspection.json", inspection)
        archive_member = "blobs/sha256/" + config_ref["sha256"]
        manifest_ref = self.put(
            f"scans/{service}.image-manifest.json",
            [
                {"Config": archive_member, "Layers": ["layers/one.tar"], "RepoTags": ["test:one"]},
            ],
        )
        finding = {
            "VulnerabilityID": "CVE-2099-0001",
            "PkgName": "synthetic-library",
            "PkgID": "synthetic-library@1.0",
            "InstalledVersion": "1.0",
            "Severity": "HIGH",
            "Description": "Original raw advisory",
            "Layer": {"DiffID": layers[0]},
            "Fingerprint": "unmodified-raw-fingerprint",
            "Status": "affected",
        }
        if fixed:
            finding["FixedVersion"] = fixed
        report = {
            "SchemaVersion": 2,
            "ArtifactType": "container_image",
            "Trivy": {"Version": "0.74.0"},
            "ArtifactID": cid,
            "ArtifactName": f"/scans/{service}.tar",
            "CreatedAt": (START + timedelta(seconds=5)).isoformat(),
            "Metadata": {
                "ImageID": cid,
                "ImageConfig": config,
                "DiffIDs": layers,
                "OS": {"Family": "debian", "Name": "13.7"},
            },
            "Results": [
                {
                    "Target": f"/scans/{service}.tar (debian 13.7)",
                    "Class": "os-pkgs",
                    "Type": "debian",
                    "Vulnerabilities": [finding] if high else [],
                }
            ],
        }
        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "components": [{"name": "synthetic-library", "type": "library"}],
            "metadata": {
                "timestamp": (START + timedelta(seconds=6)).isoformat(),
                "tools": {"components": [{"name": "trivy", "version": "0.74.0"}]},
                "component": {
                    "type": "container",
                    "properties": [{"name": "aquasecurity:trivy:ImageID", "value": cid}],
                },
            },
        }
        scan_ref = self.put(f"scans/{service}.scan.json", report)
        sbom_ref = self.put(f"scans/{service}.cdx.json", sbom)
        self.scans[service], self.sboms[service] = report, sbom
        item = {
            "service": service,
            "reference": "synthetic:" + service,
            "image_id": iid,
            "image_config_id": cid,
            "identity_inputs": {
                name: {
                    "file": Path(ref["path"]).name,
                    "sha256": ref["sha256"],
                    **({"archive_member": archive_member} if name == "config" else {}),
                }
                for name, ref in (
                    ("config", config_ref),
                    ("inspection", inspection_ref),
                    ("manifest", manifest_ref),
                )
            },
            "identity_match_fields": ["Architecture", "Os", "RootFS"],
            "repo_digests": [],
            "architecture": "arm64",
            "user": "10001",
            "scanner": gate.SCANNER,
            "scan": Path(scan_ref["path"]).name,
            "sbom": Path(sbom_ref["path"]).name,
            "complete": True,
            "scan_sha256": scan_ref["sha256"],
            "sbom_sha256": sbom_ref["sha256"],
            "counts": {"HIGH": 1} if high else {},
            "fix_available_count": int(high and bool(fixed)),
            "untriaged_high_critical_count": int(high),
        }
        self.inventory["images"].append(item)
        self.images.append(
            {
                "service": service,
                "scan": scan_ref,
                "sbom": sbom_ref,
                "config": config_ref,
                "inspection": inspection_ref,
                "manifest": manifest_ref,
            }
        )

    def add_assessment(self, fixed: str) -> None:
        item = self.inventory["images"][0]
        scan = self.scans["api"]
        finding = scan["Results"][0]["Vulnerabilities"][0]
        identity = {
            "service": "api",
            "image_id": item["image_id"],
            "image_config_id": item["image_config_id"],
            "platform": {"os": "linux", "architecture": "arm64"},
            "scanner_image": gate.SCANNER,
            "scanner_version": "0.74.0",
            "source_tree_sha256": self.source_sha,
            "raw_scan_sha256": item["scan_sha256"],
            "sbom_sha256": item["sbom_sha256"],
            "artifact": scan["ArtifactName"],
            "result_index": 0,
            "finding_index": 0,
            "target": scan["Results"][0]["Target"],
            "result_class": "os-pkgs",
            "result_type": "debian",
            "package": finding["PkgName"],
            "package_id": finding["PkgID"],
            "package_path": None,
            "installed_version": "1.0",
            "vulnerability_id": finding["VulnerabilityID"],
            "original_severity": finding["Severity"],
            "finding_sha256": gate.finding_digest(finding),
        }
        scope = {
            "membership": "shipped-runtime",
            "boundaries": "Exact image and selected call boundary",
            "exclusions": ["Other images and arbitrary injected code"],
        }
        observations = []
        for purpose in sorted(gate.QUESTIONS):
            observation = self.put(
                f"observations/{purpose}.json", {"observed": {"synthetic": purpose}}
            )
            observations.append({"file": observation, "pointer": "/observed"})
            self.proofs["proofs"].append(
                {
                    "schema_version": 1,
                    "identity": copy.deepcopy(identity),
                    "scope": copy.deepcopy(scope),
                    "purpose": purpose,
                    "observed_at": (START + timedelta(minutes=3)).isoformat(),
                    "coverage": "complete-for-question",
                    "conclusion": "Synthetic scoped observation",
                    "missing_inputs": [],
                    "limitations": ["Fixture only"],
                    "observations": [observations[-1]],
                }
            )
        proof_ref = self.put("proofs.json", self.proofs)
        record = {
            "identity": identity,
            "scope": scope,
            "decision": "not-applicable",
            "review_owner": "Synthetic reviewer",
            "review_method": "automated",
            "reviewed_at": REVIEW.isoformat(),
            "expires_at": EXPIRES.isoformat(),
            "rationale": "Affected component absent at the reviewed boundary",
            "reachability": "No identified affected call in the selected fixture",
            "exposure": "Synthetic, exact-image scope only",
            "fix": {
                "scanner_fix_available": bool(fixed),
                "scanner_fixed_version": fixed or None,
                "upstream_availability": "unknown",
                "upstream_fixed_versions": [],
                "rationale": "Raw scanner metadata retained",
            },
            "missing_inputs": [],
            "limitations": ["Not whole-program proof"],
            "evidence": [
                {
                    "file": copy.deepcopy(proof_ref),
                    "pointer": f"/proofs/{i}",
                    "purpose": p["purpose"],
                }
                for i, p in enumerate(self.proofs["proofs"])
            ],
        }
        self.manifest["assessments"].append(record)

    @property
    def record(self) -> dict[str, Any]:
        return cast_record(self.manifest["assessments"][0])

    def update_proofs(self) -> None:
        ref = self.put("proofs.json", self.proofs)
        for evidence in self.record["evidence"]:
            evidence["file"] = copy.deepcopy(ref)

    def update_artifact(self, kind: str, value: Any, service: str = "api") -> None:
        row = next(x for x in self.images if x["service"] == service)
        ref = self.put(row[kind]["path"], value)
        row[kind] = ref
        item = next(x for x in self.inventory["images"] if x["service"] == service)
        if kind in {"scan", "sbom"}:
            item[kind + "_sha256"] = ref["sha256"]
        else:
            item["identity_inputs"][kind]["sha256"] = ref["sha256"]

    def sign(self) -> str:
        self.manifest["inventory"] = self.put("scans/inventory.json", self.inventory)
        return str(self.put("review.json", self.manifest)["sha256"])

    def verify(self) -> dict[str, Any]:
        return gate.verify_bundle(self.root, "review.json", self.sign(), self.source_sha, now=NOW)


def cast_record(value: Any) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return Bundle(tmp_path)


def test_exact_current_bundle_preserves_severity_and_limits_claims(bundle: Bundle) -> None:
    result = bundle.verify()
    assert result["valid"] and result["services"] == 8
    assert result["raw_severity_counts"] == {"HIGH": 1}
    assert result["high_critical_assessments"] == 1
    assert result["rationale_truth_verified"] is False
    assert result["release_approved"] is False
    assert bundle.record["identity"]["image_id"] != bundle.record["identity"]["image_config_id"]


def test_genuine_zero_high_still_validates_all_coverage(tmp_path: Path) -> None:
    result = Bundle(tmp_path, high=False).verify()
    assert result["high_critical_assessments"] == 0
    assert result["raw_severity_counts"] == {}


def test_critical_and_residual_severities_stay_visible(bundle: Bundle) -> None:
    scan = bundle.scans["api"]
    scan["Results"][0]["Vulnerabilities"][0]["Severity"] = "CRITICAL"
    scan["Results"][0]["Vulnerabilities"].append(
        {
            "VulnerabilityID": "CVE-2099-0002",
            "PkgName": "residual",
            "PkgID": "residual@1",
            "InstalledVersion": "1",
            "Severity": "UNKNOWN",
        }
    )
    bundle.update_artifact("scan", scan)
    bundle.inventory["images"][0]["counts"] = {"CRITICAL": 1, "UNKNOWN": 1}
    bundle.manifest["assessments"] = []
    bundle.proofs = {"proofs": []}
    bundle.add_assessment("")
    result = bundle.verify()
    assert result["raw_severity_counts"] == {"CRITICAL": 1, "UNKNOWN": 1}
    assert result["high_critical_assessments"] == 1


@pytest.mark.parametrize(
    "field", ["Description", "Layer", "Fingerprint", "UnrecognizedAdvisoryField"]
)
def test_changed_raw_finding_is_not_legacy_normalized_away(bundle: Bundle, field: str) -> None:
    scan = bundle.scans["api"]
    scan["Results"][0]["Vulnerabilities"][0][field] = "new raw value"
    bundle.update_artifact("scan", scan)
    bundle.record["identity"]["raw_scan_sha256"] = bundle.inventory["images"][0]["scan_sha256"]
    for proof in bundle.proofs["proofs"]:
        proof["identity"]["raw_scan_sha256"] = bundle.record["identity"]["raw_scan_sha256"]
    bundle.update_proofs()
    with pytest.raises(gate.GateError, match="finding_identity"):
        bundle.verify()


@pytest.mark.parametrize(
    "change",
    [
        "ambiguous-config",
        "config-hash",
        "inspection-platform",
        "scan-platform",
        "scan-rootfs",
        "OS-family",
        "unknown-severity",
    ],
)
def test_current_identity_and_platform_cannot_be_relabelled(bundle: Bundle, change: str) -> None:
    row = bundle.images[0]
    if change == "ambiguous-config":
        value = json.loads((bundle.root / row["manifest"]["path"]).read_bytes())
        bundle.update_artifact("manifest", [*value, *value])
    elif change == "config-hash":
        value = json.loads((bundle.root / row["config"]["path"]).read_bytes())
        value["config"]["Labels"]["new"] = "changed"
        bundle.update_artifact("config", value)
    elif change == "inspection-platform":
        value = json.loads((bundle.root / row["inspection"]["path"]).read_bytes())
        value["Architecture"] = "amd64"
        bundle.update_artifact("inspection", value)
    else:
        scan = bundle.scans["api"]
        if change == "scan-platform":
            scan["Metadata"]["ImageConfig"]["architecture"] = "amd64"
        elif change == "scan-rootfs":
            scan["Metadata"]["DiffIDs"] = ["sha256:" + "0" * 64]
        elif change == "OS-family":
            scan["Metadata"]["OS"]["Family"] = "alpine"
        else:
            scan["Results"][0]["Vulnerabilities"][0]["Severity"] = "UNRECOGNIZED"
        bundle.update_artifact("scan", scan)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_json_observations_are_strict_without_a_pointer(bundle: Bundle, raw: bytes) -> None:
    observation = bundle.proofs["proofs"][0]["observations"][0]
    observation["file"] = bundle.put("observations/strict.json", raw)
    observation["pointer"] = None
    bundle.update_proofs()
    with pytest.raises(gate.GateError):
        bundle.verify()


def test_available_fix_is_bound_even_for_not_applicable(tmp_path: Path) -> None:
    assert Bundle(tmp_path, fixed="1.1").verify()["valid"]


def test_upstream_fix_can_exist_without_scanner_distribution_fix(bundle: Bundle) -> None:
    fix = bundle.record["fix"]
    fix.update(
        upstream_availability="available",
        upstream_fixed_versions=["upstream-component 3.10"],
        rationale="Primary-source observation identifies an upstream fix, not a distro package fix",
    )
    assert fix["scanner_fixed_version"] is None and fix["scanner_fix_available"] is False
    assert bundle.verify()["valid"]


@pytest.mark.parametrize(
    "change",
    [
        "scanner-boolean",
        "scanner-version",
        "scanner-coercion",
        "missing-upstream",
        "missing-versions",
        "available-without-version",
        "unknown-with-version",
        "unavailable-with-version",
        "duplicate-versions",
        "legacy-ambiguous-fields",
    ],
)
def test_scanner_fix_binding_and_upstream_contract_are_distinct(
    bundle: Bundle, change: str
) -> None:
    fix = bundle.record["fix"]
    if change == "scanner-boolean":
        fix["scanner_fix_available"] = True
    elif change == "scanner-version":
        fix["scanner_fixed_version"] = "new distro version"
    elif change == "scanner-coercion":
        fix["scanner_fix_available"] = 0
    elif change == "missing-upstream":
        del fix["upstream_availability"]
    elif change == "missing-versions":
        del fix["upstream_fixed_versions"]
    elif change == "available-without-version":
        fix["upstream_availability"] = "available"
    elif change in {"unknown-with-version", "unavailable-with-version"}:
        fix["upstream_availability"] = change.split("-")[0]
        fix["upstream_fixed_versions"] = ["upstream 3.10"]
    elif change == "duplicate-versions":
        fix.update(upstream_availability="available", upstream_fixed_versions=["3.10", "3.10"])
    else:
        fix["availability"] = "unavailable"
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":{"a":1,"a":2}}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1e9999}',
        b"\xff",
        b"[] trailing",
        b"[" * 100 + b"]" * 100,
    ],
)
def test_strict_json_rejects_ambiguous_or_unbounded_input(raw: bytes) -> None:
    with pytest.raises(gate.GateError):
        gate.strict_json(raw)


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "a/../b",
        "a//b",
        "a/./b",
        "/absolute",
        "a/",
        "a\\b",
        "https://host/x",
        ".",
        "..",
        "a\x00b",
        "%2e%2e/x",
        "[slug]/../outside",
        "apps//[slug]/page.tsx",
        "apps/[...path]/./route.ts",
        "[slug]\\outside",
        "infra/patches/@/../outside",
        "infra//patches/braces@3.0.3.patch",
        "infra/patches/./braces@3.0.3.patch",
        "infra/patches/braces@3.0.3.patch/",
        "infra\\patches\\braces@3.0.3.patch",
    ],
)
def test_unsafe_paths_are_rejected(path: str) -> None:
    with pytest.raises(gate.GateError):
        gate.relative_path(path)


@pytest.mark.parametrize("path", ["[slug]/page.tsx", "apps/api/[...path]/route.ts"])
def test_literal_bracket_paths_are_supported(path: str) -> None:
    assert gate.relative_path(path) == path


def test_literal_patch_version_path_is_supported() -> None:
    path = "infra/patches/braces@3.0.3.patch"
    assert gate.relative_path(path) == path


@pytest.mark.parametrize("pointer", ["#", "#/a", "a", "/~2", "/a/01", "/a/-", "/a/3", "/a/1/x"])
def test_pointer_errors_fail(pointer: str) -> None:
    with pytest.raises(gate.GateError):
        gate.json_pointer({"a": [1, 2]}, pointer)


def test_rfc6901_escaping_and_root_are_supported() -> None:
    obj = {"a/b": {"~": ["value"]}, "": "empty-key"}
    assert gate.json_pointer(obj, "/a~1b/~0/0") == "value"
    assert gate.json_pointer(obj, "/") == "empty-key"
    assert gate.json_pointer(obj, "") == obj
    assert gate.json_pointer(obj, None) == obj


@pytest.mark.parametrize("decision", ["accept", "mitigate", "block", "investigate", "approved"])
def test_runtime_high_has_no_acceptance_or_mitigation_switch(bundle: Bundle, decision: str) -> None:
    bundle.record["decision"] = decision
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "field",
    [
        "rationale",
        "reachability",
        "exposure",
        "fix",
        "missing_inputs",
        "scope",
        "review_owner",
        "reviewed_at",
        "expires_at",
        "evidence",
    ],
)
def test_required_record_fields_cannot_disappear(bundle: Bundle, field: str) -> None:
    del bundle.record[field]
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("field", ["rationale", "reachability", "exposure", "review_owner"])
def test_blank_rationale_is_not_evidence(bundle: Bundle, field: str) -> None:
    bundle.record[field] = " \n "
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "location", ["manifest", "record", "identity", "scope", "proof", "file", "inventory"]
)
def test_envelopes_forbid_extra_fields(bundle: Bundle, location: str) -> None:
    target = {
        "manifest": bundle.manifest,
        "record": bundle.record,
        "identity": bundle.record["identity"],
        "scope": bundle.record["scope"],
        "proof": bundle.proofs["proofs"][0],
        "file": bundle.record["evidence"][0]["file"],
        "inventory": bundle.inventory,
    }[location]
    target["self_approved"] = True
    if location == "proof":
        bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "field",
    [
        "service",
        "image_id",
        "image_config_id",
        "scanner_image",
        "raw_scan_sha256",
        "sbom_sha256",
        "source_tree_sha256",
        "artifact",
        "target",
        "package",
        "package_id",
        "package_path",
        "installed_version",
        "vulnerability_id",
        "finding_sha256",
        "original_severity",
        "result_index",
        "finding_index",
        "result_type",
        "result_class",
    ],
)
def test_every_raw_record_identity_dimension_is_bound(bundle: Bundle, field: str) -> None:
    identity = bundle.record["identity"]
    if field in {"result_index", "finding_index"}:
        identity[field] = 1
    elif field.endswith("sha256"):
        identity[field] = "0" * 64
    elif field in {"image_id", "image_config_id"}:
        identity[field] = "sha256:" + "0" * 64
    else:
        identity[field] = {
            "service": "migrate",
            "original_severity": "CRITICAL",
            "result_class": "lang-pkgs",
        }.get(field, "changed")
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "field", ["Description", "Layer", "Fingerprint", "FixedVersion", "NewUpstreamField"]
)
def test_full_finding_digest_includes_provenance_and_new_fields(field: str) -> None:
    original = {"Severity": "HIGH", "Description": "unchanged"}
    changed = {**original, field: "new-value"}
    assert gate.finding_digest(original) != gate.finding_digest(changed)
    assert gate.finding_digest(original) == checksum(
        json.dumps(original, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    )


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_assessments_are_one_to_one(bundle: Bundle, mode: str) -> None:
    if mode == "missing":
        bundle.manifest["assessments"] = []
    else:
        extra = copy.deepcopy(bundle.record)
        if mode == "extra":
            extra["identity"]["finding_index"] = 9
        bundle.manifest["assessments"].append(extra)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("field", ["images", "inventory"])
def test_duplicate_services_never_collapse_in_dictionary(bundle: Bundle, field: str) -> None:
    items = bundle.images if field == "images" else bundle.inventory["images"]
    items[-1] = copy.deepcopy(items[0])
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "change",
    [
        "missing-results",
        "empty-results",
        "null-vulnerabilities",
        "schema",
        "scanner",
        "os",
        "artifact",
        "metadata",
        "missing-os-result",
    ],
)
def test_malformed_zero_high_scan_cannot_pass(tmp_path: Path, change: str) -> None:
    bundle = Bundle(tmp_path, high=False)
    scan = bundle.scans["api"]
    if change == "missing-results":
        del scan["Results"]
    elif change == "empty-results":
        scan["Results"] = []
    elif change == "null-vulnerabilities":
        scan["Results"][0]["Vulnerabilities"] = None
    elif change == "missing-os-result":
        scan["Results"][0].update(Class="lang-pkgs", Type="python-pkg")
    else:
        key, value = {
            "schema": ("SchemaVersion", 99),
            "scanner": ("Trivy", {"Version": "unknown"}),
            "os": ("Metadata", {"OS": {"Family": "unknown"}}),
            "artifact": ("ArtifactType", "filesystem"),
            "metadata": ("Metadata", []),
        }[change]
        scan[key] = value
    bundle.update_artifact("scan", scan)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "change", ["empty", "version", "scanner", "config-id", "components", "timestamp"]
)
def test_sbom_coverage_is_required_even_without_highs(tmp_path: Path, change: str) -> None:
    bundle = Bundle(tmp_path, high=False)
    sbom = bundle.sboms["api"]
    if change == "empty":
        sbom = {}
    elif change == "version":
        sbom["specVersion"] = "future"
    elif change == "scanner":
        sbom["metadata"]["tools"] = {"components": []}
    elif change == "config-id":
        sbom["metadata"]["component"]["properties"][0]["value"] = "sha256:" + "0" * 64
    elif change == "timestamp":
        sbom["metadata"]["timestamp"] = (NOW + timedelta(days=1)).isoformat()
    else:
        sbom["components"] = []
    bundle.update_artifact("sbom", sbom)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "field,value",
    [
        ("complete", False),
        ("complete", 1),
        ("counts", {}),
        ("counts", {"HIGH": True}),
        ("fix_available_count", 1),
        ("untriaged_high_critical_count", 0),
        ("scanner", "unknown"),
    ],
)
def test_inventory_cannot_launder_coverage(bundle: Bundle, field: str, value: Any) -> None:
    bundle.inventory["images"][0][field] = value
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "conflicting", "pointer", "hash", "size"]
)
def test_proof_refs_are_verified(bundle: Bundle, change: str) -> None:
    ref = bundle.record["evidence"][0]
    if change == "missing":
        (bundle.root / "proofs.json").unlink()
    elif change == "duplicate":
        bundle.record["evidence"].append(copy.deepcopy(ref))
    elif change in {"conflicting", "hash"}:
        ref["file"]["sha256"] = "0" * 64
    elif change == "size":
        ref["file"]["size"] += 1
    else:
        ref["pointer"] = "/proofs/999"
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("purpose", sorted(gate.QUESTIONS))
@pytest.mark.parametrize(
    "change",
    [
        "absent",
        "empty",
        "missing-file",
        "changed-bytes",
        "wrong-hash",
        "wrong-size",
        "wrong-pointer",
        "duplicate",
        "conflicting",
    ],
)
def test_each_question_needs_real_bound_observations(
    bundle: Bundle, purpose: str, change: str
) -> None:
    proof = next(p for p in bundle.proofs["proofs"] if p["purpose"] == purpose)
    observation = proof["observations"][0]
    path = bundle.root / observation["file"]["path"]
    if change == "absent":
        del proof["observations"]
    elif change == "empty":
        proof["observations"] = []
    elif change == "missing-file":
        path.unlink()
    elif change == "changed-bytes":
        path.write_bytes(b"changed observation")
    elif change == "wrong-hash":
        observation["file"]["sha256"] = "0" * 64
    elif change == "wrong-size":
        observation["file"]["size"] += 1
    elif change == "wrong-pointer":
        observation["pointer"] = "/missing"
    else:
        duplicate = copy.deepcopy(observation)
        if change == "conflicting":
            duplicate["pointer"] = ""
            duplicate["file"]["sha256"] = "0" * 64
        proof["observations"].append(duplicate)
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("purpose", sorted(gate.QUESTIONS))
@pytest.mark.parametrize(
    "selected",
    [
        None,
        {},
        [],
        " \n\t ",
        False,
        0,
        [None, {}, []],
        {"results": []},
        {"complete": True, "observations": []},
        {"complete": False, "error": "synthetic-capture-failed", "observations": []},
        {"complete": False, "observations": ["partial hit"]},
        {"search_complete": False, "paths": ["selected.py"]},
        {"complete": True, "error": "synthetic-capture-failed", "paths": ["selected.py"]},
        {"status": "failed", "paths": ["selected.py"]},
        [{"path": "selected.py"}, {"complete": False, "observations": []}],
        {"scope": "current", "conclusion": "safe", "coverage": "complete-for-question"},
    ],
)
def test_selected_empty_or_failed_observation_cannot_support_any_proof(
    bundle: Bundle, purpose: str, selected: Any
) -> None:
    proof = next(p for p in bundle.proofs["proofs"] if p["purpose"] == purpose)
    observation = proof["observations"][0]
    observation["file"] = bundle.put(
        observation["file"]["path"], {"selected": selected, "unselected": "real content"}
    )
    observation["pointer"] = "/selected"
    bundle.update_proofs()
    with pytest.raises(gate.GateError, match="(?:empty|incomplete|failed)_observation"):
        bundle.verify()


@pytest.mark.parametrize("pointer", [None, ""])
def test_whole_json_failed_receipt_is_not_an_observation(
    bundle: Bundle, pointer: str | None
) -> None:
    observation = bundle.proofs["proofs"][0]["observations"][0]
    observation["file"] = bundle.put(
        observation["file"]["path"],
        {"complete": False, "error": "synthetic-capture-failed", "observations": []},
    )
    observation["pointer"] = pointer
    bundle.update_proofs()
    with pytest.raises(gate.GateError, match="incomplete_observation"):
        bundle.verify()


def test_non_json_whitespace_is_not_an_observation(bundle: Bundle) -> None:
    observation = bundle.proofs["proofs"][0]["observations"][0]
    observation["file"] = bundle.put("observations/empty.txt", b" \n\t ")
    observation["pointer"] = None
    bundle.update_proofs()
    with pytest.raises(gate.GateError, match="empty_observation"):
        bundle.verify()


@pytest.mark.parametrize("purpose", sorted(gate.QUESTIONS))
def test_explicit_scoped_complete_empty_result_is_valid(bundle: Bundle, purpose: str) -> None:
    proof = next(p for p in bundle.proofs["proofs"] if p["purpose"] == purpose)
    observation = proof["observations"][0]
    selected = {
        "schema_version": 1,
        "kind": "scoped-empty-result",
        "scope": copy.deepcopy(proof["scope"]),
        "complete": True,
        "examined": ["Exact selected.py import table; only the named component question"],
        "results": [],
    }
    observation["file"] = bundle.put(
        observation["file"]["path"],
        {"complete": False, "unrelated_error": "unreviewed other boundary", "selected": selected},
    )
    observation["pointer"] = "/selected"
    bundle.update_proofs()
    assert bundle.verify()["valid"]


@pytest.mark.parametrize(
    "change",
    [
        "scope",
        "incomplete",
        "coerced",
        "no-scope",
        "no-complete",
        "no-kind",
        "wrong-kind",
        "nonempty",
        "unexamined",
        "extra",
    ],
)
def test_empty_result_envelope_must_be_explicit_complete_and_same_scope(
    bundle: Bundle, change: str
) -> None:
    proof = bundle.proofs["proofs"][0]
    selected: dict[str, Any] = {
        "schema_version": 1,
        "kind": "scoped-empty-result",
        "scope": copy.deepcopy(proof["scope"]),
        "complete": True,
        "examined": ["selected.py"],
        "results": [],
    }
    if change == "scope":
        selected["scope"]["boundaries"] = "Different scope"
    elif change in {"incomplete", "coerced"}:
        selected["complete"] = False if change == "incomplete" else 1
    elif change.startswith("no-"):
        del selected[change.removeprefix("no-")]
    elif change == "wrong-kind":
        selected["kind"] = "untyped-empty-result"
    elif change == "nonempty":
        selected["results"] = ["not empty"]
    elif change == "unexamined":
        selected["examined"] = []
    else:
        selected["error"] = "failed"
    observation = proof["observations"][0]
    observation["file"] = bundle.put(observation["file"]["path"], selected)
    observation["pointer"] = None
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


def test_legacy_report_can_select_concrete_subtree_without_global_completeness(
    bundle: Bundle,
) -> None:
    proof = bundle.proofs["proofs"][0]
    observation = proof["observations"][0]
    observation["file"] = bundle.put(
        observation["file"]["path"],
        {"complete": False, "selected": {"path": "selected.py", "imports": ["json"]}},
    )
    observation["pointer"] = "/selected"
    bundle.update_proofs()
    assert bundle.verify()["valid"]


@pytest.mark.parametrize("purpose", ["component", "reachability", "exposure"])
def test_old_runtime_observations_require_exact_byte_reuse(bundle: Bundle, purpose: str) -> None:
    proof = next(p for p in bundle.proofs["proofs"] if p["purpose"] == purpose)
    proof["observed_at"] = (SOURCE_TIME - timedelta(days=1)).isoformat()
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()
    current = copy.deepcopy(proof["observations"])
    old_ref = current[0]["file"]
    current[0]["file"] = bundle.put(
        "observations/reused-current.json", (bundle.root / old_ref["path"]).read_bytes()
    )
    proof["reused_exact_bytes"] = {
        "rationale": "Same selected immutable bytes rechecked for current image",
        "verified_at": REVIEW.isoformat(),
        "current_source_tree_sha256": bundle.source_sha,
        "current": current,
    }
    bundle.update_proofs()
    assert bundle.verify()["valid"]
    current[0]["file"] = bundle.put("observations/reused-current.json", {"different": True})
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("purpose", ["advisory", "fix"])
def test_old_primary_advisory_and_fix_sources_are_not_overconstrained(
    bundle: Bundle, purpose: str
) -> None:
    proof = next(p for p in bundle.proofs["proofs"] if p["purpose"] == purpose)
    proof["observed_at"] = (SOURCE_TIME - timedelta(days=300)).isoformat()
    bundle.update_proofs()
    assert bundle.verify()["valid"]


@pytest.mark.parametrize(
    "change",
    [
        "future-review",
        "expired",
        "expiry-now",
        "review-before-scan",
        "future-proof",
        "naive-date",
        "old-proof-scope",
        "missing-inputs",
        "partial-proof",
        "build-scope",
        "wrong-fix",
    ],
)
def test_dates_scopes_and_missing_questions_fail_closed(bundle: Bundle, change: str) -> None:
    if change == "future-review":
        bundle.record["reviewed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change in {"expired", "expiry-now"}:
        bundle.record["expires_at"] = (NOW - timedelta(seconds=change == "expired")).isoformat()
    elif change == "review-before-scan":
        bundle.record["reviewed_at"] = SOURCE_TIME.isoformat()
    elif change == "naive-date":
        bundle.manifest["reviewed_at"] = REVIEW.replace(tzinfo=None).isoformat()
    elif change == "future-proof":
        bundle.proofs["proofs"][0]["observed_at"] = (NOW + timedelta(days=1)).isoformat()
    elif change == "old-proof-scope":
        bundle.proofs["proofs"][0]["identity"]["source_tree_sha256"] = "0" * 64
    elif change == "missing-inputs":
        bundle.proofs["proofs"][0]["missing_inputs"] = ["Need actual component observation"]
    elif change == "partial-proof":
        bundle.proofs["proofs"][0]["coverage"] = "partial"
    elif change == "build-scope":
        bundle.record["scope"]["membership"] = "build-only"
    else:
        bundle.record["fix"] = {
            "scanner_fix_available": True,
            "scanner_fixed_version": "9",
            "upstream_availability": "unknown",
            "upstream_fixed_versions": [],
            "rationale": "claim",
        }
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("change", ["content", "mode", "extra", "missing"])
def test_frozen_source_is_rehashed_not_a_copied_assertion(bundle: Bundle, change: str) -> None:
    path = bundle.root / "source/app.py"
    if change == "content":
        path.write_bytes(b"changed source")
    elif change == "mode":
        path.chmod(0o755)
    elif change == "missing":
        path.unlink()
    else:
        (bundle.root / "source/unlisted.py").write_bytes(b"extra build input")
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("kind", ["file-link", "parent-link", "root-link", "hardlink", "fifo"])
def test_symlinks_and_special_files_are_rejected(bundle: Bundle, tmp_path: Path, kind: str) -> None:
    path = bundle.root / "observations/advisory.json"
    other = bundle.root / "retained-observation.json"
    other.write_bytes(path.read_bytes())
    if kind == "parent-link":
        directory = bundle.root / "observations"
        directory.rename(bundle.root / "moved-observations")
        directory.symlink_to(bundle.root / "moved-observations", target_is_directory=True)
    elif kind == "root-link":
        link = tmp_path / "bundle-link"
        link.symlink_to(bundle.root, target_is_directory=True)
        expected = bundle.sign()
        with pytest.raises(REJECTED):
            gate.verify_bundle(link, "review.json", expected, bundle.source_sha, now=NOW)
        return
    else:
        path.unlink()
        if kind == "file-link":
            path.symlink_to(other)
        elif kind == "hardlink":
            os.link(other, path)
        else:
            os.mkfifo(path)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "limit", ["MAX_FILE_BYTES", "MAX_TOTAL_BYTES", "MAX_FILES", "MAX_JSON_NODES"]
)
def test_budgets_are_enforced(bundle: Bundle, monkeypatch: pytest.MonkeyPatch, limit: str) -> None:
    monkeypatch.setattr(gate, limit, 1)
    with pytest.raises(REJECTED):
        bundle.verify()


def test_external_pin_cannot_be_replaced_by_bundle_claim(bundle: Bundle) -> None:
    expected = bundle.sign()
    bundle.manifest["review_owner"] = "Changed adoption"
    bundle.sign()
    with pytest.raises(gate.GateError, match="trusted_manifest_mismatch"):
        gate.verify_bundle(bundle.root, "review.json", expected, bundle.source_sha, now=NOW)
    with pytest.raises(gate.GateError, match="source_binding"):
        gate.verify_bundle(bundle.root, "review.json", bundle.sign(), "0" * 64, now=NOW)


def test_cli_is_read_only_uses_current_clock_and_never_echoes_private_content(
    bundle: Bundle,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = bundle.sign()
    argv = [
        "--bundle-root",
        str(bundle.root),
        "--review-manifest",
        "review.json",
        "--expected-review-sha256",
        expected,
        "--expected-source-sha256",
        bundle.source_sha,
    ]
    before = {
        p.relative_to(bundle.root): p.read_bytes() for p in bundle.root.rglob("*") if p.is_file()
    }
    assert gate.main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] and not result["release_approved"]
    assert before == {
        p.relative_to(bundle.root): p.read_bytes() for p in bundle.root.rglob("*") if p.is_file()
    }
    (bundle.root / "review.json").write_bytes(b'{"PRIVATE-CONTENT":NaN}')
    assert gate.main(argv) == 1
    output = capsys.readouterr()
    assert "PRIVATE-CONTENT" not in output.out + output.err
    assert str(bundle.root) not in output.out + output.err
    assert gate.main([*argv, "--today", "2026-01-01"]) == 1
    assert "2026-01-01" not in capsys.readouterr().out


def test_direct_script_entrypoint_does_not_execute_evidence(bundle: Bundle) -> None:
    marker = bundle.root / "executed"
    observation = bundle.proofs["proofs"][0]["observations"][0]
    observation["file"] = bundle.put(
        "observations/inert.py", f"raise RuntimeError({str(marker)!r})".encode()
    )
    observation["pointer"] = None
    bundle.update_proofs()
    expected = bundle.sign()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(gate.__file__).resolve()),
            "--bundle-root",
            str(bundle.root),
            "--review-manifest",
            "review.json",
            "--expected-review-sha256",
            expected,
            "--expected-source-sha256",
            bundle.source_sha,
        ],
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert not marker.exists() and not result.stderr


def test_changes_after_cached_read_are_detected(
    bundle: Bundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    original: Callable[..., None] = gate.validate_assessment

    def change(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        (bundle.root / "source/app.py").write_bytes(b"mutated after initial verification")

    monkeypatch.setattr(gate, "validate_assessment", change)
    with pytest.raises(gate.GateError, match="file_changed"):
        bundle.verify()


@pytest.mark.parametrize("membership", ["build", "dev", "test"])
def test_shared_observation_scope_does_not_widen_image_scope(membership: str) -> None:
    scope = {"membership": membership, "boundaries": "Selected source only", "exclusions": []}
    assert gate.ObservationScope.model_validate(scope).membership == membership
    with pytest.raises(ValidationError):
        gate.Scope.model_validate(scope)
