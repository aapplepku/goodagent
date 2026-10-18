"""Reject personal workstation and temporary-directory paths in release artifacts."""

import gzip
import re
from pathlib import Path

LOCAL_PATH = re.compile(r"/(?:Users/|private/tmp/|var/folders/)")


def main() -> None:
    paths = set(Path(".").glob("*.md"))
    for directory in ("docs", "plans", "security"):
        paths.update(p for p in Path(directory).rglob("*") if p.is_file())
    failures = []
    for path in sorted(paths):
        raw = path.read_bytes()
        if path.suffix == ".gz":
            raw = gzip.decompress(raw)
        if LOCAL_PATH.search(raw.decode("utf-8", errors="replace")):
            failures.append(str(path))
    if failures:
        raise SystemExit("local-only paths in release artifacts: " + ", ".join(failures))
    print("Release documents and security artifacts contain no recognized local-only paths.")


if __name__ == "__main__":
    main()
