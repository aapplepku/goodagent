"""An applicability record must not silently approve new or unproven findings."""

import json
import runpy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path("scripts/check-image-findings.py")
ASSESSMENTS = MODULE["Assessments"].model_validate_json(
    Path("security/image-assessments.json").read_bytes()
)
REVIEW_CONTEXT = json.loads(Path("security/reviewed-image-findings.json").read_bytes())
REVIEW_DATE = max(date.fromisoformat(row["reviewed_on"]) for row in REVIEW_CONTEXT["records"])


def test_shopper_runtime_and_setup_participate_in_security_review_identity() -> None:
    assert "shopper" in MODULE["SERVICES"]
    assert "shopper" in MODULE["DEBIAN_SERVICES"]
    files = MODULE["deployment_files"](Path.cwd())
    assert "apps/shopper/Dockerfile" in files
    assert "apps/shopper/package.json" in files
    assert "apps/shopper/next.config.ts" in files
    assert "scripts/setup_self_hosted.py" in files
    assert ".dockerignore" in files
    assert any(path.startswith("apps/shopper/src/") for path in files)


def facts() -> dict[str, Any]:
    return {
        "process": {
            "Uid": "10001 10001 10001 10001",
            "NoNewPrivs": "1",
            "CapEff": "0000000000000000",
            "CapPrm": "0000000000000000",
            "CapBnd": "0000000000000000",
        },
        "setuid_setgid_files_in_runtime_paths": [],
        "absent_components": ["/usr/bin/perl", "/usr/bin/perl5.40.1"],
    }


def finding() -> dict[str, str]:
    return {
        "VulnerabilityID": "CVE-2026-13221",
        "PkgName": "perl-base",
        "InstalledVersion": "5.40.1-6",
    }


def test_exact_removed_component_has_scoped_disposition() -> None:
    status, _ = MODULE["disposition"](
        finding(), "api", facts(), ASSESSMENTS, today=date(2026, 9, 5)
    )
    assert status == "not_affected"


@pytest.mark.parametrize(
    "field,value",
    [
        ("VulnerabilityID", "CVE-2026-UNREVIEWED"),
        ("PkgName", "another-package"),
        ("InstalledVersion", "5.40.1-7"),
    ],
)
def test_unreviewed_advisory_or_package_version_stays_blocking(field: str, value: str) -> None:
    changed = {**finding(), field: value}
    status, _ = MODULE["disposition"](changed, "api", facts(), ASSESSMENTS, today=date(2026, 9, 5))
    assert status == "unresolved"


@pytest.mark.parametrize(
    "key,value",
    [
        ("Uid", "0 0 0 0"),
        ("Uid", ""),
        ("NoNewPrivs", "0"),
        ("CapEff", "0000000000000001"),
        ("CapPrm", "0000000000000001"),
        ("CapBnd", "0000000000000001"),
    ],
)
def test_weakened_privilege_controls_invalidate_assessment(key: str, value: str) -> None:
    proof = facts()
    proof["process"][key] = value
    status, _ = MODULE["disposition"](finding(), "api", proof, ASSESSMENTS, today=date(2026, 9, 5))
    assert status == "unresolved"


@pytest.mark.parametrize(
    "key,value",
    [
        ("absent_components", []),
        ("setuid_setgid_files_in_runtime_paths", ["/usr/bin/su"]),
    ],
)
def test_absence_proof_is_required(key: str, value: list[str]) -> None:
    proof = {**facts(), key: value}
    status, _ = MODULE["disposition"](finding(), "api", proof, ASSESSMENTS, today=date(2026, 9, 5))
    assert status == "unresolved"


@pytest.mark.parametrize("today", [date(2026, 9, 4), date(2026, 10, 6)])
def test_assessment_date_bounds_are_enforced(today: date) -> None:
    status, _ = MODULE["disposition"](finding(), "api", facts(), ASSESSMENTS, today=today)
    assert status == "unresolved"


def test_investigation_is_not_a_passing_exception() -> None:
    unresolved = {
        "VulnerabilityID": "CVE-2026-11822",
        "PkgName": "libsqlite3-0",
        "InstalledVersion": "3.46.1-7+deb13u1",
    }
    investigating = ASSESSMENTS.model_copy(
        update={
            "rules": [
                rule.model_copy(update={"status": "under_investigation"})
                for rule in ASSESSMENTS.rules
            ]
        }
    )
    proof = {
        **facts(),
        "storage_construction_or_native_dependencies": (
            "postgresql-and-remote-qdrant; no SQLite connections"
        ),
    }
    status, _ = MODULE["disposition"](
        unresolved, "api", proof, investigating, today=date(2026, 9, 5)
    )
    assert status == "under_investigation"


@pytest.mark.parametrize(
    "service,storage,expected",
    [
        ("api", "", "unresolved"),
        ("api", "sqlite local client", "unresolved"),
        ("api", "postgresql-and-remote-qdrant; no SQLite connections", "not_affected"),
        ("web", "", "unresolved"),
        ("web", "libc.so.6 libsqlite3.so.0", "unresolved"),
        ("qdrant", "libc.so.6 libgcc_s.so.1", "not_affected"),
    ],
)
def test_sqlite_assessment_requires_service_specific_evidence(
    service: str,
    storage: str,
    expected: str,
) -> None:
    vulnerability = {
        "VulnerabilityID": "CVE-2026-11822",
        "PkgName": "libsqlite3-0",
        "InstalledVersion": "3.46.1-7+deb13u1",
    }
    proof = {**facts(), "storage_construction_or_native_dependencies": storage}
    status, _ = MODULE["disposition"](
        vulnerability,
        service,
        proof,
        ASSESSMENTS,
        today=date(2026, 9, 5),
    )
    assert status == expected


def test_other_service_has_no_blanket_exception() -> None:
    status, _ = MODULE["disposition"](
        finding(), "postgres", facts(), ASSESSMENTS, today=date(2026, 9, 5)
    )
    assert status == "unresolved"


def reviewed_case() -> tuple[dict[str, Any], ...]:
    case = synthetic_case()
    # Mutation tests start accepted; no historical review is converted to schema 4.
    assert record_status(case, reviewed_records()) == "not_affected"
    return case


def synthetic_case() -> tuple[dict[str, Any], ...]:
    vulnerability = {**finding(), "PkgID": "perl-base@5.40.1-6", "Severity": "HIGH"}
    item = {
        "service": "api",
        "scanner": MODULE["SCANNER"],
        "image_id": "sha256:" + "a" * 64,
        "image_config_id": "sha256:" + "b" * 64,
        "architecture": "arm64",
    }
    result = {"Target": "synthetic-api", "Class": "os-pkgs", "Type": "debian"}
    report = {
        "ArtifactType": "container_image",
        "ArtifactID": item["image_config_id"],
        "Trivy": {"Version": "0.74.0"},
        "CreatedAt": f"{REVIEW_DATE}T00:00:00Z",
        "Metadata": {"ImageConfig": {"architecture": "arm64"}, "OS": {"Family": "debian"}},
    }
    vulnerability["Fingerprint"] = MODULE["scanner_fingerprint"](vulnerability, result, report)
    return vulnerability, result, report, item, facts()


def reviewed_records() -> Any:
    vulnerability, result, report, item, _ = synthetic_case()
    rule = next(rule for rule in ASSESSMENTS.rules if rule.name == "removed-perl-runtime")
    record = {
        "service": "api",
        "scanner": "trivy",
        "scanner_version": "0.74.0",
        "scanner_image": MODULE["SCANNER"],
        "scan_date": REVIEW_DATE.isoformat(),
        "review_owner": "Synthetic fixture; no real approval",
        "artifact_type": "container_image",
        "reviewed_image_id": item["image_id"],
        "reviewed_image_config_id": item["image_config_id"],
        "architecture": "arm64",
        "package": vulnerability["PkgName"],
        "installed_version": vulnerability["InstalledVersion"],
        "advisory": vulnerability["VulnerabilityID"],
        "severity": "HIGH",
        "shipped_runtime": True,
        "scope": "runtime",
        "reachability": "Synthetic component-absence case",
        "exposure": "Synthetic non-root runtime",
        "fixed_version": "",
        "fixed_version_available": False,
        "decision": "not-applicable",
        "evidence": ["synthetic-runtime-facts"],
        "rationale": "Fixture only; not an evidence adoption",
        "reviewed_on": REVIEW_DATE.isoformat(),
        "expires_on": ASSESSMENTS.expires_on.isoformat(),
        "rule": rule.name,
        "rule_sha256": MODULE["digest"](rule.model_dump(mode="json")),
        "finding_sha256": MODULE["finding_digest"](vulnerability, result, report),
    }
    document = {
        "schema_version": 4,
        "deployment_sha256": "c" * 64,
        "deployment_files": [],
        "source_archive": "synthetic-only",
        "records": [record],
    }
    return MODULE["ReviewedRecords"].model_validate_json(json.dumps(document))


def record_status(
    case: tuple[dict[str, Any], ...], records: Any, deployment: str | None = None
) -> str:
    status, _, _ = MODULE["record_disposition"](
        *case,
        ASSESSMENTS,
        records,
        deployment or records.deployment_sha256,
        today=REVIEW_DATE,
    )
    return str(status)


def test_synthetic_reviewed_record_passes_with_exact_scanner_and_proof() -> None:
    assert record_status(reviewed_case(), reviewed_records()) == "not_affected"


def test_schema_three_review_is_rejected_without_implicit_config_adoption() -> None:
    document = reviewed_records().model_dump(mode="json")
    document["schema_version"] = 3
    with pytest.raises(ValueError, match="review schema 4 required"):
        MODULE["ReviewedRecords"].model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    "field,value",
    [
        ("FixedVersion", "5.0-fixed"),
        ("Severity", "CRITICAL"),
        ("Description", "new reachable remote attack"),
        ("Status", "fixed"),
        ("LastModifiedDate", "2026-09-06T00:00:00Z"),
        ("NewScannerField", "unreviewed"),
        ("InstalledVersion", "unreviewed-version"),
        ("VulnerabilityID", "new-advisory"),
        ("Fingerprint", "unreviewed-fingerprint"),
    ],
)
def test_any_changed_finding_requires_review(field: str, value: str) -> None:
    case = reviewed_case()
    case[0][field] = value
    assert record_status(case, reviewed_records()) == "unresolved"


@pytest.mark.parametrize(
    "change", ["scanner", "architecture", "deployment", "image", "missing", "duplicate"]
)
def test_changed_artifact_context_or_missing_record_blocks(change: str) -> None:
    case, records = reviewed_case(), reviewed_records()
    if change == "scanner":
        case[2]["Trivy"]["Version"] = "0.75.0"
    if change == "architecture":
        case[3]["architecture"] = "amd64"
    if change == "image":
        case[3]["image_id"] = "sha256:" + "f" * 64
    if change == "missing":
        records.records = []
    if change == "duplicate":
        records.records *= 2
    assert (
        record_status(case, records, "changed" if change == "deployment" else None) == "unresolved"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "dev"),
        ("shipped_runtime", False),
        ("decision", "accept"),
        ("decision", "mitigate"),
        ("decision", "block"),
        ("expires_on", date(2026, 9, 4)),
        ("reviewed_on", REVIEW_DATE + timedelta(days=1)),
        ("rule_sha256", "0" * 64),
        ("fixed_version_available", True),
        ("scan_date", REVIEW_DATE + timedelta(days=1)),
        ("scan_date", REVIEW_DATE - timedelta(days=1)),
        ("reviewed_image_id", "sha256:" + "f" * 64),
    ],
)
def test_runtime_risk_cannot_be_waived_or_misclassified(field: str, value: Any) -> None:
    records = reviewed_records()
    records.records = [r.model_copy(update={field: value}) for r in records.records]
    assert record_status(reviewed_case(), records) == "unresolved"


@pytest.mark.parametrize(
    "field",
    [
        "reachability",
        "exposure",
        "evidence",
        "reviewed_on",
        "expires_on",
        "scan_date",
        "review_owner",
        "reviewed_image_config_id",
    ],
)
def test_required_review_fields_cannot_be_missing(field: str) -> None:
    record = reviewed_records().records[0].model_dump(mode="json")
    del record[field]
    with pytest.raises(ValueError):
        MODULE["RecordAssessment"].model_validate_json(json.dumps(record))


@pytest.mark.parametrize(
    "value",
    [None, "invalid", f"{REVIEW_DATE + timedelta(days=1)}T00:00:00Z", "2026-09-05"],
)
def test_missing_invalid_or_future_scan_date_blocks(value: str | None) -> None:
    case = reviewed_case()
    case[2]["CreatedAt"] = value
    assert record_status(case, reviewed_records()) == "unresolved"


@pytest.mark.parametrize(
    "time_part,expected",
    [("01:00:00+01:00", "not_affected"), ("00:30:00+01:00", "unresolved")],
)
def test_scan_date_is_bound_in_utc(time_part: str, expected: str) -> None:
    case = reviewed_case()
    case[2]["CreatedAt"] = f"{REVIEW_DATE}T{time_part}"
    assert record_status(case, reviewed_records()) == expected


def test_blank_review_owner_is_rejected() -> None:
    record = reviewed_records().records[0].model_dump(mode="json")
    record["review_owner"] = "   "
    with pytest.raises(ValueError):
        MODULE["RecordAssessment"].model_validate_json(json.dumps(record))


def test_review_context_covers_current_deployment() -> None:
    # Keep the historical mismatch visible; do not replace it with synthetic pins.
    assert {r["path"]: r["sha256"] for r in REVIEW_CONTEXT["deployment_files"]} == MODULE[
        "deployment_files"
    ](Path("."))
    assert REVIEW_CONTEXT["deployment_sha256"] == MODULE["deployment_digest"](Path("."))


def test_generated_package_metadata_does_not_bind_checkout_reachability(
    tmp_path: Path,
) -> None:
    import shutil

    root = Path(".")
    for relative in MODULE["deployment_files"](root):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    before = MODULE["deployment_digest"](tmp_path)
    generated = tmp_path / "packages/backend/src/open_commerce_backend.egg-info/PKG-INFO"
    generated.parent.mkdir(parents=True)
    generated.write_text("Host-generated packaging metadata is not application source")
    assert MODULE["deployment_digest"](tmp_path) == before
    runtime = tmp_path / "packages/backend/src/open_commerce/unreviewed.py"
    runtime.write_text("NEW_RUNTIME_PATH = True\n")
    assert MODULE["deployment_digest"](tmp_path) != before


def test_changed_layer_ids_require_new_exact_record_review() -> None:
    case = reviewed_case()
    case[0]["Layer"] = {"Digest": "different-build", "DiffID": "different-build"}
    assert record_status(case, reviewed_records()) == "unresolved"


def test_changed_image_needs_new_review_even_with_valid_fingerprint() -> None:
    case = reviewed_case()
    case[2]["ArtifactID"] = "sha256:" + "f" * 64
    case[3]["image_id"] = "sha256:" + "f" * 64
    assert record_status(case, reviewed_records()) == "unresolved"
    case[0]["Fingerprint"] = MODULE["scanner_fingerprint"](case[0], case[1], case[2])
    assert record_status(case, reviewed_records()) == "unresolved"
