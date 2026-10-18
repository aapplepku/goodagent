"""Source acquisition uses immutable saved inputs; no real scanner is invoked."""

import copy
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path("scripts/scan-source.py")
EXPECTED = {("setuptools", "83.0.0")}
REQUIREMENTS = "setuptools==83.0.0 \\" + "\n    --hash=sha256:" + "a" * 64 + "\n"


def python_report(findings: bool = False) -> dict[str, Any]:
    return {
        "dependencies": [
            {
                "name": "setuptools",
                "version": "83.0.0",
                "vulns": [{"id": "CVE-TEST", "fix_versions": []}] if findings else [],
            }
        ],
        "fixes": [],
    }


def node_report(findings: bool = False) -> dict[str, Any]:
    return {
        "actions": [],
        "muted": [],
        "advisories": {
            "1": {
                "id": 1,
                "module_name": "braces",
                "severity": "high",
                "findings": [{"version": "3.0.3", "paths": ["app>braces"]}],
            }
        }
        if findings
        else {},
        "metadata": {
            "vulnerabilities": {
                "info": 0,
                "low": 0,
                "moderate": 0,
                "high": int(findings),
                "critical": 0,
            },
            "dependencies": 1,
            "devDependencies": 0,
            "optionalDependencies": 0,
            "totalDependencies": 1,
        },
    }


def sbom_report(tool: str, findings: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4" if tool == "pip-audit" else "1.7",
        "version": 1,
        "metadata": {"timestamp": "2026-10-17T00:00:00+00:00"},
        "components": [
            {"name": "setuptools", "type": "library", "version": "83.0.0", "bom-ref": "pkg-1"}
        ],
    }
    if tool == "trivy":
        data["metadata"].update(
            tools={"components": [{"type": "application", "name": "trivy", "version": "0.74.0"}]},
            component={"type": "application", "name": "/reports/source"},
        )
        data["components"].extend(
            {"name": name, "type": "application", "bom-ref": name}
            for name in ("uv.lock", "pnpm-lock.yaml")
        )
    if findings:
        data["vulnerabilities"] = [{"id": "CVE-TEST"}]
    return data


@pytest.mark.parametrize("tool", ["pip-audit", "pnpm"])
@pytest.mark.parametrize("findings", [False, True])
def test_findings_are_complete_coverage_not_a_clean_result(tool: str, findings: bool) -> None:
    report = python_report(findings) if tool == "pip-audit" else node_report(findings)
    assert MODULE["dependency_audit_status"](
        json.dumps(report).encode(), tool, int(findings), EXPECTED
    ) == ("findings" if findings else "clean")
    assert (
        MODULE["dependency_audit_status"](
            json.dumps(report).encode(), tool, 1 - int(findings), EXPECTED
        )
        == "error"
    )
    assert (
        MODULE["dependency_audit_status"](json.dumps(report).encode(), tool, 2, EXPECTED) == "error"
    )


@pytest.mark.parametrize("tool", ["pip-audit", "pnpm"])
@pytest.mark.parametrize(
    "raw", [b"", b"{}", b"[]", b'{"error":"offline"}', b'{"x":1e400}', b'{"a":0,"a":1}']
)
def test_tool_errors_and_malformed_reports_are_not_findings(tool: str, raw: bytes) -> None:
    assert MODULE["dependency_audit_status"](raw, tool, 1, EXPECTED) == "error"


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "skipped", "wrong-version", "missing-vulns"]
)
def test_python_audit_must_cover_exact_export(change: str) -> None:
    report = python_report()
    dependency = report["dependencies"][0]
    if change == "missing":
        report["dependencies"] = []
    elif change == "duplicate":
        report["dependencies"].append(copy.deepcopy(dependency))
    elif change == "skipped":
        dependency["skip_reason"] = "unavailable"
    elif change == "wrong-version":
        dependency["version"] = "1"
    else:
        dependency.pop("vulns")
    assert (
        MODULE["dependency_audit_status"](json.dumps(report).encode(), "pip-audit", 0, EXPECTED)
        == "error"
    )


@pytest.mark.parametrize(
    "change", ["counts", "missing-paths", "muted", "zero-deps", "bad-total", "missing-actions"]
)
def test_node_audit_requires_full_unsuppressed_report_shape(change: str) -> None:
    report = node_report(True)
    if change == "counts":
        report["metadata"]["vulnerabilities"]["high"] = 0
    elif change == "missing-paths":
        report["advisories"]["1"]["findings"][0]["paths"] = []
    elif change == "muted":
        report["muted"] = ["1"]
    elif change == "zero-deps":
        report["metadata"].update(dependencies=0, totalDependencies=0)
    elif change == "bad-total":
        report["metadata"]["totalDependencies"] = 2
    else:
        report.pop("actions")
    assert (
        MODULE["dependency_audit_status"](json.dumps(report).encode(), "pnpm", 1, EXPECTED)
        == "error"
    )


def test_pnpm_retained_high_shape_with_review_action_and_workspace_paths() -> None:
    report = node_report(True)
    advisory = report["advisories"].pop("1")
    advisory.update(id=1240992, github_advisory_id="GHSA-vfj7-8cjw-p6xm")
    advisory["findings"] = [
        {
            "version": "3.0.3",
            "paths": ["apps__shopper>@next/eslint-plugin-next>fast-glob>micromatch>braces"],
            "dev": False,
            "optional": False,
        }
    ]
    report["advisories"]["1240992"] = advisory
    report["actions"] = [
        {
            "action": "review",
            "module": "braces",
            "resolves": [
                {
                    "id": 1240992,
                    "path": advisory["findings"][0]["paths"][0],
                    "dev": False,
                    "optional": False,
                    "bundled": False,
                }
            ],
        }
    ]
    report["metadata"].update(dependencies=459, totalDependencies=459)
    assert (
        MODULE["dependency_audit_status"](json.dumps(report).encode(), "pnpm", 1, EXPECTED)
        == "findings"
    )


@pytest.mark.parametrize("tool", ["pip-audit", "pnpm"])
@pytest.mark.parametrize("error_key", ["error", "errors"])
def test_findings_mixed_with_tool_errors_are_incomplete(tool: str, error_key: str) -> None:
    report = python_report(True) if tool == "pip-audit" else node_report(True)
    report[error_key] = "partial audit"
    assert (
        MODULE["dependency_audit_status"](json.dumps(report).encode(), tool, 1, EXPECTED) == "error"
    )


@pytest.mark.parametrize("bad_id", [True, "1", [1]])
def test_node_advisory_identity_is_typed(bad_id: Any) -> None:
    data = node_report(True)
    advisory = data["advisories"].pop("1")
    advisory["id"] = bad_id
    data["advisories"][str(bad_id)] = advisory
    assert (
        MODULE["dependency_audit_status"](json.dumps(data).encode(), "pnpm", 1, EXPECTED) == "error"
    )


def test_explicit_null_sbom_version_is_not_an_omitted_version() -> None:
    data = sbom_report("trivy")
    data["components"][-1]["version"] = None
    assert not MODULE["sbom_complete"](json.dumps(data).encode(), "trivy", EXPECTED)


@pytest.mark.parametrize("tool", ["pip-audit", "trivy"])
@pytest.mark.parametrize(
    "change",
    [
        "none",
        "name",
        "type",
        "version",
        "missing-version",
        "duplicate",
        "timestamp",
        "component-not-object",
        "overflow",
        "truncated",
        "missing-components",
    ],
)
def test_sbom_typed_components_and_metadata(tool: str, change: str) -> None:
    data = sbom_report(tool)
    component = data["components"][0]
    if change in {"name", "type", "version"}:
        component[change] = True
    elif change == "missing-version":
        component.pop("version")
    elif change == "duplicate":
        data["components"].append(copy.deepcopy(component))
    elif change == "timestamp":
        data["metadata"]["timestamp"] = "not-a-time"
    elif change == "component-not-object":
        data["components"] = [1]
    elif change == "missing-components":
        data.pop("components")
    raw = json.dumps(data).encode()
    if change == "overflow":
        raw = raw[:-1] + b',"extra":1e400}'
    elif change == "truncated":
        raw = raw[:-1]
    assert MODULE["sbom_complete"](raw, tool, EXPECTED) is (change == "none")


@pytest.mark.parametrize("change", ["missing", "added", "wrong-version", "duplicate-identity"])
def test_python_sbom_requires_exact_export_set(change: str) -> None:
    data = sbom_report("pip-audit")
    if change == "missing":
        data["components"] = []
    elif change == "wrong-version":
        data["components"][0]["version"] = "1"
    else:
        extra = copy.deepcopy(data["components"][0])
        extra["bom-ref"] = "second-ref"
        if change == "added":
            extra["name"] = "extra-package"
        data["components"].append(extra)
    assert not MODULE["sbom_complete"](json.dumps(data).encode(), "pip-audit", EXPECTED)


@pytest.mark.parametrize("change", ["tools", "tool-version", "root", "lockfile"])
def test_trivy_sbom_requires_pinned_scanner_root_and_lockfile_coverage(change: str) -> None:
    data = sbom_report("trivy")
    if change == "tools":
        data["metadata"].pop("tools")
    elif change == "tool-version":
        data["metadata"]["tools"]["components"][0]["version"] = "0.0.0"
    elif change == "root":
        data["metadata"]["component"]["name"] = "/live-checkout"
    else:
        data["components"].pop()
    assert not MODULE["sbom_complete"](json.dumps(data).encode(), "trivy", EXPECTED)


def test_export_parser_uses_markers_and_registry_hash_pins(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(
        REQUIREMENTS
        + '# via project\nignored==1; python_version < "1" --hash=sha256:'
        + "b" * 64
        + "\n"
    )
    assert MODULE["python_requirements"](path) == EXPECTED
    path.write_text("setuptools==83.0.0\n")
    with pytest.raises(ValueError, match="unhashed"):
        MODULE["python_requirements"](path)


@pytest.fixture
def acquisition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    output = tmp_path / "evidence"
    project = (
        '[dependency-groups]\ndev=["setuptools==83.0.0"]\n'
        "[tool.uv.workspace]\nmembers=[]\n"
        '[build-system]\nrequires=["setuptools==83.0.0"]\n'
    )
    (checkout / "pyproject.toml").write_text(project)
    (checkout / "uv.lock").write_text("frozen Python lock\n")
    (checkout / "pnpm-lock.yaml").write_text("frozen Node lock\n")
    (checkout / ".gitleaks.toml").write_text("title='synthetic'\n")
    monkeypatch.chdir(checkout)
    monkeypatch.setenv("UV", "./mock-uv")
    monkeypatch.setenv("PNPM", "./mock-pnpm")
    monkeypatch.setattr(sys, "argv", ["scan-source.py", "--output", str(output)])
    state: dict[str, Any] = {
        "checkout": checkout,
        "output": output,
        "calls": [],
        "node_findings": False,
        "python_findings": False,
        "mutate": None,
        "mutation_stage": "node",
        "live_mutation": False,
        "bad_version": None,
        "version_overrides": {},
        "node_error": False,
        "selected": b"pyproject.toml\0uv.lock\0pnpm-lock.yaml\0.gitleaks.toml\0",
        "raw_overrides": {},
        "late_mutation": None,
        "requirements": REQUIREMENTS,
    }

    def mutate() -> None:
        snapshot = output / "source"
        target = snapshot / "uv.lock"
        if state["mutate"] == "changed":
            target.write_text("different source\n")
        elif state["mutate"] == "missing":
            target.unlink()
        elif state["mutate"] == "added":
            (snapshot / "new.py").write_text("new source\n")
        elif state["mutate"] == "mode":
            target.chmod(target.stat().st_mode ^ 0o100)
        elif state["mutate"] == "symlink":
            target.unlink()
            target.symlink_to(checkout / "uv.lock")
        elif state["mutate"] == "requirements":
            (output / "python-requirements.txt").write_text("changed export\n")

    def check_output(command: list[str], **kwargs: Any) -> bytes:
        if command[:2] == ["git", "ls-files"]:
            return bytes(state["selected"])
        assert command[:3] == ["git", "-C", str(output / "history.git")]
        return b"2\n"

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        state["calls"].append((command, kwargs.get("cwd")))
        stdout = b""
        exit_code = 0
        if command[:2] == ["git", "clone"]:
            (output / "history.git").mkdir()
            if state["live_mutation"]:
                (checkout / "pyproject.toml").write_text("invalid live project after snapshot\n")
                (checkout / "pnpm-lock.yaml").write_text("changed live Node lock\n")
            if state["mutate"] and state["mutation_stage"] == "before":
                mutate()
            return subprocess.CompletedProcess(command, 0, b"", b"")
        assert kwargs["cwd"] == output / "source"
        if command[-1] in {"--version", "version"}:
            if command[0].endswith("mock-pnpm"):
                tool, text = "pnpm", "10.17.1"
            elif "pip-audit" in command:
                tool, text = "pip-audit", "pip-audit 2.10.0"
            elif command[0].endswith("mock-uv"):
                tool, text = "uv", "uv 0.8.15"
            elif MODULE["TRIVY"] in command:
                tool, text = "trivy", "Version: 0.74.0"
            else:
                assert MODULE["GITLEAKS"] in command
                tool, text = "gitleaks", "v8.30.1"
            stdout = (("unrecognized" if state["bad_version"] == tool else text) + "\n").encode()
            stdout = state["version_overrides"].get(tool, stdout)
        elif "export" in command:
            assert command[0] == str(checkout / "mock-uv")
            Path(command[command.index("--output-file") + 1]).write_text(state["requirements"])
            if state["mutate"] and state["mutation_stage"] == "export":
                mutate()
        elif "audit" in command:
            assert command[0] == str(checkout / "mock-pnpm")
            raw = (
                b'{"error":"offline"}'
                if state["node_error"]
                else json.dumps(node_report(state["node_findings"])).encode()
            )
            raw = state["raw_overrides"].get("node-audit.json", raw)
            state["node_raw"] = raw
            kwargs["stdout"].write(raw)
            exit_code = 1 if state["node_findings"] or state["node_error"] else 0
            if state["mutate"] and state["mutation_stage"] == "node":
                mutate()
        elif "pip-audit" in command:
            target = Path(command[command.index("--output") + 1])
            if target.name == "python-audit.json":
                data = python_report(state["python_findings"])
            else:
                data = sbom_report("pip-audit", state["python_findings"])
            target.write_bytes(state["raw_overrides"].get(target.name, json.dumps(data).encode()))
            exit_code = int(state["python_findings"])
        elif MODULE["GITLEAKS"] in command:
            name = Path(command[command.index("--report-path") + 1]).name
            (output / name).write_bytes(state["raw_overrides"].get(name, b"[]"))
            stdout = b"INF 2 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found\n"
        else:
            assert MODULE["TRIVY"] in command
            name = Path(command[command.index("--output") + 1]).name
            (output / name).write_bytes(
                state["raw_overrides"].get(name, json.dumps(sbom_report("trivy")).encode())
            )
            if state["mutate"] and state["mutation_stage"] == "final":
                mutate()
            if state["late_mutation"]:
                filename, change = state["late_mutation"]
                target = output / filename
                if change == "changed":
                    target.write_bytes(b"late changed evidence")
                elif change == "missing":
                    target.unlink()
                else:
                    original = target.read_bytes()
                    target.unlink()
                    replacement = checkout / "replacement-evidence"
                    replacement.write_bytes(original)
                    target.symlink_to(replacement)
        return subprocess.CompletedProcess(command, exit_code, stdout, b"")

    monkeypatch.setattr(subprocess, "check_output", check_output)
    monkeypatch.setattr(subprocess, "run", run)
    original = MODULE["validate_build_requirements"]

    def validate(root: Path) -> list[str]:
        assert root == output / "source"
        return list(original(root))

    monkeypatch.setitem(MODULE["main"].__globals__, "validate_build_requirements", validate)
    return state


def test_saved_snapshot_drives_all_acquisition_not_changed_checkout(
    acquisition: dict[str, Any],
) -> None:
    acquisition["live_mutation"] = True
    MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert inventory["complete"] and inventory["passed"] and inventory["snapshot"]["stable"]
    assert inventory["report_bindings_verified"] is True
    assert inventory["audited_build_requirements"] == ["setuptools==83.0.0"]
    assert set(inventory["tool_version_evidence"]) == {
        "uv",
        "pip-audit",
        "pnpm",
        "trivy",
        "gitleaks",
    }
    members = json.loads((output / "source-snapshot.json").read_bytes())
    files = json.loads((output / "source-files.json").read_bytes())
    assert members["."]["kind"] == "directory"
    assert files == {name: row["sha256"] for name, row in members.items() if row["kind"] == "file"}
    assert (
        inventory["snapshot"]["sha256"]
        == hashlib.sha256((output / "source-snapshot.json").read_bytes()).hexdigest()
    )
    assert all(
        row["coverage_verified"] and row["status"] == "clean" for row in inventory["reports"]
    )


@pytest.mark.parametrize("tool", ["node", "python"])
def test_valid_findings_keep_coverage_complete_but_qualification_blocked(
    acquisition: dict[str, Any], tool: str
) -> None:
    acquisition[f"{tool}_findings"] = True
    with pytest.raises(SystemExit, match="source security checks failed"):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert inventory["complete"] is True and inventory["passed"] is False
    row = next(r for r in inventory["reports"] if r["report"] == f"{tool}-audit.json")
    assert (
        row["status"] == "findings" and row["coverage_verified"] is True and row["exit_code"] == 1
    )
    if tool == "node":
        assert (output / "node-audit.json").read_bytes() == acquisition["node_raw"]


def test_audit_error_is_incomplete_not_a_reviewable_finding(acquisition: dict[str, Any]) -> None:
    acquisition["node_error"] = True
    with pytest.raises(SystemExit):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert inventory["complete"] is False and inventory["passed"] is False
    assert (output / "node-audit.json").read_bytes() == acquisition["node_raw"]
    assert (
        next(r for r in inventory["reports"] if r["report"] == "node-audit.json")["status"]
        == "error"
    )


@pytest.mark.parametrize("name", ["gitleaks-source.json", "gitleaks-history.json"])
@pytest.mark.parametrize(
    "raw", [b"", b" ", b"[", b"{}", b"null", b"[{}]", b'[{"RuleID":"synthetic"}]']
)
def test_clean_secret_log_cannot_hide_invalid_or_nonempty_report(
    acquisition: dict[str, Any], name: str, raw: bytes
) -> None:
    acquisition["raw_overrides"][name] = raw
    with pytest.raises(SystemExit, match="source security checks failed"):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert not inventory["complete"] and not inventory["passed"]
    row = next(item for item in inventory["reports"] if item["report"] == name)
    assert row["status"] == "error" and not row["coverage_verified"]
    assert row["sha256"] == hashlib.sha256(raw).hexdigest()
    assert row["log_sha256"] == hashlib.sha256((output / row["log"]).read_bytes()).hexdigest()
    assert (output / name).read_bytes() == raw


@pytest.mark.parametrize(
    "name",
    [
        "python-audit.json",
        "python.cdx.json",
        "node-audit.json",
        "gitleaks-source.json",
        "gitleaks-history.json",
        "gitleaks-source.json.log",
        "gitleaks-history.json.log",
        "uv-version.stdout",
        "uv-version.stderr",
        "pip-audit-version.stdout",
        "pnpm-version.stderr",
        "trivy-version.stdout",
        "gitleaks-version.stdout",
    ],
)
@pytest.mark.parametrize("change", ["changed", "missing", "symlink"])
def test_final_success_requires_all_retained_report_log_and_version_bindings(
    acquisition: dict[str, Any], name: str, change: str
) -> None:
    acquisition["late_mutation"] = (name, change)
    with pytest.raises(SystemExit, match="source security checks failed"):
        MODULE["main"]()
    inventory = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert not inventory["complete"] and not inventory["passed"]
    assert inventory["report_bindings_verified"] is False


@pytest.mark.parametrize("stage", ["before", "export", "node", "final"])
@pytest.mark.parametrize("change", ["changed", "missing", "added", "mode", "symlink"])
def test_snapshot_drift_stops_acquisition(
    acquisition: dict[str, Any], stage: str, change: str
) -> None:
    acquisition.update(mutate=change, mutation_stage=stage)
    with pytest.raises(ValueError, match="source snapshot"):
        MODULE["main"]()
    inventory = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert inventory["snapshot"]["stable"] is False
    assert inventory["complete"] is False and inventory["passed"] is False
    if stage == "before":
        assert all(command[0] == "git" for command, _ in acquisition["calls"])


def test_exported_requirement_mutation_blocks(acquisition: dict[str, Any]) -> None:
    acquisition["mutate"] = "requirements"
    with pytest.raises(ValueError, match="source snapshot"):
        MODULE["main"]()


@pytest.mark.parametrize("tool", ["uv", "pip-audit", "pnpm", "trivy", "gitleaks"])
def test_wrong_tool_version_retains_evidence_and_blocks(
    acquisition: dict[str, Any], tool: str
) -> None:
    acquisition["bad_version"] = tool
    with pytest.raises(ValueError, match="version evidence"):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert not inventory["complete"] and not inventory["passed"]
    assert inventory["tool_version_evidence"][tool]["verified"] is False
    assert (output / f"{tool}-version.stdout").read_bytes() == b"unrecognized\n"


def test_native_gitleaks_version_is_retained_and_verified(acquisition: dict[str, Any]) -> None:
    MODULE["main"]()
    output = acquisition["output"]
    raw = (output / "gitleaks-version.stdout").read_bytes()
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert raw == b"v8.30.1\n"
    assert inventory["complete"] and inventory["passed"]
    evidence = inventory["tool_version_evidence"]["gitleaks"]
    assert evidence["verified"] and evidence["exit_code"] == 0
    assert evidence["stdout_sha256"] == hashlib.sha256(raw).hexdigest()


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
def test_gitleaks_version_requires_exact_native_pin_and_retains_rejected_bytes(
    acquisition: dict[str, Any], raw: bytes
) -> None:
    acquisition["version_overrides"]["gitleaks"] = raw
    with pytest.raises(ValueError, match="version evidence"):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert not inventory["complete"] and not inventory["passed"]
    evidence = inventory["tool_version_evidence"]["gitleaks"]
    assert not evidence["verified"]
    assert evidence["stdout_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (output / "gitleaks-version.stdout").read_bytes() == raw
    assert not (output / "gitleaks-source.json").exists()


def test_existing_output_is_never_overwritten(acquisition: dict[str, Any]) -> None:
    output = acquisition["output"]
    output.mkdir()
    marker = output / "inventory.json"
    marker.write_text("original evidence")
    with pytest.raises(ValueError, match="new empty output"):
        MODULE["main"]()
    assert marker.read_text() == "original evidence"
    assert acquisition["calls"] == []


@pytest.mark.parametrize("change", ["missing", "symlink", "directory", "parent-symlink"])
def test_git_selected_inputs_are_never_silently_omitted(
    acquisition: dict[str, Any], change: str
) -> None:
    checkout = acquisition["checkout"]
    target = checkout / "uv.lock"
    if change == "parent-symlink":
        (checkout / "linked").symlink_to(checkout, target_is_directory=True)
        acquisition["selected"] += b"linked/uv.lock\0"
    else:
        target.unlink()
        if change == "symlink":
            target.symlink_to(checkout / "pnpm-lock.yaml")
        elif change == "directory":
            target.mkdir()
    with pytest.raises(ValueError, match="selected source"):
        MODULE["main"]()
    inventory = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert inventory["complete"] is False and inventory["passed"] is False
    assert inventory["capture_error"]
    assert acquisition["calls"] == []


def test_capture_membership_must_equal_selection(
    acquisition: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    copy2 = shutil.copy2

    def lose_copy(source: Path, destination: Path, **kwargs: Any) -> None:
        if source.name != "uv.lock":
            copy2(source, destination, **kwargs)

    monkeypatch.setattr(shutil, "copy2", lose_copy)
    with pytest.raises(ValueError, match="membership does not match Git selection"):
        MODULE["main"]()
    inventory = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert inventory["complete"] is False and inventory["passed"] is False
    assert acquisition["calls"] == []


def test_export_cannot_omit_a_declared_audited_build_pin(acquisition: dict[str, Any]) -> None:
    acquisition["requirements"] = REQUIREMENTS.replace("setuptools", "unrelated")
    with pytest.raises(ValueError, match="export omitted an audited build requirement"):
        MODULE["main"]()
    inventory = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert inventory["complete"] is False and inventory["passed"] is False
    assert inventory["requirements_sha256"]
    assert inventory["reports"] == []


@pytest.mark.parametrize(
    "report", ["python-audit.json", "node-audit.json", "python.cdx.json", "source.cdx.json"]
)
@pytest.mark.parametrize("raw", [b'{"truncated":', b'{"error":"partial audit"}'])
def test_main_retains_parse_error_reports_and_raw_exits_even_with_other_findings(
    acquisition: dict[str, Any], report: str, raw: bytes
) -> None:
    acquisition.update(node_findings=True, python_findings=True)
    acquisition["raw_overrides"][report] = raw
    with pytest.raises(SystemExit, match="source security checks failed"):
        MODULE["main"]()
    output = acquisition["output"]
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert inventory["complete"] is False and inventory["passed"] is False
    row = next(r for r in inventory["reports"] if r["report"] == report)
    assert row["exit_code"] == (0 if report == "source.cdx.json" else 1)
    assert row["status"] == "error" and not row["coverage_verified"]
    assert (output / report).read_bytes() == raw
    assert row["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("findings", [False, True])
def test_collection_retains_utc_dates_and_actual_marker_context(
    acquisition: dict[str, Any], findings: bool
) -> None:
    before = datetime.now(UTC)
    acquisition["node_findings"] = findings
    if findings:
        with pytest.raises(SystemExit, match="source security checks failed"):
            MODULE["main"]()
    else:
        MODULE["main"]()
    data = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    start = datetime.fromisoformat(data["started_at"])
    end = datetime.fromisoformat(data["completed_at"])
    assert before <= start <= end <= datetime.now(UTC)
    assert data["marker_context"] == MODULE["marker_context"]()
    assert set(data["marker_context"]) == {
        "schema_version",
        "packaging_version",
        "implementation",
        "python_version",
        "interpreter_sha256",
        "environment",
    }
    assert len(data["marker_context"]["interpreter_sha256"]) == 64
    assert data["complete"] and data["passed"] is not findings
    for command, _ in acquisition["calls"]:
        if "pip-audit" in command:
            assert command[command.index("--python") + 1] == sys.executable


def test_capture_failure_retains_dates_and_marker_provenance(acquisition: dict[str, Any]) -> None:
    acquisition["selected"] += b"missing.py\0"
    with pytest.raises(ValueError, match="selected source"):
        MODULE["main"]()
    data = json.loads((acquisition["output"] / "inventory.json").read_bytes())
    assert datetime.fromisoformat(data["started_at"]) <= datetime.fromisoformat(
        data["completed_at"]
    )
    assert data["marker_context"] == MODULE["marker_context"]()
    assert data["complete"] is False and acquisition["calls"] == []


def test_requirements_can_replay_a_complete_captured_marker_environment(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(
        REQUIREMENTS + "win-only==1; sys_platform == 'win32' --hash=sha256:" + "b" * 64 + "\n"
    )
    environment = dict(MODULE["marker_context"]()["environment"])
    environment["sys_platform"] = "linux"
    assert MODULE["python_requirements"](path, environment) == EXPECTED
    environment["sys_platform"] = "win32"
    assert MODULE["python_requirements"](path, environment) == EXPECTED | {("win-only", "1")}
    del environment["python_version"]
    with pytest.raises(ValueError, match="incomplete captured marker environment"):
        MODULE["python_requirements"](path, environment)
