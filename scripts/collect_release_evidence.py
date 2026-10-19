"""Finalize complete scan acquisition; never approve findings or publish artifacts.

Fixed workflow steps run the scanners/build separately. This module validates their
retained outputs, preserves raw failure/findings status, and packs source only after
complete secret checks. A green acquisition step is not release qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from scripts import check_release_assessments as images
from scripts import check_source_assessments as source
from scripts.check_frozen_checkout import verify_checkout
from scripts.release_evidence_archive import MAX_ARCHIVE_BYTES, pack_bundle, unpack_bundle

SOURCE_PREFIX = ".opencommerce/source-scans"
IMAGE_PREFIX = ".opencommerce/security-scans/final"
OUTPUT = ".opencommerce/ci-evidence"
SOURCE_MANIFEST = OUTPUT + "/source-collection.json"
SOURCE_RESULT = OUTPUT + "/source-result.json"
SOURCE_ARCHIVE = OUTPUT + "/source-tree.tar"
RESULT = OUTPUT + "/collection.json"


class SourceReceipt(images.StrictModel):
    schema_version: Literal[1]
    complete: images.Complete
    qualification_passed: bool
    security_approved: bool
    release_approved: bool
    commit_sha: str
    source_tree_sha256: images.Digest
    scanner_exit: int
    collection: images.FileRef
    archive: dict[str, Any]
    result: dict[str, Any]
    recorded_at: images.Timestamp
    history: dict[str, Any] | None = None


def validate_exit(scanner_exit: int, result: dict[str, Any]) -> None:
    images.require(
        type(scanner_exit) is int
        and (
            (scanner_exit == 0 and result["raw_passed"] is True)
            or (
                scanner_exit == 1
                and result["raw_passed"] is False
                and result["assessments_required"] > 0
            )
        ),
        "scanner_exit_mismatch",
    )


def validate_archive(root: Path, archive: dict[str, Any], binding: images.SourceBinding) -> None:
    images.require(archive_digest(root) == archive, "source_archive_changed")
    with tempfile.TemporaryDirectory(prefix="release-source-verify-") as temporary:
        parent = Path(temporary).resolve()
        unpack_bundle(root / SOURCE_ARCHIVE, parent / "source", archive["sha256"])
        reader = images.BundleReader(parent)
        try:
            translated = images.SourceBinding(
                directory="source",
                manifest=binding.manifest.model_copy(
                    update={"path": "source/SOURCE_SNAPSHOT.json"}
                ),
                source_tree_sha256=binding.source_tree_sha256,
            )
            images.validate_source(reader, translated, binding.source_tree_sha256)
            reader.recheck()
        finally:
            reader.close()
    images.require(archive_digest(root) == archive, "source_archive_changed")


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def reference(reader: images.BundleReader, path: str) -> images.FileRef:
    raw, _ = reader.read(path)
    ref = images.FileRef(path=path, sha256=images.digest(raw), size=len(raw))
    reader.bound(ref)
    return ref


def write_new(root: Path, path: str, value: Any) -> images.FileRef:
    path = images.relative_path(path)
    reader = images.BundleReader(root)
    parent = -1
    try:
        parent = os.dup(reader.fd)
        parts = path.split("/")
        for part in parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        raw = encoded(value)
        fd = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        return images.FileRef(path=path, sha256=images.digest(raw), size=len(raw))
    finally:
        if parent >= 0:
            os.close(parent)
        reader.close()


def archive_digest(root: Path) -> dict[str, Any]:
    reader = images.BundleReader(root)
    parent = -1
    try:
        parent = reader.directory(OUTPUT)
        fd = os.open("source-tree.tar", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            images.require(
                stat.S_ISREG(before.st_mode)
                and before.st_nlink == 1
                and 0 < before.st_size <= MAX_ARCHIVE_BYTES,
                "source_archive_type_or_size",
            )
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            images.require(
                reader.identity(before)
                == reader.identity(os.fstat(stream.fileno()))
                == reader.identity(
                    os.stat("source-tree.tar", dir_fd=parent, follow_symlinks=False)
                ),
                "source_archive_changed",
            )
        return {"path": SOURCE_ARCHIVE, "sha256": checksum, "size": before.st_size}
    finally:
        if parent >= 0:
            os.close(parent)
        reader.close()


def checkout_binding(root: Path, commit: str, export_root: str | None) -> dict[str, Any]:
    if export_root is None:
        return verify_checkout(root, commit)
    return verify_checkout(root, commit, expected_root=export_root)


def source_collection(
    root: Path, commit: str, scanner_exit: int, now: datetime, *, export_root: str | None = None
) -> dict[str, Any]:
    before = checkout_binding(root, commit, export_root)
    reader = images.BundleReader(root)
    try:
        inventory = reference(reader, SOURCE_PREFIX + "/inventory.json")
        snapshot = reference(reader, SOURCE_PREFIX + "/source/SOURCE_SNAPSHOT.json")
        images.require(snapshot.sha256 == before["snapshot"]["sha256"], "captured_snapshot_changed")
        manifest = source.CollectionManifest(
            schema_version=1,
            source=images.SourceBinding(
                manifest=snapshot,
                directory=SOURCE_PREFIX + "/source",
                source_tree_sha256=before["source_tree_sha256"],
            ),
            inventory=inventory,
            files=[reference(reader, SOURCE_PREFIX + "/" + name) for name in sorted(source.FILES)],
        )
        ref = write_new(root, SOURCE_MANIFEST, manifest.model_dump(mode="json"))
        reader.recheck()
    finally:
        reader.close()
    result = source.verify_source_collection(
        root, ref.path, ref.sha256, before["source_tree_sha256"], now=now
    )
    validate_exit(scanner_exit, result)
    images.require(checkout_binding(root, commit, export_root) == before, "checkout_changed")
    checksum = pack_bundle(root / SOURCE_PREFIX / "source", root / SOURCE_ARCHIVE)
    archive = archive_digest(root)
    images.require(archive["sha256"] == checksum, "source_archive_changed")
    validate_archive(root, archive, manifest.source)
    images.require(checkout_binding(root, commit, export_root) == before, "checkout_changed")
    final = source.verify_source_collection(
        root, ref.path, ref.sha256, before["source_tree_sha256"], now=now
    )
    images.require(final == result, "collection_changed")
    images.require(archive_digest(root) == archive, "source_archive_changed")
    receipt = {
        "schema_version": 1,
        "complete": True,
        "qualification_passed": False,
        "security_approved": False,
        "release_approved": False,
        "commit_sha": commit,
        "source_tree_sha256": before["source_tree_sha256"],
        "scanner_exit": scanner_exit,
        "collection": ref.model_dump(),
        "archive": archive,
        "result": result,
        "recorded_at": now.isoformat(),
    }
    if "history" in before:
        receipt["history"] = before["history"]
    write_new(root, SOURCE_RESULT, receipt)
    return receipt


def image_collection(
    root: Path, commit: str, now: datetime, *, export_root: str | None = None
) -> dict[str, Any]:
    before = checkout_binding(root, commit, export_root)
    reader = images.BundleReader(root)
    try:
        receipt_ref = reference(reader, SOURCE_RESULT)
        receipt = SourceReceipt.model_validate(reader.document(receipt_ref))
        images.require(
            receipt.commit_sha == commit
            and receipt.source_tree_sha256 == before["source_tree_sha256"]
            and receipt.history == before.get("history"),
            "source_receipt_identity",
        )
        images.require(
            receipt.qualification_passed
            is receipt.security_approved
            is receipt.release_approved
            is False,
            "unexpected_receipt_approval",
        )
        collection_ref = receipt.collection
        images.require(collection_ref.path == SOURCE_MANIFEST, "source_manifest_path")
        manifest = source.CollectionManifest.model_validate(reader.document(collection_ref))
        source_inventory = source.Inventory.model_validate(reader.document(manifest.inventory))
        images.require(
            source_inventory.completed_at <= receipt.recorded_at <= now, "source_receipt_date"
        )
        sources = source.verify_source_collection(
            root, collection_ref.path, collection_ref.sha256, before["source_tree_sha256"], now=now
        )
        images.require(sources == receipt.result, "source_receipt_changed")
        validate_exit(receipt.scanner_exit, sources)
        validate_archive(root, receipt.archive, manifest.source)
        inventory_ref = reference(reader, IMAGE_PREFIX + "/inventory.json")
        inventory = images.Inventory.model_validate(reader.document(inventory_ref))
        snapshot = images.SourceSnapshot.model_validate(
            reader.document(reference(reader, "SOURCE_SNAPSHOT.json"))
        )
        images.require(
            snapshot.created_at <= inventory.started_at <= inventory.completed_at <= now,
            "image_collection_dates",
        )
        entries = images.unique_services(inventory.images)
        counts: Counter[str] = Counter()
        artifacts = []
        for service in sorted(images.SERVICES):
            item = entries[service]
            refs = {
                "scan": reference(reader, IMAGE_PREFIX + "/" + item.scan),
                "sbom": reference(reader, IMAGE_PREFIX + "/" + item.sbom),
                **{
                    key: reference(
                        reader, IMAGE_PREFIX + "/" + getattr(item.identity_inputs, key).file
                    )
                    for key in ("manifest", "config", "inspection")
                },
            }
            artifact = images.ImageArtifacts(service=cast(images.Service, service), **refs)
            report, sbom = images.validate_image(reader, inventory_ref.path, item, artifact)
            images.coverage_validator()(item.model_dump(), report, sbom, today=now.date())
            for timestamp in (report["CreatedAt"], sbom["metadata"]["timestamp"]):
                images.require(
                    inventory.started_at <= images.utc_time(timestamp) <= inventory.completed_at,
                    "image_scan_date",
                )
            for group in report["Results"]:
                counts.update(finding["Severity"] for finding in group.get("Vulnerabilities", []))
            artifacts.append(artifact.model_dump())
        images.require(checkout_binding(root, commit, export_root) == before, "checkout_changed")
        images.require(
            source.verify_source_collection(
                root,
                collection_ref.path,
                collection_ref.sha256,
                before["source_tree_sha256"],
                now=now,
            )
            == sources,
            "collection_changed",
        )
        reader.recheck()
        images.require(archive_digest(root) == receipt.archive, "source_archive_changed")
        result = {
            "schema_version": 1,
            "complete": True,
            "qualification_passed": False,
            "security_approved": False,
            "release_approved": False,
            "commit_sha": commit,
            "source_tree_sha256": before["source_tree_sha256"],
            "source": sources,
            "source_receipt": receipt_ref.model_dump(),
            "source_archive": receipt.archive,
            "image_inventory": inventory_ref.model_dump(),
            "image_artifacts": artifacts,
            "raw_image_severity_counts": dict(sorted(counts.items())),
            "image_high_critical_assessments_required": counts["HIGH"] + counts["CRITICAL"],
            "recorded_at": now.isoformat(),
            "limitations": [
                "Collection completeness only; findings remain unapproved.",
                "No runtime behavior, reachability, human applicability or publication approval.",
                "Source-to-build execution requires the retained trusted workflow and provenance.",
            ],
        }
        if "history" in before:
            result["history"] = before["history"]
        write_new(root, RESULT, result)
        return result
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["source", "images"])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--export-root", help="Separately trusted original export commit pin")
    parser.add_argument("--scanner-exit", type=int)
    args = parser.parse_args()
    try:
        now = datetime.now(UTC)
        if args.phase == "source":
            images.require(args.scanner_exit is not None, "scanner_exit_required")
            result = source_collection(
                Path.cwd(), args.commit, args.scanner_exit, now, export_root=args.export_root
            )
        else:
            images.require(args.scanner_exit is None, "unexpected_scanner_exit")
            result = image_collection(Path.cwd(), args.commit, now, export_root=args.export_root)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, ValidationError, KeyError, TypeError, AttributeError):
        print(
            json.dumps(
                {"complete": False, "qualification_passed": False, "error": "collection_blocked"}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
