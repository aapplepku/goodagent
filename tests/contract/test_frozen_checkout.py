"""Tiny local export repositories only; synthetic identities, no remote operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import check_frozen_checkout as gate
from scripts.check_release_assessments import GateError, digest


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


class Export:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        self.names = [".gitattributes", ".gitignore", "app/[slug]/page.ts", "run.sh"]
        for name, raw in zip(
            self.names,
            (b"*.ts filter=fixture\n", b".build/\n", b"// synthetic\n", b"# never executed\n"),
            strict=True,
        ):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o755 if name == "run.sh" else 0o644)
        records = [
            {
                "path": name,
                "source": name,
                "sha256": digest((root / name).read_bytes()),
                "bytes": (root / name).stat().st_size,
                "mode": 0o755 if name == "run.sh" else 0o644,
            }
            for name in self.names
        ]
        self.snapshot: dict[str, Any] = {
            "schema_version": 1,
            "created_at": "2026-10-17T12:00:00Z",
            "purpose": "Synthetic exported fixture, not an approval",
            "provenance": "Synthetic source with no original history",
            "files": records,
            "source_tree_sha256": digest(encoded(records)),
        }
        self.save()
        self.git("init", "-b", "fixture")
        self.git("config", "user.name", "Synthetic Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.commit()

    def git(self, *args: str) -> str:
        executable = shutil.which("git", path=os.defpath)
        assert executable is not None
        result = subprocess.run(
            [executable, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
            cwd=self.root,
            env={
                **gate.GIT_ENV,
                "GIT_AUTHOR_DATE": "2026-10-17T12:00:00Z",
                "GIT_COMMITTER_DATE": "2026-10-17T12:00:00Z",
            },
            capture_output=True,
            check=True,
            timeout=10,
        )
        return result.stdout.decode().strip()

    def save(self) -> None:
        self.snapshot["source_tree_sha256"] = digest(encoded(self.snapshot["files"]))
        path = self.root / gate.SNAPSHOT
        path.write_bytes(encoded(self.snapshot))
        path.chmod(0o644)

    def commit(self, *, amend: bool = False) -> None:
        self.git("add", "--all")
        self.git("commit", *(["--amend"] if amend else []), "-m", "Synthetic export")
        self.head = self.git("rev-parse", "HEAD")


@pytest.fixture
def exported(tmp_path: Path) -> Export:
    return Export(tmp_path.resolve() / "export")


def test_exact_export_returns_bound_snapshot_and_ignores_build_outputs(exported: Export) -> None:
    (exported.root / ".build").mkdir()
    (exported.root / ".build/output").write_bytes(b"ignored output")
    raw = (exported.root / gate.SNAPSHOT).read_bytes()
    assert gate.verify_checkout(exported.root, exported.head) == {
        "source_tree_sha256": exported.snapshot["source_tree_sha256"],
        "commit_sha": exported.head,
        "snapshot": {"path": gate.SNAPSHOT, "sha256": digest(raw), "size": len(raw)},
        "files_count": 4,
    }
    assert gate.verify_checkout(exported.root, exported.head) == gate.verify_checkout(
        exported.root, exported.head
    )


def followup(exported: Export) -> tuple[str, str]:
    root_commit = exported.head
    name = "app/[slug]/page.ts"
    raw = b"// reviewed synthetic follow-up\n"
    (exported.root / name).write_bytes(raw)
    record = next(row for row in exported.snapshot["files"] if row["path"] == name)
    record.update(sha256=digest(raw), bytes=len(raw))
    exported.save()
    exported.commit()
    return root_commit, exported.head


def test_followup_requires_explicit_exact_export_root(exported: Export) -> None:
    root_commit, head = followup(exported)
    with pytest.raises(GateError, match="export_history"):
        gate.verify_checkout(exported.root, head)
    result = gate.verify_checkout(exported.root, head, expected_root=root_commit)
    assert result["commit_sha"] == head
    assert result["source_tree_sha256"] == exported.snapshot["source_tree_sha256"]
    assert result["history"] == {
        "root_commit": root_commit,
        "commits": [root_commit, head],
        "policy": "pinned-linear-export-v1",
    }


@pytest.mark.parametrize("pin", ["", "HEAD", "f" * 40, "A" * 40, "--help"])
def test_followup_rejects_invalid_or_unrelated_root(exported: Export, pin: str) -> None:
    _, head = followup(exported)
    with pytest.raises(GateError):
        gate.verify_checkout(exported.root, head, expected_root=pin)


def test_tip_cannot_masquerade_as_original_export_root(exported: Export) -> None:
    _, head = followup(exported)
    with pytest.raises(GateError, match="export_history"):
        gate.verify_checkout(exported.root, head, expected_root=head)


def test_followup_rejects_unrelated_refs_and_merged_history(exported: Export) -> None:
    root_commit, head = followup(exported)
    exported.git("checkout", "--orphan", "private-unrelated")
    exported.git("commit", "--allow-empty", "-m", "Unrelated synthetic history")
    exported.git("checkout", "fixture")
    with pytest.raises(GateError, match="export_history"):
        gate.verify_checkout(exported.root, head, expected_root=root_commit)
    exported.git("branch", "-D", "private-unrelated")
    exported.git("checkout", "-b", "side", root_commit)
    exported.git("commit", "--allow-empty", "-m", "Side branch")
    exported.git("checkout", "fixture")
    exported.git("merge", "--no-ff", "side", "-m", "Synthetic merge")
    with pytest.raises(GateError, match="export_history"):
        gate.verify_checkout(
            exported.root, exported.git("rev-parse", "HEAD"), expected_root=root_commit
        )


def test_followup_history_has_explicit_commit_budget(
    exported: Export, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_commit, head = followup(exported)
    monkeypatch.setattr(gate, "MAX_EXPORT_COMMITS", 1)
    with pytest.raises(GateError, match="export_history_budget"):
        gate.verify_checkout(exported.root, head, expected_root=root_commit)


@pytest.mark.parametrize("change", ["modified", "snapshot", "mode", "staged", "untracked"])
def test_followup_keeps_all_current_source_binding_guards(exported: Export, change: str) -> None:
    root_commit, head = followup(exported)
    if change == "modified":
        (exported.root / "run.sh").write_bytes(b"dirty current source")
    elif change == "snapshot":
        exported.snapshot["purpose"] = "uncommitted manifest"
        exported.save()
    elif change == "mode":
        (exported.root / "run.sh").chmod(0o644)
    else:
        (exported.root / "unexpected.txt").write_bytes(b"unreviewed")
        if change == "staged":
            exported.git("add", "unexpected.txt")
    with pytest.raises((GateError, OSError)):
        gate.verify_checkout(exported.root, head, expected_root=root_commit)


def test_exact_braces_patch_path_is_bound_to_committed_bytes(exported: Export) -> None:
    name = "infra/patches/braces@3.0.3.patch"
    path = exported.root / name
    path.parent.mkdir(parents=True)
    raw = b"synthetic patch bytes\n"
    path.write_bytes(raw)
    path.chmod(0o644)
    exported.snapshot["files"].append(
        {"path": name, "source": name, "sha256": digest(raw), "bytes": len(raw), "mode": 0o644}
    )
    exported.snapshot["files"].sort(key=lambda row: row["path"])
    exported.save()
    exported.commit(amend=True)
    result = gate.verify_checkout(exported.root, exported.head)
    assert result["files_count"] == 5
    assert result["source_tree_sha256"] == exported.snapshot["source_tree_sha256"]
    path.write_bytes(b"changed patch bytes\n")
    with pytest.raises(GateError, match="^source_binding$"):
        gate.verify_checkout(exported.root, exported.head)


@pytest.mark.parametrize("pin", ["", "HEAD", "f" * 40, "a" * 39, "A" * 40, "--help"])
def test_requires_exact_commit_pin(exported: Export, pin: str) -> None:
    with pytest.raises(GateError):
        gate.verify_checkout(exported.root, pin)


@pytest.mark.parametrize(
    "change",
    ["modified", "deleted", "untracked", "staged", "snapshot", "history", "mode", "assume", "skip"],
)
def test_dirty_or_historical_export_fails(exported: Export, change: str) -> None:
    path = exported.root / "run.sh"
    if change in {"assume", "skip"}:
        exported.git(
            "update-index",
            "--assume-unchanged" if change == "assume" else "--skip-worktree",
            "run.sh",
        )
        path.write_bytes(b"hidden dirty bytes")
    elif change == "modified":
        path.write_bytes(b"changed")
    elif change == "deleted":
        path.unlink()
    elif change in {"untracked", "staged"}:
        (exported.root / "extra.txt").write_bytes(b"extra")
        if change == "staged":
            exported.git("add", "extra.txt")
    elif change == "snapshot":
        (exported.root / gate.SNAPSHOT).write_bytes(b"{}")
    elif change == "history":
        exported.git("commit", "--allow-empty", "-m", "Not a history-free export")
        exported.head = exported.git("rev-parse", "HEAD")
    else:
        exported.git("config", "core.filemode", "false")
        path.chmod(0o644)
    with pytest.raises((ValueError, OSError)):
        gate.verify_checkout(exported.root, exported.head)


@pytest.mark.parametrize("changed_source", [True, False])
def test_rewritten_snapshot_cannot_override_committed_blobs(
    exported: Export, changed_source: bool
) -> None:
    exported.git("update-index", "--assume-unchanged", "run.sh", gate.SNAPSHOT)
    if changed_source:
        raw = b"new bytes acknowledged only by an uncommitted snapshot"
        (exported.root / "run.sh").write_bytes(raw)
        record = next(row for row in exported.snapshot["files"] if row["path"] == "run.sh")
        record.update(sha256=digest(raw), bytes=len(raw))
    else:
        exported.snapshot["provenance"] = "Changed uncommitted provenance"
    exported.save()
    with pytest.raises(
        GateError, match="^git_blob_binding$" if changed_source else "^snapshot_git_binding$"
    ):
        gate.verify_checkout(exported.root, exported.head)


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "unsorted",
        "missing",
        "self",
        "unsafe",
        "size",
        "digest",
        "mode",
        "extra-field",
        "tree-digest",
    ],
)
def test_committed_bad_manifest_is_not_authoritative(exported: Export, change: str) -> None:
    records = exported.snapshot["files"]
    if change == "duplicate":
        records.append(records[0].copy())
    elif change == "unsorted":
        records.reverse()
    elif change == "missing":
        records.pop()
    elif change in {"self", "unsafe"}:
        records[0]["path"] = gate.SNAPSHOT if change == "self" else "../outside"
    elif change == "size":
        records[0]["bytes"] += 1
    elif change == "digest":
        records[0]["sha256"] = "f" * 64
    elif change == "mode":
        records[0]["mode"] = 0o600
    elif change == "extra-field":
        records[0]["unreviewed"] = True
    exported.save()
    if change == "tree-digest":
        exported.snapshot["source_tree_sha256"] = "0" * 64
        (exported.root / gate.SNAPSHOT).write_bytes(encoded(exported.snapshot))
    exported.commit(amend=True)
    with pytest.raises(ValueError):
        gate.verify_checkout(exported.root, exported.head)


@pytest.mark.parametrize("change", ["symlink", "hardlink", "parent", "root", "gitdir"])
def test_linked_inputs_are_rejected(exported: Export, tmp_path: Path, change: str) -> None:
    root = exported.root
    path = root / "run.sh"
    if change == "hardlink":
        os.link(path, tmp_path / "second-name")
    elif change == "symlink":
        outside = tmp_path / "outside"
        path.rename(outside)
        path.symlink_to(outside)
    elif change in {"parent", "gitdir"}:
        path = root / ("app" if change == "parent" else ".git")
        outside = tmp_path / "outside"
        path.rename(outside)
        path.symlink_to(outside, target_is_directory=True)
    else:
        root = tmp_path / "alias"
        root.symlink_to(exported.root, target_is_directory=True)
    with pytest.raises((GateError, OSError)):
        gate.verify_checkout(root, exported.head)


@pytest.mark.parametrize(
    "name",
    [
        "commondir",
        "info/grafts",
        "objects/info/alternates",
        "objects/info/http-alternates",
    ],
)
def test_git_external_storage_and_history_overrides_fail(exported: Export, name: str) -> None:
    (exported.root / ".git" / name).write_bytes(b"/not-an-authorized-input\n")
    with pytest.raises(GateError, match="external_git_storage"):
        gate.verify_checkout(exported.root, exported.head)


def test_shallow_checkout_is_rejected_even_with_single_visible_commit(exported: Export) -> None:
    (exported.root / ".git/shallow").write_text(exported.head + "\n")
    assert exported.git("rev-list", "--count", "--all") == "1"
    assert exported.git("rev-parse", "--is-shallow-repository") == "true"
    with pytest.raises(GateError, match="shallow_repository"):
        gate.verify_checkout(exported.root, exported.head)


def test_git_does_not_execute_filters_hooks_or_fsmonitor(exported: Export, tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    command = f"touch {marker}"
    for key in ("core.fsmonitor", "filter.fixture.clean", "diff.external"):
        exported.git("config", key, command)
    hook = exported.root / ".git/hooks/post-index-change"
    hook.write_text(f"#!/bin/sh\n{command}\n")
    hook.chmod(0o755)
    gate.verify_checkout(exported.root, exported.head)
    assert not marker.exists()


def test_git_config_includes_are_not_followed(exported: Export) -> None:
    exported.git("config", "include.path", "/not-an-authorized-input")
    with pytest.raises(GateError, match="git_configuration"):
        gate.verify_checkout(exported.root, exported.head)


def test_inherited_git_environment_cannot_redirect_checkout(
    exported: Export, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_CONFIG_GLOBAL",
        "GIT_SHALLOW_FILE",
        "GIT_INDEX_FILE",
    ):
        monkeypatch.setenv(key, "/not-an-authorized-input")
    assert gate.verify_checkout(exported.root, exported.head)["commit_sha"] == exported.head


@pytest.mark.parametrize(
    "limit,error", [("GIT_TIMEOUT", "git_timeout"), ("MAX_GIT_BYTES", "git_output_budget")]
)
def test_git_failure_bounds_reap_the_owned_process(
    exported: Export, monkeypatch: pytest.MonkeyPatch, limit: str, error: str
) -> None:
    processes = []
    original = subprocess.Popen

    def start(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(gate, limit, 0)
    monkeypatch.setattr(subprocess, "Popen", start)
    with pytest.raises(GateError, match=error):
        gate._git(exported.root, "--version")
    assert len(processes) == 1 and processes[0].poll() is not None


def test_final_recheck_catches_source_change(
    exported: Export, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = gate._git
    calls = 0

    def changed(root: Path, *args: str) -> bytes:
        nonlocal calls
        raw = original(root, *args)
        if args == ("ls-files", "--others", "--exclude-standard", "-z"):
            calls += 1
            if calls == 2:
                (exported.root / "run.sh").write_bytes(b"changed during final phase")
        return raw

    monkeypatch.setattr(gate, "_git", changed)
    with pytest.raises(GateError, match="file_changed"):
        gate.verify_checkout(exported.root, exported.head)


def test_cli_defaults_to_cwd_and_never_echoes_bad_input(
    exported: Export, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(exported.root)
    monkeypatch.setattr(sys, "argv", ["check_frozen_checkout", "--commit", exported.head])
    assert gate.main() == 0
    assert json.loads(capsys.readouterr().out)["snapshot"]["path"] == gate.SNAPSHOT
    monkeypatch.setattr(sys, "argv", ["check_frozen_checkout", "--commit", "private-placeholder"])
    assert gate.main() == 1
    assert json.loads(capsys.readouterr().out) == {"valid": False, "error": "invalid_checkout"}
