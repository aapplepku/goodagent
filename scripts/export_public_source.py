"""Stage a history-free source candidate from an explicit, hash-checked inventory.

This creates private review material only. It does not qualify, commit or publish it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.source_only_notices import COLLECTIONS, public_file, public_retention

ROOT = Path(__file__).resolve().parents[1]
EXPORT_OVERRIDES = {".github/workflows/ci.yml": "infra/github/public-ci.yml"}
RETAINED_ARCHIVES: dict[str, str] = json.loads(
    (ROOT / "infra/public-export-archives.json").read_bytes()
)
RETAINED_ASSETS: dict[str, str] = json.loads(
    (ROOT / "infra/public-export-assets.json").read_bytes()
)
DATA_DIRECTORIES = (
    "examples/datasets/",
    "packages/backend/src/open_commerce/stores/sample_data/",
)
ARCHIVE_SUFFIXES = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".tbz",
    ".tbz2",
    ".xz",
    ".txz",
    ".zst",
    ".lz",
    ".lzma",
    ".whl",
    ".jar",
    ".war",
}
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
DIRECTORIES = {"apps", "packages", "scripts", "tests", "docs", "examples", "infra", "security"}
ROOT_FILES = {
    "AGENTS.md",
    "PLANS.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "NOTICE",
    "DCO.md",
    "CODE_OF_CONDUCT.md",
    "THIRD_PARTY_NOTICES.md",
    "Makefile",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "docker-compose.yml",
    "alembic.ini",
    "conftest.py",
    ".env.example",
    ".editorconfig",
    ".gitignore",
    ".dockerignore",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
}
PRIVATE_TOOLS = {
    "scripts/build_claude_handoff.py",
    "scripts/claude_exchange.py",
    "scripts/claude_review_cycle.py",
    "scripts/claude_ui_evidence.py",
    "tests/contract/test_claude_handoff.py",
    "tests/contract/test_claude_exchange.py",
    "tests/contract/test_claude_review_cycle.py",
    "tests/contract/test_claude_ui_evidence.py",
    "scripts/snapshot-checkout.py",
}
PRIVATE_EVIDENCE = {
    "examples/eval/merchandising-decisions-v2/hosted/original/api-evidence.json",
    "examples/eval/merchandising-decisions-v2/validation/remote-delivery.json",
}
PRIVATE_PARTS = {
    ".git",
    ".opencommerce",
    "qa",
    ".env",
    ".venv",
    ".tools",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    "test-results",
    "playwright-report",
    "coverage",
    "htmlcov",
}
ENV_TEMPLATES = {".env.example", "infra/docker/hosted.env.example"}
SOURCE_ENV_FILES = {"packages/backend/src/open_commerce/persistence/migrations/env.py"}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".json",
    ".jsonl",
    ".csv",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".sh",
    ".lock",
    ".example",
    ".mako",
    ".patch",
}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".pdf", ".webm", ".mp4", ".vtt"}
EXTENSIONLESS_FILES = {".gitkeep", "COPYRIGHT", "Dockerfile", "LICENSE", "NOTICE", "healthcheck"}
SECRET = re.compile(
    rb"(?:sk-(?:proj-)?[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
LOCAL_PATH = re.compile(rb"/(?:Users|home)/[^/\s\"']+/|/private/" rb"var/folders/")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def private_environment_name(name: str) -> bool:
    return (
        name.lower() == "env"
        or name.lower().startswith(".env")
        or re.search(r"\.env(?:[.~_-]|$)", name, re.IGNORECASE) is not None
    )


def omission(path: str) -> str | None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in path or ":" in path:
        raise ValueError("invalid relative source path")
    if not candidate.parts or candidate.as_posix() != path:
        raise ValueError("non-canonical source path")
    if path in PRIVATE_TOOLS:
        return "private review tooling and dependent tests"
    if path.lower() in PRIVATE_EVIDENCE:
        return "private account/tool-response evidence; public failure summary provided separately"
    if (
        any(
            part.lower() in PRIVATE_PARTS
            or part.lower().startswith((".next", ".env."))
            or private_environment_name(part)
            or part.lower().endswith((".egg-info", ".tsbuildinfo"))
            for part in candidate.parts
        )
        and path not in ENV_TEMPLATES | SOURCE_ENV_FILES
    ):
        return "private or generated state"
    if candidate.suffix.lower() in ARCHIVE_SUFFIXES and path not in RETAINED_ARCHIVES:
        return "unapproved archive"
    if candidate.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key"}:
        return "unapproved archive, runtime data or credential file"
    if (
        candidate.suffix.lower() in MEDIA_SUFFIXES
        or candidate.suffix.lower() == ".csv"
        or path.startswith(DATA_DIRECTORIES)
    ) and path not in RETAINED_ASSETS:
        return "unreviewed media or dataset file"
    if path in ROOT_FILES or path == "openapi/openapi.json":
        return None
    if (
        candidate.suffix.lower() not in TEXT_SUFFIXES | MEDIA_SUFFIXES
        and candidate.name not in EXTENSIONLESS_FILES
        and path not in RETAINED_ARCHIVES
    ):
        return "unapproved file type; explicit review required"
    if candidate.parts[0] in DIRECTORIES or path.startswith(".github/"):
        return None
    return "outside the public source selection"


def inspect_text(content: bytes, relative: str, *, check_paths: bool) -> None:
    if SECRET.search(content):
        raise ValueError(f"credential-shaped content; review privately: {relative}")
    if check_paths and LOCAL_PATH.search(content):
        raise ValueError(f"workstation path; review privately: {relative}")


def compressed_or_archive(content: bytes) -> bool:
    return (
        content.startswith(
            (
                b"PK\x03\x04",
                b"PK\x05\x06",
                b"\x1f\x8b",
                b"7z\xbc\xaf\x27\x1c",
                b"Rar!",
                b"\xfd7zXZ\x00",
                b"BZh",
                b"\x28\xb5\x2f\xfd",
                b"MSCF",
                b"\x04\x22\x4d\x18",
                b"\x02\x21\x4c\x18",
                b"070701",
                b"070702",
                b"070707",
                b"\x71\xc7",
                b"\xc7\x71",
            )
        )
        or content[257:262] == b"ustar"
    )


def inspect_archive(content: bytes, relative: str) -> None:
    if digest(content) != RETAINED_ARCHIVES.get(relative):
        raise ValueError(f"retained archive changed; review privately: {relative}")
    # Never extract to disk. Bound the total expansion, including tar headers.
    with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
        expanded = compressed.read(MAX_EXPANDED_BYTES + 1)
    if len(expanded) > MAX_EXPANDED_BYTES:
        raise ValueError(f"oversized archive expansion: {relative}")
    if relative.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
            for index, member in enumerate(archive):
                parts = PurePosixPath(member.name)
                if (
                    index >= 10000
                    or not member.isfile()
                    or parts.is_absolute()
                    or ".." in parts.parts
                    or "\\" in member.name
                    or member.size > MAX_EXPANDED_BYTES
                ):
                    raise ValueError(f"unsafe retained archive member: {relative}")
                if any(
                    part.lower() in {".git", ".opencommerce", "qa"}
                    or private_environment_name(part)
                    for part in parts.parts
                ):
                    raise ValueError(f"private retained archive member: {relative}")
                inspect_text(
                    encoded(
                        {
                            "name": member.name,
                            "uname": member.uname,
                            "gname": member.gname,
                            "pax_headers": member.pax_headers,
                        }
                    ),
                    relative,
                    check_paths=True,
                )
                stream = archive.extractfile(member)
                assert stream is not None
                text = stream.read(MAX_EXPANDED_BYTES + 1)
                if compressed_or_archive(text):
                    raise ValueError(f"nested archive requires separate review: {relative}")
                inspect_text(text, relative, check_paths=True)
    else:
        if compressed_or_archive(expanded):
            raise ValueError(f"nested archive requires separate review: {relative}")
        inspect_text(expanded, relative, check_paths=True)


def validate_destination(root: Path, output: Path) -> None:
    source, destination = root.resolve(), output.resolve()
    if output.exists() or output.is_symlink() or source.is_relative_to(destination):
        raise ValueError("choose a new destination, not the source or its parent")
    if destination.is_relative_to(source) and not destination.is_relative_to(
        source / ".opencommerce"
    ):
        raise ValueError("destination must be outside the checkout or in .opencommerce")
    if any(part.is_symlink() for part in [output, *output.parents]):
        raise ValueError("symlink destination is not allowed")


def read_source(root: Path, relative: str) -> tuple[bytes, int]:
    if omission(relative) is not None:
        raise ValueError(f"private/unselected source member: {relative}")
    path = root / relative
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
        raise ValueError(f"symlink source member: {relative}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("source member escapes root")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
        raise ValueError(f"non-regular or oversized source member: {relative}")
    content = path.read_bytes()
    if relative in RETAINED_ASSETS and digest(content) != RETAINED_ASSETS[relative]:
        raise ValueError(f"retained asset changed; review privately: {relative}")
    if relative in RETAINED_ARCHIVES:
        inspect_archive(content, relative)
    elif compressed_or_archive(content):
        raise ValueError(f"unapproved archive content: {relative}")
    elif relative not in RETAINED_ASSETS:
        # PDF readers tolerate a preamble; inspect header starts in the first 1 KiB.
        pdf_header = content.find(b"%PDF-", 0, 1028)
        if 0 <= pdf_header < 1024 or content.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8")):
            raise ValueError(f"unreviewed binary content: {relative}")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"non-text content requires explicit review: {relative}") from None
        if b"\x00" in content:
            raise ValueError(f"non-text content requires explicit review: {relative}")
    # Test fixtures intentionally contain fake paths; the full export still needs Gitleaks.
    inspect_text(
        content,
        relative,
        check_paths=path.suffix in TEXT_SUFFIXES
        and not relative.startswith(("tests/", "packages/backend/tests/")),
    )
    return content, 0o755 if info.st_mode & stat.S_IXUSR else 0o644


def source_paths(root: Path) -> list[str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return sorted({os.fsdecode(name) for name in raw.split(b"\0") if name})


def read_public_source(root: Path, relative: str) -> tuple[bytes, int]:
    content, mode = read_source(root, relative)
    if relative == "infra/public-export-archives.json":
        return public_retention(content), mode
    if any(
        relative == f"{directory}/{policy[key]}"
        for directory, policy in COLLECTIONS.items()
        for key in ("manifest", "archive")
    ):
        return public_file(relative, lambda name: read_source(root, name)[0]), mode
    return content, mode


def inventory(root: Path, paths: list[str]) -> dict[str, Any]:
    files = []
    excluded = {}
    for relative in sorted(set(paths)):
        reason = omission(relative)
        if reason:
            excluded[relative] = reason
            continue
        if not (root / relative).exists() and not (root / relative).is_symlink():
            continue  # A tracked deletion must not be resurrected from Git history.
        source = EXPORT_OVERRIDES.get(relative, relative)
        content, mode = read_public_source(root, source)
        files.append(
            {
                "path": relative,
                "source": source,
                "sha256": digest(content),
                "bytes": len(content),
                "mode": mode,
            }
        )
    return {"schema_version": 1, "files": files, "excluded": excluded}


def export(root: Path, manifest: dict[str, Any], output: Path) -> str:
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("unsupported source manifest")
    validate_destination(root, output)
    records = manifest["files"]
    if not records or len({record["path"] for record in records}) != len(records):
        raise ValueError("empty or duplicate source manifest")

    # Validate every file before writing any output; recheck hashes during copying too.
    def checked(record: dict[str, Any]) -> bytes:
        if omission(record["path"]) is not None:
            raise ValueError(f"private/unselected source member: {record['path']}")
        expected_source = EXPORT_OVERRIDES.get(record["path"], record["path"])
        if record["source"] != expected_source:
            raise ValueError("unapproved public-source substitution")
        content, mode = read_public_source(root, expected_source)
        if (digest(content), len(content), mode) != (
            record["sha256"],
            record["bytes"],
            record["mode"],
        ):
            raise ValueError(f"source changed after inventory: {record['path']}")
        return content

    for record in records:
        checked(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".source-stage-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for record in records:
            destination = staging / record["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(checked(record))
            destination.chmod(record["mode"])
        public = {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "purpose": "Private alpha candidate; not qualified or approved for publication",
            "provenance": (
                "Current working source, including uncommitted implementation; "
                "explicit hash-bound source-only notice derivatives; no Git history copied"
            ),
            "files": records,
            "source_tree_sha256": digest(encoded(records)),
        }
        (staging / "SOURCE_SNAPSHOT.json").write_bytes(encoded(public))
        staging.rename(output)
    return str(public["source_tree_sha256"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--inventory", type=Path, help="Write a private explicit file/hash selection"
    )
    actions.add_argument("--manifest", type=Path, help="Export exactly this reviewed inventory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.inventory:
        validate_destination(ROOT, args.inventory)
        report = inventory(ROOT, source_paths(ROOT))
        report["created_at"] = datetime.now(UTC).isoformat()
        report["source_head"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.inventory, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded(report))
        print(
            f"Private inventory: {len(report['files'])} files; {len(report['excluded'])} exclusions"
        )
        return
    if args.output is None:
        parser.error("--manifest requires --output")
    report = json.loads(args.manifest.read_bytes())
    checksum = export(ROOT, report, args.output)
    print(f"History-free private candidate staged; source tree SHA-256: {checksum}")
    print(
        "No Git repository, commit, tag, upload or publication was created. Audit and qualify next."
    )


if __name__ == "__main__":
    main()
