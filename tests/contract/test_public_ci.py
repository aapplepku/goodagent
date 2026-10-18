"""The public first commit must pass the same DCO policy without a parent commit."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]


@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
@pytest.mark.parametrize("before", ["", "0" * 40, "a" * 40, "existing-root"])
@pytest.mark.parametrize("signed_followups", [0, 1, 2])
def test_public_root_commit_dco(
    tmp_path: Path, signed: bool, event: str, before: str, signed_followups: int
) -> None:
    history = tmp_path / "contribution-history"
    history.mkdir()

    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(history),
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

    git("init", "--initial-branch=main")
    message = "Public source snapshot" + (
        "\n\nSigned-off-by: Test Author <author@example.test>" if signed else ""
    )
    git("commit", "--allow-empty", "-m", message)
    root_sha = git("rev-parse", "HEAD")
    for _ in range(signed_followups):
        git("commit", "--allow-empty", "-s", "-m", "Signed later contribution")
    trusted = tmp_path / "trusted-policy/scripts"
    trusted.mkdir(parents=True)
    shutil.copyfile("scripts/check_dco.py", trusted / "check_dco.py")
    workflow = yaml.safe_load(Path("infra/github/public-ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    command = workflow["jobs"]["authorization"]["steps"][-1]["run"]
    environment = {
        **os.environ,
        "PR_BASE": "",
        "BEFORE_SHA": (
            (root_sha if signed_followups else "0" * 40) if before == "existing-root" else before
        ),
        "HEAD_SHA": git("rev-parse", "HEAD"),
        "EVENT_NAME": event,
        "CURRENT_REF": "main",
        "DEFAULT_BRANCH": "main",
    }

    def run_check(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-eu", "-c", command],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    if before == "existing-root" and signed_followups:
        initial = run_check(
            {**environment, "EVENT_NAME": "push", "HEAD_SHA": root_sha, "BEFORE_SHA": "0" * 40}
        )
        assert (initial.returncode == 0) is signed, initial.stdout + initial.stderr
    result = run_check(environment)
    assert (result.returncode == 0) is signed, result.stdout + result.stderr
