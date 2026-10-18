"""Hash-bind text diagnostics to a separate secret-screened upload tree.

The workflow must run the pinned offline secret scanner between prepare and verify.
This is an upload-privacy boundary, never a vulnerability or qualification waiver.
Binary browser evidence needs separate human review and is not uploaded here.
"""

from __future__ import annotations

import argparse
import json
import os
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

from scripts import check_release_assessments as gate
from scripts import collect_release_evidence as collector
from scripts.stage_release_upload import new_file

BASE = ".opencommerce/ci-upload"
PROVENANCE = ".opencommerce/ci-evidence/provenance.json"
PROFILES = {
    "qualification": (
        ".opencommerce/ci-evidence/*",
        ".opencommerce/*-proof.json",
        ".opencommerce/source-scans/*",
        ".opencommerce/security-scans/final/*.json",
        ".opencommerce/controller-*",
        "security/*assessments.json",
        "security/reviewed-image-findings.json",
        "apps/web/test-results/self-hosted-compose/*/receipt.json",
    ),
    "shard": (".opencommerce/controller-*", ".opencommerce/ci-evidence/*"),
    "complete": (
        ".opencommerce/controller-primary.json.gz",
        ".opencommerce/controller-reproduction.json.gz",
        ".opencommerce/controller-assembly.json",
        PROVENANCE,
    ),
    "diagnostics": (".opencommerce/ci-evidence/*.json", ".opencommerce/source-scans/*"),
}
SUFFIXES = (".json", ".jsonl", ".json.gz", ".log", ".stdout", ".stderr", ".txt")
MAX_TOTAL = 256 * 1024 * 1024


def selected(path: str, profile: str) -> bool:
    name = PurePosixPath(gate.relative_path(path))
    return path.endswith(SUFFIXES) and any(name.match(p) for p in PROFILES[profile])


def decoded(raw: bytes, path: str) -> bytes:
    if path.endswith(".gz"):
        # Our benchmark writers use gzip.compress(..., mtime=0). Reject optional
        # names/comments/extra fields and trailers that text-only screening misses.
        gate.require(
            len(raw) >= 18 and raw[:8] == b"\x1f\x8b\x08\x00\x00\x00\x00\x00",
            "gzip_metadata",
        )
        decoder = zlib.decompressobj(wbits=31)
        raw = decoder.decompress(raw, gate.MAX_FILE_BYTES + 1)
        gate.require(len(raw) <= gate.MAX_FILE_BYTES, "expanded_file_budget")
        gate.require(
            decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            "gzip_single_member",
        )
    raw.decode("utf-8", errors="strict")
    return raw


def require_tree(reader: gate.BundleReader, directory: str, paths: set[str]) -> None:
    directories = {"."}
    for path in paths:
        directories.update(str(parent) for parent in PurePosixPath(path).parents)
    expected = (paths, directories)
    gate.require(reader.source_tree_paths(directory) == expected, "staging_membership")
    reader.source_memberships[directory] = expected


def prepare(root: Path, profile: str, commit: str) -> dict[str, Any]:
    gate.require(profile in PROFILES, "profile")
    gate.require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "commit")
    reader = gate.BundleReader(root)
    try:
        provenance = gate.strict_json(reader.read(PROVENANCE)[0])
        gate.require(
            provenance.get("commit_matches") is True
            and provenance.get("commit_sha") == commit
            and provenance.get("expected_commit_sha") == commit,
            "provenance_commit",
        )
        refs = [
            gate.FileRef.model_validate(
                {"path": item["path"], "sha256": item["sha256"], "size": item["bytes"]}
            )
            for item in provenance["files"]
            if selected(item["path"], profile)
        ]
        refs.append(collector.reference(reader, PROVENANCE))
        gate.require(len({r.path for r in refs}) == len(refs), "duplicate_path")
        gate.require(len(refs) <= gate.MAX_FILES, "file_count_budget")
        prefix = f"{BASE}/{profile}"
        # Exclusive directories prevent stale or partially screened runs being reused.
        with new_file(reader, prefix + "/reserved"):
            pass
        parent = reader.directory(prefix)
        try:
            os.mkdir("upload", mode=0o700, dir_fd=parent)
            os.mkdir("screen", mode=0o700, dir_fd=parent)
        finally:
            os.close(parent)
        records = []
        total = 0
        for ref in sorted(refs, key=lambda r: r.path):
            raw = reader.bound(ref)
            text = decoded(raw, ref.path)
            total += len(raw) + len(text)
            gate.require(total <= MAX_TOTAL, "total_budget")
            # Scanner archive exclusions must not skip this already-expanded text.
            scan_path = ref.path.removesuffix(".gz") + ".screen.txt"
            if ref.path.startswith(".opencommerce/security-scans/final/"):
                # Preserve the collector's exact /data/<service> report names so
                # its existing narrow public-fingerprint allowlist still applies.
                scan_path = ref.path.removeprefix(".opencommerce/security-scans/final/")
            with new_file(reader, prefix + "/upload/" + ref.path) as handle:
                handle.write(raw)
            with new_file(reader, prefix + "/screen/" + scan_path) as handle:
                handle.write(text)
            records.append(
                {
                    "upload": collector.reference(
                        reader, prefix + "/upload/" + ref.path
                    ).model_dump(),
                    "screen": collector.reference(
                        reader, prefix + "/screen/" + scan_path
                    ).model_dump(),
                }
            )
        receipt = {"schema_version": 1, "commit": commit, "profile": profile, "files": records}
        receipt_ref = collector.write_new(root, prefix + "/receipt.json", receipt)
        reader.recheck()
        return {
            "prepared_files": len(records),
            "receipt_sha256": receipt_ref.sha256,
            "qualification_passed": False,
        }
    finally:
        reader.close()


def verify(root: Path, profile: str, commit: str, receipt_sha256: str) -> dict[str, Any]:
    gate.require(profile in PROFILES, "profile")
    reader = gate.BundleReader(root)
    prefix = f"{BASE}/{profile}"
    try:
        raw = reader.read(prefix + "/receipt.json")[0]
        gate.require(gate.digest(raw) == receipt_sha256, "receipt_binding")
        receipt = gate.strict_json(raw)
        gate.require(
            receipt.get("schema_version") == 1
            and receipt.get("commit") == commit
            and receipt.get("profile") == profile,
            "receipt_context",
        )
        paths: dict[str, set[str]] = {"upload": set(), "screen": set()}
        for item in receipt["files"]:
            for kind in paths:
                ref = gate.FileRef.model_validate(item[kind])
                expected = prefix + "/" + kind + "/"
                gate.require(ref.path.startswith(expected), "receipt_path")
                gate.require(ref.path not in paths[kind], "duplicate_path")
                reader.bound(ref)
                paths[kind].add(ref.path.removeprefix(expected))
            upload = gate.FileRef.model_validate(item["upload"])
            screen = gate.FileRef.model_validate(item["screen"])
            gate.require(
                decoded(reader.bound(upload), upload.path) == reader.bound(screen), "screen_content"
            )
        gate.require(bool(paths["upload"]), "empty_staging")
        for kind, members in paths.items():
            require_tree(reader, prefix + "/" + kind, members)
        reader.recheck()
        return {"verified_files": len(paths["upload"]), "qualification_passed": False}
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument("profile", choices=tuple(PROFILES))
    args = parser.parse_args()
    try:
        commit = os.environ.get("EVIDENCE_COMMIT", "")
        if args.phase == "prepare":
            result = prepare(Path.cwd(), args.profile, commit)
            if output := os.environ.get("GITHUB_OUTPUT"):
                with Path(output).open("a") as stream:
                    stream.write(f"receipt_sha256={result['receipt_sha256']}\n")
        else:
            result = verify(
                Path.cwd(), args.profile, commit, os.environ.get("EVIDENCE_RECEIPT_SHA256", "")
            )
    except (OSError, ValueError, KeyError, TypeError, zlib.error):
        print('{"upload_allowed":false,"reason":"diagnostics_privacy_staging_failed"}')
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
