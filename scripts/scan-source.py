"""Retain dependency, secret and source-SBOM evidence without modifying dependencies."""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import packaging
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

TRIVY = (
    "aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
)
GITLEAKS = (
    "ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:"
    "c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)
# Include merge-resolution patches without restricting traversal to the first parent.
GITLEAKS_HISTORY_LOG_OPTIONS = "--all --full-history --diff-merges=first-parent"
UV_VERSION = "0.8.15"
PNPM_VERSION = "10.17.1"
PIP_AUDIT_VERSION = "2.10.0"
COMPONENT_TYPES = {
    "application",
    "framework",
    "library",
    "container",
    "platform",
    "operating-system",
    "device",
    "device-driver",
    "firmware",
    "file",
    "machine-learning-model",
    "data",
    "cryptographic-asset",
}


def capture_source(snapshot: Path, selected: list[bytes]) -> None:
    """Every Git-selected input must be a regular file with unlinked parents."""
    paths = [Path(os.fsdecode(name)) for name in sorted(set(selected)) if name]
    if not paths:
        raise ValueError("empty Git source selection")
    for path in paths:
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise ValueError("source snapshot path escapes the checkout")
        try:
            for parent in path.parents:
                if not stat.S_ISDIR(parent.lstat().st_mode):
                    raise ValueError("selected source has a linked or non-directory parent")
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("selected source is linked or nonregular")
        except OSError:
            raise ValueError("selected source or parent is missing or unreadable") from None
    for path in paths:
        destination = snapshot / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination, follow_symlinks=False)


def snapshot_members(root: Path) -> dict[str, dict[str, str | int]]:
    """Bind every saved file/directory and mode; never follow source symlinks."""
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("unsupported source snapshot root")
    members: dict[str, dict[str, str | int]] = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        record: dict[str, str | int] = {"mode": stat.S_IMODE(info.st_mode)}
        if stat.S_ISDIR(info.st_mode):
            record["kind"] = "directory"
        elif stat.S_ISREG(info.st_mode):
            record.update(kind="file", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            raise ValueError("unsupported source snapshot member")
        members[str(path.relative_to(root))] = record
    return members


def report_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate report key")
            result[key] = value
        return result

    def number(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite report number")
        return parsed

    result = json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=number)
    if not isinstance(result, dict) or "error" in result or "errors" in result:
        raise ValueError("invalid audit report")
    return result


def marker_context() -> dict[str, Any]:
    """Allowlisted interpreter metadata, never process environment variables.

    A replay verifier must match this trusted interpreter/packaging environment;
    these values are not a caller-controlled override or cross-platform coverage.
    """
    return {
        "schema_version": 1,
        "packaging_version": packaging.__version__,
        "implementation": sys.implementation.name,
        "python_version": platform.python_version(),
        "interpreter_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "environment": default_environment(),
    }


def python_requirements(
    path: Path, marker_environment: dict[str, str] | None = None
) -> set[tuple[str, str]]:
    """Parse uv's hash-locked export with current or explicitly captured markers.

    The caller verifies captured marker provenance before supplying an environment.
    Require every packaging marker key so omitted values cannot fall back to host state.
    """
    if marker_environment is not None and (
        set(marker_environment) != set(default_environment())
        or not all(isinstance(value, str) for value in marker_environment.values())
    ):
        raise ValueError("incomplete captured marker environment")
    expected: set[tuple[str, str]] = set()
    for line in path.read_text().replace("\\\n", "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        requirement_text, *hashes = re.split(r"\s+--hash=", line)
        if not hashes or any(not re.fullmatch(r"sha256:[0-9a-f]{64}\s*", h) for h in hashes):
            raise ValueError("unhashed or malformed exported requirement")
        requirement = Requirement(requirement_text)
        pins = list(requirement.specifier)
        if requirement.url or len(pins) != 1 or pins[0].operator != "==" or "*" in pins[0].version:
            raise ValueError("exported requirement is not an exact registry pin")
        if requirement.marker is None or requirement.marker.evaluate(
            environment=marker_environment
        ):
            expected.add((canonicalize_name(requirement.name), pins[0].version))
    if not expected:
        raise ValueError("empty exported dependency set")
    return expected


def dependency_audit_status(
    raw: bytes, tool: str, exit_code: int, expected_python: set[tuple[str, str]]
) -> str:
    """Classify coverage, not approval; a complete findings report still blocks."""
    try:
        data = report_json(raw)
        if tool == "pip-audit":
            dependencies = data["dependencies"]
            if not isinstance(dependencies, list) or not dependencies or data.get("fixes") != []:
                return "error"
            actual = set()
            findings = 0
            for dependency in dependencies:
                name, version, vulns = (dependency[k] for k in ("name", "version", "vulns"))
                if (
                    not isinstance(name, str)
                    or not name.strip()
                    or not isinstance(version, str)
                    or not version.strip()
                    or not isinstance(vulns, list)
                    or "skip_reason" in dependency
                ):
                    return "error"
                identity = (canonicalize_name(name), version)
                if identity in actual:
                    return "error"
                actual.add(identity)
                for vuln in vulns:
                    if (
                        not isinstance(vuln, dict)
                        or not isinstance(vuln.get("id"), str)
                        or not vuln["id"].strip()
                    ):
                        return "error"
                    findings += 1
            if actual != expected_python:
                return "error"
        elif tool == "pnpm":
            metadata, advisories = data["metadata"], data["advisories"]
            if (
                not isinstance(advisories, dict)
                or data.get("muted") != []
                or not isinstance(data.get("actions"), list)
            ):
                return "error"
            counts = metadata["vulnerabilities"]
            levels = {"info", "low", "moderate", "high", "critical"}
            if (
                not isinstance(counts, dict)
                or set(counts) != levels
                or any(type(v) is not int or v < 0 for v in counts.values())
            ):
                return "error"
            totals = [
                metadata[k]
                for k in (
                    "dependencies",
                    "devDependencies",
                    "optionalDependencies",
                    "totalDependencies",
                )
            ]
            if (
                any(type(v) is not int or v < 0 for v in totals)
                or totals[-1] <= 0
                or sum(totals[:3]) != totals[-1]
            ):
                return "error"
            actual_counts = dict.fromkeys(levels, 0)
            for key, advisory in advisories.items():
                if (
                    type(advisory["id"]) is not int
                    or advisory["id"] <= 0
                    or str(advisory["id"]) != key
                    or not isinstance(advisory.get("module_name"), str)
                    or not advisory["module_name"].strip()
                    or advisory.get("severity") not in levels
                    or not isinstance(advisory.get("findings"), list)
                    or not advisory["findings"]
                ):
                    return "error"
                for finding in advisory["findings"]:
                    if (
                        not isinstance(finding.get("version"), str)
                        or not finding["version"].strip()
                        or not isinstance(finding.get("paths"), list)
                        or not finding["paths"]
                        or not all(isinstance(p, str) and p.strip() for p in finding["paths"])
                    ):
                        return "error"
                actual_counts[advisory["severity"]] += 1
            if counts != actual_counts:
                return "error"
            findings = len(advisories)
        else:
            return "error"
        if exit_code != (1 if findings else 0):
            return "error"
        return "findings" if findings else "clean"
    except (ValueError, TypeError, KeyError, AttributeError):
        return "error"


def sbom_complete(raw: bytes, tool: str, expected_python: set[tuple[str, str]]) -> bool:
    """Validate pinned CycloneDX shapes, including exact Python package coverage."""
    try:
        data = report_json(raw)
        components, metadata = data["components"], data["metadata"]
        if (
            data.get("bomFormat") != "CycloneDX"
            or data.get("specVersion") != ("1.4" if tool == "pip-audit" else "1.7")
            or type(data.get("version")) is not int
            or data["version"] < 1
            or not isinstance(components, list)
            or not components
            or not isinstance(metadata, dict)
            or not isinstance(metadata.get("timestamp"), str)
            or datetime.fromisoformat(metadata["timestamp"].replace("Z", "+00:00")).tzinfo is None
        ):
            return False
        identities = set()
        refs = set()
        for component in components:
            name, kind = component["name"], component["type"]
            version, ref = component.get("version"), component["bom-ref"]
            if (
                not isinstance(name, str)
                or not name.strip()
                or not isinstance(kind, str)
                or kind not in COMPONENT_TYPES
                or (
                    "version" in component and (not isinstance(version, str) or not version.strip())
                )
                or (kind == "library" and version is None)
                or not isinstance(ref, str)
                or not ref.strip()
                or ref in refs
            ):
                return False
            refs.add(ref)
            if tool == "pip-audit":
                identity = (canonicalize_name(name), version)
                if kind != "library" or identity in identities:
                    return False
                identities.add(identity)
        vulnerabilities = data.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list) or any(
            not isinstance(v, dict) or not isinstance(v.get("id"), str) or not v["id"].strip()
            for v in vulnerabilities
        ):
            return False
        if tool == "pip-audit":
            # pip-audit 2.10.0 omits tool metadata; separately retained --version binds it.
            return identities == expected_python
        if tool != "trivy":
            return False
        scanner = metadata["tools"]["components"]
        root = metadata["component"]
        lockfiles = {c["name"] for c in components if c["type"] == "application"}
        return (
            isinstance(scanner, list)
            and len(scanner) == 1
            and scanner[0].get("type") == "application"
            and scanner[0].get("name") == "trivy"
            and scanner[0].get("version") == "0.74.0"
            and root.get("type") == "application"
            and root.get("name") == "/reports/source"
            and {"uv.lock", "pnpm-lock.yaml"} <= lockfiles
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def validate_build_requirements(root: Path) -> list[str]:
    """Every isolated build pin must also enter the hash-locked dependency audit."""
    project = tomllib.loads((root / "pyproject.toml").read_text())
    audited = {str(Requirement(item)) for item in project["dependency-groups"]["dev"]}
    paths = [root / "pyproject.toml"]
    for member in project["tool"]["uv"]["workspace"]["members"]:
        paths.extend(path / "pyproject.toml" for path in root.glob(member))
    requirements = set()
    for path in paths:
        data = tomllib.loads(path.read_text())
        for value in data.get("build-system", {}).get("requires", []):
            requirement = Requirement(value)
            pins = list(requirement.specifier)
            if (
                requirement.url
                or requirement.marker
                or requirement.extras
                or len(pins) != 1
                or pins[0].operator != "=="
                or "*" in pins[0].version
                or str(requirement) not in audited
            ):
                raise ValueError(f"Build requirement is not an exact audited dev pin: {value}")
            requirements.add(str(requirement))
    if not requirements:
        raise ValueError("No workspace build requirements found")
    return sorted(requirements)


def secret_scan_complete(log: str, expected_commits: int | None = None) -> bool:
    """Pinned Gitleaks may exit zero after Git errors; require coverage evidence."""
    plain = re.sub(r"\x1b\[[0-9;]*m", "", log)
    if re.search(r"\b(?:ERR|FTL|WRN)\b", plain) or "no leaks found" not in plain:
        return False
    size = re.findall(r"scanned ~([0-9]+) bytes", plain)
    if len(size) != 1 or int(size[0]) <= 0:
        return False
    if expected_commits is not None:
        counts = re.findall(r"\b([0-9]+) commits? scanned\.", plain)
        return expected_commits > 0 and counts == [str(expected_commits)]
    return True


def clean_secret_report(raw: bytes | None) -> bool:
    """The pinned scanner's successful clean report must be an empty JSON array."""
    if raw is None:
        return False
    try:
        value = json.loads(raw)
        return isinstance(value, list) and not value
    except (ValueError, UnicodeError, RecursionError):
        return False


def retained_bytes(path: Path) -> bytes | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            return None
        return path.read_bytes()
    except OSError:
        return None


def main() -> None:
    started_at = datetime.now(UTC).isoformat()
    markers = marker_context()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".opencommerce/source-scans"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("use a new empty output directory; old scans are evidence")
    snapshot = output / "source"
    if snapshot.exists():
        raise ValueError("use a new output directory; old source snapshots are evidence")
    snapshot.mkdir()
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    ).split(b"\0")
    try:
        capture_source(snapshot, paths)
        members = snapshot_members(snapshot)
        selected = {str(Path(os.fsdecode(name))) for name in paths if name}
        if {name for name, item in members.items() if item["kind"] == "file"} != selected:
            raise ValueError("captured source membership does not match Git selection")
    except (OSError, ValueError):
        (output / "inventory.json").write_text(
            json.dumps(
                {
                    "complete": False,
                    "passed": False,
                    "capture_error": "Git-selected source capture failed",
                    "snapshot": {"stable": False},
                    "started_at": started_at,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "marker_context": markers,
                }
            )
            + "\n"
        )
        raise
    source_files = {
        name: item["sha256"] for name, item in members.items() if item["kind"] == "file"
    }
    (output / "source-files.json").write_text(
        json.dumps(source_files, sort_keys=True, indent=2) + "\n"
    )
    manifest = output / "source-snapshot.json"
    manifest.write_text(json.dumps(members, sort_keys=True, indent=2) + "\n")
    results: list[dict[str, Any]] = []
    versions: dict[str, Any] = {}
    inventory: dict[str, Any] = {
        "complete": False,
        "passed": False,
        "started_at": started_at,
        "completed_at": None,
        "marker_context": markers,
        "reports": results,
        "tools": {
            "uv": UV_VERSION,
            "pip-audit": PIP_AUDIT_VERSION,
            "pnpm": PNPM_VERSION,
            "trivy": TRIVY,
            "gitleaks": GITLEAKS,
        },
        "tool_version_evidence": versions,
        "snapshot": {
            "manifest": manifest.name,
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "source_files_sha256": hashlib.sha256(
                (output / "source-files.json").read_bytes()
            ).hexdigest(),
            "stable": False,
        },
        "scope": (
            "Dependency export/audits from the saved source snapshot; nonignored source "
            "and full available Git history. Coverage is not qualification."
        ),
    }

    def persist() -> None:
        (output / "inventory.json").write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        )

    def verify_snapshot() -> None:
        try:
            stable = snapshot_members(snapshot) == members
            stable = (
                stable
                and hashlib.sha256(manifest.read_bytes()).hexdigest()
                == inventory["snapshot"]["sha256"]
            )
            stable = (
                stable
                and hashlib.sha256((output / "source-files.json").read_bytes()).hexdigest()
                == inventory["snapshot"]["source_files_sha256"]
            )
            if "requirements_sha256" in inventory:
                stable = (
                    stable
                    and hashlib.sha256(
                        (output / "python-requirements.txt").read_bytes()
                    ).hexdigest()
                    == inventory["requirements_sha256"]
                )
        except (OSError, ValueError):
            stable = False
        inventory["snapshot"]["stable"] = stable
        if not stable:
            inventory.update(complete=False, passed=False)
            persist()
            raise ValueError("source snapshot membership, bytes or modes changed")

    persist()
    verify_snapshot()
    inventory["audited_build_requirements"] = validate_build_requirements(snapshot)
    verify_snapshot()
    history = output / "history.git"
    subprocess.run(
        ["git", "clone", "--mirror", "--no-local", str(Path.cwd()), str(history)],
        check=True,
    )
    expected_commits = int(
        subprocess.check_output(["git", "-C", str(history), "rev-list", "--count", "--all"])
    )
    inventory["expected_history_commits"] = expected_commits
    expected_python: set[tuple[str, str]] = set()

    def version(name: str, command: list[str], prefix: str) -> None:
        verify_snapshot()
        completed = subprocess.run(command, cwd=snapshot, capture_output=True, check=False)
        for suffix, raw in (("stdout", completed.stdout), ("stderr", completed.stderr)):
            (output / f"{name}-version.{suffix}").write_bytes(raw)
        valid = completed.returncode == 0 and (
            completed.stdout == (prefix + "\n").encode()
            if name == "gitleaks"
            else bool(
                re.match(
                    re.escape(prefix) + r"(?:\s|$)",
                    completed.stdout.decode("utf-8", errors="replace"),
                )
            )
        )
        versions[name] = {
            "exit_code": completed.returncode,
            "verified": valid,
            "stdout": f"{name}-version.stdout",
            "stderr": f"{name}-version.stderr",
            "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        }
        verify_snapshot()
        persist()
        if not valid:
            raise ValueError("scanner version evidence does not match pin")

    def scan(
        name: str,
        command: list[str],
        *,
        capture: bool = False,
        secret: bool = False,
        commits: int | None = None,
        dependency: str | None = None,
        sbom: bool = False,
    ) -> None:
        verify_snapshot()
        report = output / name
        coverage_verified = True
        status = "clean"
        if secret:
            completed = subprocess.run(
                command, cwd=snapshot, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
            )
            log = output / f"{name}.log"
            log.write_bytes(completed.stdout)
            decoded = completed.stdout.decode("utf-8", errors="replace")
            print(decoded, flush=True)
            coverage_verified = secret_scan_complete(decoded, commits)
        elif capture:
            with report.open("wb") as stream:
                completed = subprocess.run(command, cwd=snapshot, stdout=stream, check=False)
        else:
            completed = subprocess.run(command, cwd=snapshot, check=False)
        report_raw = retained_bytes(report)
        if dependency:
            status = (
                dependency_audit_status(
                    report_raw, dependency, completed.returncode, expected_python
                )
                if report_raw is not None
                else "error"
            )
            coverage_verified = status != "error"
        elif sbom:
            try:
                if report_raw is None:
                    raise ValueError("missing report")
                raw = report_raw
                data = report_json(raw)
                coverage_verified = sbom_complete(
                    raw, "pip-audit" if name == "python.cdx.json" else "trivy", expected_python
                )
                if name == "python.cdx.json":
                    audit_data = report_json((output / "python-audit.json").read_bytes())
                    findings = {v["id"] for d in audit_data["dependencies"] for v in d["vulns"]}
                    coverage_verified = (
                        coverage_verified
                        and results[0]["coverage_verified"]
                        and {v["id"] for v in data.get("vulnerabilities", [])} == findings
                        and completed.returncode == (1 if findings else 0)
                    )
                else:
                    coverage_verified = coverage_verified and completed.returncode == 0
            except (OSError, ValueError, TypeError, KeyError):
                coverage_verified = False
            status = "findings" if coverage_verified and completed.returncode == 1 else "clean"
        else:
            coverage_verified = coverage_verified and completed.returncode == 0
            if secret:
                coverage_verified = coverage_verified and clean_secret_report(report_raw)
        if not coverage_verified:
            status = "error"
        results.append(
            {
                "report": name,
                "exit_code": completed.returncode,
                "coverage_verified": coverage_verified,
                "status": status,
                "sha256": hashlib.sha256(report_raw).hexdigest()
                if report_raw is not None
                else "missing",
            }
        )
        if secret:
            results[-1].update(
                log=f"{name}.log", log_sha256=hashlib.sha256(completed.stdout).hexdigest()
            )
        verify_snapshot()
        persist()
        print(f"{name}: exit {completed.returncode}", flush=True)
        if not coverage_verified:
            print(f"{name}: coverage failed; retained scanner log is not a pass", flush=True)

    uv = os.environ.get("UV") or shutil.which("uv") or ".tools/uv/bin/uv"
    if "/" in uv:
        uv = str(Path(uv).resolve())
    version("uv", [uv, "--version"], f"uv {UV_VERSION}")
    requirements = output / "python-requirements.txt"
    verify_snapshot()
    subprocess.run(
        [
            uv,
            "export",
            "--frozen",
            "--all-packages",
            "--all-extras",
            "--group",
            "dev",
            "--no-emit-workspace",
            "--no-header",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
        check=True,
        cwd=snapshot,
        stdout=subprocess.DEVNULL,
    )
    verify_snapshot()
    inventory["requirements_sha256"] = hashlib.sha256(requirements.read_bytes()).hexdigest()
    expected_python = python_requirements(requirements, markers["environment"])
    for value in inventory["audited_build_requirements"]:
        requirement = Requirement(value)
        pin = next(iter(requirement.specifier))
        if (canonicalize_name(requirement.name), pin.version) not in expected_python:
            persist()
            raise ValueError("export omitted an audited build requirement")
    audit_tool = [
        uv,
        "tool",
        "run",
        "--python",
        sys.executable,
        "--from",
        "pip-audit==2.10.0",
        "pip-audit",
    ]
    version("pip-audit", [*audit_tool, "--version"], f"pip-audit {PIP_AUDIT_VERSION}")
    audit = [
        *audit_tool,
        "--requirement",
        str(requirements),
        "--disable-pip",
        "--require-hashes",
        "--strict",
        "--progress-spinner",
        "off",
    ]
    scan(
        "python-audit.json",
        [*audit, "--format", "json", "--output", str(output / "python-audit.json")],
        dependency="pip-audit",
    )
    scan(
        "python.cdx.json",
        [*audit, "--format", "cyclonedx-json", "--output", str(output / "python.cdx.json")],
        sbom=True,
    )
    pnpm = shlex.split(os.environ.get("PNPM", "env CI=true npm exec --yes pnpm@10.17.1 --"))
    if pnpm and "/" in pnpm[0]:
        pnpm[0] = str(Path(pnpm[0]).resolve())
    version("pnpm", [*pnpm, "--version"], PNPM_VERSION)
    scan("node-audit.json", [*pnpm, "audit", "--json"], capture=True, dependency="pnpm")
    docker = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{output}:/reports",
        "-v",
        f"{snapshot}:/reports/source:ro",
    ]
    version("trivy", [*docker, TRIVY, "--version"], "Version: 0.74.0")
    version("gitleaks", [*docker, GITLEAKS, "version"], "v8.30.1")
    leak_options = [
        "--config",
        "/reports/source/.gitleaks.toml",
        "--no-banner",
        "--redact=100",
        "--report-format",
        "json",
        "--report-path",
    ]
    scan(
        "gitleaks-source.json",
        [
            *docker,
            GITLEAKS,
            *leak_options,
            "/reports/gitleaks-source.json",
            "dir",
            "/reports/source",
        ],
        secret=True,
    )
    scan(
        "gitleaks-history.json",
        [
            *docker,
            "-e",
            "GIT_CONFIG_COUNT=1",
            "-e",
            "GIT_CONFIG_KEY_0=safe.directory",
            "-e",
            "GIT_CONFIG_VALUE_0=/repo",
            "-v",
            f"{history}:/repo:ro",
            GITLEAKS,
            *leak_options,
            "/reports/gitleaks-history.json",
            "git",
            "/repo",
            f"--log-opts={GITLEAKS_HISTORY_LOG_OPTIONS}",
        ],
        secret=True,
        commits=expected_commits,
    )
    scan(
        "source.cdx.json",
        [
            *docker,
            TRIVY,
            "fs",
            "--include-dev-deps",
            "--cache-dir",
            "/reports/cache",
            "--format",
            "cyclonedx",
            "--output",
            "/reports/source.cdx.json",
            "/reports/source",
        ],
        sbom=True,
    )
    verify_snapshot()
    bindings = [(item["report"], item["sha256"]) for item in results]
    bindings.extend((item["log"], item["log_sha256"]) for item in results if "log" in item)
    bindings.extend(
        (item[suffix], item[f"{suffix}_sha256"])
        for item in versions.values()
        for suffix in ("stdout", "stderr")
    )
    bindings_verified = True
    for name, expected_hash in bindings:
        retained = retained_bytes(output / name)
        if retained is None or hashlib.sha256(retained).hexdigest() != expected_hash:
            bindings_verified = False
    inventory["report_bindings_verified"] = bindings_verified
    complete = (
        bindings_verified
        and len(results) == 6
        and all(item["coverage_verified"] and item["sha256"] != "missing" for item in results)
    )
    passed = all(
        item["exit_code"] == 0 and item["sha256"] != "missing" and item["coverage_verified"]
        for item in results
    )
    inventory.update(
        complete=complete, passed=complete and passed, completed_at=datetime.now(UTC).isoformat()
    )
    persist()
    if not inventory["passed"]:
        raise SystemExit("source security checks failed; retained reports show errors or findings")


if __name__ == "__main__":
    main()
