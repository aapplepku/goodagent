"""Release verification preserves the committed full benchmark as its first reference."""

import hashlib
import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]


def test_full_workflow_requires_all_shards_and_full_reproduction() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/qualification.yml").read_text())
    jobs = workflow["jobs"]
    shards = jobs["controller-shards"]
    assert shards["strategy"] == {
        "fail-fast": False,
        "max-parallel": 4,
        "matrix": {"shard": [0, 1, 2, 3]},
    }
    step = next(s for s in shards["steps"] if "controller-shards.py run" in s.get("run", ""))
    assert step["timeout-minutes"] < shards["timeout-minutes"] < 360
    upload = next(s for s in shards["steps"] if "upload-artifact@" in s.get("uses", ""))
    assert "always()" in upload["if"]
    assert "steps.artifact_privacy.outcome == 'success'" in upload["if"]
    assert upload["with"]["path"] == ".opencommerce/ci-upload/shard/upload/"
    complete = jobs["controller-complete"]
    assert complete["needs"] == "controller-shards"
    assert "always()" in complete["if"]
    assert complete["steps"][0]["run"] == 'test "$SHARD_RESULT" = success'
    assert any("controller-shards.py assemble" in s.get("run", "") for s in complete["steps"])


def test_security_runs_after_failure_and_raw_upload_requires_privacy_and_provenance() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/qualification.yml").read_text())
    job = workflow["jobs"]["verify"]
    assert job["runs-on"] == "ubuntu-24.04-arm"
    steps = job["steps"]
    for name in (
        "Dependency and secret scans, source SBOM",
        "Container scans and per-image SBOMs",
        "Review gate for container findings",
        "Image privilege and component evidence",
    ):
        step = next(s for s in steps if s.get("name") == name)
        assert "!cancelled()" in step["if"]
        assert not step.get("continue-on-error")
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert "always()" in upload["if"]
    assert "steps.provenance.outcome == 'success'" in upload["if"]
    assert "steps.artifact_privacy.outcome == 'success'" in upload["if"]
    assert upload["with"]["include-hidden-files"]
    assert upload["with"]["path"] == ".opencommerce/ci-upload/qualification/upload/"
    privacy = next(s for s in steps if s.get("id") == "artifact_privacy")
    assert "always()" in privacy["if"]
    assert "steps.provenance.outcome == 'success'" in privacy["if"]
    assert privacy["uses"] == "./.github/actions/screen-diagnostics"
    assert privacy["with"] == {"profile": "qualification", "commit": "${{ github.sha }}"}


def test_private_rc_requires_private_branch_and_dco_before_qualification() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/release-candidate.yml").read_text())
    jobs = workflow["jobs"]
    assert jobs["qualification"]["needs"] == "authorization"
    assert jobs["qualification"]["with"]["full-benchmark"] is True
    steps = jobs["authorization"]["steps"]
    guard = steps[0]
    assert 'test "$PRIVATE_REPOSITORY" = true' in guard["run"]
    assert 'test "$RC_REF" = refs/heads/release/v0.1.0-rc1' in guard["run"]
    assert steps[-1]["env"]["RC_BASE"] == "e44eda8353e0d90184f7109473a12397ce0b5b0b"
    assert 'git merge-base --is-ancestor "$RC_BASE" HEAD' in steps[-1]["run"]
    assert 'check_dco.py --repository . --base "$RC_BASE"' in steps[-1]["run"]
    assert '--head "$(git rev-parse HEAD)"' in steps[-1]["run"]
    assert '--expected-author "Han Chen <hc414t@gmail.com>"' in steps[-1]["run"]
    assert workflow["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", "infra/github/public-ci.yml"])
def test_normal_development_emits_all_protected_contexts_without_rc_ref(path: str) -> None:
    workflow = yaml.safe_load(Path(path).read_text())
    # PyYAML's YAML 1.1 loader interprets the GitHub `on` key as boolean True.
    events = workflow[True]
    assert {"push", "pull_request", "workflow_dispatch"} <= events.keys()
    assert "paths" not in (events["push"] or {})
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert jobs["qualification"]["needs"] == "authorization"
    assert jobs["qualification"]["with"]["full-benchmark"] is True
    guard = jobs["authorization"]
    assert guard["name"] in {"Private RC and DCO", "Alpha DCO"}
    steps = guard["steps"]
    offset = 1 if guard["name"] == "Private RC and DCO" else 0
    if offset:
        assert steps[0]["run"] == 'test "$PRIVATE_REPOSITORY" = true'
    else:
        assert "PRIVATE_REPOSITORY" not in Path(path).read_text()
        assert "--all --head" in steps[-1]["run"]
    assert steps[offset]["with"]["path"] == "trusted-policy"
    assert "pull_request.base.sha" in steps[offset]["with"]["ref"]
    assert "default_branch" in steps[offset]["with"]["ref"]
    assert steps[offset + 1]["with"]["path"] == "contribution-history"
    assert steps[offset + 1]["with"]["fetch-depth"] == 0
    assert not steps[offset + 1]["with"]["persist-credentials"]
    assert not steps[offset + 1]["with"]["submodules"]
    command = steps[-1]["run"]
    assert "python3 -I trusted-policy/scripts/check_dco.py" in command
    assert "release/v0.1.0-rc1" not in command
    assert "c261741" not in command
    assert 'BASE_SHA="$PR_BASE"' in command
    if offset:
        assert 'BASE_SHA="$BEFORE_SHA"' in command
        assert "git -C trusted-policy rev-parse HEAD" in command
    assert all(not s.get("continue-on-error", False) for s in steps)


@pytest.mark.parametrize(
    "event,ref",
    [
        ("pull_request", "prep/test"),
        ("push", "prep/test"),
        ("push", "main"),
        ("workflow_dispatch", "main"),
    ],
)
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize(
    "workflow_path", [".github/workflows/ci.yml", "infra/github/public-ci.yml"]
)
def test_development_dco_ranges_execute_against_real_history(
    tmp_path: Path, event: str, ref: str, signed: bool, workflow_path: str
) -> None:
    workflow = yaml.safe_load(Path(workflow_path).read_text())
    trusted = tmp_path / "trusted-policy"
    trusted.mkdir()

    def git(directory: Path, *args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(directory),
                "-c",
                "user.name=Test Author",
                "-c",
                "user.email=author@example.test",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                *args,
            ],
            text=True,
        ).strip()

    git(trusted, "init", "--initial-branch=main")
    (trusted / "scripts").mkdir()
    shutil.copyfile("scripts/check_dco.py", trusted / "scripts/check_dco.py")
    git(trusted, "add", "scripts/check_dco.py")
    if workflow["jobs"]["authorization"]["name"] == "Alpha DCO":
        git(trusted, "commit", "-s", "-m", "Signed public source snapshot")
    else:
        git(trusted, "commit", "-m", "Trusted private base predates DCO")
    base = git(trusted, "rev-parse", "HEAD")
    history = tmp_path / "contribution-history"
    git(tmp_path, "clone", "--no-local", str(trusted), str(history))
    message = "Contribution" + (
        "\n\nSigned-off-by: Test Author <author@example.test>" if signed else ""
    )
    git(history, "commit", "--allow-empty", "-m", message)
    head = git(history, "rev-parse", "HEAD")
    # A hostile contribution must not replace the trusted checker at execution.
    (history / "scripts/check_dco.py").write_text("raise SystemExit(0)\n")
    command = workflow["jobs"]["authorization"]["steps"][-1]["run"]
    result = subprocess.run(
        ["bash", "-eu", "-c", command],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PR_BASE": base if event == "pull_request" else "",
            "HEAD_SHA": head,
            "BEFORE_SHA": base,
            "EVENT_NAME": event,
            "CURRENT_REF": ref,
            "DEFAULT_BRANCH": "main",
        },
        check=False,
    )
    assert (result.returncode == 0) is signed, result.stdout + result.stderr


def test_provenance_retains_hashes_but_fails_on_wrong_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = runpy.run_path(str(Path("scripts/record-hosted-evidence.py").resolve()))
    evidence = tmp_path / ".opencommerce/security-scans/final"
    evidence.mkdir(parents=True)
    (evidence / "api.scan.json").write_text('{"raw": true}\n')
    partial = tmp_path / ".opencommerce/controller-primary.json.partial.jsonl"
    partial.write_text('{"complete": false}\n')
    smoke = tmp_path / ".opencommerce/controller-smoke.json"
    smoke.write_text('{"complete": true}\n')
    scan_log = tmp_path / ".opencommerce/source-scans/gitleaks-history.json.log"
    scan_log.parent.mkdir()
    scan_log.write_text("0 commits scanned.\n")
    version_evidence = {
        "uv-version.stdout": b"uv 0.8.15\n",
        "uv-version.stderr": b"",
    }
    for name, content in version_evidence.items():
        (scan_log.parent / name).write_bytes(content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVIDENCE_COMMIT", "wrong")
    monkeypatch.delenv("EVIDENCE_WORKFLOW_PATH", raising=False)
    monkeypatch.delenv("EVIDENCE_STAGE_OUTCOMES", raising=False)
    monkeypatch.setitem(module["main"].__globals__, "version", lambda *args: "synthetic-version")
    with pytest.raises(SystemExit, match="checkout SHA differs"):
        module["main"]()
    report = json.loads((tmp_path / ".opencommerce/ci-evidence/provenance.json").read_bytes())
    assert report["commit_matches"] is False
    assert len(report["files"]) == 6
    for name, content in version_evidence.items():
        entry = next(item for item in report["files"] if item["path"].endswith(name))
        assert entry["sha256"] == hashlib.sha256(content).hexdigest()
        assert entry["bytes"] == len(content)
    assert any(item["path"].endswith("controller-smoke.json") for item in report["files"])
    assert any(item["path"].endswith(".log") for item in report["files"])
    assert any(item["path"].endswith(".partial.jsonl") for item in report["files"])
    assert len(report["files"][0]["sha256"]) == 64
    assert "not a pass" in report["workflow_result"]
    assert {"node", "npm", "pnpm", "python", "uv", "docker", "compose"} <= set(
        report["environment"]
    )
