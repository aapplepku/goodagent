"""Collect immutable upstream and installed optional-encoder notices without editing text."""

import gzip
import hashlib
import io
import json
import tarfile
from importlib.metadata import distribution
from pathlib import Path
from typing import Any

import httpx

PACKAGES = (
    "onnxruntime",
    "tokenizers",
    "huggingface-hub",
    "hf-xet",
    "flatbuffers",
    "fsspec",
    "filelock",
    "tqdm",
)
UPSTREAM = (("huggingface/tokenizers", "v0.23.2"), ("google/flatbuffers", "v25.12.19"))
MODEL_REVISION = "dfa9feb5cece5be2cc8fc23a3cf1f32473a9d56f"


def main() -> None:
    output = Path("security/third-party/learned-search")
    if (output / "manifest.json").exists():
        raise SystemExit("Refusing to replace retained license provenance")
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    records: list[dict[str, Any]] = []
    for name in PACKAGES:
        package = distribution(name)
        found = {}
        for path in package.files or []:
            if ".." in path.parts or path.is_absolute():
                continue
            if any(word in str(path).lower() for word in ("license", "licence", "notice")):
                data = Path(str(package.locate_file(path))).read_bytes()
                key = f"{name}@{package.version}/{path}"
                files[key] = data
                found[key] = hashlib.sha256(data).hexdigest()
        records.append(
            {
                "package": name,
                "version": package.version,
                "license_expression": package.metadata.get("License-Expression")
                or package.metadata.get("License"),
                "classifiers": package.metadata.get_all("Classifier", []),
                "installed_notices": found,
            }
        )
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for repo, tag in UPSTREAM:
            response = client.get(f"https://api.github.com/repos/{repo}/commits/{tag}")
            response.raise_for_status()
            commit = response.json()["sha"]
            url = f"https://raw.githubusercontent.com/{repo}/{commit}/LICENSE"
            response = client.get(url)
            response.raise_for_status()
            key = f"upstream/{repo.replace('/', '-')}/{commit}/LICENSE"
            files[key] = response.content
            records.append(
                {
                    "upstream_repository": repo,
                    "tag": tag,
                    "commit": commit,
                    "url": url,
                    "file": key,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
            )
        url = f"https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/raw/{MODEL_REVISION}/README.md"
        response = client.get(url)
        response.raise_for_status()
        files["model/model-card.md"] = response.content
        records.append(
            {
                "model_card_url": url,
                "revision": MODEL_REVISION,
                "license_basis": (
                    "Apache-2.0 declaration in pinned model card; "
                    "no separate LICENSE in model repository"
                ),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, data in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    raw = gzip.compress(stream.getvalue(), mtime=0)
    (output / "notices.tar.gz").write_bytes(raw)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Optional learned encoder, installed Python package notices and supplemental "
                    "upstream licenses. Native transitive inventories are scanner-limited, "
                    "not a redistribution certification."
                ),
                "records": records,
                "archive_sha256": hashlib.sha256(raw).hexdigest(),
                "files": {
                    name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
                },
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    print(f"Retained {len(files)} unmodified notice/model-card files")


if __name__ == "__main__":
    main()
