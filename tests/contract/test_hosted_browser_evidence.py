"""Retained browser evidence is complete, recursive and read without following links."""

import hashlib
import json
import os
import runpy
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def recorder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    module = runpy.run_path(str(ROOT / "scripts/record-hosted-evidence.py"))

    def version(*args: str) -> str:
        return "a" * 40 if args == ("git", "rev-parse", "HEAD") else "synthetic version"

    monkeypatch.setitem(module["main"].__globals__, "version", version)
    monkeypatch.setenv("EVIDENCE_COMMIT", "a" * 40)
    monkeypatch.setenv("EVIDENCE_WORKFLOW_PATH", ".github/workflows/qualification.yml")
    monkeypatch.setenv("EVIDENCE_STAGE_OUTCOMES", "{}")
    monkeypatch.chdir(tmp_path)
    return module


def test_browser_trees_are_hashed_but_only_screened_diagnostics_are_uploaded(
    recorder: dict[str, Any],
) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/qualification.yml").read_text())
    upload = next(
        step
        for step in workflow["jobs"]["verify"]["steps"]
        if "upload-artifact@" in step.get("uses", "")
    )
    assert "always()" in upload["if"]
    assert "steps.artifact_privacy.outcome == 'success'" in upload["if"]
    assert upload["with"]["include-hidden-files"] is True
    uploaded = upload["with"]["path"].splitlines()
    fixtures = {}
    for app in ("web", "shopper"):
        assert f"apps/{app}/test-results/" not in uploaded
        for relative in (
            "failure/nested/trace.zip",
            "failure/screenshot.png",
            ".last-run.json",
            "self-hosted-compose/receipt.json",
        ):
            path = Path(f"apps/{app}/test-results/{relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = f"synthetic {app} {relative}".encode()
            path.write_bytes(raw)
            fixtures[str(path)] = {
                "path": str(path),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
    recorder["main"]()
    result = json.loads(Path(".opencommerce/ci-evidence/provenance.json").read_bytes())
    assert {row["path"]: row for row in result["files"]} == fixtures
    assert result["commit_matches"] is True
    assert uploaded == [".opencommerce/ci-upload/qualification/upload/"]


def test_early_failure_without_browser_directories_still_records(recorder: dict[str, Any]) -> None:
    recorder["main"]()
    result = json.loads(Path(".opencommerce/ci-evidence/provenance.json").read_bytes())
    assert result["files"] == []


@pytest.mark.parametrize("app", ["web", "shopper"])
@pytest.mark.parametrize(
    "kind",
    [
        "file-link",
        "broken-link",
        "directory-link",
        "root-link",
        "ancestor-link",
        "hardlink",
        "fifo",
        "root-file",
    ],
)
def test_unsafe_browser_evidence_fails_closed(
    recorder: dict[str, Any], tmp_path: Path, app: str, kind: str
) -> None:
    root = Path(f"apps/{app}/test-results")
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"must never be read or changed")
    leaf = root / "trace.zip"
    if kind == "file-link":
        leaf.symlink_to(sentinel)
    elif kind == "broken-link":
        leaf.symlink_to(outside / "missing")
    elif kind == "directory-link":
        (root / "nested").symlink_to(outside, target_is_directory=True)
    elif kind in {"root-link", "root-file"}:
        root.rmdir()
        if kind == "root-link":
            root.symlink_to(outside, target_is_directory=True)
        else:
            root.write_bytes(b"not a directory")
    elif kind == "ancestor-link":
        root.rmdir()
        root.parent.rmdir()
        root.parent.symlink_to(outside, target_is_directory=True)
    elif kind == "hardlink":
        os.link(sentinel, leaf)
    else:
        os.mkfifo(leaf)
    with pytest.raises((OSError, ValueError)):
        recorder["main"]()
    assert sentinel.read_bytes() == b"must never be read or changed"
    assert not Path(".opencommerce/ci-evidence/provenance.json").exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_output_cannot_overwrite_linked_or_nonregular_files(
    recorder: dict[str, Any], tmp_path: Path, kind: str
) -> None:
    output = Path(".opencommerce/ci-evidence/provenance.json")
    output.parent.mkdir(parents=True)
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"preserve this")
    if kind == "symlink":
        output.symlink_to(sentinel)
    elif kind == "hardlink":
        os.link(sentinel, output)
    else:
        os.mkfifo(output)
    with pytest.raises((OSError, ValueError)):
        recorder["main"]()
    assert sentinel.read_bytes() == b"preserve this"


def test_output_parent_symlink_is_not_followed(recorder: dict[str, Any], tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    Path(".opencommerce").symlink_to(outside, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        recorder["main"]()
    assert list(outside.iterdir()) == []


def test_file_hash_rejects_ancestor_replaced_during_read(
    recorder: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "original"
    parent.mkdir()
    evidence = parent / "trace.zip"
    evidence.write_bytes(b"synthetic trace")
    other = tmp_path / "other"
    other.mkdir()
    (other / "trace.zip").write_bytes(b"replacement trace")
    original_digest = hashlib.file_digest

    def replace_parent(handle: Any, algorithm: str) -> Any:
        result = original_digest(handle, algorithm)
        parent.rename(tmp_path / "moved")
        parent.symlink_to(other, target_is_directory=True)
        return result

    monkeypatch.setattr(hashlib, "file_digest", replace_parent)
    with pytest.raises(ValueError, match="directory changed"):
        recorder["file_record"](evidence)


def test_disappearing_browser_descendant_is_not_silently_omitted(
    recorder: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path("apps/web/test-results")
    child = root / "nested"
    child.mkdir(parents=True)
    original = recorder["browser_evidence_files"]

    def disappear(path: Path, *, optional: bool = True) -> list[Path]:
        if path == child:
            child.rmdir()
        result: list[Path] = original(path, optional=optional)
        return result

    monkeypatch.setitem(original.__globals__, "browser_evidence_files", disappear)
    with pytest.raises(FileNotFoundError):
        recorder["main"]()
