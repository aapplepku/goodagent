"""DCO validation uses real Git histories, not fabricated checker output."""

import runpy
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

check_range = runpy.run_path("scripts/check_dco.py")["check_range"]


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(path),
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


@pytest.fixture
def history(tmp_path: Path) -> tuple[Path, str]:
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "commit", "--allow-empty", "-m", "Private base predating DCO policy")
    return tmp_path, git(tmp_path, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "message",
    [
        "Unsigned contribution",
        "Change\n\nSigned-off-by: Someone Else <author@example.test>",
        "Change\n\nSigned-off-by: Test Author <wrong@example.test>",
        "Change\n\nSigned-off-by: Test Author <author@example.test>\n\nNot a trailer block.",
        "Change\n\nSigned-off-by: Test Author <broken>",
        "Change\n\nCo-authored-by: Second Author <second@example.test>\n"
        "Signed-off-by: Test Author <author@example.test>",
    ],
)
def test_unsigned_or_invalid_contribution_fails(history: tuple[Path, str], message: str) -> None:
    path, base = history
    git(path, "commit", "--allow-empty", "-m", message)
    assert len(check_range(path, base, git(path, "rev-parse", "HEAD"))) == 1


def test_every_commit_is_checked_and_valid_coauthor_passes(history: tuple[Path, str]) -> None:
    path, base = history
    git(path, "commit", "--allow-empty", "-m", "Unsigned earlier change")
    unsigned = git(path, "rev-parse", "HEAD")
    git(path, "commit", "--allow-empty", "-s", "-m", "Signed later change")
    git(
        path,
        "commit",
        "--allow-empty",
        "-s",
        "-m",
        "Shared change\n\nCo-authored-by: Second Author <second@example.test>\n"
        "Signed-off-by: Second Author <second@example.test>",
    )
    head = git(path, "rev-parse", "HEAD")
    assert check_range(path, unsigned, head) == []
    assert check_range(path, base, head) == [f"{unsigned}: missing author/coauthor DCO sign-off"]


def test_divider_cannot_hide_unsigned_coauthor(history: tuple[Path, str]) -> None:
    path, base = history
    git(
        path,
        "commit",
        "--allow-empty",
        "-m",
        "Change\n\nSigned-off-by: Test Author <author@example.test>\n\n"
        "---\n\nCo-authored-by: Second Author <second@example.test>",
    )
    head = git(path, "rev-parse", "HEAD")
    assert check_range(path, base, head) == [f"{head}: missing author/coauthor DCO sign-off"]


@pytest.mark.parametrize("coauthor", [False, True])
def test_markdown_divider_before_final_signoffs_is_valid(
    history: tuple[Path, str], coauthor: bool
) -> None:
    path, base = history
    message = "Change\n\n---\n\nImplementation notes."
    if coauthor:
        message += (
            "\n\nCo-authored-by: Second Author <second@example.test>\n"
            "Signed-off-by: Second Author <second@example.test>"
        )
    git(path, "commit", "--allow-empty", "-s", "-m", message)
    assert check_range(path, base, git(path, "rev-parse", "HEAD")) == []


@pytest.mark.parametrize("cleanup", ["verbatim", "whitespace"])
@pytest.mark.parametrize("signed_coauthor", [False, True])
def test_stored_scissors_delimiter_fails_closed(
    history: tuple[Path, str], cleanup: str, signed_coauthor: bool
) -> None:
    path, base = history
    message = (
        "Change\n\nSigned-off-by: Test Author <author@example.test>\n\n"
        "# ------------------------ >8 ------------------------\n\n"
        "Co-authored-by: Second Author <second@example.test>"
    )
    if signed_coauthor:
        message += "\nSigned-off-by: Second Author <second@example.test>"
    git(path, "commit", "--allow-empty", f"--cleanup={cleanup}", "-m", message)
    head = git(path, "rev-parse", "HEAD")
    assert git(path, "show", "--no-patch", "--format=%B", head) == message
    assert check_range(path, base, head) == [f"{head}: ambiguous commit-message scissors marker"]


def test_empty_or_unsafe_range_fails(history: tuple[Path, str]) -> None:
    path, base = history
    with pytest.raises(ValueError, match="no contributed commits"):
        check_range(path, base, base)
    with pytest.raises(ValueError, match="full commit"):
        check_range(path, "--all", base)


@pytest.mark.parametrize("signed", [True, False])
def test_history_free_export_checks_root_commit(tmp_path: Path, signed: bool) -> None:
    git(tmp_path, "init", "--initial-branch=main")
    message = "Public snapshot" + (
        "\n\nSigned-off-by: Test Author <author@example.test>" if signed else ""
    )
    git(tmp_path, "commit", "--allow-empty", "-m", message)
    head = git(tmp_path, "rev-parse", "HEAD")
    failures = check_range(tmp_path, None, head)
    assert (failures == []) is signed
    git(tmp_path, "commit", "--allow-empty", "-s", "-m", "Signed subsequent change")
    assert check_range(tmp_path, None, git(tmp_path, "rev-parse", "HEAD")) == failures


def test_signed_commit_with_wrong_rc_author_fails(history: tuple[Path, str]) -> None:
    path, base = history
    git(path, "commit", "--allow-empty", "-s", "-m", "Signed but not the owner")
    head = git(path, "rev-parse", "HEAD")
    assert check_range(path, base, head, expected_author="Test Author <author@example.test>") == []
    assert check_range(path, base, head, expected_author="Han Chen <hc414t@gmail.com>") == [
        f"{head}: author differs from confirmed RC owner identity"
    ]


def test_ci_runs_only_trusted_checker_with_read_only_permissions() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/dco.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request_target" in triggers
    steps = workflow["jobs"]["dco"]["steps"]
    assert steps[0]["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert steps[1]["with"]["fetch-depth"] == 0
    assert all(step["with"]["persist-credentials"] is False for step in steps[:2])
    commands = [step["run"] for step in steps if "run" in step]
    assert commands == [
        "python3 -I trusted-policy/scripts/check_dco.py --repository contribution-history "
        '--base "$BASE_SHA" --head "$HEAD_SHA"'
    ]
