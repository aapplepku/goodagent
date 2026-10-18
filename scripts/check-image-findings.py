"""Fail closed on unreviewed HIGH/CRITICAL findings; retain original severities."""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import check_release_assessments as identity_gate

SERVICES = {"api", "migrate", "worker", "web", "shopper", "postgres", "redis", "qdrant"}
DEBIAN_SERVICES = {"api", "migrate", "worker", "web", "shopper", "qdrant"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}
COMPONENT_TYPES = {
    "application",
    "framework",
    "library",
    "container",
    "platform",
    "operating-system",
    "device",
    "device-driver",
    "firmware",
    "file",
    "machine-learning-model",
    "data",
    "cryptographic-asset",
}
SCANNER = (
    "aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def strict_json(data: bytes) -> Any:
    def pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in entries:
            require(name not in result, "duplicate JSON key")
            result[name] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError("non-finite JSON value")

    def finite_float(value: str) -> float:
        number = float(value)
        require(math.isfinite(number), "non-finite JSON value")
        return number

    return json.loads(
        data, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float
    )


def service_entries(document: dict[str, Any], field: str) -> dict[str, dict[str, Any]]:
    require(isinstance(document, dict), "invalid collection document")
    require(document.get("complete") is True, "incomplete collection")
    entries = document.get(field)
    if not isinstance(entries, list) or len(entries) != len(SERVICES):
        raise ValueError("eight services required")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        require(isinstance(entry, dict), "invalid service entry")
        name = entry.get("service")
        require(isinstance(name, str) and name in SERVICES, "unknown service")
        require(name not in result, "duplicate service")
        result[name] = entry
    require(set(result) == SERVICES, "missing service")
    return result


def validate_scan_coverage(
    item: dict[str, Any], report: dict[str, Any], sbom: dict[str, Any], *, today: date
) -> None:
    """An empty finding set is valid only after complete, matching scan coverage."""
    require(all(isinstance(v, dict) for v in (item, report, sbom)), "invalid scan document")
    require(item.get("complete") is True, "incomplete image scan")
    require(
        all(
            isinstance(item.get(k), str) and re.fullmatch(r"sha256:[0-9a-f]{64}", item[k])
            for k in ("image_id", "image_config_id")
        ),
        "invalid image identity",
    )
    require(item.get("scanner") == SCANNER, "unrecognized scanner image")
    require(
        type(report.get("SchemaVersion")) is int and report["SchemaVersion"] == 2,
        "unrecognized report schema",
    )
    require(report.get("ArtifactType") == "container_image", "wrong artifact type")
    require(report.get("Trivy") == {"Version": "0.74.0"}, "unrecognized scanner version")
    metadata = report.get("Metadata")
    if not isinstance(metadata, dict):
        raise ValueError("missing image metadata")
    require(
        report.get("ArtifactID") == metadata.get("ImageID") == item.get("image_config_id")
        and isinstance(item.get("image_config_id"), str),
        "scan image config mismatch",
    )
    config = metadata.get("ImageConfig")
    if not isinstance(config, dict):
        raise ValueError("missing image configuration")
    require(
        config.get("architecture") == item.get("architecture")
        and item.get("architecture") in {"arm64", "amd64"},
        "scan platform mismatch",
    )
    os_info = metadata.get("OS")
    if not isinstance(os_info, dict) or os_info.get("Family") not in {"debian", "alpine"}:
        raise ValueError("unknown OS")
    try:
        scanned_at = datetime.fromisoformat(report["CreatedAt"])
        require(scanned_at.tzinfo is not None, "scan date requires timezone")
        require(scanned_at.astimezone(UTC).date() <= today, "future scan")
    except (KeyError, TypeError) as error:
        raise ValueError("missing scan date") from error
    results = report.get("Results")
    if not isinstance(results, list) or not results:
        raise ValueError("missing scan results")
    counts: Counter[str] = Counter()
    fixes = 0
    targets: set[tuple[str, str, str]] = set()
    os_seen = False
    for result in results:
        require(isinstance(result, dict), "invalid result")
        target, kind, category = (result.get(k) for k in ("Target", "Type", "Class"))
        require(
            all(isinstance(v, str) and v for v in (target, kind, category)),
            "missing result identity",
        )
        require(category in {"os-pkgs", "lang-pkgs"}, "unexpected scanner result class")
        identity = (target, kind, category)
        require(identity not in targets, "duplicate scan result")
        targets.add(identity)
        if category == "os-pkgs":
            require(kind == os_info["Family"], "OS coverage mismatch")
            os_seen = True
        findings = result.get("Vulnerabilities", [])
        require(isinstance(findings, list), "malformed vulnerabilities")
        for finding in findings:
            require(isinstance(finding, dict), "malformed finding")
            require(
                all(
                    isinstance(finding.get(k), str) and finding[k]
                    for k in ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
                ),
                "missing finding identity",
            )
            if category == "os-pkgs" or "PkgID" in finding:
                require(
                    isinstance(finding.get("PkgID"), str) and bool(finding["PkgID"]),
                    "invalid package ID",
                )
            require(finding["Severity"] in SEVERITIES, "unrecognized severity")
            counts[finding["Severity"]] += 1
            fixes += bool(finding.get("FixedVersion"))
    require(os_seen, "OS package coverage missing")
    recorded = item.get("counts")
    if not isinstance(recorded, dict):
        raise ValueError("missing severity counts")
    require(
        all(k in SEVERITIES and type(v) is int and v >= 0 for k, v in recorded.items()),
        "invalid severity counts",
    )
    require(recorded == dict(counts), "severity counts mismatch")
    require(
        type(item.get("fix_available_count")) is int and item["fix_available_count"] == fixes,
        "fix counts mismatch",
    )
    require(
        type(item.get("untriaged_high_critical_count")) is int
        and item["untriaged_high_critical_count"] == counts["HIGH"] + counts["CRITICAL"],
        "HIGH/CRITICAL counts mismatch",
    )
    require(
        sbom.get("bomFormat") == "CycloneDX" and sbom.get("specVersion") == "1.7",
        "invalid SBOM format",
    )
    require(type(sbom.get("version")) is int and sbom["version"] >= 1, "invalid SBOM version")
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("SBOM package coverage missing")
    require(
        all(
            isinstance(c, dict)
            and isinstance(c.get("name"), str)
            and bool(c["name"].strip())
            and isinstance(c.get("type"), str)
            and c["type"] in COMPONENT_TYPES
            for c in components
        ),
        "invalid SBOM component",
    )
    meta = sbom.get("metadata")
    if not isinstance(meta, dict):
        raise ValueError("missing SBOM metadata")
    tools = meta.get("tools")
    if not isinstance(tools, dict) or not isinstance(tools.get("components"), list):
        raise ValueError("missing SBOM scanner")
    require(
        any(
            isinstance(t, dict) and t.get("name") == "trivy" and t.get("version") == "0.74.0"
            for t in tools["components"]
        ),
        "SBOM scanner mismatch",
    )
    component = meta.get("component")
    if not isinstance(component, dict) or component.get("type") != "container":
        raise ValueError("missing SBOM image")
    properties = component.get("properties")
    if not isinstance(properties, list) or not all(isinstance(p, dict) for p in properties):
        raise ValueError("invalid SBOM image properties")
    ids = [p.get("value") for p in properties if p.get("name") == "aquasecurity:trivy:ImageID"]
    require(ids == [item["image_config_id"]], "SBOM image mismatch")


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: Literal["not_affected", "under_investigation"]
    vulnerabilities: list[str]
    packages: dict[str, list[str]]
    required_absent: list[str]
    requires_storage_proof: bool = False
    reason: str
    references: list[str]


class Assessments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    scope: str
    reviewed_on: date
    expires_on: date
    rules: list[Rule]


class RecordAssessment(BaseModel):
    """One reviewed scanner record, not an advisory-wide severity suppression."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    service: str
    scanner: Literal["trivy"]
    scanner_version: str = Field(min_length=1)
    scanner_image: str = Field(min_length=1)
    scan_date: date
    review_owner: str = Field(min_length=1)
    artifact_type: Literal["container_image"]
    reviewed_image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reviewed_image_config_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    architecture: str = Field(min_length=1)
    package: str = Field(min_length=1)
    installed_version: str = Field(min_length=1)
    advisory: str = Field(min_length=1)
    severity: Literal["HIGH", "CRITICAL"]
    shipped_runtime: bool
    scope: Literal["runtime", "build", "dev", "test"]
    reachability: str = Field(min_length=1)
    exposure: str = Field(min_length=1)
    fixed_version: str
    fixed_version_available: bool
    decision: Literal["block", "mitigate", "accept", "not-applicable"]
    evidence: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    reviewed_on: date
    expires_on: date
    rule: str = Field(min_length=1)
    rule_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reviewed_image_config_id", mode="before")
    @classmethod
    def exact_config_id(cls, value: Any) -> str:
        require(
            isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None,
            "invalid reviewed image config ID",
        )
        return str(value)


class DeploymentFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewedRecords(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[4]
    deployment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deployment_files: list[DeploymentFile]
    source_archive: str = Field(min_length=1)
    records: list[RecordAssessment]

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema_version(cls, value: Any) -> int:
        require(type(value) is int and value == 4, "review schema 4 required")
        return int(value)


def retained_image(
    reader: identity_gate.BundleReader, item: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate collected image/config relationships without equating their IDs."""
    image = identity_gate.InventoryImage.model_validate(item)

    def ref(path: str, checksum: str) -> identity_gate.FileRef:
        raw, _ = reader.read(path)
        return identity_gate.FileRef(path=path, sha256=checksum, size=len(raw))

    inputs = image.identity_inputs
    artifacts = identity_gate.ImageArtifacts(
        service=image.service,
        scan=ref(image.scan, image.scan_sha256),
        sbom=ref(image.sbom, image.sbom_sha256),
        manifest=ref(inputs.manifest.file, inputs.manifest.sha256),
        config=ref(inputs.config.file, inputs.config.sha256),
        inspection=ref(inputs.inspection.file, inputs.inspection.sha256),
    )
    return identity_gate.validate_image(reader, "inventory.json", image, artifacts)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def deployment_files(root: Path) -> dict[str, str]:
    """Invalidate reachability review when application, dependencies or isolation change."""
    paths = {
        path
        for directory in (
            "packages/backend/src",
            "packages/sdk-typescript/src",
            "apps/web/src",
            "apps/shopper/src",
            "infra/docker",
            "infra/patches",
            "security/third-party/learned-search",
        )
        for path in (root / directory).rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
        and path.suffix != ".pyc"
        and "__tests__" not in path.parts
        and ".test." not in path.name
    }
    paths.update(
        root / name
        for name in (
            "docker-compose.yml",
            ".env.example",
            "uv.lock",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
            "pyproject.toml",
            "packages/backend/pyproject.toml",
            "package.json",
            "apps/web/package.json",
            "apps/web/next.config.ts",
            "apps/shopper/package.json",
            "apps/shopper/next.config.ts",
            "apps/api/Dockerfile",
            "apps/worker/Dockerfile",
            "apps/web/Dockerfile",
            "apps/shopper/Dockerfile",
            ".dockerignore",
            "scripts/setup_self_hosted.py",
            "scripts/probe-python-storage.py",
            "scripts/verify-runtime-images.py",
            "scripts/observe_runtime_workload.py",
            "scripts/probe-runtime-workload.sh",
            "scripts/probe-image-components.sh",
            "scripts/verify_learned_search_runtime.py",
        )
    )
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }


def deployment_digest(root: Path) -> str:
    return digest(deployment_files(root))


def finding_digest(finding: dict[str, Any], result: dict[str, Any], report: dict[str, Any]) -> str:
    # Schema 4 pins the entire finding, including layer provenance and scanner fingerprint.
    return digest(
        {
            "finding": finding,
            "scanner": report.get("Trivy"),
            "artifact_type": report.get("ArtifactType"),
            "os": report.get("Metadata", {}).get("OS"),
            "architecture": report.get("Metadata", {}).get("ImageConfig", {}).get("architecture"),
            "class": result.get("Class"),
            "type": result.get("Type"),
            "target": result.get("Target"),
        }
    )


def scanner_fingerprint(
    finding: dict[str, Any], result: dict[str, Any], report: dict[str, Any]
) -> str:
    # Trivy v0.74.0: SHA-256(ArtifactID:Target:PkgID:VulnerabilityID).
    value = ":".join(
        str(value)
        for value in (
            report.get("ArtifactID"),
            result.get("Target"),
            finding.get("PkgID"),
            finding.get("VulnerabilityID"),
        )
    )
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def record_disposition(
    finding: dict[str, Any],
    result: dict[str, Any],
    report: dict[str, Any],
    item: dict[str, Any],
    proof: dict[str, Any],
    assessments: Assessments,
    reviewed: ReviewedRecords,
    deployment: str,
    *,
    today: date,
) -> tuple[str, str, RecordAssessment | None]:
    matches = [
        r
        for r in reviewed.records
        if (r.service, r.package, r.installed_version, r.advisory)
        == (
            item["service"],
            finding["PkgName"],
            finding["InstalledVersion"],
            finding["VulnerabilityID"],
        )
    ]
    record = matches[0] if len(matches) == 1 else None
    if record is None:
        return "unresolved", "missing or duplicate per-record assessment", None
    if finding.get("Fingerprint") != scanner_fingerprint(finding, result, report):
        return "unresolved", "scanner fingerprint does not match raw artifact identity", record
    if deployment != reviewed.deployment_sha256:
        return "unresolved", "deployment changed: reachability review required", record
    try:
        scanned_at = datetime.fromisoformat(report["CreatedAt"])
        if scanned_at.tzinfo is None or scanned_at.astimezone(UTC).date() > today:
            raise ValueError("scan timestamp must be timezone-aware and not future-dated")
    except (KeyError, TypeError, ValueError):
        return "unresolved", "raw scan date missing, invalid or future-dated", record
    if record.scan_date > record.reviewed_on:
        return "unresolved", "assessment predates its reviewed scan", record
    if record.scan_date != scanned_at.astimezone(UTC).date():
        return "unresolved", "scan date differs from reviewed raw evidence", record
    if record.reviewed_image_id != item.get("image_id"):
        return "unresolved", "exact image changed: applicability review required", record
    if record.reviewed_image_config_id != item.get("image_config_id"):
        return "unresolved", "exact image config changed: applicability review required", record
    if not record.reviewed_on <= today <= record.expires_on:
        return "unresolved", "record review is future-dated or expired", record
    if record.finding_sha256 != finding_digest(finding, result, report):
        return "unresolved", "raw finding or scanner context changed", record
    if (
        record.scanner_version != report.get("Trivy", {}).get("Version")
        or record.scanner_image != item.get("scanner")
        or record.architecture != item.get("architecture")
        or record.artifact_type != report.get("ArtifactType")
        or record.severity != finding["Severity"]
        or record.fixed_version != (finding.get("FixedVersion") or "")
        or record.fixed_version_available != bool(finding.get("FixedVersion"))
        or not record.shipped_runtime
        or record.scope != "runtime"
    ):
        return (
            "unresolved",
            "assessment identity, fix availability or runtime scope differs",
            record,
        )
    rules = [rule for rule in assessments.rules if rule.name == record.rule]
    if len(rules) != 1 or digest(rules[0].model_dump(mode="json")) != record.rule_sha256:
        return "unresolved", "applicability rule changed or missing", record
    if record.decision != "not-applicable":
        return "unresolved", "applicable shipped-runtime finding remains blocking", record
    status, reason = disposition(finding, item["service"], proof, assessments, today=today)
    if result.get("Type") != "debian" or reason != record.rule:
        return "unresolved", "component proof does not match reviewed rule", record
    return status, reason, record


def disposition(
    finding: dict[str, Any],
    service: str,
    proof: dict[str, Any],
    assessments: Assessments,
    *,
    today: date,
) -> tuple[str, str]:
    if not assessments.reviewed_on <= today <= assessments.expires_on:
        return "unresolved", "assessment missing, future-dated or expired"
    if service not in DEBIAN_SERVICES:
        return "unresolved", "no applicability exception for this service"
    process = proof.get("process", {})
    uids = str(process.get("Uid", "")).split()
    if len(uids) != 4 or any(not uid.isdigit() or int(uid) == 0 for uid in uids):
        return "unresolved", "non-root proof missing"
    if (
        process.get("NoNewPrivs") != "1"
        or any(process.get(key) != "0000000000000000" for key in ("CapEff", "CapPrm", "CapBnd"))
        or proof.get("setuid_setgid_files_in_runtime_paths") != []
    ):
        return "unresolved", "privilege controls not proven"
    for rule in assessments.rules:
        if finding["VulnerabilityID"] not in rule.vulnerabilities:
            continue
        if finding["InstalledVersion"] not in rule.packages.get(finding["PkgName"], []):
            continue
        if not rule.reason or not rule.references:
            return "unresolved", "assessment lacks rationale or sources"
        if not set(rule.required_absent) <= set(proof.get("absent_components", [])):
            return "unresolved", f"{rule.name}: component absence not proven"
        if rule.requires_storage_proof:
            storage = proof.get("storage_construction_or_native_dependencies", "")
            if service in {"api", "worker", "migrate"}:
                if storage != "postgresql-and-remote-qdrant; no SQLite connections":
                    return "unresolved", "remote-only storage construction not proven"
            elif not storage or "libc.so" not in storage or "sqlite" in storage.lower():
                return "unresolved", "system SQLite native-linkage evidence missing or changed"
        return rule.status, rule.name
    return "unresolved", "no exact advisory/package/version assessment"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scans", type=Path, default=Path(".opencommerce/security-scans/final"))
    parser.add_argument(
        "--proof", type=Path, default=Path(".opencommerce/runtime-image-proof.json")
    )
    parser.add_argument("--assessments", type=Path, default=Path("security/image-assessments.json"))
    parser.add_argument(
        "--reviewed-findings", type=Path, default=Path("security/reviewed-image-findings.json")
    )
    args = parser.parse_args()
    assessment_raw = args.assessments.read_bytes()
    assessments = Assessments.model_validate_json(assessment_raw)
    reviewed_raw = args.reviewed_findings.read_bytes()
    identity_gate.strict_json(reviewed_raw)
    reviewed = ReviewedRecords.model_validate_json(reviewed_raw)
    deployment = deployment_digest(Path("."))
    proof_raw = args.proof.read_bytes()
    proof = strict_json(proof_raw)
    proofs = service_entries(proof, "images")
    rows = []
    with closing(identity_gate.BundleReader(args.scans)) as reader:
        inventory = identity_gate.strict_json(reader.read("inventory.json")[0])
        images = service_entries(inventory, "images")
        for service, item in sorted(images.items()):
            require(item.get("scan") == f"{service}.scan.json", "invalid scan filename")
            require(item.get("sbom") == f"{service}.cdx.json", "invalid SBOM filename")
            image_proof = proofs[service]
            if (
                image_proof["image_id"] != item["image_id"]
                or image_proof["architecture"] != item["architecture"]
            ):
                raise SystemExit(f"{service}: scan and runtime proof image IDs differ")
            report, sbom = retained_image(reader, item)
            validate_scan_coverage(item, report, sbom, today=datetime.now(UTC).date())
            for result in report["Results"]:
                for finding in result.get("Vulnerabilities", []):
                    if finding["Severity"] not in {"HIGH", "CRITICAL"}:
                        continue
                    status, reason, record = record_disposition(
                        finding,
                        result,
                        report,
                        item,
                        image_proof,
                        assessments,
                        reviewed,
                        deployment,
                        today=datetime.now(UTC).date(),
                    )
                    rows.append(
                        {
                            "service": service,
                            "image_id": item["image_id"],
                            "image_config_id": item["image_config_id"],
                            "advisory": finding["VulnerabilityID"],
                            "package": finding["PkgName"],
                            "installed_version": finding["InstalledVersion"],
                            "scanner_severity": finding["Severity"],
                            "status": status,
                            "assessment": reason,
                            "scanner": "trivy",
                            "scanner_version": report.get("Trivy", {}).get("Version"),
                            "scanner_image": item["scanner"],
                            "scan_date": report.get("CreatedAt"),
                            "review_owner": record.review_owner if record else None,
                            "artifact": report.get("ArtifactName"),
                            "raw_scan": item["scan"],
                            "raw_scan_sha256": item["scan_sha256"],
                            "finding_sha256": finding_digest(finding, result, report),
                            "fixed_version": finding.get("FixedVersion") or "",
                            "fixed_version_available": bool(finding.get("FixedVersion")),
                            "shipped_runtime": True,
                            "scope": "runtime",
                            "decision": "not-applicable" if status == "not_affected" else "block",
                            "review": record.model_dump(mode="json") if record else None,
                        }
                    )
        reader.recheck()
    unresolved = sum(row["status"] != "not_affected" for row in rows)
    (args.scans / "dispositions.json").write_text(
        json.dumps(
            {
                "passed": unresolved == 0,
                "unresolved_high_critical": unresolved,
                "raw_high_critical": len(rows),
                "findings": rows,
                "assessment_sha256": hashlib.sha256(assessment_raw).hexdigest(),
                "runtime_proof_sha256": hashlib.sha256(proof_raw).hexdigest(),
                "reviewed_records_sha256": hashlib.sha256(reviewed_raw).hexdigest(),
                "deployment_sha256": deployment,
                "scope": assessments.scope,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    print(f"{len(rows)} raw HIGH/CRITICAL entries; {unresolved} unresolved. No severity changed.")
    if unresolved:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
