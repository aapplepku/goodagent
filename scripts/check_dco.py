"""Check every contributed commit using Git's structured commit/trailer interfaces."""

import argparse
import re
import subprocess
from pathlib import Path

IDENTITY = re.compile(r"([^<>\r\n]+) <([^<>\s]+@[^<>\s]+)>")
OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
SCISSORS = "------------------------ >8 ------------------------"


def git(repository: Path, *args: str, input_text: str | None = None) -> str:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repository), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def identity(value: str) -> tuple[str, str]:
    match = IDENTITY.fullmatch(value.strip())
    if not match or not match[1].strip():
        raise ValueError("malformed contributor identity")
    return match[1].strip(), match[2].casefold()


def check_range(
    repository: Path, base: str | None, head: str, *, expected_author: str | None = None
) -> list[str]:
    expected = identity(expected_author) if expected_author is not None else None
    for revision in (head,) if base is None else (base, head):
        if not OBJECT_ID.fullmatch(revision):
            raise ValueError("base and head must be full commit object IDs")
        if git(repository, "rev-parse", "--verify", f"{revision}^{{commit}}").strip() != revision:
            raise ValueError("revision does not name the expected commit")
    # A history-free public snapshot has no parent; explicitly check its root too.
    selection = head if base is None else f"{base}..{head}"
    commits = git(repository, "rev-list", "--reverse", selection).splitlines()
    if not commits:
        raise ValueError("no contributed commits found; check the selected PR range")
    failures = []
    for commit in commits:
        name, email, message = git(
            repository, "show", "--no-patch", "--format=%an%x00%ae%x00%B", commit
        ).split("\0", 2)
        # Git trims scissors suffixes even with --no-divider. Never certify a partial message.
        if SCISSORS in message:
            failures.append(f"{commit}: ambiguous commit-message scissors marker")
            continue
        try:
            author = identity(f"{name} <{email}>")
            if expected is not None and author != expected:
                failures.append(f"{commit}: author differs from confirmed RC owner identity")
            required = {author}
            signed = set()
            # This is a full commit message, not an email patch with a --- divider.
            trailers = git(
                repository, "interpret-trailers", "--parse", "--no-divider", input_text=message
            )
            for line in trailers.splitlines():
                key, _, value = line.partition(":")
                if key.casefold() == "signed-off-by":
                    signed.add(identity(value))
                elif key.casefold() == "co-authored-by":
                    required.add(identity(value))
            if not required.issubset(signed):
                failures.append(f"{commit}: missing author/coauthor DCO sign-off")
        except ValueError:
            failures.append(f"{commit}: malformed author/coauthor/sign-off identity")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--base")
    selection.add_argument("--all", action="store_true", help="Check all ancestors including root")
    parser.add_argument("--head", required=True)
    parser.add_argument("--expected-author")
    args = parser.parse_args()
    try:
        failures = check_range(
            args.repository, args.base, args.head, expected_author=args.expected_author
        )
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"DCO range could not be verified: {type(error).__name__}") from error
    if failures:
        raise SystemExit("\n".join(failures))
    print("DCO passed for every contributed commit; certification truth remains the contributor's.")


if __name__ == "__main__":
    main()
