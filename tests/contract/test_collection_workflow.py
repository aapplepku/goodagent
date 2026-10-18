"""Acquisition is fixed, private-safe by default, and never an approval decision."""

import hashlib
import json
import os
import runpy
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

WORKFLOW = Path(".github/workflows/collect-release-evidence.yml")
PROVENANCE = Path("scripts/record-hosted-evidence.py")


def test_collection_is_manual_read_only_and_fresh_default_branch() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    assert workflow[True] == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["collect"]
    assert job["timeout-minutes"] <= 180
    steps = job["steps"]
    assert 'test "$REF" = "refs/heads/$DEFAULT_BRANCH"' in steps[0]["run"]
    assert 'test "$ATTEMPT" = 1' in steps[0]["run"]
    checkout = next(s for s in steps if "checkout@" in s.get("uses", ""))
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "fetch-depth": 0,
        "persist-credentials": False,
        "submodules": False,
        "lfs": False,
    }
    assert all(not s.get("continue-on-error") for s in steps)
    for step in steps:
        if "uses" in step:
            assert len(step["uses"].split("@")[1]) == 40
    assert "secrets." not in WORKFLOW.read_text()
    assert "security/current-release-approval.json" not in WORKFLOW.read_text()


def test_build_and_scan_use_same_controlled_inputs_without_running_apps() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["collect"]["steps"]
    by_id = {step["id"]: step for step in steps if "id" in step}
    for name in ("source", "build", "images"):
        command = by_id[name]["run"]
        assert 'env -i PATH="$PATH" HOME="$HOME"' in command
        assert "DOCKER_HOST=unix:///var/run/docker.sock" in command
        assert 'DOCKER_CONFIG="$RUNNER_TEMP/evidence-docker"' in command
    for name in ("build", "images"):
        assert (
            'COMPOSE_FILE=docker-compose.yml COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME"'
            in by_id[name]["run"]
        )
        assert "--env-file .env.example" in by_id[name]["run"]
    assert "--no-cache" in by_id["build"]["run"]
    assert "scanner_exit=$?" in by_id["source"]["run"]
    assert '--scanner-exit "$scanner_exit"' in by_id["source"]["run"]
    assert "always()" in by_id["after"]["if"]
    for banned in ("compose up", "compose down", "push origin", "docker push", "gh release"):
        assert banned not in WORKFLOW.read_text()


def test_uploads_are_bounded_and_sensitive_payloads_require_clean_checks() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["collect"]["steps"]
    uploads = [step for step in steps if "upload-artifact@" in step.get("uses", "")]
    assert len(uploads) == 3
    for upload in uploads:
        assert upload["with"]["retention-days"] == 30
        for path in upload["with"]["path"].splitlines():
            assert path.startswith(".opencommerce/")
            assert not path.endswith("/") or path == ".opencommerce/release-upload/"
            assert path not in {".opencommerce/**", ".opencommerce/ci-evidence/*"}
        assert "source-scans/source/" not in upload["with"]["path"]
    source_archive = next(
        s for s in uploads if s["with"]["path"] == ".opencommerce/release-upload/"
    )
    for check in (
        "source",
        "image_privacy",
        "finalize",
        "after",
        "upload_ready",
        "image_upload_check",
    ):
        assert f"steps.{check}.outcome == 'success'" in source_archive["if"]
    assert "success()" in source_archive["if"]
    privacy = next(s for s in steps if s.get("id") == "image_privacy")
    assert "--redact=100" in privacy["run"]
    assert "--ignore-gitleaks-allow" in privacy["run"]
    assert "--network none" in privacy["run"]
    assert '-v "$PWD/.gitleaks.toml:/config/.gitleaks.toml:ro"' in privacy["run"]
    assert "--config /config/.gitleaks.toml" in privacy["run"]
    assert '--user "$(id -u):$(id -g)"' in privacy["run"]
    assert "stage_release_upload prepare-images" in privacy["run"]
    assert "release-upload/.opencommerce/security-scans/final" in privacy["run"]
    assert any("stage_release_upload finalize" in step.get("run", "") for step in steps)
    fallback = next(s for s in uploads if "image-collection-" in s["with"]["name"])
    assert "steps.image_upload_check.outcome == 'success'" in fallback["if"]
    image_check = next(s for s in steps if s.get("id") == "image_upload_check")
    assert "stage_release_upload verify-images" in image_check["run"]
    assert "always()" in image_check["if"]
    assert "collect-release-evidence.yml" in Path(".github/workflows/qualification.yml").read_text()


def test_provenance_preserves_failed_and_missing_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    module = runpy.run_path(str(PROVENANCE))
    stages = {stage: "skipped" for stage in module["STAGES"]}
    stages["source"] = "failure"
    stages["dependencies"] = "success"
    monkeypatch.setenv("EVIDENCE_WORKFLOW_PATH", str(WORKFLOW))
    monkeypatch.setenv("EVIDENCE_STAGE_OUTCOMES", json.dumps(stages))
    assert module["workflow_context"]() == (str(WORKFLOW), stages)
    monkeypatch.setenv("EVIDENCE_STAGE_OUTCOMES", "{}")
    with pytest.raises(ValueError, match="missing"):
        module["workflow_context"]()


@pytest.mark.parametrize(
    "value", ['{"source":"approved"}', '{"other":"success"}', "[]", '{"source":[]}']
)
def test_provenance_rejects_forged_outcomes(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVIDENCE_STAGE_OUTCOMES", value)
    with pytest.raises(ValueError):
        runpy.run_path(str(PROVENANCE))["workflow_context"]()


def test_provenance_rejects_unknown_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVIDENCE_WORKFLOW_PATH", "arbitrary.yml")
    with pytest.raises(ValueError, match="unsupported"):
        runpy.run_path(str(PROVENANCE))["workflow_context"]()


def test_provenance_hashes_without_loading_whole_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "evidence.tar"
    raw = b"archive transport fixture" * 65536
    path.write_bytes(raw)
    module = runpy.run_path(str(PROVENANCE))
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("must stream"))
    result = module["file_record"](path)
    assert result == {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    alias = tmp_path / "link"
    alias.symlink_to(path)
    with pytest.raises((OSError, ValueError)):
        module["file_record"](alias)
    os.link(path, tmp_path / "hardlink")
    with pytest.raises(ValueError):
        module["file_record"](path)
