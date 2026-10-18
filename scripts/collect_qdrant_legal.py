"""Preserve legal files from exact sources named by Qdrant's built-image SPDX inventory."""

import argparse
import concurrent.futures
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dependency_attribution import require_attribution

LEGAL = re.compile(
    r"(^|[._-])(licen[sc]e|notice|copying|copyright|authors)([._-]|$)|third.?party.*notic",
    re.IGNORECASE,
)
CACHE = Path(".opencommerce/legal-source-downloads")
APACHE_DECLARATIONS = {
    ("actix-web-extras", "0.1.0"),
    ("crc32c", "0.6.8"),
    ("fxhash", "0.2.1"),
    ("http-serde", "2.1.1"),
    ("rustls-platform-verifier-android", "0.1.1"),
    ("winapi-i686-pc-windows-gnu", "0.4.0"),
    ("winapi-x86_64-pc-windows-gnu", "0.4.0"),
}


def download(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if cached.exists():
        return cached.read_bytes()
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Open-Commerce-legal-audit"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                data = bytes(response.read(128 * 1024 * 1024 + 1))
            if len(data) > 128 * 1024 * 1024:
                raise ValueError("source archive exceeds download size limit")
            temporary = cached.with_suffix(f".{time.time_ns()}.tmp")
            temporary.write_bytes(data)
            temporary.replace(cached)
            return data
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def archive_files(data: bytes) -> dict[str, bytes]:
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe source archive path")
            if not member.isfile():
                continue
            if not (
                LEGAL.search(path.name)
                or path.name
                in ("Cargo.toml", "Cargo.toml.orig", ".cargo_vcs_info.json", "README.md")
                or path.suffix == ".rs"
            ):
                continue
            if member.size > 8 * 1024 * 1024:
                raise ValueError("legal file exceeds size limit")
            stream = archive.extractfile(member)
            assert stream is not None
            result[str(PurePosixPath(*path.parts[1:]))] = stream.read()
    return result


def github_source(repository: str, revision: str) -> str:
    match = re.fullmatch(
        r"https://github.com/([\w.-]+/[\w.-]+?)(?:\.git)?(?:/tree/[\w./-]+)?/?", repository
    )
    codeberg = re.fullmatch(r"https://codeberg.org/([\w.-]+/[\w.-]+)", repository)
    if codeberg and re.fullmatch(r"[0-9a-f]{40}", revision):
        return f"https://codeberg.org/{codeberg[1]}/archive/{revision}.tar.gz"
    if not match or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("upstream fallback needs an exact GitHub repository/commit")
    return f"https://codeload.github.com/{match[1]}/tar.gz/{revision}"


def collect_package(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    name, version = package["name"], package["versionInfo"]
    location = package.get("downloadLocation", "NONE")
    if not re.fullmatch(r"[\w.-]+", name) or not re.fullmatch(r"[\w.+-]+", version):
        raise ValueError("unsafe package identity")
    if location == "NONE":
        url = "https://codeload.github.com/qdrant/qdrant/tar.gz/refs/tags/v1.19.1"
    elif location == "registry+https://github.com/rust-lang/crates.io-index":
        url = f"https://static.crates.io/crates/{name}/{name}-{version}.crate"
    elif location.startswith("git+"):
        repository, revision = location[4:].split("#", 1)
        url = github_source(repository.split("?", 1)[0], revision)
    else:
        raise ValueError(f"unreviewed package source: {name}")
    data = download(url)
    sources = [{"url": url, "sha256": hashlib.sha256(data).hexdigest()}]
    contents = archive_files(data)
    notices = {p: b for p, b in contents.items() if LEGAL.search(PurePosixPath(p).name)}
    selection = None
    if not notices and (name, version) in APACHE_DECLARATIONS:
        metadata = tomllib.loads(contents["Cargo.toml"].decode())["package"]
        if "Apache-2.0" not in metadata["license"]:
            raise ValueError("reviewed upstream Apache option changed")
        # These exact crates publish their grant in metadata/source instead of a LICENSE file.
        # Preserve declarations and all source attribution verbatim, plus the selected full text.
        notices = dict(contents)
        license_url = "https://www.apache.org/licenses/LICENSE-2.0.txt"
        license_text = download(license_url)
        notices["LICENSE-APACHE-2.0"] = license_text
        sources.append({"url": license_url, "sha256": hashlib.sha256(license_text).hexdigest()})
        selection = "Apache-2.0; upstream declarations and source attribution retained verbatim"
    if not notices:
        metadata = tomllib.loads(contents["Cargo.toml"].decode())
        if (name, version) == ("symbolic-common", "13.1.1"):
            upstream = "https://codeload.github.com/getsentry/symbolic/tar.gz/refs/tags/13.1.1"
        else:
            vcs = json.loads(contents[".cargo_vcs_info.json"])
            upstream = github_source(metadata["package"]["repository"], vcs["git"]["sha1"])
        source = download(upstream)
        sources.append({"url": upstream, "sha256": hashlib.sha256(source).hexdigest()})
        notices = {
            p: b for p, b in archive_files(source).items() if LEGAL.search(PurePosixPath(p).name)
        }
    if not notices:
        if (name, version) == ("stumpalo", "1.0.0"):
            metadata = tomllib.loads(contents["Cargo.toml"].decode())["package"]
            if metadata["license"] != "BSD-3-Clause":
                raise ValueError("reviewed upstream BSD declaration changed")
            # The published crate/revision has no separate copyright or license file.
            # Retain its declarations/source and the unchanged standard license template;
            # do not invent a copyright holder or replace template placeholders.
            notices = dict(contents)
            license_url = (
                "https://raw.githubusercontent.com/spdx/license-list-data/"
                "v3.27.0/text/BSD-3-Clause.txt"
            )
            license_text = download(license_url)
            notices["BSD-3-Clause-standard-template.txt"] = license_text
            sources.append({"url": license_url, "sha256": hashlib.sha256(license_text).hexdigest()})
            selection = "BSD-3-Clause declared upstream; standard template, no invented attribution"
    if not notices:
        raise ValueError(f"no original legal files found for {name}@{version}")
    files = {f"{name}@{version}/{p}": b for p, b in notices.items()}
    record = {
        "name": name,
        "version": version,
        "license": package.get("licenseDeclared"),
        "license_selection": selection,
        "sources": sources,
        "files": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())},
    }
    require_attribution([record], files)
    return record, files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("use a new legal evidence output directory")
    raw = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "cat",
            args.image,
            "/qdrant/qdrant.spdx.json",
        ]
    )
    sbom = json.loads(raw)
    packages = sorted(sbom["packages"], key=lambda p: (p["name"], p["versionInfo"]))
    records: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    failures: list[dict[str, str]] = []
    # Sources are read as data only. No archive path is extracted and no build script is run.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(collect_package, p): p for p in packages}
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            try:
                record, notices = future.result()
            except Exception as error:
                package = futures[future]
                failures.append(
                    {
                        "name": package["name"],
                        "version": package["versionInfo"],
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                continue
            records.append(record)
            for path, data in notices.items():
                if path in files and files[path] != data:
                    raise ValueError("conflicting package legal file")
                files[path] = data
            if index % 25 == 0:
                print(f"{index}/{len(packages)} package notices preserved", flush=True)
    if failures:
        report = Path(".opencommerce/qdrant-legal-failures.json")
        report.write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
        raise SystemExit(f"{len(failures)} missing notices; original errors retained in {report}")
    records.sort(key=lambda p: (p["name"], p["version"]))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path, data in sorted(files.items()):
            info = tarfile.TarInfo(path)
            info.mode, info.mtime, info.size = 0o444, 0, len(data)
            archive.addfile(info, io.BytesIO(data))
    bundle = gzip.compress(buffer.getvalue(), mtime=0)
    args.output.mkdir(parents=True)
    (args.output / "notices.tar.gz").write_bytes(bundle)
    (args.output / "upstream.spdx.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (args.output / "manifest.json").write_text(
        json.dumps(
            {
                "complete": True,
                "image": args.image,
                "first_party_license": "Apache-2.0",
                "scope": (
                    "all upstream SPDX packages, including non-runtime/build/platform dependencies"
                ),
                "sbom_sha256": hashlib.sha256(raw).hexdigest(),
                "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
                "packages": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"Preserved {len(files)} original legal files for {len(records)} packages")


if __name__ == "__main__":
    main()
