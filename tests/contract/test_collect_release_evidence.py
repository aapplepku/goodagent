"""Synthetic finalization: checkout is stubbed; scan gates and packing run for real.

Mutation hooks wrap real operations without replacing their validation results.
No scanner, Git command/history, network, Docker, or private evidence is used.
"""

from __future__ import annotations

import copy
import json
import stat
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from scripts import check_release_assessments as image_gate
from scripts import collect_release_evidence as collector
from scripts.check_release_assessments import SERVICES, GateError, digest
from scripts.check_source_assessments import CollectionManifest
from scripts.release_evidence_archive import pack_bundle

from .test_release_assessment_gate import NOW as IMAGE_NOW
from .test_release_assessment_gate import Bundle as ImageBundle
from .test_source_assessments import END as SOURCE_END
from .test_source_assessments import NOW as SOURCE_NOW
from .test_source_assessments import Bundle as SourceBundle

COMMIT = "c" * 40
REJECTED = (ValueError, ValidationError, OSError, KeyError, TypeError, AttributeError)


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


@dataclass
class Acquisition:
    root: Path
    source: SourceBundle
    images: ImageBundle
    now: datetime
    checkout_binding: dict[str, Any]
    checkout_calls: int = 0
    on_checkout: Callable[[int], None] | None = None

    def verify_checkout(
        self, root: Path, commit: str, *, expected_root: str | None = None
    ) -> dict[str, Any]:
        assert root == self.root and commit == COMMIT
        history = self.checkout_binding.get("history")
        assert expected_root == (history["root_commit"] if history else None)
        self.checkout_calls += 1
        if self.on_checkout is not None:
            self.on_checkout(self.checkout_calls)
        return copy.deepcopy(self.checkout_binding)

    def write(self, path: str, value: Any) -> None:
        (self.root / path).write_bytes(value if isinstance(value, bytes) else encoded(value))

    def read(self, path: str) -> Any:
        return json.loads((self.root / path).read_bytes())

    def source_inventory(self) -> None:
        self.write(collector.SOURCE_PREFIX + "/inventory.json", self.source.inventory)

    def source_report(self, name: str, value: Any) -> None:
        raw = value if isinstance(value, bytes) else encoded(value)
        self.write(collector.SOURCE_PREFIX + "/" + name, raw)
        row = next(row for row in self.source.inventory["reports"] if row["report"] == name)
        row["sha256"] = digest(raw)
        self.source_inventory()

    def image_inventory(self) -> None:
        self.write(collector.IMAGE_PREFIX + "/inventory.json", self.images.inventory)

    def image_report(self, service: str) -> None:
        raw = encoded(self.images.scans[service])
        item = next(item for item in self.images.inventory["images"] if item["service"] == service)
        self.write(collector.IMAGE_PREFIX + "/" + item["scan"], raw)
        item["scan_sha256"] = digest(raw)
        self.image_inventory()

    def collect_source(self, scanner_exit: int = 1) -> dict[str, Any]:
        return collector.source_collection(self.root, COMMIT, scanner_exit, self.now)

    def collect_images(self) -> dict[str, Any]:
        return collector.image_collection(self.root, COMMIT, self.now)

    def assert_no_source_archive(self) -> None:
        assert not (self.root / collector.SOURCE_ARCHIVE).exists()
        assert not (self.root / collector.SOURCE_RESULT).exists()
        assert not (self.root / collector.RESULT).exists()


def acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, findings: bool = True
) -> Acquisition:
    root = tmp_path.resolve() / "checkout"
    images = ImageBundle(root, high=findings)
    source = SourceBundle(root, python=findings, node=findings)
    snapshot = (root / "frozen/SOURCE_SNAPSHOT.json").read_bytes()
    (root / "SOURCE_SNAPSHOT.json").write_bytes(snapshot)
    for old, new in (("audit", collector.SOURCE_PREFIX), ("scans", collector.IMAGE_PREFIX)):
        destination = root / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root / old).rename(destination)
    state = Acquisition(
        root,
        source,
        images,
        max(IMAGE_NOW, SOURCE_NOW),
        {
            "source_tree_sha256": source.source_sha,
            "commit_sha": COMMIT,
            "snapshot": {
                "path": "SOURCE_SNAPSHOT.json",
                "sha256": digest(snapshot),
                "size": len(snapshot),
            },
            "files_count": len(source.source_files) - 1,
        },
    )
    monkeypatch.setattr(collector, "verify_checkout", state.verify_checkout)
    assert not (root / ".git").exists()
    return state


@pytest.fixture
def candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Acquisition:
    return acquisition(tmp_path, monkeypatch)


@pytest.mark.parametrize("findings", [True, False])
def test_real_source_and_image_collection_never_invent_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, findings: bool
) -> None:
    candidate = acquisition(tmp_path, monkeypatch, findings=findings)
    retained = {
        p.relative_to(candidate.root): p.read_bytes()
        for directory in (collector.SOURCE_PREFIX, collector.IMAGE_PREFIX)
        for p in (candidate.root / directory).rglob("*")
        if p.is_file()
    }
    source_receipt = candidate.collect_source(int(findings))
    source_receipt_raw = (candidate.root / collector.SOURCE_RESULT).read_bytes()
    result = candidate.collect_images()
    assert source_receipt == candidate.read(collector.SOURCE_RESULT)
    assert result == candidate.read(collector.RESULT)
    assert result["source_receipt"] == {
        "path": collector.SOURCE_RESULT,
        "sha256": digest(source_receipt_raw),
        "size": len(source_receipt_raw),
    }
    for receipt in (source_receipt, result):
        assert receipt["complete"] is True
        assert receipt["qualification_passed"] is False
        assert receipt["security_approved"] is receipt["release_approved"] is False
        assert receipt["commit_sha"] == COMMIT
        assert receipt["source_tree_sha256"] == candidate.source.source_sha
        assert "assessments" not in receipt and "decisions" not in receipt
    raw_source = source_receipt["result"]
    assert raw_source == result["source"]
    assert raw_source["complete"] is True and raw_source["raw_passed"] is (not findings)
    assert raw_source["assessments_required"] == (2 if findings else 0)
    assert raw_source["rawcounts"]["records_by_raw_severity"] == (
        {"UNKNOWN": 1, "high": 1} if findings else {}
    )
    assert raw_source["security_approved"] is raw_source["release_approved"] is False
    assert result["raw_image_severity_counts"] == ({"HIGH": 1} if findings else {})
    assert result["image_high_critical_assessments_required"] == int(findings)
    assert {item["service"] for item in result["image_artifacts"]} == SERVICES
    manifest = candidate.read(collector.SOURCE_MANIFEST)
    CollectionManifest.model_validate(manifest)
    assert set(manifest) == {"schema_version", "source", "inventory", "files"}
    assert len(manifest["files"]) == 21
    archive = candidate.root / collector.SOURCE_ARCHIVE
    assert digest(archive.read_bytes()) == source_receipt["archive"]["sha256"]
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    with tarfile.open(archive, mode="r:") as transport:
        members = transport.getmembers()
        assert members[0].name == "."
        assert {member.name for member in members if member.isfile()} == set(
            candidate.source.source_files
        )
        for member in members:
            if member.isfile():
                stream = transport.extractfile(member)
                assert stream is not None
                with stream:
                    assert stream.read() == candidate.source.source_files[member.name]
    for path, raw in retained.items():
        assert (candidate.root / path).read_bytes() == raw


def test_followup_collection_binds_the_same_explicit_history_across_both_phases(
    candidate: Acquisition,
) -> None:
    root_commit = "a" * 40
    history = {
        "root_commit": root_commit,
        "commits": [root_commit, COMMIT],
        "policy": "pinned-linear-export-v1",
    }
    candidate.checkout_binding["history"] = history
    source_receipt = collector.source_collection(
        candidate.root, COMMIT, 1, candidate.now, export_root=root_commit
    )
    result = collector.image_collection(
        candidate.root, COMMIT, candidate.now, export_root=root_commit
    )
    assert source_receipt["history"] == result["history"] == history
    assert result["qualification_passed"] is result["security_approved"] is False


@pytest.mark.parametrize("change", ["missing", "root", "members", "policy"])
def test_image_collection_rejects_changed_or_missing_source_history(
    candidate: Acquisition, change: str
) -> None:
    root_commit = "a" * 40
    history = {
        "root_commit": root_commit,
        "commits": [root_commit, COMMIT],
        "policy": "pinned-linear-export-v1",
    }
    candidate.checkout_binding["history"] = history
    collector.source_collection(candidate.root, COMMIT, 1, candidate.now, export_root=root_commit)
    receipt = candidate.read(collector.SOURCE_RESULT)
    if change == "missing":
        receipt.pop("history")
    elif change == "root":
        receipt["history"]["root_commit"] = "b" * 40
    elif change == "members":
        receipt["history"]["commits"].pop()
    else:
        receipt["history"]["policy"] = "unreviewed"
    candidate.write(collector.SOURCE_RESULT, receipt)
    with pytest.raises(GateError, match="source_receipt_identity"):
        collector.image_collection(candidate.root, COMMIT, candidate.now, export_root=root_commit)
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize("findings,scanner_exit", [(True, 0), (True, 2), (True, -1), (False, 1)])
def test_raw_scanner_exit_must_match_real_collection_before_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, findings: bool, scanner_exit: int
) -> None:
    candidate = acquisition(tmp_path, monkeypatch, findings=findings)
    with pytest.raises(GateError, match="scanner_exit_mismatch"):
        candidate.collect_source(scanner_exit)
    candidate.assert_no_source_archive()


@pytest.mark.parametrize(
    "problem",
    [
        "incomplete",
        "coverage",
        "version",
        "malformed",
        "secret-source",
        "secret-history",
        "secret-log",
    ],
)
def test_incomplete_or_secret_collection_never_creates_source_archive(
    candidate: Acquisition, problem: str
) -> None:
    if problem == "incomplete":
        candidate.source.inventory["complete"] = False
    elif problem == "coverage":
        candidate.source.inventory["reports"][0]["coverage_verified"] = False
    elif problem == "version":
        candidate.source.inventory["tool_version_evidence"]["pnpm"]["verified"] = False
    elif problem == "malformed":
        candidate.source_report("node-audit.json", {})
    elif problem.startswith("secret-") and problem != "secret-log":
        name = "gitleaks-" + problem.removeprefix("secret-") + ".json"
        candidate.source_report(name, [{"RuleID": "synthetic", "Secret": "fixture-only"}])
    else:
        name = "gitleaks-history.json"
        raw = b"synthetic incomplete history scan\n"
        candidate.write(collector.SOURCE_PREFIX + "/" + name + ".log", raw)
        row = next(row for row in candidate.source.inventory["reports"] if row["report"] == name)
        row["log_sha256"] = digest(raw)
    candidate.source_inventory()
    with pytest.raises(REJECTED):
        candidate.collect_source()
    candidate.assert_no_source_archive()


@pytest.mark.parametrize("change", ["bytes", "mode", "snapshot", "empty-directory", "symlink"])
def test_tampered_captured_source_blocks_archive(candidate: Acquisition, change: str) -> None:
    directory = candidate.root / collector.SOURCE_PREFIX / "source"
    path = directory / "uv.lock"
    if change == "bytes":
        path.write_bytes(b"changed source")
    elif change == "mode":
        path.chmod(0o755)
    elif change == "snapshot":
        with (directory / "SOURCE_SNAPSHOT.json").open("ab") as stream:
            stream.write(b" ")
    elif change == "empty-directory":
        (directory / "unmanifested-empty").mkdir()
    else:
        path.unlink()
        path.symlink_to(candidate.root / "frozen/uv.lock")
    with pytest.raises(REJECTED):
        candidate.collect_source()
    candidate.assert_no_source_archive()


@pytest.mark.parametrize("call", [2, 3])
def test_checkout_identity_changes_are_not_receipted(candidate: Acquisition, call: int) -> None:
    def change(current: int) -> None:
        if current == call:
            candidate.checkout_binding["source_tree_sha256"] = "f" * 64

    candidate.on_checkout = change
    with pytest.raises(GateError, match="checkout_changed"):
        candidate.collect_source()
    assert not (candidate.root / collector.SOURCE_RESULT).exists()
    assert (candidate.root / collector.SOURCE_ARCHIVE).exists() is (call == 3)


def test_images_require_completed_source_phase(candidate: Acquisition) -> None:
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize(
    "change", ["commit", "source", "result", "manifest-path", "manifest-hash", "archive"]
)
def test_changed_source_receipt_bindings_block_image_finalization(
    candidate: Acquisition, change: str
) -> None:
    receipt = candidate.collect_source()
    if change == "commit":
        receipt["commit_sha"] = "d" * 40
    elif change == "source":
        receipt["source_tree_sha256"] = "f" * 64
    elif change == "result":
        receipt["result"]["assessments_required"] = 0
    elif change == "manifest-path":
        receipt["collection"]["path"] = "unrelated.json"
    elif change == "manifest-hash":
        receipt["collection"]["sha256"] = "f" * 64
    else:
        receipt["archive"]["sha256"] = "f" * 64
    candidate.write(collector.SOURCE_RESULT, receipt)
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("complete", False),
        ("scanner_exit", 2),
        ("qualification_passed", True),
        ("security_approved", True),
        ("release_approved", True),
        ("recorded_at", (SOURCE_END - timedelta(seconds=1)).isoformat()),
        ("recorded_at", (max(IMAGE_NOW, SOURCE_NOW) + timedelta(seconds=1)).isoformat()),
    ],
)
def test_inconsistent_source_receipt_status_and_chronology_are_rejected(
    candidate: Acquisition, field: str, value: Any
) -> None:
    receipt = candidate.collect_source()
    receipt[field] = value
    candidate.write(collector.SOURCE_RESULT, receipt)
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize(
    "path",
    [
        collector.SOURCE_PREFIX + "/source/uv.lock",
        collector.SOURCE_PREFIX + "/inventory.json",
        collector.SOURCE_PREFIX + "/python-audit.json",
        collector.SOURCE_MANIFEST,
        collector.SOURCE_ARCHIVE,
    ],
)
def test_stale_source_receipt_cannot_reuse_changed_evidence(
    candidate: Acquisition, path: str
) -> None:
    candidate.collect_source()
    with (candidate.root / path).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "incomplete", "counts"])
def test_image_inventory_requires_all_exact_services_and_raw_counts(
    candidate: Acquisition, change: str
) -> None:
    candidate.collect_source()
    items = candidate.images.inventory["images"]
    if change == "missing":
        items.pop()
    elif change == "extra":
        items.append({**items[0], "service": "extra"})
    elif change == "duplicate":
        items[-1] = copy.deepcopy(items[0])
    elif change == "incomplete":
        items[0]["complete"] = False
    else:
        items[0]["counts"] = {"HIGH": 0}
    candidate.image_inventory()
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize("change", ["missing-results", "config", "future-date", "raw-hash"])
def test_image_report_coverage_identity_dates_and_bytes_are_rechecked(
    candidate: Acquisition, change: str
) -> None:
    candidate.collect_source()
    report = candidate.images.scans["api"]
    if change == "missing-results":
        del report["Results"]
    elif change == "config":
        report["Metadata"]["ImageConfig"]["architecture"] = "amd64"
    elif change == "future-date":
        report["CreatedAt"] = (candidate.now + timedelta(seconds=1)).isoformat()
    else:
        path = candidate.root / collector.IMAGE_PREFIX / "api.scan.json"
        with path.open("ab") as stream:
            stream.write(b" ")
    if change != "raw-hash":
        candidate.image_report("api")
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert not (candidate.root / collector.RESULT).exists()


@pytest.mark.parametrize("phase", ["source", "images"])
def test_last_checkout_revalidation_cannot_hide_changed_captured_source(
    candidate: Acquisition, phase: str
) -> None:
    if phase == "images":
        candidate.collect_source()
    candidate.checkout_calls = 0

    def change(call: int) -> None:
        if call == (3 if phase == "source" else 2):
            path = candidate.root / collector.SOURCE_PREFIX / "source/uv.lock"
            path.write_bytes(b"changed captured source")

    candidate.on_checkout = change
    with pytest.raises(REJECTED):
        candidate.collect_source() if phase == "source" else candidate.collect_images()
    result = collector.SOURCE_RESULT if phase == "source" else collector.RESULT
    assert not (candidate.root / result).exists()


@pytest.mark.parametrize(
    "path", [collector.SOURCE_MANIFEST, collector.SOURCE_ARCHIVE, collector.SOURCE_RESULT]
)
def test_existing_source_outputs_are_preserved_not_overwritten(
    candidate: Acquisition, path: str
) -> None:
    output = candidate.root / path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"retained prior attempt")
    with pytest.raises(REJECTED):
        candidate.collect_source()
    assert output.read_bytes() == b"retained prior attempt"


def test_existing_final_receipt_is_preserved_not_overwritten(candidate: Acquisition) -> None:
    candidate.collect_source()
    output = candidate.root / collector.RESULT
    output.write_bytes(b"retained prior final receipt")
    with pytest.raises(REJECTED):
        candidate.collect_images()
    assert output.read_bytes() == b"retained prior final receipt"


def test_rehashed_wrong_source_archive_cannot_replace_bound_snapshot(
    candidate: Acquisition, tmp_path: Path
) -> None:
    receipt = candidate.collect_source()
    wrong_source = tmp_path / "wrong-source"
    for name, raw in candidate.source.source_files.items():
        path = wrong_source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
    (wrong_source / "uv.lock").write_bytes(b"wrong synthetic source\n")
    replacement = tmp_path / "replacement.tar"
    checksum = pack_bundle(wrong_source, replacement)
    raw_archive = replacement.read_bytes()
    assert digest(raw_archive) == checksum
    candidate.write(collector.SOURCE_ARCHIVE, raw_archive)
    receipt["archive"] = {
        "path": collector.SOURCE_ARCHIVE,
        "sha256": checksum,
        "size": len(raw_archive),
    }
    candidate.write(collector.SOURCE_RESULT, receipt)
    assert collector.archive_digest(candidate.root) == receipt["archive"]
    captured = candidate.root / collector.SOURCE_PREFIX / "source/uv.lock"
    assert captured.read_bytes() == candidate.source.source_files["uv.lock"]

    with pytest.raises(REJECTED):
        candidate.collect_images()

    assert not (candidate.root / collector.RESULT).exists()
    assert (candidate.root / collector.SOURCE_ARCHIVE).read_bytes() == raw_archive


def test_source_changed_during_pack_then_restored_does_not_receipt_wrong_archive(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch
) -> None:
    packed = False
    wrong = b"source changed only while packing\n"

    def changed_pack(root: Path, output: Path) -> str:
        nonlocal packed
        path = root / "uv.lock"
        original = path.read_bytes()
        path.write_bytes(wrong)
        try:
            checksum = pack_bundle(root, output)
            packed = True
            return checksum
        finally:
            path.write_bytes(original)

    monkeypatch.setattr(collector, "pack_bundle", changed_pack)
    with pytest.raises(REJECTED):
        candidate.collect_source()

    assert packed
    captured = candidate.root / collector.SOURCE_PREFIX / "source/uv.lock"
    assert captured.read_bytes() == candidate.source.source_files["uv.lock"]
    assert not (candidate.root / collector.SOURCE_RESULT).exists()
    assert not (candidate.root / collector.RESULT).exists()
    with tarfile.open(candidate.root / collector.SOURCE_ARCHIVE, mode="r:") as transport:
        stream = transport.extractfile("uv.lock")
        assert stream is not None
        with stream:
            assert stream.read() == wrong


def test_source_archive_is_rechecked_after_real_image_validation(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = candidate.collect_source()
    archive = candidate.root / collector.SOURCE_ARCHIVE
    original_size = archive.stat().st_size
    with tarfile.open(archive, mode="r:") as transport:
        offset = transport.getmember("uv.lock").offset_data
    original_validate = image_gate.validate_image
    mutated = False

    def changed_archive(
        reader: image_gate.BundleReader,
        inventory_path: str,
        item: image_gate.InventoryImage,
        artifacts: image_gate.ImageArtifacts,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal mutated
        result = original_validate(reader, inventory_path, item, artifacts)
        if not mutated:
            with archive.open("r+b") as stream:
                stream.seek(offset)
                original = stream.read(1)
                stream.seek(offset)
                stream.write(bytes([original[0] ^ 1]))
            mutated = True
        return result

    monkeypatch.setattr(image_gate, "validate_image", changed_archive)
    with pytest.raises(REJECTED):
        candidate.collect_images()

    assert mutated
    assert archive.stat().st_size == original_size
    assert digest(archive.read_bytes()) != receipt["archive"]["sha256"]
    assert not (candidate.root / collector.RESULT).exists()
    assert candidate.read(collector.SOURCE_RESULT) == receipt
