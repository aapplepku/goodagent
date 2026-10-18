"""Create bounded source-distribution derivatives; never qualify dependency binaries."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.verify_release_legal import tar_contents, verify_collection_files

PROFILE = "goodagent-source-only-notices-v1"
COLLECTIONS: dict[str, dict[str, Any]] = {
    "security/third-party/qdrant-1.19.1": {
        "manifest": "manifest.json",
        "archive": "notices.tar.gz",
        "original_manifest": "24bd9700235506589f3ae721ba514cf26fc2ccdeaf0054bfc57bb0c0ac19b971",
        "original_archive": "706c13de0660a0f7c2aa929eecc3267232a76e797b84662e5ec1763e25694ed8",
        "excluded": ["stumpalo@1.0.0"],
    },
    "security/third-party/sharp-libvips-1.3.3": {
        "manifest": "native-manifest.json",
        "archive": "native-notices.tar.gz",
        "original_manifest": "1d51e3c38c526a7a10b18fc7aa6f0b462e312b4e937533abaf08243e8165b7dd",
        "original_archive": "997e5b6bb52de07542955106d2e634c1360bba6b0c073dae8782ed729444cb3e",
        "excluded": ["block@0.1.6", "objc-foundation@0.1.1", "objc_id@0.1.1"],
    },
    "security/third-party/sharp-libvips-1.3.4": {
        "manifest": "native-manifest.json",
        "archive": "native-notices.tar.gz",
        "original_manifest": "924e9730cd6af1dbcaba18d5577ae0f6e1b93fad4d046b08e6c6412c6f741795",
        "original_archive": "bc8c9e3bdbeb6f570447a2eb04a51754876862e05b8f2f480bcd550c9751e461",
        "excluded": ["block@0.1.6", "objc-foundation@0.1.1", "objc_id@0.1.1"],
    },
}
# Exact public derivatives are independently reviewed alongside the transformation.
DERIVED_HASHES = {
    "security/third-party/qdrant-1.19.1/manifest.json": (
        "6dafa3b2c278ce4def91c7c88a9067b34f110c69d386580f48e7a89200a26bac"
    ),
    "security/third-party/qdrant-1.19.1/notices.tar.gz": (
        "fc1e95e2159c97f5855eae3bb7e3cea7b26fad67622eedb8489fbc873ea6c3c7"
    ),
    "security/third-party/sharp-libvips-1.3.3/native-manifest.json": (
        "e8c4838de1f1a40d63467ae08d47849910e353fa246eb7be5296b2d75643c8ac"
    ),
    "security/third-party/sharp-libvips-1.3.3/native-notices.tar.gz": (
        "27d7c5f7800717dbb880963b1710e54639bc0e737fdc76007d26b9718693878a"
    ),
    "security/third-party/sharp-libvips-1.3.4/native-manifest.json": (
        "f20e40c5c4668528552e6c0193055c97b5c2aa8111d1901dbb833b7f66346592"
    ),
    "security/third-party/sharp-libvips-1.3.4/native-notices.tar.gz": (
        "56169a0fd86bdb3c54f24a02b73b7f0730b0f06bd76d1aa165f7357b397d12f7"
    ),
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def exclusion_text(identity: str) -> bytes:
    return (
        "GoodAgent source distribution exclusion\n\n"
        f"Dependency: {identity}\n"
        "The applicable original upstream attribution notice remains unresolved.\n"
        "All copied files of this dependency were excluded from this source bundle.\n"
        "This is a first-party disclosure, not an upstream license or permission.\n"
        "Its identity remains in the dependency inventory for audit and build coverage.\n"
        "Dependency binaries are not included in this source distribution.\n"
        "Runtime/image redistribution remains blocked pending original notice review.\n"
        "See docs/DEPENDENCY_ATTRIBUTION.md and the original file hashes in the manifest.\n"
    ).encode()


def archive_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, content in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(content), 0o644, 0
            archive.addfile(member, io.BytesIO(content))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, filename="", mode="wb", mtime=0) as stream:
        stream.write(buffer.getvalue())
    return compressed.getvalue()


def derive(directory: str, manifest_raw: bytes, archive_raw: bytes) -> tuple[bytes, bytes]:
    policy = COLLECTIONS[directory]
    if (digest(manifest_raw), digest(archive_raw)) != (
        policy["original_manifest"],
        policy["original_archive"],
    ):
        raise ValueError("source-only derivation requires exact reviewed original bytes")
    manifest = json.loads(manifest_raw)
    files = tar_contents(archive_raw)
    identities = verify_collection_files(manifest["packages"], files)
    if not set(policy["excluded"]) <= identities:
        raise ValueError("source-only exclusion is absent from original inventory")
    removed_count = 0
    for package in manifest["packages"]:
        identity = f"{package['name']}@{package['version']}"
        if identity not in policy["excluded"]:
            continue
        package["excluded_files"] = package["files"]
        removed_count += len(package["files"])
        for name in package["files"]:
            del files[name]
        name = f"{identity}/SOURCE_ONLY_OMISSION.txt"
        files[name] = exclusion_text(identity)
        package["files"] = {name: digest(files[name])}
        package["attribution_status"] = "blocked; upstream copies excluded from source distribution"
    public_archive = archive_bytes(files)
    manifest["bundle_sha256"] = digest(public_archive)
    manifest["attribution_complete"] = False
    manifest["source_distribution"] = {
        "profile": PROFILE,
        "original_manifest_sha256": policy["original_manifest"],
        "original_archive_sha256": policy["original_archive"],
        "excluded_packages": policy["excluded"],
        "excluded_files": removed_count,
        "runtime_redistribution_qualified": False,
    }
    manifest["scope"] = (
        "Complete recorded dependency inventory, with explicit first-party exclusion records "
        "in place of all copied files of the known attribution-gap packages. "
        "Not complete upstream attribution and not binary/image redistribution qualification."
    )
    verify_collection_files(manifest["packages"], files)
    return encoded(manifest), public_archive


def public_file(relative: str, read: Callable[[str], bytes]) -> bytes:
    for directory, policy in COLLECTIONS.items():
        names = [f"{directory}/{policy[key]}" for key in ("manifest", "archive")]
        if relative not in names:
            continue
        original = tuple(read(name) for name in names)
        if all(
            digest(raw) == DERIVED_HASHES.get(name)
            for name, raw in zip(names, original, strict=True)
        ):
            return original[names.index(relative)]
        derived = derive(directory, *original)
        if any(
            digest(raw) != DERIVED_HASHES.get(name)
            for name, raw in zip(names, derived, strict=True)
        ):
            raise ValueError("source-only derivative differs from reviewed public identity")
        return derived[names.index(relative)]
    raise ValueError("unreviewed source-only substitution")


def public_retention(raw: bytes) -> bytes:
    retained = json.loads(raw)
    for directory, policy in COLLECTIONS.items():
        name = f"{directory}/{policy['archive']}"
        if retained.get(name) not in {policy["original_archive"], DERIVED_HASHES.get(name)}:
            raise ValueError("source-only archive retention identity changed")
        retained[name] = DERIVED_HASHES[name]
    return encoded(retained)


def verify_public_collections(root: Path) -> list[dict[str, Any]]:
    """Fail if any reviewed public derivative was changed, omitted or replaced."""
    records = []
    for directory, policy in COLLECTIONS.items():
        manifest_name = f"{directory}/{policy['manifest']}"
        archive_name = f"{directory}/{policy['archive']}"
        manifest_raw, archive_raw = (
            (root / manifest_name).read_bytes(),
            (root / archive_name).read_bytes(),
        )
        if (digest(manifest_raw), digest(archive_raw)) != (
            DERIVED_HASHES[manifest_name],
            DERIVED_HASHES[archive_name],
        ):
            raise ValueError("public source-only collection is missing or changed")
        manifest = json.loads(manifest_raw)
        files = tar_contents(archive_raw)
        verify_collection_files(manifest["packages"], files)
        for identity in policy["excluded"]:
            assert {
                name: data for name, data in files.items() if name.startswith(identity + "/")
            } == {f"{identity}/SOURCE_ONLY_OMISSION.txt": exclusion_text(identity)}
        records.append(
            {
                "collection": directory,
                "manifest_sha256": digest(manifest_raw),
                "archive_sha256": digest(archive_raw),
                "excluded_packages": policy["excluded"],
                "excluded_files": manifest["source_distribution"]["excluded_files"],
            }
        )
    return records
