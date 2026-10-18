"""Retain reproducible first-pass search source without altering the working tree."""

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/eval/search-merchandising-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-normalizer-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to replace retained source archive")
    normalizer = "packages/backend/src/open_commerce/search/normalization.py"
    old = subprocess.run(
        ["git", "show", f"{args.original_normalizer_ref}:{normalizer}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    paths = [
        *sorted((ROOT / "packages/backend/src/open_commerce/search").glob("*.py")),
        ROOT / "packages/backend/src/open_commerce/simulator/merchandising_catalog.py",
        ROOT / "uv.lock",
        DATA / "protocol.md",
        DATA / "judgments.json",
        ROOT / "scripts/run_search_merchandising_evaluation.py",
    ]
    files = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
    files[normalizer] = old
    digest = hashlib.sha256()
    for path in paths:
        relative = str(path.relative_to(ROOT))
        digest.update(relative.encode() + b"\0" + files[relative])
    expected = {
        json.loads((DATA / name).read_text())["source_fingerprint"]
        for name in ("development.json", "held-out.json")
    }
    if expected != {digest.hexdigest()}:
        raise ValueError(
            "Source reconstruction does not match BOTH retained first-pass fingerprints"
        )
    for path in (ROOT / "packages/backend/src").rglob("*.py"):
        files.setdefault(str(path.relative_to(ROOT)), path.read_bytes())
    for name in ("pyproject.toml", "packages/backend/pyproject.toml"):
        files[name] = (ROOT / name).read_bytes()
    payload = {
        "source_fingerprint": digest.hexdigest(),
        "normalizer_restored_in_archive_only_from_ref": args.original_normalizer_ref,
        "working_tree_changed": False,
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "text": data.decode()}
            for name, data in sorted(files.items())
        },
    }
    raw = json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n"
    args.output.write_bytes(gzip.compress(raw, mtime=0))
    print(
        json.dumps(
            {
                "source_fingerprint": digest.hexdigest(),
                "archive_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "file_count": len(files),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
