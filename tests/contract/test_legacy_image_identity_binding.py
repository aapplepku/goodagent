"""Synthetic schema-4 legacy reviews; no historical approval is upgraded."""

from __future__ import annotations

import copy
import json
import os
import runpy
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from .test_release_assessment_gate import Bundle, checksum, encoded

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / "scripts/check-image-findings.py"))
DEPLOYMENT = "d" * 64


class LegacyBundle:
    def __init__(self, root: Path, *, high: bool = True) -> None:
        self.root = root.resolve()
        self.bundle = Bundle(self.root, high=high)
        self.item = self.bundle.inventory["images"][0]
        self.report = self.bundle.scans["api"]
        self.result = self.report["Results"][0]
        self.finding = self.result["Vulnerabilities"][0] if high else None
        if self.finding is not None:
            self.fingerprint()
        self.bundle.update_artifact("scan", self.report)
        today = datetime.now(UTC).date()
        expiry = today + timedelta(days=7)
        rule = {
            "name": "synthetic-absent-component",
            "status": "not_affected",
            "vulnerabilities": ["CVE-2099-0001"],
            "packages": {"synthetic-library": ["1.0"]},
            "required_absent": ["/synthetic/not-installed"],
            "requires_storage_proof": False,
            "reason": "Synthetic fixture only",
            "references": ["synthetic-observation"],
        }
        self.policy: dict[str, Any] = {
            "schema_version": 1,
            "scope": "Synthetic private test only",
            "reviewed_on": today.isoformat(),
            "expires_on": expiry.isoformat(),
            "rules": [rule],
        }
        self.record: dict[str, Any] = {
            "service": "api",
            "scanner": "trivy",
            "scanner_version": "0.74.0",
            "scanner_image": MODULE["SCANNER"],
            "scan_date": datetime.fromisoformat(self.report["CreatedAt"]).date().isoformat(),
            "review_owner": "Synthetic reviewer",
            "artifact_type": "container_image",
            "reviewed_image_id": self.item["image_id"],
            "reviewed_image_config_id": self.item["image_config_id"],
            "architecture": "arm64",
            "package": "synthetic-library",
            "installed_version": "1.0",
            "advisory": "CVE-2099-0001",
            "severity": "HIGH",
            "shipped_runtime": True,
            "scope": "runtime",
            "reachability": "Synthetic scope",
            "exposure": "Synthetic scope",
            "fixed_version": "",
            "fixed_version_available": False,
            "decision": "not-applicable",
            "evidence": ["synthetic-observation"],
            "rationale": "Fixture only; no release clearance",
            "reviewed_on": today.isoformat(),
            "expires_on": expiry.isoformat(),
            "rule": rule["name"],
            "rule_sha256": MODULE["digest"](rule),
            "finding_sha256": MODULE["finding_digest"](
                self.finding or {}, self.result, self.report
            ),
        }
        self.review: dict[str, Any] = {
            "schema_version": 4,
            "deployment_sha256": DEPLOYMENT,
            "deployment_files": [],
            "source_archive": "synthetic-only",
            "records": [self.record] if high else [],
        }
        self.proof: dict[str, Any] = {
            "complete": True,
            "images": [
                {
                    "service": row["service"],
                    "image_id": row["image_id"],
                    "architecture": row["architecture"],
                    "process": {
                        "Uid": "10001 10001 10001 10001",
                        "NoNewPrivs": "1",
                        "CapEff": "0000000000000000",
                        "CapPrm": "0000000000000000",
                        "CapBnd": "0000000000000000",
                    },
                    "setuid_setgid_files_in_runtime_paths": [],
                    "absent_components": ["/synthetic/not-installed"],
                }
                for row in self.bundle.inventory["images"]
            ],
        }

    @property
    def output(self) -> Path:
        return self.root / "scans/dispositions.json"

    def fingerprint(self) -> None:
        assert self.finding is not None
        self.finding["Fingerprint"] = MODULE["scanner_fingerprint"](
            self.finding, self.result, self.report
        )

    def config(self, *, consistent: bool, architecture: str = "arm64") -> None:
        """Replace config/layers; optionally update the retained relationship too."""
        config = copy.deepcopy(self.report["Metadata"]["ImageConfig"])
        config["architecture"] = architecture
        config["rootfs"]["diff_ids"] = ["sha256:" + "b" * 64]
        config["config"]["Labels"]["fixture-service"] = "different-synthetic-image"
        self.item["image_config_id"] = "sha256:" + checksum(encoded(config))
        self.item["architecture"] = architecture
        self.report["ArtifactID"] = self.item["image_config_id"]
        self.report["Metadata"].update(
            ImageID=self.item["image_config_id"],
            ImageConfig=config,
            DiffIDs=list(config["rootfs"]["diff_ids"]),
        )
        if self.finding is not None:
            self.finding["Layer"] = {"DiffID": config["rootfs"]["diff_ids"][0]}
            self.fingerprint()
        self.bundle.sboms["api"]["metadata"]["component"]["properties"][0]["value"] = self.item[
            "image_config_id"
        ]
        self.bundle.update_artifact("scan", self.report)
        self.bundle.update_artifact("sbom", self.bundle.sboms["api"])
        if consistent:
            self.bundle.update_artifact("config", config)
            member = "blobs/sha256/" + self.item["image_config_id"].removeprefix("sha256:")
            self.item["identity_inputs"]["config"]["archive_member"] = member
            self.bundle.update_artifact(
                "manifest", [{"Config": member, "Layers": ["layers/one.tar"]}]
            )
            self.bundle.update_artifact(
                "inspection",
                {
                    "Id": self.item["image_id"],
                    "Architecture": architecture,
                    "Os": "linux",
                    "RootFS": {"Type": "layers", "Layers": config["rootfs"]["diff_ids"]},
                },
            )

    def arguments(self) -> list[str]:
        self.bundle.put("scans/inventory.json", self.bundle.inventory)
        self.bundle.put("policy.json", self.policy)
        self.bundle.put("reviewed.json", self.review)
        self.bundle.put("runtime-proof.json", self.proof)
        self.output.unlink(missing_ok=True)
        return [
            "--scans",
            str(self.root / "scans"),
            "--proof",
            str(self.root / "runtime-proof.json"),
            "--assessments",
            str(self.root / "policy.json"),
            "--reviewed-findings",
            str(self.root / "reviewed.json"),
        ]

    def run(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
        monkeypatch.setattr(sys, "argv", ["check-image-findings.py", *self.arguments()])
        monkeypatch.setitem(MODULE["main"].__globals__, "deployment_digest", lambda _: DEPLOYMENT)
        MODULE["main"]()
        result = json.loads(self.output.read_bytes())
        assert isinstance(result, dict)
        return result


@pytest.fixture
def bundle(tmp_path: Path) -> LegacyBundle:
    return LegacyBundle(tmp_path)


@pytest.mark.parametrize("architecture", ["arm64", "amd64"])
@pytest.mark.parametrize("same_id", [False, True])
def test_verified_index_config_relationship_can_have_distinct_ids(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, architecture: str, same_id: bool
) -> None:
    bundle.config(consistent=True, architecture=architecture)
    if same_id:
        bundle.item["image_id"] = bundle.item["image_config_id"]
        inspection = json.loads((bundle.root / "scans/api.image-inspection.json").read_bytes())
        inspection["Id"] = bundle.item["image_id"]
        bundle.bundle.update_artifact("inspection", inspection)
    bundle.proof["images"][0].update(architecture=architecture, image_id=bundle.item["image_id"])
    bundle.record.update(
        architecture=architecture,
        reviewed_image_id=bundle.item["image_id"],
        reviewed_image_config_id=bundle.item["image_config_id"],
        finding_sha256=MODULE["finding_digest"](bundle.finding, bundle.result, bundle.report),
    )
    result = bundle.run(monkeypatch)
    assert result["passed"] is True
    assert result["raw_high_critical"] == 1 and result["unresolved_high_critical"] == 0
    assert (bundle.item["image_id"] == bundle.item["image_config_id"]) is same_id


def test_original_mixed_config_counterexample_is_rejected(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert bundle.run(monkeypatch)["passed"] is True
    review_before = encoded(bundle.review)
    bundle.config(consistent=False)
    assert encoded(bundle.review) == review_before
    with pytest.raises(ValueError, match="image_identity"):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize("change", ["diff-id", "digest", "missing", "malformed", "new-field"])
def test_changed_finding_provenance_requires_new_review(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    assert bundle.run(monkeypatch)["passed"] is True
    assert bundle.finding is not None
    review_before = encoded(bundle.review)
    if change == "diff-id":
        bundle.finding["Layer"]["DiffID"] = "sha256:" + "f" * 64
    elif change == "digest":
        bundle.finding["Layer"]["Digest"] = "sha256:" + "f" * 64
    elif change == "missing":
        del bundle.finding["Layer"]
    elif change == "malformed":
        bundle.finding["Layer"] = "not-a-layer-object"
    else:
        bundle.finding["NewScannerField"] = {"previously_unreviewed": True}
    bundle.bundle.update_artifact("scan", bundle.report)
    assert encoded(bundle.review) == review_before
    with pytest.raises(SystemExit) as rejected:
        bundle.run(monkeypatch)
    assert rejected.value.code == 1
    output = json.loads(bundle.output.read_bytes())
    assert output["passed"] is False and output["unresolved_high_critical"] == 1
    assert output["findings"][0]["assessment"] == "raw finding or scanner context changed"


def test_consistent_new_config_still_needs_exact_new_review(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert bundle.run(monkeypatch)["passed"] is True
    review_before = encoded(bundle.review)
    bundle.config(consistent=True)
    assert encoded(bundle.review) == review_before
    with pytest.raises(SystemExit) as rejected:
        bundle.run(monkeypatch)
    assert rejected.value.code == 1
    result = json.loads(bundle.output.read_bytes())
    assert result["passed"] is False and result["unresolved_high_critical"] == 1
    assert result["findings"][0]["scanner_severity"] == "HIGH"
    assert result["findings"][0]["assessment"] == (
        "exact image config changed: applicability review required"
    )
    bundle.record["reviewed_image_config_id"] = bundle.item["image_config_id"]
    bundle.record["finding_sha256"] = MODULE["finding_digest"](
        bundle.finding, bundle.result, bundle.report
    )
    assert bundle.run(monkeypatch)["passed"] is True


@pytest.mark.parametrize("kind", ["scan", "sbom", "manifest", "config", "inspection"])
@pytest.mark.parametrize("change", ["missing", "bytes", "hash"])
def test_retained_files_require_exact_original_bytes_and_hashes(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, kind: str, change: str
) -> None:
    ref = bundle.bundle.images[0][kind]
    path = bundle.root / ref["path"]
    if change == "missing":
        path.unlink()
    elif change == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif kind in {"scan", "sbom"}:
        bundle.item[kind + "_sha256"] = "0" * 64
    else:
        bundle.item["identity_inputs"][kind]["sha256"] = "0" * 64
    with pytest.raises((ValueError, OSError)):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize("kind", ["manifest", "config", "inspection"])
@pytest.mark.parametrize("missing", ["entry", "hash", "file"])
def test_missing_identity_references_never_fall_back_to_report_claims(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, kind: str, missing: str
) -> None:
    if missing == "entry":
        del bundle.item["identity_inputs"][kind]
    else:
        del bundle.item["identity_inputs"][kind]["sha256" if missing == "hash" else "file"]
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize(
    "change",
    [
        "config-id",
        "inspection-id",
        "inspection-platform",
        "inspection-layers",
        "manifest-config",
        "scan-layers",
        "sbom-id",
    ],
)
def test_rehashed_relationship_mismatches_are_rejected(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    if change == "config-id":
        bundle.item["image_config_id"] = "sha256:" + "f" * 64
    elif change.startswith("inspection"):
        inspection = json.loads((bundle.root / "scans/api.image-inspection.json").read_bytes())
        if change == "inspection-id":
            inspection["Id"] = "sha256:" + "f" * 64
        elif change == "inspection-platform":
            inspection["Architecture"] = "amd64"
        else:
            inspection["RootFS"]["Layers"] = ["sha256:" + "f" * 64]
        bundle.bundle.update_artifact("inspection", inspection)
    elif change == "manifest-config":
        manifest = [{"Config": "unrelated.json", "Layers": ["layers/one.tar"]}]
        bundle.bundle.update_artifact("manifest", manifest)
    elif change == "scan-layers":
        bundle.report["Metadata"]["DiffIDs"] = ["sha256:" + "f" * 64]
        bundle.bundle.update_artifact("scan", bundle.report)
    else:
        bundle.bundle.sboms["api"]["metadata"]["component"]["properties"][0]["value"] = (
            "sha256:" + "f" * 64
        )
        bundle.bundle.update_artifact("sbom", bundle.bundle.sboms["api"])
    with pytest.raises(ValueError):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize("schema", [3, 4.0, "4", True, None])
def test_review_schema_is_exact_and_legacy_is_not_implicitly_migrated(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, schema: Any
) -> None:
    bundle.review["schema_version"] = schema
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        True,
        "",
        "f" * 64,
        "sha256:" + "A" * 64,
        " sha256:" + "a" * 64,
        "sha256:" + "a" * 64 + "\n",
    ],
)
def test_config_review_pin_is_strict_and_never_normalized(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, value: Any
) -> None:
    bundle.record["reviewed_image_config_id"] = value
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


def test_config_review_pin_is_required(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    del bundle.record["reviewed_image_config_id"]
    with pytest.raises(ValidationError, match="reviewed_image_config_id"):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize("field", ["shipped_runtime", "fixed_version_available"])
def test_review_boolean_types_are_not_coerced(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    bundle.record[field] = 1 if field == "shipped_runtime" else 0
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)


@pytest.mark.parametrize("field", ["complete", "counts", "fix_available_count"])
def test_retained_inventory_types_are_strict(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    bundle.item[field] = {"complete": 1, "counts": {"HIGH": True}, "fix_available_count": False}[
        field
    ]
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "traversal"])
def test_identity_inputs_cannot_escape_or_alias_retained_files(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = bundle.root / "scans/api.image-config.json"
    if kind == "traversal":
        bundle.item["identity_inputs"]["config"]["file"] = "../scans/api.image-config.json"
    else:
        other = bundle.root / "other-config.json"
        path.rename(other)
        if kind == "symlink":
            path.symlink_to(other)
        else:
            os.link(other, path)
    with pytest.raises((ValueError, OSError)):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "expired",
        "deployment",
        "changed-high",
        "new-high",
        "new-critical",
        "scanner",
        "scanner-version",
        "accept",
    ],
)
def test_existing_blocking_conditions_remain_blocking(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    assert bundle.finding is not None
    if change == "missing":
        bundle.review["records"] = []
    elif change == "expired":
        bundle.record["expires_on"] = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    elif change == "deployment":
        bundle.review["deployment_sha256"] = "0" * 64
    elif change == "changed-high":
        bundle.finding["Description"] = "Changed advisory"
    elif change.startswith("new-"):
        severity = "CRITICAL" if change == "new-critical" else "HIGH"
        extra = {**bundle.finding, "VulnerabilityID": "CVE-2099-NEW", "Severity": severity}
        extra["Fingerprint"] = MODULE["scanner_fingerprint"](extra, bundle.result, bundle.report)
        bundle.result["Vulnerabilities"].append(extra)
        bundle.item["counts"] = {"HIGH": 2} if severity == "HIGH" else {"HIGH": 1, "CRITICAL": 1}
        bundle.item["untriaged_high_critical_count"] = 2
    elif change == "scanner":
        bundle.item["scanner"] = "unreviewed-scanner"
    elif change == "scanner-version":
        bundle.report["Trivy"]["Version"] = "0.75.0"
    else:
        bundle.record["decision"] = "accept"
    bundle.bundle.update_artifact("scan", bundle.report)
    with pytest.raises((ValueError, SystemExit)):
        bundle.run(monkeypatch)
    if bundle.output.exists():
        assert json.loads(bundle.output.read_bytes())["passed"] is False


@pytest.mark.parametrize("high", [False, True])
def test_missing_identity_is_blocking_even_without_high_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, high: bool
) -> None:
    bundle = LegacyBundle(tmp_path, high=high)
    del bundle.item["identity_inputs"]
    with pytest.raises(ValidationError):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize("medium", [False, True])
def test_complete_zero_high_collection_still_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, medium: bool
) -> None:
    bundle = LegacyBundle(tmp_path, high=False)
    if medium:
        bundle.result["Vulnerabilities"] = [
            {
                "PkgName": "synthetic",
                "PkgID": "synthetic@1",
                "InstalledVersion": "1",
                "VulnerabilityID": "CVE-2099-MEDIUM",
                "Severity": "MEDIUM",
            }
        ]
        bundle.item["counts"] = {"MEDIUM": 1}
        bundle.bundle.update_artifact("scan", bundle.report)
    result = bundle.run(monkeypatch)
    assert result["passed"] is True and result["raw_high_critical"] == 0


def test_inputs_are_rechecked_before_a_success_output(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = MODULE["record_disposition"]

    def mutate(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        path = bundle.root / "scans/api.image-config.json"
        path.write_bytes(path.read_bytes() + b" ")
        return result

    monkeypatch.setitem(MODULE["main"].__globals__, "record_disposition", mutate)
    with pytest.raises(ValueError, match="file_changed"):
        bundle.run(monkeypatch)
    assert not bundle.output.exists()


@pytest.mark.parametrize(
    "path,field",
    [("policy.json", "assessment_sha256"), ("runtime-proof.json", "runtime_proof_sha256")],
)
def test_output_hashes_bind_validated_policy_and_proof_snapshots(
    bundle: LegacyBundle, monkeypatch: pytest.MonkeyPatch, path: str, field: str
) -> None:
    original = MODULE["record_disposition"]
    validated_bytes: list[bytes] = []

    def replace_after_validation(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        evidence_path = bundle.root / path
        validated_bytes.append(evidence_path.read_bytes())
        evidence_path.write_bytes(b'{"unvalidated_replacement":true}\n')
        return result

    monkeypatch.setitem(MODULE["main"].__globals__, "record_disposition", replace_after_validation)
    output = bundle.run(monkeypatch)
    assert output["passed"] is True
    assert len(validated_bytes) == 1
    assert output[field] == checksum(validated_bytes[0])
    assert output[field] != checksum((bundle.root / path).read_bytes())


def test_direct_entrypoint_uses_the_same_identity_gate(bundle: LegacyBundle) -> None:
    bundle.review["deployment_sha256"] = MODULE["deployment_digest"](ROOT)
    args = bundle.arguments()
    command = [sys.executable, "-B", str(ROOT / "scripts/check-image-findings.py"), *args]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    control = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, timeout=15)
    assert control.returncode == 0, control.stderr
    bundle.config(consistent=False)
    bundle.arguments()
    rejected = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, timeout=15)
    assert rejected.returncode != 0
    assert not bundle.output.exists()
