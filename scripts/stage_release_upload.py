"""Stage acquisition bytes, not approval: only screened image copies are uploaded.

The trusted workflow runs Gitleaks between prepare-images and finalize. This helper
binds that staging tree to the collector receipts; it neither runs a scanner nor
authenticates a human decision. Failed staging is retained and must not be uploaded
as a complete candidate. Retry in a fresh checkout, never overwrite evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, BinaryIO, Literal

from pydantic import Field, ValidationError

from scripts import check_release_assessments as gate
from scripts import check_source_assessments as source
from scripts import collect_release_evidence as collector
from scripts.release_evidence_archive import MAX_ARCHIVE_BYTES

UPLOAD = ".opencommerce/release-upload"
MANIFEST = collector.OUTPUT + "/image-upload.json"
PROVENANCE = collector.OUTPUT + "/provenance.json"
CHECKOUTS = tuple(collector.OUTPUT + f"/checkout-{phase}.json" for phase in ("before", "after"))
CI_FILES = {
    MANIFEST,
    PROVENANCE,
    *CHECKOUTS,
    collector.SOURCE_MANIFEST,
    collector.SOURCE_RESULT,
    collector.RESULT,
}
FLAGS = ("qualification_passed", "security_approved", "release_approved")
STAGES = {
    "dependencies",
    "before",
    "source",
    "build",
    "images",
    "image_privacy",
    "finalize",
    "after",
}


class ImageUpload(gate.StrictModel):
    schema_version: Literal[1]
    files: Annotated[list[gate.FileRef], Field(min_length=1, max_length=gate.MAX_FILES)]
    qualification_passed: bool
    security_approved: bool
    release_approved: bool


class ArchiveRef(gate.StrictModel):
    path: Literal[".opencommerce/ci-evidence/source-tree.tar"]
    sha256: gate.Digest
    size: Annotated[int, Field(gt=0, le=MAX_ARCHIVE_BYTES)]


def no_approval(value: dict[str, Any], flags: tuple[str, ...] = FLAGS) -> None:
    gate.require(all(value.get(flag) is False for flag in flags), "approval_not_allowed")


def flat_json(reader: gate.BundleReader, directory: str) -> set[str]:
    """Enumerate only immediate JSON inputs, never open leftover image archives."""
    fd = reader.directory(directory)
    try:
        found = set()
        with os.scandir(fd) as listing:
            for count, item in enumerate(listing, 1):
                gate.require(count <= gate.MAX_FILES, "file_count_budget")
                if item.name.endswith(".json"):
                    found.add(gate.relative_path(directory + "/" + item.name))
        return found
    finally:
        os.close(fd)


@contextmanager
def new_file(reader: gate.BundleReader, path: str) -> Iterator[BinaryIO]:
    fd = os.dup(reader.fd)
    try:
        parts = gate.relative_path(path).split("/")
        for part in parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        with os.fdopen(leaf, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            yield stream
            stream.flush()
            info = os.fstat(stream.fileno())
            gate.require(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600,
                "output_type_or_permissions",
            )
            reader.identities[path] = reader.identity(info)
    finally:
        os.close(fd)


def exact_tree(reader: gate.BundleReader, paths: set[str]) -> None:
    directories = {"."}
    for path in paths:
        directories.update(str(parent) for parent in PurePosixPath(path).parents)
    # Preserve canonical .opencommerce paths relative to the upload root.
    expected = (paths, directories)
    gate.require(reader.source_tree_paths(UPLOAD) == expected, "upload_membership")
    reader.source_memberships[UPLOAD] = expected


def prepare_images(root: Path) -> dict[str, Any]:
    reader = gate.BundleReader(root)
    try:
        paths = flat_json(reader, collector.IMAGE_PREFIX)
        gate.require(bool(paths), "empty_image_inputs")
        refs = [collector.reference(reader, path) for path in sorted(paths)]
        parent = reader.directory(".opencommerce")
        try:
            os.mkdir("release-upload", mode=0o700, dir_fd=parent)
        finally:
            os.close(parent)
        for ref in refs:
            with new_file(reader, UPLOAD + "/" + ref.path) as stream:
                stream.write(reader.bound(ref))
            reader.bound(ref.model_copy(update={"path": UPLOAD + "/" + ref.path}))
        exact_tree(reader, paths)
        gate.require(flat_json(reader, collector.IMAGE_PREFIX) == paths, "image_membership_changed")
        reader.recheck()
        manifest = ImageUpload(schema_version=1, files=refs, **dict.fromkeys(FLAGS, False))
        collector.write_new(root, MANIFEST, manifest.model_dump(mode="json"))
        reader.recheck()
        return {"images_prepared": len(refs), **dict.fromkeys(FLAGS, False)}
    finally:
        reader.close()


def screened_images(reader: gate.BundleReader) -> dict[str, gate.FileRef]:
    prepared = ImageUpload.model_validate(reader.document(collector.reference(reader, MANIFEST)))
    no_approval(prepared.model_dump())
    refs = {ref.path: ref for ref in prepared.files}
    gate.require(
        len(refs) == len(prepared.files)
        and all(
            str(PurePosixPath(path).parent) == collector.IMAGE_PREFIX and path.endswith(".json")
            for path in refs
        ),
        "image_manifest_paths",
    )
    directory = UPLOAD + "/" + collector.IMAGE_PREFIX
    expected = ({PurePosixPath(path).name for path in refs}, {"."})
    gate.require(reader.source_tree_paths(directory) == expected, "image_upload_membership")
    reader.source_memberships[directory] = expected
    for ref in prepared.files:
        staged_path = UPLOAD + "/" + ref.path
        reader.bound(ref.model_copy(update={"path": staged_path}))
        gate.require(reader.read(staged_path)[1] == 0o600, "staged_permissions")
    return refs


def verify_images(root: Path) -> dict[str, Any]:
    """Read-only image-subtree guard, independent of full collection success.

    The caller must also require the earlier Gitleaks step to have succeeded.
    This checks preserved bytes, not privacy or acquisition completeness itself.
    """
    reader = gate.BundleReader(root)
    try:
        refs = screened_images(reader)
        reader.recheck()
        return {"images_verified": len(refs), **dict.fromkeys(FLAGS, False)}
    finally:
        reader.close()


def image_bindings(
    reader: gate.BundleReader, result: dict[str, Any], prepared: dict[str, gate.FileRef]
) -> None:
    inventory_ref = gate.FileRef.model_validate(result["image_inventory"])
    gate.require(inventory_ref.path == collector.IMAGE_PREFIX + "/inventory.json", "inventory_path")
    gate.require(prepared.get(inventory_ref.path) == inventory_ref, "image_inventory_binding")
    inventory = gate.Inventory.model_validate(
        reader.document(
            inventory_ref.model_copy(update={"path": UPLOAD + "/" + inventory_ref.path})
        )
    )
    entries = gate.unique_services(inventory.images)
    artifacts = gate.unique_services(
        [gate.ImageArtifacts.model_validate(item) for item in result["image_artifacts"]]
    )
    used = {inventory_ref.path}
    for service, item in entries.items():
        expected = {"scan": (item.scan, item.scan_sha256), "sbom": (item.sbom, item.sbom_sha256)}
        for name in ("manifest", "config", "inspection"):
            value = getattr(item.identity_inputs, name)
            expected[name] = (value.file, value.sha256)
        for name, (filename, checksum) in expected.items():
            ref = getattr(artifacts[service], name)
            gate.require(
                ref.path == collector.IMAGE_PREFIX + "/" + filename
                and ref.sha256 == checksum
                and prepared.get(ref.path) == ref,
                "image_artifact_binding",
            )
            used.add(ref.path)
    gate.require(used == set(prepared), "image_artifact_membership")


def copy_archive(reader: gate.BundleReader, ref: ArchiveRef) -> None:
    parent = reader.directory(collector.OUTPUT)
    try:
        fd = os.open("source-tree.tar", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as source_stream:
            before = os.fstat(source_stream.fileno())
            gate.require(
                stat.S_ISREG(before.st_mode)
                and before.st_nlink == 1
                and before.st_size == ref.size,
                "archive_type_or_size",
            )
            checksum = hashlib.sha256()
            remaining = ref.size
            target = UPLOAD + "/" + ref.path
            with new_file(reader, target) as output:
                while remaining:
                    chunk = source_stream.read(min(1024 * 1024, remaining))
                    gate.require(bool(chunk), "archive_truncated")
                    checksum.update(chunk)
                    output.write(chunk)
                    remaining -= len(chunk)
                gate.require(
                    not source_stream.read(1) and checksum.hexdigest() == ref.sha256,
                    "archive_binding",
                )
                output.flush()
                reader.identities[target] = reader.identity(os.fstat(output.fileno()))
            identity = reader.identity(before)
            gate.require(
                identity
                == reader.identity(os.fstat(source_stream.fileno()))
                == reader.identity(
                    os.stat("source-tree.tar", dir_fd=parent, follow_symlinks=False)
                ),
                "archive_changed",
            )
            reader.identities[ref.path] = identity
    finally:
        os.close(parent)


def finalize_upload(root: Path) -> dict[str, Any]:
    reader = gate.BundleReader(root)
    try:
        # Only these CI records are part of the current fixed collection workflow.
        gate.require(flat_json(reader, collector.OUTPUT) == CI_FILES, "ci_membership")
        refs = {path: collector.reference(reader, path) for path in sorted(CI_FILES)}
        result = reader.document(refs[collector.RESULT])
        gate.require(
            type(result["schema_version"]) is int
            and result["schema_version"] == 1
            and result["complete"] is True,
            "collection_incomplete",
        )
        no_approval(result)
        gate.require(
            gate.FileRef.model_validate(result["source_receipt"]) == refs[collector.SOURCE_RESULT],
            "source_receipt_binding",
        )
        receipt = collector.SourceReceipt.model_validate(
            reader.document(refs[collector.SOURCE_RESULT])
        )
        no_approval(receipt.model_dump())
        gate.require(
            re.fullmatch(r"[0-9a-f]{40}", receipt.commit_sha) is not None
            and result["commit_sha"] == receipt.commit_sha
            and result["source_tree_sha256"] == receipt.source_tree_sha256
            and result["source"] == receipt.result
            and receipt.result.get("complete") is True,
            "collection_source_binding",
        )
        no_approval(
            receipt.result, ("security_approved", "release_approved", "rationale_truth_verified")
        )
        gate.require(
            receipt.collection == refs[collector.SOURCE_MANIFEST], "source_manifest_binding"
        )
        manifest = source.CollectionManifest.model_validate(reader.document(receipt.collection))
        gate.require(
            manifest.source.directory == collector.SOURCE_PREFIX + "/source"
            and manifest.source.manifest.path == manifest.source.directory + "/SOURCE_SNAPSHOT.json"
            and manifest.source.source_tree_sha256 == receipt.source_tree_sha256
            and manifest.inventory.path == collector.SOURCE_PREFIX + "/inventory.json",
            "source_paths",
        )
        source_refs = [manifest.inventory, *manifest.files]
        gate.require(
            len(manifest.files) == len(source.FILES)
            and {ref.path for ref in manifest.files}
            == {collector.SOURCE_PREFIX + "/" + name for name in source.FILES},
            "source_membership",
        )
        for ref in source_refs:
            reader.bound(ref)
            refs[ref.path] = ref
        snapshot = manifest.source.manifest.model_copy(update={"path": "SOURCE_SNAPSHOT.json"})
        reader.bound(snapshot)
        refs[snapshot.path] = snapshot
        for path in CHECKOUTS:
            checkout = reader.document(refs[path])
            gate.require(
                checkout.get("valid") is True
                and checkout["commit_sha"] == receipt.commit_sha
                and checkout["source_tree_sha256"] == receipt.source_tree_sha256
                and checkout["snapshot"] == snapshot.model_dump(),
                "checkout_binding",
            )
        archive = ArchiveRef.model_validate(receipt.archive)
        gate.require(result["source_archive"] == archive.model_dump(), "archive_receipt_binding")

        image_refs = screened_images(reader)
        exact_tree(reader, set(image_refs))
        image_bindings(reader, result, image_refs)

        provenance = reader.document(refs[PROVENANCE])
        gate.require(
            provenance.get("commit_matches") is True
            and provenance["commit_sha"] == provenance["expected_commit_sha"] == receipt.commit_sha
            and provenance["commands_source"]
            == ".github/workflows/collect-release-evidence.yml at commit_sha"
            and provenance["run_attempt"] == "1"
            and provenance["stage_outcomes"] == dict.fromkeys(STAGES, "success"),
            "provenance_context",
        )
        recorded = {gate.relative_path(row["path"]): row for row in provenance["files"]}
        gate.require(len(recorded) == len(provenance["files"]), "provenance_duplicates")
        provenance_refs: list[gate.FileRef | ArchiveRef] = [
            *refs.values(),
            *image_refs.values(),
            archive,
        ]
        for bound_ref in provenance_refs:
            if bound_ref.path not in {PROVENANCE, snapshot.path}:
                row = recorded.get(bound_ref.path)
                gate.require(
                    row
                    == {"path": bound_ref.path, "sha256": bound_ref.sha256, "bytes": bound_ref.size}
                    and type(row["bytes"]) is int,
                    "provenance_binding",
                )
        collector.validate_archive(root, archive.model_dump(), manifest.source)
        reader.recheck()
        for ref in refs.values():
            with new_file(reader, UPLOAD + "/" + ref.path) as stream:
                stream.write(reader.bound(ref))
            reader.bound(ref.model_copy(update={"path": UPLOAD + "/" + ref.path}))
        copy_archive(reader, archive)
        paths = set(refs) | set(image_refs) | {archive.path}
        exact_tree(reader, paths)
        reader.recheck()
        return {"complete": True, "files_count": len(paths), **dict.fromkeys(FLAGS, False)}
    finally:
        reader.close()


def main() -> int:
    try:
        commands = {
            "prepare-images": prepare_images,
            "verify-images": verify_images,
            "finalize": finalize_upload,
        }
        parser = gate.SafeParser(description=__doc__)
        parser.add_argument("phase", choices=tuple(commands))
        parser.add_argument("--root", type=Path, default=Path.cwd())
        args = parser.parse_args()
        result = commands[args.phase](args.root)
    except (OSError, ValueError, ValidationError, KeyError, TypeError, AttributeError):
        print(
            json.dumps(
                {"complete": False, "error": "upload_staging_failed", **dict.fromkeys(FLAGS, False)}
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
