"""The stopped optional runtime is blocked evidence, never a passing application waiver."""

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

ROOT = Path("security/model-runtime")


def verify_records(assessment: dict[str, Any], report: dict[str, Any]) -> None:
    findings = [v for r in report["Results"] for v in r.get("Vulnerabilities", []) or []]
    high = [v for v in findings if v["Severity"] in {"HIGH", "CRITICAL"}]
    records = assessment["records"]
    assert len(records) == len(high) == assessment["blocked_high_critical"]
    assert assessment["untriaged_high_critical"] == 0
    assert assessment["runtime_qualified"] is False
    assert assessment["status"] == "LIVE_MODEL_VALIDATION_BLOCKED"
    assert assessment["raw_total"] == len(findings)
    for finding in high:
        matches = [
            r
            for r in records
            if (r["package"], r["installed_version"], r["advisory"])
            == (finding["PkgName"], finding["InstalledVersion"], finding["VulnerabilityID"])
        ]
        assert len(matches) == 1
        row = matches[0]
        assert (
            row["finding_sha256"]
            == hashlib.sha256(
                json.dumps(finding, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        assert row["decision"] == "block"
        assert row["severity"] == finding["Severity"]
        assert (
            row["shipped_runtime"] is False and row["used_in_optional_validation_runtime"] is True
        )
        assert row["scope"] == "runtime"
        assert row["scanner_version"] == report["Trivy"]["Version"]
        assert row["fixed_version"] == finding.get("FixedVersion", "")
        assert (
            date.fromisoformat(row["reviewed_on"])
            <= date.today()
            <= date.fromisoformat(row["expires_on"])
        )
        assert all(
            row[k] for k in ("evidence", "reachability", "exposure", "rationale", "artifact_sha256")
        )


def test_all_optional_runtime_high_critical_findings_remain_explicitly_blocked() -> None:
    assessment = json.loads((ROOT / "assessment.json").read_bytes())
    report = json.loads(gzip.decompress((ROOT / "ollama-arm64.scan.json.gz").read_bytes()))
    verify_records(assessment, report)
    for item in json.loads((ROOT / "manifest.json").read_text())["files"]:
        raw = (ROOT / item["path"]).read_bytes()
        if item["path"].endswith(".gz"):
            assert hashlib.sha256(raw).hexdigest() == item["compressed_sha256"]
            assert hashlib.sha256(gzip.decompress(raw)).hexdigest() == item["uncompressed_sha256"]
        else:
            assert hashlib.sha256(raw).hexdigest() == item["sha256"]


@pytest.mark.parametrize("change", ["missing", "waiver", "changed", "expired", "qualified"])
def test_model_runtime_record_cannot_silently_become_qualified(change: str) -> None:
    assessment = json.loads((ROOT / "assessment.json").read_bytes())
    report = json.loads(gzip.decompress((ROOT / "ollama-arm64.scan.json.gz").read_bytes()))
    if change == "missing":
        assessment["records"].pop()
    elif change == "waiver":
        assessment["records"][0]["decision"] = "accept"
    elif change == "changed":
        assessment["records"][0]["finding_sha256"] = "changed"
    elif change == "expired":
        assessment["records"][0]["expires_on"] = "2000-01-01"
    else:
        assessment["runtime_qualified"] = True
    with pytest.raises(AssertionError):
        verify_records(assessment, report)
