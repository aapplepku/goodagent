"""Malformed coverage must never turn into a passing zero-finding review."""

import copy
import hashlib
import json
import runpy
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from .test_release_assessment_gate import Bundle

MODULE = runpy.run_path("scripts/check-image-findings.py")
TODAY = date(2026, 10, 17)


def fixture() -> tuple[dict[str, Any], ...]:
    image = "sha256:" + "a" * 64
    item = {
        "complete": True,
        "service": "api",
        "scanner": MODULE["SCANNER"],
        "image_id": image,
        "image_config_id": image,
        "architecture": "arm64",
        "counts": {},
        "fix_available_count": 0,
        "untriaged_high_critical_count": 0,
    }
    report = {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "ArtifactID": image,
        "Trivy": {"Version": "0.74.0"},
        "CreatedAt": "2026-10-17T00:00:00Z",
        "Metadata": {
            "ImageID": image,
            "ImageConfig": {"architecture": "arm64"},
            "OS": {"Family": "debian"},
        },
        "Results": [{"Target": "/scans/api.tar", "Class": "os-pkgs", "Type": "debian"}],
    }
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "components": [{"type": "operating-system", "name": "debian"}],
        "metadata": {
            "tools": {"components": [{"name": "trivy", "version": "0.74.0"}]},
            "component": {
                "type": "container",
                "properties": [{"name": "aquasecurity:trivy:ImageID", "value": image}],
            },
        },
    }
    return item, report, sbom


def test_complete_zero_finding_scan_has_real_os_and_sbom_coverage() -> None:
    MODULE["validate_scan_coverage"](*fixture(), today=TODAY)


@pytest.mark.parametrize(
    "index,path,value",
    [
        (0, ["complete"], False),
        (0, ["complete"], 1),
        (0, ["scanner"], "other-scanner"),
        (0, ["counts"], {"HIGH": 1}),
        (0, ["counts"], {"HIGH": True}),
        (0, ["counts"], {"bogus": 0}),
        (0, ["fix_available_count"], 1),
        (0, ["untriaged_high_critical_count"], 1),
        (1, ["Results"], None),
        (1, ["Results"], []),
        (1, ["Results"], {}),
        (1, ["SchemaVersion"], 3),
        (1, ["Trivy", "Version"], "0.75.0"),
        (1, ["ArtifactID"], "another-image"),
        (1, ["ArtifactType"], "filesystem"),
        (1, ["Metadata", "ImageConfig", "architecture"], "amd64"),
        (1, ["Metadata", "OS", "Family"], "unknown"),
        (1, ["CreatedAt"], "2026-10-18T00:00:00Z"),
        (1, ["CreatedAt"], "2026-10-17T00:00:00"),
        (2, ["components"], []),
        (2, ["components"], [{"name": 1, "type": "library"}]),
        (2, ["components"], [{"name": "package", "type": {"library": True}}]),
        (2, ["components"], [{"name": " ", "type": "library"}]),
        (2, ["components"], [{"name": "package", "type": "made-up"}]),
        (2, ["bomFormat"], "wrong"),
        (2, ["specVersion"], "unknown"),
        (2, ["version"], True),
        (2, ["metadata", "tools", "components"], []),
        (2, ["metadata", "component", "properties"], []),
    ],
)
def test_invalid_coverage_blocks_even_with_zero_findings(
    index: int, path: list[str], value: Any
) -> None:
    values = fixture()
    container = values[index]
    for name in path[:-1]:
        container = container[name]
    container[path[-1]] = value
    with pytest.raises(ValueError):
        MODULE["validate_scan_coverage"](*values, today=TODAY)


@pytest.mark.parametrize("field", ["Results", "CreatedAt", "Metadata", "Trivy"])
def test_missing_fields_are_not_empty_scans(field: str) -> None:
    values = fixture()
    values[1].pop(field)
    with pytest.raises(ValueError):
        MODULE["validate_scan_coverage"](*values, today=TODAY)


def test_findings_and_unknown_severity_are_counted_without_relabeling() -> None:
    item, report, sbom = fixture()
    finding = {
        "VulnerabilityID": "CVE-TEST",
        "PkgName": "pkg",
        "PkgID": "pkg@1",
        "InstalledVersion": "1",
        "Severity": "HIGH",
        "FixedVersion": "2",
    }
    report["Results"][0]["Vulnerabilities"] = [finding]
    with pytest.raises(ValueError, match="counts mismatch"):
        MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)
    item.update(counts={"HIGH": 1}, fix_available_count=1, untriaged_high_critical_count=1)
    MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)
    finding["Severity"] = "UNKNOWN"
    item.update(counts={"UNKNOWN": 1}, untriaged_high_critical_count=0)
    MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)
    finding["Severity"] = "NEW-SEVERITY"
    with pytest.raises(ValueError, match="unrecognized severity"):
        MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)


def test_missing_os_and_duplicate_results_are_rejected() -> None:
    values = fixture()
    result = values[1]["Results"][0]
    values[1]["Results"].append(copy.deepcopy(result))
    with pytest.raises(ValueError, match="duplicate scan result"):
        MODULE["validate_scan_coverage"](*values, today=TODAY)
    values[1]["Results"].pop()
    result.update(Class="lang-pkgs", Type="python-pkg")
    with pytest.raises(ValueError, match="OS package coverage"):
        MODULE["validate_scan_coverage"](*values, today=TODAY)


def test_language_finding_can_omit_pkgid_but_os_finding_cannot() -> None:
    item, report, sbom = fixture()
    finding = {
        "VulnerabilityID": "CVE-LANGUAGE",
        "PkgName": "package",
        "InstalledVersion": "1",
        "Severity": "MEDIUM",
    }
    report["Results"].append(
        {
            "Target": "Python",
            "Class": "lang-pkgs",
            "Type": "python-pkg",
            "Vulnerabilities": [finding],
        }
    )
    item["counts"] = {"MEDIUM": 1}
    MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)
    report["Results"].pop()
    report["Results"][0]["Vulnerabilities"] = [finding]
    with pytest.raises(ValueError, match="package ID"):
        MODULE["validate_scan_coverage"](item, report, sbom, today=TODAY)


def test_unique_complete_service_set_is_required_before_dict_construction() -> None:
    document: dict[str, Any] = {
        "complete": True,
        "images": [{"service": s} for s in MODULE["SERVICES"]],
    }
    assert set(MODULE["service_entries"](document, "images")) == MODULE["SERVICES"]
    document["images"][-1] = document["images"][0]
    with pytest.raises(ValueError, match="duplicate service"):
        MODULE["service_entries"](document, "images")
    document["images"].pop()
    with pytest.raises(ValueError, match="eight services"):
        MODULE["service_entries"](document, "images")


@pytest.mark.parametrize(
    "data",
    [
        b'{"complete":false,"complete":true}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e400}',
        b'{"x":-1e400}',
        b'{"nested":{"a":0,"a":1}}',
    ],
)
def test_duplicate_and_nonfinite_json_is_rejected(data: bytes) -> None:
    with pytest.raises(ValueError):
        MODULE["strict_json"](data)
    assert MODULE["strict_json"](json.dumps({"value": 0}).encode()) == {"value": 0}


def test_finite_json_floats_remain_supported() -> None:
    assert MODULE["strict_json"](b'{"value":1.25}') == {"value": 1.25}


@pytest.mark.parametrize(
    "case,error",
    [
        ("zero", None),
        ("medium-only", None),
        ("original-malformed", "complete"),
        ("missing-results", "missing scan results"),
        ("duplicate-service", "duplicate service"),
        ("duplicate-result", "duplicate scan result"),
        ("bad-counts", "severity counts mismatch"),
        ("sbom-truthy", "invalid SBOM component"),
        ("positive-overflow", "invalid_json"),
        ("negative-overflow", "invalid_json"),
        ("sbom-overflow", "invalid_json"),
    ],
)
def test_main_coverage_gate_with_synthetic_retained_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, error: str | None
) -> None:
    bundle = Bundle(tmp_path, high=False)
    scans = tmp_path / "scans"
    images = bundle.inventory["images"]
    proofs = []
    for item in images:
        service = item["service"]
        report, sbom = bundle.scans[service], bundle.sboms[service]
        report["CreatedAt"] = "2020-01-01T00:00:00Z"
        if service == "api":
            if case == "original-malformed":
                item.update(complete=False, counts={"HIGH": 1})
                report = {"Metadata": {"ImageID": item["image_config_id"]}}
                sbom = {}
            elif case == "missing-results":
                report.pop("Results")
            elif case == "duplicate-result":
                report["Results"].append(copy.deepcopy(report["Results"][0]))
            elif case == "bad-counts":
                item["counts"] = {"HIGH": 1}
            elif case == "sbom-truthy":
                sbom["components"] = [{"name": ["not-a-string"], "type": 7}]
            elif case == "medium-only":
                report["Results"][0]["Vulnerabilities"] = [
                    {
                        "VulnerabilityID": "CVE-TEST",
                        "PkgName": "pkg",
                        "PkgID": "pkg@1",
                        "InstalledVersion": "1",
                        "Severity": "MEDIUM",
                    }
                ]
                item["counts"] = {"MEDIUM": 1}
        for key, document in (("scan", report), ("sbom", sbom)):
            raw = json.dumps(document).encode()
            overflow = service == "api" and (
                (key == "scan" and case in {"positive-overflow", "negative-overflow"})
                or (key == "sbom" and case == "sbom-overflow")
            )
            if overflow:
                number = b"-1e400" if case == "negative-overflow" else b"1e400"
                raw = raw[:-1] + b',"overflow":' + number + b"}"
            bundle.put("scans/" + item[key], raw)
            item[f"{key}_sha256"] = hashlib.sha256(raw).hexdigest()
        proofs.append({"service": service, "image_id": item["image_id"], "architecture": "arm64"})
    if case == "duplicate-service":
        images[-1] = images[0]
    bundle.put("scans/inventory.json", bundle.inventory)
    bundle.put("synthetic-proof.json", {"complete": True, "images": proofs})
    bundle.put(
        "synthetic-assessments.json",
        {
            "schema_version": 1,
            "scope": "synthetic coverage only",
            "reviewed_on": "2020-01-01",
            "expires_on": "2020-01-02",
            "rules": [],
        },
    )
    bundle.put(
        "synthetic-records.json",
        {
            "schema_version": 4,
            "deployment_sha256": "0" * 64,
            "deployment_files": [],
            "source_archive": "synthetic",
            "records": [],
        },
    )
    # Real bounded-reader checks against disposable files, never historical evidence.
    monkeypatch.setitem(MODULE["main"].__globals__, "deployment_digest", lambda root: "0" * 64)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check-image-findings.py",
            "--scans",
            str(scans),
            "--proof",
            str(tmp_path / "synthetic-proof.json"),
            "--assessments",
            str(tmp_path / "synthetic-assessments.json"),
            "--reviewed-findings",
            str(tmp_path / "synthetic-records.json"),
        ],
    )
    if error is not None:
        with pytest.raises(ValueError, match=error):
            MODULE["main"]()
        assert not (scans / "dispositions.json").exists()
    else:
        MODULE["main"]()
        output = json.loads((scans / "dispositions.json").read_bytes())
        assert output["passed"] is True
        assert output["raw_high_critical"] == output["unresolved_high_critical"] == 0
        assert output["findings"] == []
