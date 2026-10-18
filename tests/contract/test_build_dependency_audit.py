"""PEP 517 build dependencies cannot fall outside the locked vulnerability audit."""

import ast
import gzip
import hashlib
import json
import runpy
import shlex
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

validate = runpy.run_path("scripts/scan-source.py")["validate_build_requirements"]
scan_complete = runpy.run_path("scripts/scan-source.py")["secret_scan_complete"]
history_options = runpy.run_path("scripts/scan-source.py")["GITLEAKS_HISTORY_LOG_OPTIONS"]


@pytest.mark.parametrize(
    ("log", "commits", "expected"),
    [
        ("INF 8 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found", 8, True),
        ("INF 0 commits scanned.\nINF scanned ~0 bytes\nINF no leaks found", 8, False),
        ("INF 7 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found", 8, False),
        ("ERR [git] fatal: ownership\nINF scanned ~500 bytes\nINF no leaks found", 8, False),
        (
            "INF 8 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found\nERR failed",
            8,
            False,
        ),
        ("INF scanned ~500 bytes\nINF no leaks found", 8, False),
        ("INF scanned ~500 bytes\nINF no leaks found", None, True),
        ("WRN skipped file\nINF scanned ~500 bytes\nINF no leaks found", None, False),
        ("INF scanned ~0 bytes\nINF no leaks found", None, False),
        ("INF 0 commits scanned.\nINF scanned ~500 bytes\nINF no leaks found", 0, False),
    ],
)
def test_secret_scanner_requires_complete_error_free_coverage(
    log: str, commits: int | None, expected: bool
) -> None:
    assert scan_complete(log, commits) is expected


def test_workspace_build_pins_are_included_in_audited_dev_lock() -> None:
    assert validate(Path.cwd()) == ["setuptools==83.0.0", "wheel==0.46.2"]


def test_secret_history_includes_both_ancestries_and_merge_resolution(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(tmp_path),
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

    def commit_file(name: str) -> str:
        (tmp_path / f"{name}.txt").write_text(f"{name}_evidence\n")
        git("add", ".")
        git("commit", "-m", name)
        return git("rev-parse", "HEAD")

    git("init", "--initial-branch=main")
    commits = {commit_file("base")}
    git("switch", "-c", "contribution")
    commits.add(commit_file("side_branch"))
    git("switch", "main")
    commits.add(commit_file("first_parent"))
    git("merge", "--no-ff", "--no-commit", "contribution")
    commits.add(commit_file("merge_resolution"))
    options = shlex.split(history_options)
    assert "--all" in options and "--full-history" in options
    assert "--first-parent" not in options and "--no-merges" not in options
    assert "--diff-merges=first-parent" in options
    patch = git("log", "-p", "-U0", *options)
    assert {line.split()[1] for line in patch.splitlines() if line.startswith("commit ")} == commits
    for name in ("base", "side_branch", "first_parent", "merge_resolution"):
        assert f"+{name}_evidence" in patch
    assert "+merge_resolution_evidence" not in git("log", "-p", "-U0", "--all")


def test_both_secret_scan_calls_require_coverage_and_history_is_narrowly_trusted() -> None:
    source = Path("scripts/scan-source.py").read_text()
    tree = ast.parse(source)
    calls = {
        node.args[0].value: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "scan"
        and isinstance(node.args[0], ast.Constant)
    }
    for name in ["gitleaks-source.json", "gitleaks-history.json"]:
        assert any(
            k.arg == "secret" and ast.unparse(k.value) == "True" for k in calls[name].keywords
        )
    assert any(k.arg == "commits" for k in calls["gitleaks-history.json"].keywords)
    assert "GITLEAKS_HISTORY_LOG_OPTIONS" in ast.unparse(calls["gitleaks-history.json"])
    assert '"GIT_CONFIG_VALUE_0=/repo"' in source
    assert "safe.directory=*" not in source and '"--global"' not in source


@pytest.mark.parametrize(
    "requirement", ["setuptools==75.8.0", "setuptools>=83", "setuptools==83.*", "wheel==0.45.1"]
)
def test_unlocked_missing_or_changed_build_pin_fails(tmp_path: Path, requirement: str) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["setuptools==83.0.0"]\n'
        '[tool.uv.workspace]\nmembers = ["backend"]\n'
    )
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/pyproject.toml").write_text(
        f'[build-system]\nrequires = ["{requirement}"]\n'
    )
    with pytest.raises(ValueError, match="exact audited dev pin"):
        validate(tmp_path)


@pytest.mark.parametrize("script", ["scripts/scan-source.py", "scripts/scan-images.py"])
def test_scanners_use_bind_mount_owner_without_restoring_capabilities(script: str) -> None:
    tree = ast.parse(Path(script).read_text())
    command = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.List)
        and any(
            isinstance(target, ast.Name) and target.id in {"docker", "scanner"}
            for target in node.targets
        )
    )
    assert isinstance(command, ast.List)
    values = [
        item.value if isinstance(item, ast.Constant) else ast.unparse(item) for item in command.elts
    ]
    assert values[values.index("--user") + 1] == "f'{os.getuid()}:{os.getgid()}'"
    assert values[values.index("--cap-drop") + 1] == "ALL"
    assert values[values.index("--security-opt") + 1] == "no-new-privileges"
    assert "--privileged" not in values and "--cap-add" not in values


def test_every_preserved_build_finding_has_current_hash_bound_assessment() -> None:
    root = Path("security/build-tool-findings/2026-09-05")
    manifest = json.loads((root / "manifest.json").read_bytes())
    raw = {}
    for item in manifest["files"]:
        compressed = (root / item["path"]).read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == item["compressed_sha256"]
        value = gzip.decompress(compressed)
        assert hashlib.sha256(value).hexdigest() == item["uncompressed_sha256"]
        if item["path"].endswith(".json.gz"):
            raw[item["path"]] = json.loads(value)
    findings = [
        finding
        for dependency in raw["old-build-audit.json.gz"]["dependencies"]
        for finding in dependency["vulns"]
    ]
    records = json.loads((root / "assessments.json").read_bytes())["records"]
    assert len(findings) == 5 and len(records) == 8
    assert {r["raw_record_index"] for r in records if r["scanner"] == "pip-audit"} == set(range(5))
    required = {
        "scanner_version",
        "scan_date",
        "artifact",
        "image",
        "package",
        "installed_version",
        "advisory",
        "severity",
        "shipped_runtime",
        "scope",
        "reachability",
        "exposure",
        "fixed_versions_available",
        "fixed_version",
        "decision",
        "resolution",
        "evidence",
        "rationale",
        "review_owner",
        "reviewed_on",
        "expires_on",
    }
    for record in records:
        assert required <= record.keys()
        assert record["scope"] == "build" and record["shipped_runtime"] is False
        assert record["decision"] == "mitigate" and record["fixed_versions_available"]
        assert record["review_owner"] and record["evidence"]
        assert (
            date.fromisoformat(record["scan_date"])
            <= date.fromisoformat(record["reviewed_on"])
            <= datetime.now(UTC).date()
        )
        assert date.fromisoformat(record["expires_on"]) >= datetime.now(UTC).date()
        finding = (
            findings[record["raw_record_index"]]
            if record["scanner"] == "pip-audit"
            else raw[record["raw_file"]]
        )
        digest = hashlib.sha256(
            json.dumps(finding, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert digest == record["finding_sha256"]
    patched = raw["patched-python-audit.json.gz"]["dependencies"]
    for name, version in [("setuptools", "83.0.0"), ("wheel", "0.46.2")]:
        package = next(p for p in patched if p["name"] == name)
        assert package["version"] == version and package["vulns"] == []
