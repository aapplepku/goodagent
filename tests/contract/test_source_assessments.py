"""Synthetic immutable bundles only; no scanners, captured programs or approvals."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from scripts import check_release_assessments as shared
from scripts import check_source_assessments as gate

NOW = datetime.now(UTC).replace(microsecond=0)
START = NOW - timedelta(hours=1)
CREATED = START - timedelta(hours=1)
END = START + timedelta(minutes=2)
REVIEW = END + timedelta(minutes=1)
EXPIRES = NOW + timedelta(days=7)
REJECTED = (ValueError, ValidationError, OSError, KeyError, TypeError, AttributeError)


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


class Bundle:
    def __init__(
        self,
        root: Path,
        *,
        python: bool = True,
        node: bool = True,
        membership: str = "dev",
        decision: str = "mitigate",
        extra_source_files: dict[str, bytes] | None = None,
    ) -> None:
        self.root = root
        self.source_files = {
            ".gitleaks.toml": b"title='synthetic'\n",
            "pyproject.toml": (
                b'[dependency-groups]\ndev=["setuptools==83.0.0"]\n'
                b"[tool.uv.workspace]\nmembers=[]\n[build-system]\n"
                b'requires=["setuptools==83.0.0"]\n'
            ),
            "uv.lock": (
                'version=1\nrequires-python=">=3.12"\n'
                '[[package]]\nname="fixture"\nversion="1"\nsource={virtual="."}\n'
                'dependencies=[{name="alpha"}]\n[package.dev-dependencies]\ndev=[{name="setuptools"}]\n'
                '[[package]]\nname="alpha"\nversion="1.0"\nsource={registry="https://pypi.org/simple"}\n'
                'wheels=[{hash="sha256:' + "a" * 64 + '"}]\n'
                '[[package]]\nname="setuptools"\nversion="83.0.0"\nsource={registry="https://pypi.org/simple"}\n'
                'wheels=[{hash="sha256:' + "b" * 64 + '"}]\n'
            ).encode(),
            "pnpm-lock.yaml": (
                b"lockfileVersion: '9.0'\nimporters:\n  .: {}\npackages:\n  braces@3.0.3: {}\n"
                b"snapshots:\n  braces@3.0.3: {}\n"
            ),
        }
        self.source_files.update(extra_source_files or {})
        file_rows = []
        for name, raw in sorted(self.source_files.items()):
            self.put("frozen/" + name, raw)
            file_rows.append(
                {
                    "path": name,
                    "source": name,
                    "sha256": shared.digest(raw),
                    "bytes": len(raw),
                    "mode": 0o644,
                }
            )
        self.source_sha = shared.digest(encoded(file_rows))
        source_ref = self.put(
            "frozen/SOURCE_SNAPSHOT.json",
            {
                "schema_version": 1,
                "created_at": CREATED.isoformat(),
                "purpose": "synthetic",
                "provenance": "No release approval",
                "source_tree_sha256": self.source_sha,
                "files": file_rows,
            },
        )
        self.source_files["SOURCE_SNAPSHOT.json"] = (root / source_ref["path"]).read_bytes()
        members: dict[str, Any] = {".": {"kind": "directory", "mode": 0o755}}
        for name, raw in self.source_files.items():
            self.put("audit/source/" + name, raw)
            members[name] = {"kind": "file", "mode": 0o644, "sha256": shared.digest(raw)}
            for parent in Path(name).parents:
                (root / "audit/source" / parent).chmod(0o755)
                members[parent.as_posix()] = {"kind": "directory", "mode": 0o755}
        (root / "audit/source").chmod(0o755)
        self.put("audit/source-snapshot.json", members)
        self.put(
            "audit/source-files.json",
            {name: shared.digest(raw) for name, raw in self.source_files.items()},
        )
        self.put(
            "audit/python-requirements.txt",
            (
                "alpha==1.0 --hash=sha256:"
                + "a" * 64
                + "\nsetuptools==83.0.0 --hash=sha256:"
                + "b" * 64
                + "\n"
            ).encode(),
        )
        self.docs: dict[str, Any] = {
            "python-audit.json": {
                "dependencies": [
                    {
                        "name": "alpha",
                        "version": "1.0",
                        "vulns": [
                            {
                                "id": "CVE-TEST-PY",
                                "fix_versions": [],
                                "description": "retained advisory",
                            }
                        ]
                        if python
                        else [],
                    },
                    {"name": "setuptools", "version": "83.0.0", "vulns": []},
                ],
                "fixes": [],
            },
            "node-audit.json": {
                "actions": [],
                "muted": [],
                "advisories": {
                    "1": {
                        "id": 1,
                        "module_name": "braces",
                        "severity": "high",
                        "github_advisory_id": "GHSA-test",
                        "patched_versions": "<0.0.0",
                        "overview": "retained full advisory",
                        "findings": [{"version": "3.0.3", "paths": ["app>braces"], "dev": False}],
                    },
                }
                if node
                else {},
                "metadata": {
                    "vulnerabilities": {
                        "info": 0,
                        "low": 0,
                        "moderate": 0,
                        "high": int(node),
                        "critical": 0,
                    },
                    "dependencies": 2,
                    "devDependencies": 0,
                    "optionalDependencies": 0,
                    "totalDependencies": 2,
                },
            },
            "python.cdx.json": self.sbom("pip-audit", python),
            "source.cdx.json": self.sbom("trivy", False),
            "gitleaks-source.json": [],
            "gitleaks-history.json": [],
        }
        prefixes = {
            "uv": "uv 0.8.15",
            "pip-audit": "pip-audit 2.10.0",
            "pnpm": "10.17.1",
            "trivy": "Version: 0.74.0",
            "gitleaks": "v8.30.1",
        }
        versions = {}
        for name, prefix in prefixes.items():
            out = self.put(f"audit/{name}-version.stdout", (prefix + "\n").encode())
            err = self.put(f"audit/{name}-version.stderr", b"")
            versions[name] = {
                "exit_code": 0,
                "verified": True,
                "stdout": f"{name}-version.stdout",
                "stderr": f"{name}-version.stderr",
                "stdout_sha256": out["sha256"],
                "stderr_sha256": err["sha256"],
            }
        rows = []
        for name, data in self.docs.items():
            ref = self.put("audit/" + name, data)
            exit_code = int(
                python
                if name in {"python-audit.json", "python.cdx.json"}
                else node
                if name == "node-audit.json"
                else False
            )
            row = {
                "report": name,
                "exit_code": exit_code,
                "coverage_verified": True,
                "status": "findings" if exit_code else "clean",
                "sha256": ref["sha256"],
            }
            if name.startswith("gitleaks"):
                log = self.put(
                    "audit/" + name + ".log",
                    b"INF 2 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found\n",
                )
                row.update(log=name + ".log", log_sha256=log["sha256"])
            rows.append(row)
        self.inventory: dict[str, Any] = {
            "complete": True,
            "passed": not (node or python),
            "started_at": START.isoformat(),
            "completed_at": END.isoformat(),
            "marker_context": gate.collector()["marker_context"](),
            "reports": rows,
            "tools": gate.pinned_tools(),
            "tool_version_evidence": versions,
            "snapshot": {
                "manifest": "source-snapshot.json",
                "sha256": self.ref("audit/source-snapshot.json")["sha256"],
                "source_files_sha256": self.ref("audit/source-files.json")["sha256"],
                "stable": True,
            },
            "scope": "Synthetic frozen source and available history",
            "audited_build_requirements": ["setuptools==83.0.0"],
            "expected_history_commits": 2,
            "requirements_sha256": self.ref("audit/python-requirements.txt")["sha256"],
            "report_bindings_verified": True,
        }
        self.manifest: dict[str, Any] = {
            "schema_version": 1,
            "hash_format": "source-full-finding-json-v1",
            "review_owner": "Synthetic owner",
            "review_method": "automated",
            "reviewed_at": REVIEW.isoformat(),
            "expires_at": EXPIRES.isoformat(),
            "source": {
                "manifest": source_ref,
                "directory": "frozen",
                "source_tree_sha256": self.source_sha,
            },
            "inventory": self.put("audit/inventory.json", self.inventory),
            "files": [],
            "assessments": [],
            "limitations": ["Synthetic only"],
        }
        self.sign()
        reports_raw = {name: (self.root / "audit" / name).read_bytes() for name in gate.FILES}
        identities = gate.records(
            gate.ReviewManifest.model_validate(self.manifest),
            reports_raw,
            self.docs["python-audit.json"],
            self.docs["node-audit.json"],
        )
        self.proofs: list[dict[str, Any]] = []
        for identity, fixes, available in identities:
            scope = {
                "membership": membership,
                "boundaries": "Exact frozen source and named dependency paths",
                "exclusions": ["Other runtimes"],
            }
            questions = shared.QUESTIONS | (
                {"remediation", "verification"} if decision == "mitigate" else set()
            )
            evidence = []
            for purpose in sorted(questions):
                i = len(self.proofs)
                observation = self.put(
                    f"observations/{i}.json",
                    {"observed": {"path": "selected-source.py", "detail": purpose}},
                )
                proof = {
                    "schema_version": 1,
                    "identity": identity.model_dump(),
                    "scope": scope,
                    "purpose": purpose,
                    "observed_at": REVIEW.isoformat(),
                    "coverage": "complete-for-question",
                    "conclusion": "Synthetic scoped result",
                    "missing_inputs": [],
                    "limitations": [],
                    "observations": [{"file": observation, "pointer": "/observed"}],
                }
                self.proofs.append(proof)
                evidence.append(
                    {
                        "file": {"path": "proofs.json", "sha256": "0" * 64, "size": 0},
                        "pointer": f"/{i}",
                        "purpose": purpose,
                    }
                )
            self.manifest["assessments"].append(
                {
                    "identity": identity.model_dump(),
                    "scope": scope,
                    "decision": decision,
                    "review_owner": "Synthetic owner",
                    "review_method": "automated",
                    "reviewed_at": REVIEW.isoformat(),
                    "expires_at": EXPIRES.isoformat(),
                    "rationale": "Scoped reviewed fixture",
                    "reachability": "Selected boundary only",
                    "exposure": "No real exposure claim",
                    "missing_inputs": [],
                    "limitations": [],
                    "fix": {
                        "scanner_fixed_versions": fixes,
                        "scanner_fix_available": available,
                        "upstream_availability": "unknown",
                        "upstream_fixed_versions": [],
                        "rationale": "No unverified upstream fix claim",
                    },
                    "evidence": evidence,
                }
            )
        self.update_proofs()

    def sbom(self, tool: str, vulnerable: bool) -> dict[str, Any]:
        components = [
            {
                "type": "library",
                "name": name,
                "version": version,
                "bom-ref": name,
                "purl": f"pkg:pypi/{name}@{version}",
            }
            for name, version in (("alpha", "1.0"), ("setuptools", "83.0.0"))
        ]
        data: dict[str, Any] = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4" if tool == "pip-audit" else "1.7",
            "version": 1,
            "metadata": {"timestamp": (START + timedelta(minutes=1)).isoformat()},
            "components": components,
        }
        if tool == "trivy":
            data["metadata"].update(
                tools={
                    "components": [{"name": "trivy", "version": "0.74.0", "type": "application"}]
                },
                component={"type": "application", "name": "/reports/source"},
            )
            components.extend(
                [
                    {
                        "name": "fixture",
                        "version": "1",
                        "type": "library",
                        "bom-ref": "fixture",
                        "purl": "pkg:pypi/fixture@1",
                    },
                    {
                        "name": "braces",
                        "version": "3.0.3",
                        "type": "library",
                        "bom-ref": "braces",
                        "purl": "pkg:npm/braces@3.0.3",
                    },
                ]
            )
            components.extend(
                {"name": name, "type": "application", "bom-ref": name}
                for name in ("uv.lock", "pnpm-lock.yaml")
            )
        if vulnerable:
            data["vulnerabilities"] = [{"id": "CVE-TEST-PY"}]
        return data

    def put(self, path: str, value: Any) -> dict[str, Any]:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value if isinstance(value, bytes) else encoded(value))
        destination.chmod(0o644)
        return self.ref(path)

    def ref(self, path: str) -> dict[str, Any]:
        raw = (self.root / path).read_bytes()
        return {"path": path, "size": len(raw), "sha256": shared.digest(raw)}

    def sign(self) -> str:
        self.manifest["inventory"] = self.put("audit/inventory.json", self.inventory)
        self.manifest["files"] = [self.ref("audit/" + name) for name in sorted(gate.FILES)]
        return str(self.put("review.json", self.manifest)["sha256"])

    def update_proofs(self) -> None:
        ref = self.put("proofs.json", self.proofs)
        for record in self.manifest["assessments"]:
            for evidence in record["evidence"]:
                evidence["file"] = copy.deepcopy(ref)

    def report(self, name: str, data: Any) -> None:
        ref = self.put("audit/" + name, data)
        next(row for row in self.inventory["reports"] if row["report"] == name)["sha256"] = ref[
            "sha256"
        ]

    def verify(self) -> dict[str, Any]:
        return gate.verify_source_bundle(
            self.root, "review.json", self.sign(), self.source_sha, NOW
        )


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return Bundle(tmp_path)


def test_every_advisory_including_unknown_python_requires_review(bundle: Bundle) -> None:
    result = bundle.verify()
    assert result["valid"] and result["assessments"] == 2
    assert result["rawcounts"]["records_by_raw_severity"] == {"UNKNOWN": 1, "high": 1}
    assert not result["rationale_truth_verified"] and not result["release_approved"]
    assert bundle.inventory["passed"] is False


def test_zero_findings_validates_full_collection(tmp_path: Path) -> None:
    result = Bundle(tmp_path, node=False, python=False).verify()
    assert result["valid"] and result["assessments"] == 0


@pytest.mark.parametrize("membership", ["build", "dev", "test", "shipped-runtime"])
def test_not_applicable_allows_only_the_explicit_scope(tmp_path: Path, membership: str) -> None:
    assert Bundle(tmp_path, membership=membership, decision="not-applicable").verify()["valid"]


def test_runtime_mitigation_is_never_an_override(tmp_path: Path) -> None:
    with pytest.raises(shared.GateError, match="runtime_mitigation"):
        Bundle(tmp_path, membership="shipped-runtime").verify()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "duplicate",
        "accept",
        "expired",
        "future",
        "severity",
        "fix",
        "owner",
        "scope",
    ],
)
def test_adoption_identity_dates_and_policy_fail_closed(bundle: Bundle, change: str) -> None:
    record = bundle.manifest["assessments"][0]
    if change == "missing":
        bundle.manifest["assessments"].pop(0)
    elif change in {"extra", "duplicate"}:
        bundle.manifest["assessments"].append(copy.deepcopy(record))
        if change == "extra":
            bundle.manifest["assessments"][-1]["identity"]["record_pointer"] = "/different"
    elif change == "accept":
        record["decision"] = "accept"
    elif change == "expired":
        record["expires_at"] = NOW.isoformat()
    elif change == "future":
        record["reviewed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "severity":
        record["identity"]["original_severity"] = "low"
    elif change == "fix":
        record["fix"]["scanner_fix_available"] = True
    elif change == "owner":
        record["review_owner"] = " "
    else:
        record["scope"]["membership"] = "unknown"
    with pytest.raises(REJECTED):
        bundle.verify()


def test_upstream_fix_does_not_imply_scanner_or_shipped_fix(bundle: Bundle) -> None:
    bundle.manifest["assessments"][0]["fix"].update(
        upstream_availability="available", upstream_fixed_versions=["upstream 2.0"]
    )
    assert bundle.verify()["valid"]


@pytest.mark.parametrize(
    "purpose",
    ["advisory", "component", "reachability", "exposure", "fix", "remediation", "verification"],
)
@pytest.mark.parametrize(
    "change", ["missing", "missing-observation", "failed", "empty", "hash", "pointer", "scope"]
)
def test_every_question_requires_real_scoped_observations(
    bundle: Bundle, purpose: str, change: str
) -> None:
    record = bundle.manifest["assessments"][0]
    proof = next(p for p in bundle.proofs if p["purpose"] == purpose)
    if change == "missing":
        record["evidence"] = [r for r in record["evidence"] if r["purpose"] != purpose]
    elif change == "missing-observation":
        proof["observations"] = []
    elif change in {"failed", "empty"}:
        value = (
            {"complete": False, "error": "capture failed", "observations": []}
            if change == "failed"
            else None
        )
        proof["observations"][0]["file"] = bundle.put(
            "observations/invalid.json", {"observed": value}
        )
    elif change == "hash":
        proof["observations"][0]["file"]["sha256"] = "0" * 64
    elif change == "pointer":
        proof["observations"][0]["pointer"] = "/missing"
    else:
        proof["scope"] = {**proof["scope"], "boundaries": "other scope"}
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "purpose", ["component", "reachability", "exposure", "remediation", "verification"]
)
def test_factual_observations_must_be_current_or_explicitly_reused(
    bundle: Bundle, purpose: str
) -> None:
    proof = next(p for p in bundle.proofs if p["purpose"] == purpose)
    proof["observed_at"] = (CREATED - timedelta(days=1)).isoformat()
    bundle.update_proofs()
    with pytest.raises(shared.GateError, match="predating_observation"):
        bundle.verify()
    proof["reused_exact_bytes"] = {
        "rationale": "Selected bytes independently rechecked",
        "verified_at": REVIEW.isoformat(),
        "current_source_tree_sha256": bundle.source_sha,
        "current": copy.deepcopy(proof["observations"]),
    }
    bundle.update_proofs()
    assert bundle.verify()["valid"]


@pytest.mark.parametrize("report", sorted(gate.REPORTS))
@pytest.mark.parametrize("change", ["malformed", "duplicate-json", "nonfinite", "missing"])
def test_zero_findings_never_skips_report_validation(
    tmp_path: Path, report: str, change: str
) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    if change == "missing":
        (bundle.root / "audit" / report).unlink()
    else:
        bundle.report(
            report,
            {"malformed": b"{}", "duplicate-json": b'{"x":1,"x":2}', "nonfinite": b'{"x":NaN}'}[
                change
            ],
        )
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "change",
    [
        "complete",
        "passed",
        "coverage",
        "status",
        "duplicate-report",
        "missing-tool",
        "version",
        "stderr",
        "missing-start",
        "future",
        "marker",
        "marker-python",
        "marker-hash",
        "packaging",
    ],
)
def test_collection_claims_are_recomputed(tmp_path: Path, change: str) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    inventory = bundle.inventory
    if change in {"complete", "passed"}:
        inventory[change] = False
    elif change == "coverage":
        inventory["reports"][0]["coverage_verified"] = False
    elif change == "status":
        inventory["reports"][0]["status"] = "findings"
    elif change == "duplicate-report":
        inventory["reports"][-1] = copy.deepcopy(inventory["reports"][0])
    elif change == "missing-tool":
        inventory["tool_version_evidence"].pop("uv")
    elif change == "version":
        ref = bundle.put("audit/uv-version.stdout", b"uv 0.0.0\n")
        inventory["tool_version_evidence"]["uv"]["stdout_sha256"] = ref["sha256"]
    elif change == "stderr":
        bundle.put("audit/uv-version.stderr", b"changed bytes")
    elif change == "missing-start":
        inventory.pop("started_at")
    elif change == "future":
        inventory["completed_at"] = (NOW + timedelta(days=1)).isoformat()
    elif change == "marker":
        inventory["marker_context"]["environment"]["sys_platform"] = "arbitrary"
    elif change == "marker-python":
        inventory["marker_context"]["python_version"] = "3.14.0"
    elif change == "marker-hash":
        inventory["marker_context"]["interpreter_sha256"] = "0" * 64
    else:
        inventory["marker_context"]["packaging_version"] = "unknown"
    with pytest.raises(REJECTED):
        bundle.verify()


def test_native_gitleaks_version_passes_source_review_and_collection(bundle: Bundle) -> None:
    raw = (bundle.root / "audit/gitleaks-version.stdout").read_bytes()
    assert raw == b"v8.30.1\n"
    result = bundle.verify()
    assert result["valid"] and not result["release_approved"]
    _, checksum = collection_manifest(bundle)
    collection = gate.verify_source_collection(
        bundle.root, "collection.json", checksum, bundle.source_sha, NOW
    )
    assert collection["complete"] and not collection["raw_passed"]
    assert not collection["security_approved"] and not collection["release_approved"]
    assert (bundle.root / "audit/gitleaks-version.stdout").read_bytes() == raw


@pytest.mark.parametrize(
    "raw",
    [
        b"8.30.1\n",
        b"v8.30.0\n",
        b"v8.30.10\n",
        b"v8.30.1-rc1\n",
        b"v8.30.1+dirty\n",
        b"v8.30.1 extra\n",
        b"v8.30.1\nextra\n",
        b"v8.30.1",
    ],
)
def test_rebound_gitleaks_version_requires_exact_native_pin(bundle: Bundle, raw: bytes) -> None:
    ref = bundle.put("audit/gitleaks-version.stdout", raw)
    bundle.inventory["tool_version_evidence"]["gitleaks"]["stdout_sha256"] = ref["sha256"]
    with pytest.raises(shared.GateError, match="^version_output$"):
        bundle.verify()
    _, checksum = collection_manifest(bundle)
    with pytest.raises(shared.GateError, match="^version_output$"):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize("name", ["gitleaks-source.json", "gitleaks-history.json"])
@pytest.mark.parametrize("change", ["finding", "error-log", "zero-bytes", "wrong-commits"])
def test_secret_findings_or_incomplete_logs_never_have_an_exception(
    tmp_path: Path, name: str, change: str
) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    row = next(r for r in bundle.inventory["reports"] if r["report"] == name)
    if change == "finding":
        bundle.report(name, [{"RuleID": "generic-api-key", "Secret": "synthetic-only"}])
    else:
        log = (
            b"ERR git failed\nno leaks found\n"
            if change == "error-log"
            else b"INF 2 commits scanned.\nINF scanned ~0 bytes\nINF no leaks found\n"
            if change == "zero-bytes"
            else b"INF 1 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found\n"
        )
        if change == "wrong-commits" and name == "gitleaks-source.json":
            log = b"INF scanned ~500 bytes\nWRN partial traversal\nINF no leaks found\n"
        ref = bundle.put("audit/" + name + ".log", log)
        row["log_sha256"] = ref["sha256"]
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "change",
    [
        "requirements",
        "marker-omission",
        "python-coverage",
        "node-total",
        "sbom-version",
        "sbom-packages",
        "sbom-time",
        "build-pins",
    ],
)
def test_dependencies_and_sboms_are_exact_not_success_flags(tmp_path: Path, change: str) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    if change in {"requirements", "marker-omission"}:
        raw = (bundle.root / "audit/python-requirements.txt").read_bytes()
        raw = raw.replace(
            b"alpha==1.0",
            b"alpha==9.0" if change == "requirements" else b"alpha==1.0; python_version < '1'",
        )
        ref = bundle.put("audit/python-requirements.txt", raw)
        bundle.inventory["requirements_sha256"] = ref["sha256"]
    elif change == "python-coverage":
        bundle.docs["python-audit.json"]["dependencies"].pop()
        bundle.report("python-audit.json", bundle.docs["python-audit.json"])
    elif change == "node-total":
        bundle.docs["node-audit.json"]["metadata"].update(dependencies=3, totalDependencies=3)
        bundle.report("node-audit.json", bundle.docs["node-audit.json"])
    elif change == "build-pins":
        bundle.inventory["audited_build_requirements"] = ["other==1"]
    else:
        data = bundle.docs["source.cdx.json"]
        if change == "sbom-version":
            data["specVersion"] = "future"
        elif change == "sbom-time":
            data["metadata"]["timestamp"] = CREATED.isoformat()
        else:
            data["components"] = [c for c in data["components"] if c["name"] != "braces"]
        bundle.report("source.cdx.json", data)
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("change", ["bytes", "mode", "extra", "manifest-self", "symlink"])
def test_saved_snapshot_matches_approved_files_modes_and_manifest(
    tmp_path: Path, change: str
) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    path = bundle.root / "audit/source/uv.lock"
    if change == "bytes":
        path.write_bytes(b"changed")
    elif change == "mode":
        path.chmod(0o755)
    elif change == "extra":
        (path.parent / "extra.py").write_bytes(b"unexpected")
    elif change == "manifest-self":
        (path.parent / "SOURCE_SNAPSHOT.json").unlink()
    else:
        path.unlink()
        path.symlink_to(bundle.root / "frozen/uv.lock")
    with pytest.raises(REJECTED):
        bundle.verify()


def test_source_manifest_and_saved_snapshot_accept_literal_next_routes(tmp_path: Path) -> None:
    bundle = Bundle(
        tmp_path,
        extra_source_files={
            "apps/shopper/app/api/[...path]/route.ts": b"export const fixture = true;\n",
            "apps/shopper/app/store/[slug]/page.tsx": b"export default 'synthetic';\n",
        },
    )
    result = bundle.verify()
    assert result["valid"] and result["assessments"] == 2
    assert not result["rationale_truth_verified"] and not result["release_approved"]


def test_source_manifest_and_saved_snapshot_accept_exact_braces_patch(tmp_path: Path) -> None:
    bundle = Bundle(
        tmp_path,
        extra_source_files={"infra/patches/braces@3.0.3.patch": b"synthetic patch bytes\n"},
    )
    result = bundle.verify()
    assert result["valid"] and result["assessments"] == 2
    assert not result["rationale_truth_verified"] and not result["release_approved"]
    _, checksum = collection_manifest(bundle)
    collection = gate.verify_source_collection(
        tmp_path, "collection.json", checksum, bundle.source_sha, NOW
    )
    assert collection["complete"] and collection["assessments_required"] == 2
    assert not collection["raw_passed"]
    assert not collection["security_approved"] and not collection["release_approved"]


@pytest.mark.parametrize("change", ["bytes", "mode", "symlink"])
def test_exact_braces_patch_requires_bound_bytes_mode_and_no_links(
    tmp_path: Path, change: str
) -> None:
    path = "infra/patches/braces@3.0.3.patch"
    bundle = Bundle(tmp_path, extra_source_files={path: b"synthetic patch bytes\n"})
    checksum = bundle.sign()
    saved = tmp_path / "audit/source" / path
    if change == "bytes":
        saved.write_bytes(b"changed")
    elif change == "mode":
        saved.chmod(0o755)
    else:
        saved.unlink()
        saved.symlink_to(tmp_path / "frozen" / path)
    with pytest.raises(REJECTED):
        gate.verify_source_bundle(tmp_path, "review.json", checksum, bundle.source_sha, NOW)


@pytest.mark.parametrize("change", ["bytes", "symlink"])
def test_bracket_paths_still_require_exact_unlinked_bytes(tmp_path: Path, change: str) -> None:
    path = "apps/api/[...path]/route.ts"
    bundle = Bundle(tmp_path, extra_source_files={path: b"synthetic source\n"})
    checksum = bundle.sign()
    saved = tmp_path / "audit/source" / path
    if change == "bytes":
        saved.write_bytes(b"changed")
    else:
        saved.unlink()
        saved.symlink_to(tmp_path / "frozen" / path)
    with pytest.raises(REJECTED):
        gate.verify_source_bundle(tmp_path, "review.json", checksum, bundle.source_sha, NOW)


@pytest.mark.parametrize("directory", ["frozen", "audit/source"])
@pytest.mark.parametrize("stage", ["initial", "final-snapshot", "final-reader"])
def test_unmanifested_empty_directory_rejected_at_initial_and_final_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str, stage: str
) -> None:
    bundle = Bundle(tmp_path, node=False, python=False)
    checksum = bundle.sign()
    assert gate.verify_source_bundle(tmp_path, "review.json", checksum, bundle.source_sha, NOW)[
        "valid"
    ]
    extra = tmp_path / directory / "extra-empty"
    if stage == "initial":
        extra.mkdir()
    elif stage == "final-snapshot":
        original_snapshot = gate.verify_snapshot
        calls = 0

        def changed_snapshot(
            reader: shared.BundleReader, manifest: gate.ReviewManifest, raw: dict[str, bytes]
        ) -> dict[str, bytes]:
            nonlocal calls
            calls += 1
            if calls == 2:
                extra.mkdir()
            return original_snapshot(reader, manifest, raw)

        monkeypatch.setattr(gate, "verify_snapshot", changed_snapshot)
    else:
        original_recheck = shared.BundleReader.recheck

        def changed_recheck(reader: shared.BundleReader) -> None:
            extra.mkdir()
            original_recheck(reader)

        monkeypatch.setattr(shared.BundleReader, "recheck", changed_recheck)
    with pytest.raises(shared.GateError, match="source_membership|source_directory_membership"):
        gate.verify_source_bundle(tmp_path, "review.json", checksum, bundle.source_sha, NOW)
    assert extra.is_dir() and not list(extra.iterdir())
    assert shared.digest((tmp_path / "review.json").read_bytes()) == checksum


@pytest.mark.parametrize(
    "key,value",
    [
        ("overview", "changed"),
        ("severity", "critical"),
        ("new_field", "new"),
        ("patched_versions", ">=4"),
    ],
)
def test_full_node_advisory_hash_preserves_all_fields(bundle: Bundle, key: str, value: str) -> None:
    advisory = bundle.docs["node-audit.json"]["advisories"]["1"]
    old = shared.finding_digest(
        {"advisory": advisory, "finding_index": 0, "finding": advisory["findings"][0]}
    )
    assert old == bundle.manifest["assessments"][1]["identity"]["finding_sha256"]
    advisory[key] = value
    assert old != shared.finding_digest(
        {"advisory": advisory, "finding_index": 0, "finding": advisory["findings"][0]}
    )
    bundle.report("node-audit.json", bundle.docs["node-audit.json"])
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize("change", ["path", "version", "new-field"])
def test_full_node_finding_cannot_be_rebound_without_review(bundle: Bundle, change: str) -> None:
    finding = bundle.docs["node-audit.json"]["advisories"]["1"]["findings"][0]
    finding[{"path": "paths", "version": "version", "new-field": "new_field"}[change]] = (
        ["other>braces"] if change == "path" else "changed"
    )
    bundle.report("node-audit.json", bundle.docs["node-audit.json"])
    with pytest.raises(REJECTED):
        bundle.verify()


@pytest.mark.parametrize(
    "raw", [b"x: 1\nx: 2", b"x: &x [*x]", b"!!python/object:bad {}", b"lockfileVersion: .nan"]
)
def test_lock_yaml_is_bounded_strict_and_nonexecuting(raw: bytes) -> None:
    with pytest.raises((*REJECTED, yaml.YAMLError)):
        gate.node_lock(raw)


def test_external_pins_and_safe_cli(bundle: Bundle, capsys: pytest.CaptureFixture[str]) -> None:
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
    assert gate.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    bundle.manifest["review_owner"] = "Unadopted claim"
    bundle.sign()
    assert gate.main(argv) == 1
    output = capsys.readouterr()
    assert "Unadopted" not in output.out and str(bundle.root) not in output.out + output.err
    assert gate.main([*argv, "--today", "2000-01-01"]) == 1


def test_cli_does_not_execute_evidence_or_write_bundle(bundle: Bundle) -> None:
    observation = bundle.proofs[0]["observations"][0]
    observation["file"] = bundle.put(
        "observations/inert.py", b"raise RuntimeError('do not execute')\n"
    )
    observation["pointer"] = None
    bundle.update_proofs()
    expected = bundle.sign()
    before = {
        p.relative_to(bundle.root): p.read_bytes() for p in bundle.root.rglob("*") if p.is_file()
    }
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
        timeout=15,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr
    assert before == {
        p.relative_to(bundle.root): p.read_bytes() for p in bundle.root.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("change", ["path", "conflict", "duplicate", "hardlink", "budget"])
def test_reused_reader_rejects_unsafe_or_unbounded_refs(
    bundle: Bundle, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    observation = bundle.proofs[0]["observations"][0]
    if change == "path":
        observation["file"]["path"] = "../outside"
    elif change in {"conflict", "duplicate"}:
        duplicate = copy.deepcopy(observation)
        if change == "conflict":
            duplicate["pointer"] = ""
            duplicate["file"]["sha256"] = "0" * 64
        bundle.proofs[0]["observations"].append(duplicate)
    elif change == "hardlink":
        os.link(bundle.root / observation["file"]["path"], bundle.root / "linked")
    else:
        monkeypatch.setattr(shared, "MAX_TOTAL_BYTES", 1)
    bundle.update_proofs()
    with pytest.raises(REJECTED):
        bundle.verify()


def collection_manifest(bundle: Bundle) -> tuple[dict[str, Any], str]:
    manifest = {
        "schema_version": 1,
        "source": copy.deepcopy(bundle.manifest["source"]),
        "inventory": bundle.put("audit/inventory.json", bundle.inventory),
        "files": [bundle.ref("audit/" + name) for name in sorted(gate.FILES)],
    }
    ref = bundle.put("collection.json", manifest)
    return manifest, str(ref["sha256"])


@pytest.mark.parametrize(
    "python,node", [(True, True), (True, False), (False, True), (False, False)]
)
def test_collection_complete_is_not_clean_or_assessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, python: bool, node: bool
) -> None:
    bundle = Bundle(tmp_path, python=python, node=node)
    manifest, checksum = collection_manifest(bundle)
    assert set(manifest) == {"schema_version", "source", "inventory", "files"}
    (tmp_path / "proofs.json").unlink()

    def forbid_review(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("collection must not construct or evaluate a review")

    monkeypatch.setattr(gate.ReviewManifest, "model_validate", forbid_review)
    monkeypatch.setattr(gate, "assessment", forbid_review)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = gate.verify_source_collection(
        tmp_path, "collection.json", checksum, bundle.source_sha, NOW
    )
    assert result["complete"] is True
    assert result["raw_passed"] is (not (python or node))
    assert result["assessments_required"] == int(python) + int(node)
    assert result["rawcounts"]["python_advisories"] == int(python)
    assert result["rawcounts"]["node_advisories_by_severity"]["high"] == int(node)
    assert result["rawcounts"]["records_by_raw_severity"] == {
        **({"UNKNOWN": 1} if python else {}),
        **({"high": 1} if node else {}),
    }
    assert result["rawcounts"]["secret_findings"] == 0
    assert result["security_approved"] is result["release_approved"] is False
    assert result["rationale_truth_verified"] is False
    assert "valid" not in result and "assessments" not in result
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


def test_collection_cannot_substitute_for_required_review(bundle: Bundle) -> None:
    _, checksum = collection_manifest(bundle)
    result = gate.verify_source_collection(
        bundle.root, "collection.json", checksum, bundle.source_sha, NOW
    )
    assert result["complete"] and result["assessments_required"] == 2
    with pytest.raises(ValidationError):
        gate.verify_source_bundle(bundle.root, "collection.json", checksum, bundle.source_sha, NOW)
    bundle.manifest["assessments"] = []
    with pytest.raises(shared.GateError, match="assessment_coverage"):
        bundle.verify()


@pytest.mark.parametrize(
    "field,value", [("assessments", []), ("security_approved", True), ("review_owner", "synthetic")]
)
def test_collection_manifest_has_no_decision_or_review_fields(
    bundle: Bundle, field: str, value: Any
) -> None:
    manifest, _ = collection_manifest(bundle)
    manifest[field] = value
    checksum = bundle.put("collection.json", manifest)["sha256"]
    with pytest.raises(ValidationError):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize("name", sorted(gate.FILES))
def test_collection_requires_every_bound_raw_file(bundle: Bundle, name: str) -> None:
    _, checksum = collection_manifest(bundle)
    (bundle.root / "audit" / name).unlink()
    with pytest.raises(REJECTED):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize("name", sorted(gate.REPORTS))
def test_collection_rejects_ambiguous_raw_report_json(bundle: Bundle, name: str) -> None:
    bundle.report(name, b'{"duplicate":1,"duplicate":2}')
    _, checksum = collection_manifest(bundle)
    with pytest.raises(shared.GateError, match="invalid_json"):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize("name", ["gitleaks-source.json", "gitleaks-history.json"])
@pytest.mark.parametrize("problem", ["finding", "incomplete-log"])
def test_collection_never_accepts_secret_findings_or_incomplete_logs(
    bundle: Bundle, name: str, problem: str
) -> None:
    if problem == "finding":
        bundle.report(name, [{"RuleID": "synthetic", "Secret": "fixture-only"}])
    else:
        ref = bundle.put("audit/" + name + ".log", b"synthetic scan failed\n")
        row = next(row for row in bundle.inventory["reports"] if row["report"] == name)
        row["log_sha256"] = ref["sha256"]
    _, checksum = collection_manifest(bundle)
    with pytest.raises(shared.GateError, match="secret_findings|secret_coverage"):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("started_at", (CREATED - timedelta(seconds=1)).isoformat()),
        ("completed_at", (START - timedelta(seconds=1)).isoformat()),
        ("completed_at", (NOW + timedelta(seconds=1)).isoformat()),
        ("started_at", None),
        ("completed_at", None),
        ("started_at", START.replace(tzinfo=None).isoformat()),
        ("complete", False),
        ("passed", True),
    ],
)
def test_collection_rejects_invalid_chronology_and_false_status(
    bundle: Bundle, field: str, value: Any
) -> None:
    bundle.inventory[field] = value
    _, checksum = collection_manifest(bundle)
    with pytest.raises(REJECTED):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


def test_collection_requires_matching_marker_environment(bundle: Bundle) -> None:
    bundle.inventory["marker_context"]["environment"]["python_version"] = "0.0"
    _, checksum = collection_manifest(bundle)
    with pytest.raises(shared.GateError, match="marker_interpreter_mismatch"):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize(
    "change", ["python-severity", "python-fix", "node-fix", "node-duplicate-path"]
)
def test_collection_validates_each_raw_record_without_assessments(
    bundle: Bundle, change: str
) -> None:
    if change.startswith("python"):
        name = "python-audit.json"
        vuln = bundle.docs[name]["dependencies"][0]["vulns"][0]
        if change == "python-severity":
            vuln["severity"] = "unsupported"
        else:
            vuln["fix_versions"] = [None]
    else:
        name = "node-audit.json"
        advisory = bundle.docs[name]["advisories"]["1"]
        if change == "node-fix":
            advisory["patched_versions"] = None
        else:
            paths = advisory["findings"][0]["paths"]
            paths.append(paths[0])
    bundle.report(name, bundle.docs[name])
    _, checksum = collection_manifest(bundle)
    with pytest.raises(REJECTED):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )


@pytest.mark.parametrize(
    "change",
    [
        "manifest-pin",
        "source-pin",
        "manifest-bytes",
        "inventory-bytes",
        "raw-bytes",
        "source-bytes",
    ],
)
def test_collection_rejects_changed_pins_and_bound_bytes(bundle: Bundle, change: str) -> None:
    _, checksum = collection_manifest(bundle)
    source_checksum = bundle.source_sha
    if change == "manifest-pin":
        checksum = "0" * 64
    elif change == "source-pin":
        source_checksum = "0" * 64
    else:
        path = {
            "manifest-bytes": "collection.json",
            "inventory-bytes": "audit/inventory.json",
            "raw-bytes": "audit/node-audit.json",
            "source-bytes": "frozen/uv.lock",
        }[change]
        with (bundle.root / path).open("ab") as stream:
            stream.write(b" ")
    with pytest.raises(shared.GateError):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, source_checksum, NOW
        )


@pytest.mark.parametrize(
    "change", ["saved-bytes", "saved-empty-directory", "frozen-empty-directory"]
)
def test_collection_rechecks_after_record_validation(
    bundle: Bundle, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    _, checksum = collection_manifest(bundle)
    original = gate.records

    def mutate(
        manifest: gate.CollectionManifest,
        raw: dict[str, bytes],
        python: dict[str, Any],
        node: dict[str, Any],
    ) -> list[tuple[gate.Identity, list[str], bool]]:
        result = original(manifest, raw, python, node)
        if change == "saved-bytes":
            (bundle.root / "audit/source/uv.lock").write_bytes(b"changed")
        else:
            directory = "frozen" if change == "frozen-empty-directory" else "audit/source"
            (bundle.root / directory / "extra-empty").mkdir()
        return result

    monkeypatch.setattr(gate, "records", mutate)
    with pytest.raises(shared.GateError):
        gate.verify_source_collection(
            bundle.root, "collection.json", checksum, bundle.source_sha, NOW
        )
