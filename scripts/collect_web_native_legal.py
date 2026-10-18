"""Collect unchanged legal text from the exact sharp-libvips native source versions."""

import argparse
import concurrent.futures
import gzip
import hashlib
import io
import json
import re
import tarfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.collect_qdrant_legal import LEGAL, archive_files, collect_package, download
from scripts.dependency_attribution import require_attribution

SOURCES = {
    "aom": "https://storage.googleapis.com/aom-releases/libaom-{v}.tar.gz",
    "archive": "https://github.com/libarchive/libarchive/releases/download/v{v}/libarchive-{v}.tar.xz",
    "cairo": "https://cairographics.org/releases/cairo-{v}.tar.xz",
    "cgif": "https://codeload.github.com/dloebl/cgif/tar.gz/refs/tags/v{v}",
    "exif": "https://github.com/libexif/libexif/releases/download/v{v}/libexif-{v}.tar.xz",
    "expat": "https://github.com/libexpat/libexpat/releases/download/R_{under}/expat-{v}.tar.xz",
    "ffi": "https://github.com/libffi/libffi/releases/download/v{v}/libffi-{v}.tar.gz",
    "fontconfig": "https://gitlab.freedesktop.org/fontconfig/fontconfig/-/archive/{v}/fontconfig-{v}.tar.gz",
    "freetype": "https://codeload.github.com/freetype/freetype/tar.gz/refs/tags/VER-{dash}",
    "fribidi": "https://github.com/fribidi/fribidi/releases/download/v{v}/fribidi-{v}.tar.xz",
    "glib": "https://download.gnome.org/sources/glib/{minor}/glib-{v}.tar.xz",
    "harfbuzz": "https://codeload.github.com/harfbuzz/harfbuzz/tar.gz/refs/tags/{v}",
    "heif": "https://github.com/strukturag/libheif/releases/download/v{v}/libheif-{v}.tar.gz",
    "highway": "https://codeload.github.com/google/highway/tar.gz/refs/tags/{v}",
    "imagequant": "https://codeload.github.com/lovell/libimagequant/tar.gz/refs/tags/v{v}",
    "lcms": "https://github.com/mm2/Little-CMS/releases/download/lcms{v}/lcms2-{v}.tar.gz",
    "mozjpeg": "https://codeload.github.com/mozilla/mozjpeg/tar.gz/{v}",
    "pango": "https://download.gnome.org/sources/pango/{minor}/pango-{v}.tar.xz",
    "pixman": "https://cairographics.org/releases/pixman-{v}.tar.gz",
    "png": "https://codeload.github.com/pnggroup/libpng/tar.gz/refs/tags/v{v}",
    "proxy-libintl": "https://codeload.github.com/frida/proxy-libintl/tar.gz/refs/tags/{v}",
    "rsvg": "https://download.gnome.org/sources/librsvg/{minor}/librsvg-{v}.tar.xz",
    "tiff": "https://gitlab.com/libtiff/libtiff/-/archive/v{v}/libtiff-v{v}.tar.gz",
    "uhdr": "https://codeload.github.com/google/libultrahdr/tar.gz/refs/tags/v{v}",
    "vips": "https://github.com/libvips/libvips/releases/download/v{v}/vips-{v}.tar.xz",
    "webp": "https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-{v}.tar.gz",
    "xml2": "https://download.gnome.org/sources/libxml2/{minor}/libxml2-{v}.tar.xz",
    "zlib-ng": "https://codeload.github.com/zlib-ng/zlib-ng/tar.gz/refs/tags/{v}",
}
MIT_DECLARATIONS = {
    ("block", "0.1.6"),
    ("difflib", "0.4.0"),
    ("malloc_buf", "0.0.6"),
    ("objc-foundation", "0.1.1"),
    ("objc_id", "0.1.1"),
}
SEPARATE_UPSTREAM_NOTICES = {
    ("malloc_buf", "0.0.6"): ("SSheldon/malloc_buf", "d9a3e539642bd90e07df458d226b19cdfa606863"),
    ("difflib", "0.4.0"): ("DimaKudosh/difflib", "f035fb8e656f27119e23eca9d5b996df14f3885e"),
}


def collect_locked_crate(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    name, version = package["name"], package["versionInfo"]
    if (name, version) not in MIT_DECLARATIONS:
        return collect_package(package)
    url = f"https://static.crates.io/crates/{name}/{name}-{version}.crate"
    raw = download(url)
    originals = archive_files(raw)
    metadata = tomllib.loads(originals["Cargo.toml"].decode())["package"]
    if metadata["license"] != "MIT" or not metadata.get("authors"):
        raise ValueError("reviewed MIT declaration/attribution changed")
    license_url = "https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/MIT.txt"
    license_raw = download(license_url)
    originals["MIT-standard-template.txt"] = license_raw
    sources = [
        {"url": url, "sha256": hashlib.sha256(raw).hexdigest()},
        {"url": license_url, "sha256": hashlib.sha256(license_raw).hexdigest()},
    ]
    if (name, version) in SEPARATE_UPSTREAM_NOTICES:
        repository, revision = SEPARATE_UPSTREAM_NOTICES[name, version]
        upstream = f"https://codeload.github.com/{repository}/tar.gz/{revision}"
        upstream_raw = download(upstream)
        notices = {
            p: b
            for p, b in archive_files(upstream_raw).items()
            if LEGAL.search(PurePosixPath(p).name)
        }
        if not notices:
            raise ValueError("separately recorded upstream notice is missing")
        originals.update({f"upstream-notices/{p}": b for p, b in notices.items()})
        sources.append({"url": upstream, "sha256": hashlib.sha256(upstream_raw).hexdigest()})
    files = {f"{name}@{version}/{p}": b for p, b in originals.items()}
    record = {
        "name": name,
        "version": version,
        "license": "MIT",
        "license_selection": (
            "upstream MIT declaration and original authors/source; "
            "unchanged standard template, no invented attribution"
        ),
        "sources": sources,
        "files": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())},
    }
    require_attribution([record], files)
    return record, files


def source_files(raw: bytes) -> dict[str, bytes]:
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe native source path")
            if not member.isfile() or not (
                LEGAL.search(path.name)
                or path.name.lower() in {"patents", "ftl.txt", "gplv2.txt", "cargo.lock"}
            ):
                continue
            if member.size > 8 * 1024 * 1024:
                raise ValueError("oversized native legal file")
            stream = archive.extractfile(member)
            assert stream is not None
            files[str(PurePosixPath(*path.parts[1:]))] = stream.read()
    return files


def collect_native(item: tuple[str, str]) -> tuple[dict[str, Any], dict[str, bytes]]:
    name, version = item
    if name not in SOURCES or not re.fullmatch(r"[0-9a-z.-]+", version):
        raise ValueError("unreviewed native identity")
    url = SOURCES[name].format(
        v=version,
        minor=".".join(version.split(".")[:2]),
        dash=version.replace(".", "-"),
        under=version.replace(".", "_"),
    )
    raw = download(url)
    originals = source_files(raw)
    if not any(PurePosixPath(p).name != "Cargo.lock" for p in originals):
        raise ValueError(f"no legal text for {name}@{version}")
    files = {f"{name}@{version}/{p}": b for p, b in originals.items()}
    return {
        "name": name,
        "version": version,
        "sources": [{"url": url, "sha256": hashlib.sha256(raw).hexdigest()}],
        "files": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())},
    }, files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    versions = json.loads(args.versions.read_bytes())
    if set(versions) != set(SOURCES):
        raise ValueError("native inventory changed; review every added/removed component")
    records: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(collect_native, item): item for item in versions.items()}
        for future in concurrent.futures.as_completed(futures):
            try:
                record, contents = future.result()
                records.append(record)
                files.update(contents)
                print(f"Native notices: {record['name']}", flush=True)
            except Exception as error:
                failures.append({"package": futures[future], "error": str(error)})
    if failures:
        Path(".opencommerce/web-native-legal-failures.json").write_text(
            json.dumps(failures, indent=2) + "\n"
        )
        raise SystemExit(f"{len(failures)} native notice collections failed")
    # librsvg embeds Rust dependencies; retain all locked crates, including build-only entries.
    crates = {}
    for name, content in files.items():
        if PurePosixPath(name).name == "Cargo.lock":
            for package in tomllib.loads(content.decode())["package"]:
                source = package.get("source")
                if source:
                    crates[(package["name"], package["version"])] = {
                        "name": package["name"],
                        "versionInfo": package["version"],
                        "downloadLocation": source,
                    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(collect_locked_crate, p): p for p in crates.values()}
        for future in concurrent.futures.as_completed(futures):
            try:
                record, contents = future.result()
                records.append(record)
                for name, content in contents.items():
                    if name in files and files[name] != content:
                        raise ValueError("conflicting native notice")
                    files[name] = content
            except Exception as error:
                failures.append({"package": futures[future], "error": str(error)})
    if failures:
        Path(".opencommerce/web-native-legal-failures.json").write_text(
            json.dumps(failures, indent=2) + "\n"
        )
        raise SystemExit(f"{len(failures)} Rust notice collections failed")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.mode, member.mtime, member.size = 0o444, 0, len(content)
            archive.addfile(member, io.BytesIO(content))
    bundle = gzip.compress(buffer.getvalue(), mtime=0)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "native-notices.tar.gz").write_bytes(bundle)
    (args.output / "native-manifest.json").write_text(
        json.dumps(
            {
                "complete": True,
                "versions": versions,
                "scope": (
                    "all named native libraries and locked Rust dependencies, "
                    "including build entries"
                ),
                "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
                "packages": sorted(records, key=lambda p: (p["name"], p["version"])),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    print(f"Preserved {len(files)} files from {len(records)} exact source packages")


if __name__ == "__main__":
    main()
