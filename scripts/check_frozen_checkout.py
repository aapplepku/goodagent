"""Bind a clean export, optionally descended from a separately trusted root pin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.check_release_assessments import (
    BundleReader,
    FileRef,
    GateError,
    SafeParser,
    SourceSnapshot,
    digest,
    relative_path,
    require,
    strict_json,
)

SNAPSHOT = "SOURCE_SNAPSHOT.json"
GIT_TIMEOUT = 30
MAX_GIT_BYTES = 8 * 1024 * 1024
MAX_EXPORT_COMMITS = 256
GIT_ENV = {
    "PATH": os.defpath,
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_ATTR_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_NO_LAZY_FETCH": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
}


def _git(root: Path, *args: str) -> bytes:
    executable = shutil.which("git", path=os.defpath)
    require(executable is not None, "git_unavailable")
    command = [str(executable), "--no-pager"]
    for setting in (
        "core.fsmonitor=false",
        "core.hooksPath=/dev/null",
        "core.attributesFile=/dev/null",
        "core.excludesFile=/dev/null",
        "protocol.allow=never",
        "core.untrackedCache=false",
    ):
        command.extend(("-c", setting))
    with subprocess.Popen(
        [*command, *args],
        cwd=root,
        env=GIT_ENV,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        try:
            if process.stdout is None:
                raise GateError("git_pipe")
            output = bytearray()
            deadline = time.monotonic() + GIT_TIMEOUT
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    require(remaining > 0 and bool(selector.select(remaining)), "git_timeout")
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    output.extend(chunk)
                    require(len(output) <= MAX_GIT_BYTES, "git_output_budget")
            require(
                process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0, "git_failed"
            )
            return bytes(output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def _entries(raw: bytes, *, index: bool) -> dict[str, tuple[int, str]]:
    require(raw.endswith(b"\0"), "empty_git_membership")
    entries = {}
    for row in raw[:-1].split(b"\0"):
        metadata, name = row.decode("ascii").split("\t")
        mode, second, third = metadata.split(" ")
        oid = second if index else third
        path = relative_path(name)
        require(
            mode in {"100644", "100755"} and re.fullmatch(r"[0-9a-f]{40}", oid) is not None,
            "git_entry",
        )
        require((third == "0" if index else second == "blob") and path not in entries, "git_entry")
        entries[path] = (int(mode, 8) & 0o777, oid)
    require(len(entries) <= 4097, "git_membership_budget")
    return entries


def _history(root: Path, expected: str, expected_root: str | None) -> dict[str, Any] | None:
    rows = _git(root, "rev-list", "--all", "--parents", "HEAD").splitlines()
    require(len(rows) <= MAX_EXPORT_COMMITS, "export_history_budget")
    if expected_root is None:
        require(rows == [expected.encode()], "export_history")
    members: dict[str, list[str]] = {}
    for row in rows:
        fields = row.decode("ascii").split(" ")
        require(
            len(fields) in {1, 2}
            and all(re.fullmatch(r"[0-9a-f]{40}", field) for field in fields)
            and fields[0] not in members,
            "export_history",
        )
        members[fields[0]] = fields[1:]
    chain = []
    current = expected
    while True:
        require(current in members and current not in chain, "export_history")
        chain.append(current)
        parents = members[current]
        commit = _git(root, "cat-file", "commit", current)
        require(_blob_id(commit, "commit") == current, "commit_object")
        headers = commit.split(b"\n\n", 1)[0].splitlines()
        require(
            [line for line in headers if line.startswith(b"parent ")]
            == [f"parent {parent}".encode() for parent in parents],
            "export_history",
        )
        if not parents:
            break
        current = parents[0]
    require(current == (expected_root or expected) and len(chain) == len(members), "export_history")
    if expected_root is None:
        return None
    return {
        "policy": "pinned-linear-export-v1",
        "root_commit": expected_root,
        "commits": list(reversed(chain)),
    }


def _state(
    root: Path, expected: str, expected_root: str | None
) -> tuple[dict[str, tuple[int, str]], dict[str, Any] | None]:
    require(_git(root, "rev-parse", "--is-shallow-repository") == b"false\n", "shallow_repository")
    require(
        _git(root, "rev-parse", "--verify", "HEAD") == (expected + "\n").encode(), "head_mismatch"
    )
    history = _history(root, expected, expected_root)
    tree = _entries(_git(root, "ls-tree", "-rz", "--full-tree", "HEAD"), index=False)
    index = _entries(_git(root, "ls-files", "--stage", "-z"), index=True)
    require(tree == index, "staged_changes")
    require(not _git(root, "ls-files", "--others", "--exclude-standard", "-z"), "untracked_files")
    return tree, history


def _blob_id(raw: bytes, kind: str = "blob") -> str:
    return hashlib.sha1(f"{kind} {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()


def verify_checkout(
    root: Path, expected_commit: str, *, expected_root: str | None = None
) -> dict[str, Any]:
    """Return source bindings only; ignored build outputs are not export members."""
    require(
        isinstance(expected_commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", expected_commit) is not None,
        "commit_pin",
    )
    require(
        expected_root is None
        or (
            isinstance(expected_root, str)
            and re.fullmatch(r"[0-9a-f]{40}", expected_root) is not None
        ),
        "export_root_pin",
    )
    root = root.absolute()
    reader = BundleReader(root)
    try:
        git_members = reader.source_tree_paths(".git")
        require("shallow" not in git_members[0], "shallow_repository")
        require(
            not (
                {
                    "commondir",
                    "info/grafts",
                    "objects/info/alternates",
                    "objects/info/http-alternates",
                }
                & git_members[0]
            ),
            "external_git_storage",
        )
        reader.read(".git/config")
        # Parse only this file before allowing repository discovery; includes are forbidden.
        config = _git(
            Path("/"),
            "config",
            "--file",
            str(root / ".git/config"),
            "--no-includes",
            "--null",
            "--list",
        )
        for item in config.split(b"\0"):
            key = item.split(b"\n", 1)[0].lower()
            require(
                not key.startswith((b"include.", b"includeif.", b"extensions."))
                and key != b"core.worktree",
                "git_configuration",
            )
        before, history = _state(root, expected_commit, expected_root)
        raw, snapshot_mode = reader.read(SNAPSHOT)
        snapshot = SourceSnapshot.model_validate(strict_json(raw))
        records = [entry.model_dump() for entry in snapshot.files]
        encoded = (json.dumps(records, sort_keys=True, indent=2) + "\n").encode()
        require(digest(encoded) == snapshot.source_tree_sha256, "source_tree_digest")
        paths = [entry.path for entry in snapshot.files]
        require(paths == sorted(set(paths)) and SNAPSHOT not in paths, "snapshot_membership")
        require(set(before) == {*paths, SNAPSHOT}, "tracked_membership")
        for entry in snapshot.files:
            content, mode = reader.read(entry.path)
            require(
                (len(content), digest(content), mode) == (entry.bytes, entry.sha256, entry.mode),
                "source_binding",
            )
            require(before[entry.path] == (mode, _blob_id(content)), "git_blob_binding")
        require(before[SNAPSHOT] == (snapshot_mode, _blob_id(raw)), "snapshot_git_binding")
        require(_state(root, expected_commit, expected_root) == (before, history), "git_changed")
        reader.recheck()
        require(reader.source_tree_paths(".git") == git_members, "git_metadata_changed")
        with_root = BundleReader(root)
        try:
            require(
                os.fstat(reader.fd).st_ino == os.fstat(with_root.fd).st_ino
                and os.fstat(reader.fd).st_dev == os.fstat(with_root.fd).st_dev,
                "root_changed",
            )
        finally:
            with_root.close()
        result = {
            "source_tree_sha256": snapshot.source_tree_sha256,
            "commit_sha": expected_commit,
            "snapshot": FileRef(path=SNAPSHOT, sha256=digest(raw), size=len(raw)).model_dump(),
            "files_count": len(paths),
        }
        if history is not None:
            result["history"] = history
        return result
    finally:
        reader.close()


def main() -> int:
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--root", type=Path, default=Path.cwd())
        parser.add_argument("--commit", required=True)
        parser.add_argument("--export-root", help="Separately trusted original export commit pin")
        args = parser.parse_args()
        print(
            json.dumps(
                {
                    "valid": True,
                    **verify_checkout(args.root, args.commit, expected_root=args.export_root),
                }
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({"valid": False, "error": "invalid_checkout"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
