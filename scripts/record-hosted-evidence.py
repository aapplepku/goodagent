"""Record provenance and byte hashes without inventing a passing workflow result."""

import hashlib
import json
import os
import platform
import stat
import subprocess
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path

WORKFLOWS = {
    ".github/workflows/qualification.yml",
    ".github/workflows/collect-release-evidence.yml",
}
STAGES = {
    "dependencies",
    "before",
    "source",
    "build",
    "images",
    "image_privacy",
    "finalize",
    "after",
}
BROWSER_EVIDENCE = (Path("apps/web/test-results"), Path("apps/shopper/test-results"))


@contextmanager
def evidence_directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """Pin every ancestor without following links, including during replacement races."""
    if ".." in path.parts:
        raise ValueError("unsupported evidence directory")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        descriptor = os.open(path.anchor or ".", flags)
        stack.callback(os.close, descriptor)
        ancestors: list[tuple[int, str, os.stat_result]] = []
        for part in path.parts[1:] if path.is_absolute() else path.parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=descriptor)
            stack.callback(os.close, child)
            ancestors.append((descriptor, part, os.fstat(child)))
            descriptor = child
        yield descriptor
        for parent, name, before in ancestors:
            after = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (before.st_dev, before.st_ino, before.st_mode) != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
            ):
                raise ValueError("evidence directory changed while recording")


def browser_evidence_files(root: Path, *, optional: bool = True) -> list[Path]:
    """Missing test output is allowed after early failure; unsafe output is never ignored."""
    with ExitStack() as stack:
        try:
            descriptor = stack.enter_context(evidence_directory(root))
        except FileNotFoundError:
            if optional:
                return []
            raise
        files = []
        for name in sorted(os.listdir(descriptor)):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            path = root / name
            if stat.S_ISDIR(info.st_mode):
                files.extend(browser_evidence_files(path, optional=False))
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                files.append(path)
            else:
                raise ValueError("unsupported browser evidence member")
        return files


def file_record(path: Path) -> dict[str, str | int]:
    def identity(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    with evidence_directory(path.parent) as parent:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError("unsupported evidence file")
            checksum = hashlib.file_digest(handle, "sha256").hexdigest()
            if identity(before) != identity(os.fstat(handle.fileno())) or identity(
                before
            ) != identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)):
                raise ValueError("evidence file changed while recording")
    return {"path": str(path), "sha256": checksum, "bytes": before.st_size}


def workflow_context() -> tuple[str, dict[str, str]]:
    workflow = os.environ.get("EVIDENCE_WORKFLOW_PATH", ".github/workflows/qualification.yml")
    if workflow not in WORKFLOWS:
        raise ValueError("unsupported evidence workflow")
    stages = json.loads(os.environ.get("EVIDENCE_STAGE_OUTCOMES", "{}"))
    if not isinstance(stages, dict) or any(
        key not in STAGES
        or not isinstance(value, str)
        or value not in {"success", "failure", "cancelled", "skipped", ""}
        for key, value in stages.items()
    ):
        raise ValueError("unsupported stage outcome")
    if workflow.endswith("collect-release-evidence.yml") and set(stages) != STAGES:
        raise ValueError("missing collection stage outcomes")
    return workflow, stages


def version(*command: str) -> str:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {type(error).__name__}"
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def main() -> None:
    workflow, stages = workflow_context()
    output = Path(".opencommerce/ci-evidence/provenance.json")
    with evidence_directory(output.parent, create=True):
        pass
    paths = sorted(
        {
            path
            for pattern in (
                ".opencommerce/ci-evidence/*",
                ".opencommerce/*-proof.json",
                ".opencommerce/source-scans/*.json",
                ".opencommerce/source-scans/*.txt",
                ".opencommerce/source-scans/*.log",
                ".opencommerce/source-scans/*-version.stdout",
                ".opencommerce/source-scans/*-version.stderr",
                ".opencommerce/security-scans/final/*.json",
                ".opencommerce/controller-*.json.gz",
                ".opencommerce/controller-*.partial.jsonl",
                ".opencommerce/controller-assembly.json",
                ".opencommerce/controller-smoke.json",
                "security/*assessments.json",
                "security/reviewed-image-findings.json",
            )
            for path in Path(".").glob(pattern)
            if path != output
        }
        | {path for root in BROWSER_EVIDENCE for path in browser_evidence_files(root)}
    )
    actual_commit = version("git", "rev-parse", "HEAD")
    expected_commit = os.environ.get("EVIDENCE_COMMIT", "")
    evidence = {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "workflow_url": os.environ.get("EVIDENCE_RUN_URL"),
        "run_attempt": os.environ.get("EVIDENCE_RUN_ATTEMPT"),
        "commit_sha": actual_commit,
        "expected_commit_sha": expected_commit,
        "commit_matches": actual_commit == expected_commit,
        "workflow_result": "retrieve final conclusion from GitHub; this is not a pass attestation",
        "environment": {
            "runner_os": os.environ.get("EVIDENCE_RUNNER_OS"),
            "runner_arch": os.environ.get("EVIDENCE_RUNNER_ARCH"),
            "kernel": platform.release(),
            "python": version(".venv/bin/python", "--version"),
            "node": version("node", "--version"),
            "npm": version("npm", "--version"),
            "pnpm": version("npm", "exec", "--offline", "--yes", "pnpm@10.17.1", "--", "--version"),
            "uv": version("uv", "--version"),
            "docker": version("docker", "--version"),
            "compose": version("docker", "compose", "version"),
        },
        "files": [file_record(path) for path in paths],
        "commands_source": f"{workflow} at commit_sha",
        "stage_outcomes": stages,
        "retention": "Download all raw artifacts before the hosted 30-day retention expires.",
    }
    with evidence_directory(output.parent) as parent:
        descriptor = os.open(
            output.name,
            os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "w") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("unsupported provenance output")
            handle.truncate()
            handle.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    if not evidence["commit_matches"]:
        raise SystemExit(
            "checkout SHA differs from workflow SHA; evidence is not release-qualified"
        )


if __name__ == "__main__":
    main()
