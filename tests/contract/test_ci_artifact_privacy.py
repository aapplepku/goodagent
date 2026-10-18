"""Failed qualification can retain evidence, but cannot bypass upload privacy."""

import gzip
import hashlib
import io
import json
import os
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from scripts import check_release_assessments as gate
from scripts import stage_ci_artifacts as stage

COMMIT = "a" * 40


def fixture(root: Path, contents: dict[str, bytes]) -> None:
    files = []
    for path, raw in contents.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    provenance = root / stage.PROVENANCE
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(
        json.dumps(
            {
                "commit_matches": True,
                "commit_sha": COMMIT,
                "expected_commit_sha": COMMIT,
                "files": files,
                "workflow_result": "failure is not a pass",
            }
        )
    )


def test_failed_security_reports_and_compressed_content_are_screened(tmp_path: Path) -> None:
    paths = {
        ".opencommerce/security-scans/final/api.image-config.json": b'{"Env":["marker"]}',
        ".opencommerce/source-scans/python-audit.json": b'{"high_findings":3}',
        ".opencommerce/controller-primary.json.gz": gzip.compress(
            b'{"canary":"private-marker"}', mtime=0
        ),
        ".opencommerce/ci-evidence/compose.log": b"synthetic failure\n",
        "apps/web/test-results/test/trace.zip": b"binary browser session",
    }
    fixture(tmp_path, paths)
    prepared = stage.prepare(tmp_path, "qualification", COMMIT)
    assert prepared["prepared_files"] == 5
    assert prepared["qualification_passed"] is False
    prefix = tmp_path / stage.BASE / "qualification"
    assert (prefix / "screen/api.image-config.json").read_bytes() == paths[
        ".opencommerce/security-scans/final/api.image-config.json"
    ]
    assert (
        b"private-marker"
        in (prefix / "screen/.opencommerce/controller-primary.json.screen.txt").read_bytes()
    )
    assert not (prefix / "upload/apps").exists()
    assert (
        stage.verify(tmp_path, "qualification", COMMIT, prepared["receipt_sha256"])[
            "verified_files"
        ]
        == 5
    )
    for path, raw in paths.items():
        assert (tmp_path / path).read_bytes() == raw


@pytest.mark.parametrize("kind", ["upload", "screen", "receipt", "extra", "symlink", "hardlink"])
def test_changes_after_screening_are_rejected(tmp_path: Path, kind: str) -> None:
    path = ".opencommerce/ci-evidence/compose.log"
    fixture(tmp_path, {path: b"fixture"})
    result = stage.prepare(tmp_path, "qualification", COMMIT)
    prefix = tmp_path / stage.BASE / "qualification"
    target = prefix / "upload" / path
    if kind == "upload":
        target.write_bytes(b"changed")
    elif kind == "screen":
        (prefix / "screen" / (path + ".screen.txt")).write_bytes(b"changed")
    elif kind == "receipt":
        (prefix / "receipt.json").write_text("{}")
    elif kind == "extra":
        (prefix / "upload/extra.log").write_bytes(b"unscanned")
    elif kind == "symlink":
        target.unlink()
        target.symlink_to(tmp_path / path)
    else:
        os.link(target, tmp_path / "alias")
    with pytest.raises((ValueError, OSError)):
        stage.verify(tmp_path, "qualification", COMMIT, result["receipt_sha256"])


@pytest.mark.parametrize("problem", ["provenance", "changed", "binary", "compressed", "expanded"])
def test_bad_inputs_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    path = ".opencommerce/ci-evidence/compose.log"
    raw = b"fixture"
    if problem == "binary":
        raw = b"\xff"
    if problem in {"compressed", "expanded"}:
        path = ".opencommerce/controller-primary.json.gz"
        raw = b"not gzip" if problem == "compressed" else gzip.compress(b"x" * 10000, mtime=0)
    fixture(tmp_path, {path: raw})
    if problem == "provenance":
        p = tmp_path / stage.PROVENANCE
        value = json.loads(p.read_bytes())
        value["commit_matches"] = False
        p.write_text(json.dumps(value))
    if problem == "changed":
        (tmp_path / path).write_bytes(b"new")
    if problem == "expanded":
        monkeypatch.setattr(gate, "MAX_FILE_BYTES", 2000)
    with pytest.raises((ValueError, OSError)):
        stage.prepare(tmp_path, "qualification", COMMIT)


def test_reruns_do_not_overwrite_staged_evidence(tmp_path: Path) -> None:
    fixture(tmp_path, {})
    result = stage.prepare(tmp_path, "diagnostics", COMMIT)
    with pytest.raises(FileExistsError):
        stage.prepare(tmp_path, "diagnostics", COMMIT)
    stage.verify(tmp_path, "diagnostics", COMMIT, result["receipt_sha256"])


@pytest.mark.parametrize("profile", tuple(stage.PROFILES))
def test_every_profile_retains_bound_provenance_and_rejects_wrong_commit(
    tmp_path: Path, profile: str
) -> None:
    fixture(tmp_path, {".opencommerce/controller-primary.json.gz": gzip.compress(b"{}", mtime=0)})
    result = stage.prepare(tmp_path, profile, COMMIT)
    stage.verify(tmp_path, profile, COMMIT, result["receipt_sha256"])
    with pytest.raises(ValueError):
        stage.verify(tmp_path, profile, "b" * 40, result["receipt_sha256"])
    assert (tmp_path / stage.BASE / profile / "upload" / stage.PROVENANCE).exists()


@pytest.mark.parametrize(
    "kind", ["filename", "comment", "extra", "timestamp", "trailing", "member"]
)
def test_unscanned_gzip_metadata_and_additional_members_are_rejected(kind: str) -> None:
    raw = gzip.compress(b'{"safe":"fixture"}', mtime=0)
    if kind == "filename":
        buffer = io.BytesIO()
        with gzip.GzipFile(
            fileobj=buffer, filename="private-header-canary", mode="wb", mtime=0
        ) as f:
            f.write(b'{"safe":"fixture"}')
        raw = buffer.getvalue()
    elif kind == "comment":
        raw = raw[:3] + b"\x10" + raw[4:10] + b"private-header-canary\0" + raw[10:]
    elif kind == "extra":
        raw = raw[:3] + b"\x04" + raw[4:10] + b"\x03\x00abc" + raw[10:]
    elif kind == "timestamp":
        raw = raw[:4] + b"abcd" + raw[8:]
    elif kind == "trailing":
        raw += b"private-trailing-canary"
    else:
        raw += gzip.compress(b"private-member-canary", mtime=0)
    with pytest.raises(ValueError):
        stage.decoded(raw, "controller-primary.json.gz")


def test_upload_steps_cannot_bypass_failed_privacy_or_provenance() -> None:
    for workflow in ("qualification.yml", "collect-release-evidence.yml"):
        jobs = yaml.safe_load(Path(".github/workflows", workflow).read_text())["jobs"]
        for job in jobs.values():
            for step in job["steps"]:
                path = step.get("with", {}).get("path", "")
                if "ci-upload/" not in path:
                    continue
                assert "steps.provenance.outcome == 'success'" in step["if"]
                assert "privacy.outcome == 'success'" in step["if"]
                assert "always()" in step["if"]
                assert not step.get("continue-on-error")
                assert path.endswith("/upload/")
    action = yaml.safe_load(Path(".github/actions/screen-diagnostics/action.yml").read_text())
    steps = action["runs"]["steps"]
    assert "prepare" in steps[0]["run"] and "verify" in steps[2]["run"]
    assert "steps.prepare.outputs.receipt_sha256" in steps[2]["env"]["EVIDENCE_RECEIPT_SHA256"]
    scan = steps[1]["run"]
    for argument in (
        "--network none",
        "--redact=100",
        "--ignore-gitleaks-allow",
        "--max-target-megabytes=32",
    ):
        assert argument in scan
    assert "/screen:/data:ro" in scan and "@sha256:" in scan
    assert all("if" not in step and not step.get("continue-on-error") for step in steps)
