"""Explicit install of the two immutable learned-search data files, with hashes."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from open_commerce.search.learned_embeddings import MODEL_FILES, MODEL_REPOSITORY, MODEL_REVISION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    evidence = []
    for name, (remote_path, expected) in MODEL_FILES.items():
        path = args.directory / name
        if path.is_symlink():
            raise ValueError("model artifact cannot be a symlink")
        url = f"https://huggingface.co/{MODEL_REPOSITORY}/resolve/{MODEL_REVISION}/{remote_path}"
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read(100_000_001)
            if len(data) > 100_000_000 or hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("downloaded model does not match pinned bytes")
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("existing model artifact checksum mismatch")
        evidence.append(
            {"file": name, "sha256": expected, "bytes": path.stat().st_size, "url": url}
        )
    print(
        json.dumps(
            {"model": MODEL_REPOSITORY, "revision": MODEL_REVISION, "files": evidence}, indent=2
        )
    )


if __name__ == "__main__":
    main()
