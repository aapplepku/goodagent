"""Local synthetic acquisition only: no scanner, Docker, network or private inputs."""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

import pytest
from scripts import check_release_assessments as gate
from scripts import check_source_assessments as source
from scripts import collect_release_evidence as collector
from scripts import stage_release_upload as upload
from scripts.release_evidence_archive import MAX_ARCHIVE_BYTES, pack_bundle

from .test_collect_release_evidence import COMMIT, Acquisition, acquisition

REJECTED = (ValueError, OSError, KeyError, TypeError, AttributeError)


@pytest.fixture
def candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Acquisition:
    return acquisition(tmp_path, monkeypatch)


def provenance(candidate: Acquisition) -> None:
    paths = {path for path in upload.CI_FILES if path != upload.PROVENANCE}
    paths.update(collector.SOURCE_PREFIX + "/" + name for name in source.FILES)
    paths.update({collector.SOURCE_PREFIX + "/inventory.json", collector.SOURCE_ARCHIVE})
    paths.update(ref["path"] for ref in candidate.read(upload.MANIFEST)["files"])
    candidate.write(
        upload.PROVENANCE,
        {
            "schema_version": 1,
            "commit_matches": True,
            "commit_sha": COMMIT,
            "expected_commit_sha": COMMIT,
            "commands_source": ".github/workflows/collect-release-evidence.yml at commit_sha",
            "run_attempt": "1",
            "stage_outcomes": dict.fromkeys(upload.STAGES, "success"),
            "files": [
                {
                    "path": path,
                    "sha256": gate.digest((candidate.root / path).read_bytes()),
                    "bytes": (candidate.root / path).stat().st_size,
                }
                for path in sorted(paths)
            ],
        },
    )


@pytest.fixture
def collected(candidate: Acquisition) -> Acquisition:
    candidate.collect_source()
    for path in upload.CHECKOUTS:
        candidate.write(path, {"valid": True, **candidate.checkout_binding})
    upload.prepare_images(candidate.root)
    candidate.collect_images()
    provenance(candidate)
    return candidate


@pytest.mark.parametrize("changed", [None, "before", "after", "result"])
def test_followup_upload_requires_consistent_checkout_and_receipt_history(
    candidate: Acquisition, changed: str | None
) -> None:
    root_commit = "a" * 40
    candidate.checkout_binding["history"] = {
        "root_commit": root_commit,
        "commits": [root_commit, COMMIT],
        "policy": "pinned-linear-export-v1",
    }
    collector.source_collection(candidate.root, COMMIT, 1, candidate.now, export_root=root_commit)
    for path in upload.CHECKOUTS:
        candidate.write(path, {"valid": True, **candidate.checkout_binding})
    upload.prepare_images(candidate.root)
    collector.image_collection(candidate.root, COMMIT, candidate.now, export_root=root_commit)
    if changed is not None:
        path = (
            collector.RESULT
            if changed == "result"
            else collector.OUTPUT + f"/checkout-{changed}.json"
        )
        document = candidate.read(path)
        document["history"]["root_commit"] = "b" * 40
        candidate.write(path, document)
    provenance(candidate)
    if changed is None:
        assert upload.finalize_upload(candidate.root)["complete"] is True
        result = candidate.read(upload.UPLOAD + "/" + collector.RESULT)
        assert result["history"] == candidate.checkout_binding["history"]
    else:
        with pytest.raises(gate.GateError):
            upload.finalize_upload(candidate.root)


def test_complete_mirror_keeps_screened_images_raw_findings_and_no_approval(
    collected: Acquisition,
) -> None:
    root = collected.root
    staged = root / upload.UPLOAD
    image_paths = [ref["path"] for ref in collected.read(upload.MANIFEST)["files"]]
    original_images = {
        path: ((staged / path).read_bytes(), (staged / path).stat().st_ino) for path in image_paths
    }
    # Originals changed after collection/provenance are never substituted for screened copies.
    (root / image_paths[0]).write_bytes(b"synthetic unscreened replacement")
    (root / collector.IMAGE_PREFIX / "failed-image.tar").write_bytes(b"not uploadable")
    (root / collector.OUTPUT / "build.log").write_bytes(b"not uploadable")
    (root / ".env").write_bytes(b"synthetic-only-not-a-credential")
    result = upload.finalize_upload(root)
    paths = {str(path.relative_to(staged)) for path in staged.rglob("*") if path.is_file()}
    expected = (
        set(image_paths)
        | upload.CI_FILES
        | {
            "SOURCE_SNAPSHOT.json",
            collector.SOURCE_ARCHIVE,
            collector.SOURCE_PREFIX + "/inventory.json",
        }
        | {collector.SOURCE_PREFIX + "/" + name for name in source.FILES}
    )
    assert paths == expected
    assert result == {
        "complete": True,
        "files_count": len(paths),
        **dict.fromkeys(upload.FLAGS, False),
    }
    for path in paths:
        target = staged / path
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert target.stat().st_nlink == 1
        if path in original_images:
            assert (target.read_bytes(), target.stat().st_ino) == original_images[path]
        else:
            assert target.read_bytes() == (root / path).read_bytes()
    for directory in staged.rglob("*"):
        if directory.is_dir():
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    result_json = json.loads((staged / collector.RESULT).read_bytes())
    assert result_json["raw_image_severity_counts"] == {"HIGH": 1}
    assert result_json["source"]["assessments_required"] == 2
    assert result_json["source"]["raw_passed"] is False


def test_prepare_incomplete_inputs_for_privacy_without_claiming_collection(
    candidate: Acquisition,
) -> None:
    candidate.write(collector.IMAGE_PREFIX + "/inventory.json", {"complete": False})
    result = upload.prepare_images(candidate.root)
    assert "complete" not in result
    manifest = candidate.read(upload.MANIFEST)
    assert len(manifest["files"]) == result["images_prepared"] == 41
    for ref in manifest["files"]:
        assert not ref["path"].startswith(upload.UPLOAD)
        assert ref["sha256"] == gate.digest(
            (candidate.root / upload.UPLOAD / ref["path"]).read_bytes()
        )


@pytest.mark.parametrize(
    "problem", ["symlink", "hardlink", "fifo", "directory", "oversize", "linked-parent"]
)
def test_prepare_rejects_unsafe_inputs(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    path = candidate.root / collector.IMAGE_PREFIX / "api.scan.json"
    if problem == "symlink":
        path.unlink()
        path.symlink_to(candidate.root / collector.IMAGE_PREFIX / "web.scan.json")
    elif problem == "hardlink":
        os.link(path, path.with_suffix(".other"))
    elif problem == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif problem == "directory":
        path.unlink()
        path.mkdir()
    elif problem == "oversize":
        monkeypatch.setattr(gate, "MAX_FILE_BYTES", 1)
    else:
        directory = path.parent
        target = directory.with_name("saved")
        directory.rename(target)
        directory.symlink_to(target, target_is_directory=True)
    with pytest.raises(REJECTED):
        upload.prepare_images(candidate.root)
    assert not (candidate.root / upload.MANIFEST).exists()


@pytest.mark.parametrize("phase", ["prepare", "finalize"])
def test_outputs_are_never_overwritten(collected: Acquisition, phase: str) -> None:
    function = upload.prepare_images if phase == "prepare" else upload.finalize_upload
    if phase == "finalize":
        function(collected.root)
    before = {
        str(p): p.read_bytes() for p in (collected.root / upload.UPLOAD).rglob("*") if p.is_file()
    }
    with pytest.raises(REJECTED):
        function(collected.root)
    assert before == {path: Path(path).read_bytes() for path in before}


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "changed",
        "extra-json",
        "extra-secret",
        "extra-directory",
        "symlink",
        "hardlink",
        "permissions",
    ],
)
def test_screened_tree_must_still_be_exact(collected: Acquisition, problem: str) -> None:
    staged = collected.root / upload.UPLOAD
    path = staged / collector.IMAGE_PREFIX / "api.scan.json"
    if problem == "missing":
        path.unlink()
    elif problem == "changed":
        path.write_bytes(b"changed")
    elif problem == "extra-json":
        (path.parent / "extra.json").write_bytes(b"{}")
    elif problem == "extra-secret":
        (staged / ".env").write_bytes(b"synthetic canary")
    elif problem == "extra-directory":
        (staged / "cache").mkdir()
    elif problem == "symlink":
        path.unlink()
        path.symlink_to(collected.root / collector.IMAGE_PREFIX / "api.scan.json")
    elif problem == "hardlink":
        os.link(path, collected.root / "extra-link")
    else:
        path.chmod(0o644)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)
    assert not (staged / collector.RESULT).exists()


@pytest.mark.parametrize(
    "problem",
    [
        "incomplete",
        "qualification_passed",
        "security_approved",
        "release_approved",
        "commit",
        "source",
        "result",
        "missing-service",
        "duplicate-service",
        "artifact-hash",
        "artifact-size",
        "artifact-path",
        "inventory-hash",
        "archive",
    ],
)
def test_collection_bindings_are_required_even_with_refreshed_provenance(
    collected: Acquisition, problem: str
) -> None:
    result = collected.read(collector.RESULT)
    if problem == "incomplete":
        result["complete"] = False
    elif problem in upload.FLAGS:
        result[problem] = True
    elif problem in {"commit", "source"}:
        result["commit_sha" if problem == "commit" else "source_tree_sha256"] = "f" * (
            40 if problem == "commit" else 64
        )
    elif problem == "result":
        result["source"]["assessments_required"] = 0
    elif problem == "missing-service":
        result["image_artifacts"].pop()
    elif problem == "duplicate-service":
        result["image_artifacts"][-1] = result["image_artifacts"][0]
    elif problem.startswith("artifact-"):
        key = {"artifact-hash": "sha256", "artifact-size": "size", "artifact-path": "path"}[problem]
        result["image_artifacts"][0]["scan"][key] = {
            "sha256": "f" * 64,
            "size": 1,
            "path": "elsewhere.json",
        }[key]
    elif problem == "inventory-hash":
        result["image_inventory"]["sha256"] = "f" * 64
    else:
        result["source_archive"]["sha256"] = "f" * 64
    collected.write(collector.RESULT, result)
    provenance(collected)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "changed",
        "hardlink",
        "parent-symlink",
        "root-snapshot",
        "checkout",
        "manifest-file-set",
    ],
)
def test_source_receipt_bindings_are_not_replaced_by_provenance(
    collected: Acquisition, problem: str
) -> None:
    path = collected.root / collector.SOURCE_PREFIX / "python-audit.json"
    if problem == "missing":
        path.unlink()
    elif problem == "changed":
        path.write_bytes(b"changed")
        provenance(collected)
    elif problem == "hardlink":
        os.link(path, collected.root / "extra-link")
    elif problem == "parent-symlink":
        target = path.parent.with_name("saved")
        path.parent.rename(target)
        path.parent.symlink_to(target, target_is_directory=True)
    elif problem == "root-snapshot":
        (collected.root / "SOURCE_SNAPSHOT.json").write_bytes(b"{}")
    elif problem == "checkout":
        document = collected.read(upload.CHECKOUTS[1])
        document["source_tree_sha256"] = "f" * 64
        collected.write(upload.CHECKOUTS[1], document)
        provenance(collected)
    else:
        document = collected.read(collector.SOURCE_MANIFEST)
        document["files"].pop()
        collected.write(collector.SOURCE_MANIFEST, document)
        receipt = collected.read(collector.SOURCE_RESULT)
        raw = (collected.root / collector.SOURCE_MANIFEST).read_bytes()
        receipt["collection"].update(sha256=gate.digest(raw), size=len(raw))
        collected.write(collector.SOURCE_RESULT, receipt)
        provenance(collected)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


@pytest.mark.parametrize("change", ["scanner-exit", "secret-result"])
def test_source_receipt_cannot_be_replaced_after_collection(
    collected: Acquisition, change: str
) -> None:
    original_result = (collected.root / collector.RESULT).read_bytes()
    receipt = collected.read(collector.SOURCE_RESULT)
    assert receipt["scanner_exit"] == 1 and receipt["result"]["raw_passed"] is False
    if change == "scanner-exit":
        receipt["scanner_exit"] = 0
    else:
        report_path = collector.SOURCE_PREFIX + "/gitleaks-source.json"
        assert collected.read(report_path) == []
        collected.source_report(
            "gitleaks-source.json", [{"RuleID": "synthetic", "Secret": "fixture-only-canary"}]
        )
        manifest = collected.read(collector.SOURCE_MANIFEST)
        for ref in [manifest["inventory"], *manifest["files"]]:
            raw = (collected.root / ref["path"]).read_bytes()
            ref.update(sha256=gate.digest(raw), size=len(raw))
        collected.write(collector.SOURCE_MANIFEST, manifest)
        raw = (collected.root / collector.SOURCE_MANIFEST).read_bytes()
        receipt["collection"].update(sha256=gate.digest(raw), size=len(raw))
    collected.write(collector.SOURCE_RESULT, receipt)
    provenance(collected)
    assert (collected.root / collector.RESULT).read_bytes() == original_result
    assert collected.read(collector.RESULT)["source"] == receipt["result"]
    with pytest.raises(gate.GateError, match="source_receipt_binding"):
        upload.finalize_upload(collected.root)
    assert not (collected.root / upload.UPLOAD / collector.RESULT).exists()


@pytest.mark.parametrize("field", ["missing", "path", "sha256", "size"])
def test_source_receipt_pin_is_required_and_exact(collected: Acquisition, field: str) -> None:
    result = collected.read(collector.RESULT)
    if field == "missing":
        del result["source_receipt"]
    else:
        result["source_receipt"][field] = {
            "path": collector.SOURCE_MANIFEST,
            "sha256": "f" * 64,
            "size": 1,
        }[field]
    collected.write(collector.RESULT, result)
    provenance(collected)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "hash",
        "duplicate",
        "attempt",
        "privacy",
        "missing-stage",
        "commit",
        "workflow",
        "ci-extra",
    ],
)
def test_provenance_must_bind_every_exported_input(collected: Acquisition, problem: str) -> None:
    document = collected.read(upload.PROVENANCE)
    if problem == "missing":
        document["files"].pop()
    elif problem == "hash":
        document["files"][0]["sha256"] = "f" * 64
    elif problem == "duplicate":
        document["files"].append(document["files"][0])
    elif problem == "attempt":
        document["run_attempt"] = "2"
    elif problem == "privacy":
        document["stage_outcomes"]["image_privacy"] = "failure"
    elif problem == "missing-stage":
        document["stage_outcomes"].pop("after")
    elif problem == "commit":
        document["expected_commit_sha"] = "f" * 40
    elif problem == "workflow":
        document["commands_source"] = ".github/workflows/qualification.yml at commit_sha"
    else:
        collected.write(collector.OUTPUT + "/unselected.json", {})
    collected.write(upload.PROVENANCE, document)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


@pytest.mark.parametrize("problem", ["hash", "size", "symlink", "hardlink", "cap"])
def test_archive_is_streamed_with_exact_bound_regular_input(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    path = collected.root / collector.SOURCE_ARCHIVE
    if problem == "hash":
        raw = path.read_bytes()
        path.write_bytes(b"!" + raw[1:])
    elif problem == "size":
        with path.open("ab") as handle:
            handle.write(b"!")
    elif problem == "symlink":
        target = path.with_name("elsewhere.tar")
        path.rename(target)
        path.symlink_to(target)
    elif problem == "hardlink":
        os.link(path, path.with_name("elsewhere.tar"))
    else:
        receipt = collected.read(collector.SOURCE_RESULT)
        receipt["archive"]["size"] = MAX_ARCHIVE_BYTES + 1
        collected.write(collector.SOURCE_RESULT, receipt)
        result = collected.read(collector.RESULT)
        result["source_archive"] = receipt["archive"]
        collected.write(collector.RESULT, result)
        provenance(collected)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


def test_archive_not_loaded_through_json_reader(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = gate.BundleReader.read

    def read(self: gate.BundleReader, path: str) -> tuple[bytes, int]:
        assert not path.endswith(".tar")
        return original(self, path)

    monkeypatch.setattr(gate.BundleReader, "read", read)
    assert upload.finalize_upload(collected.root)["complete"] is True


def test_rehashed_unrelated_archive_cannot_replace_the_collected_source(
    collected: Acquisition, tmp_path: Path
) -> None:
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    # Keep the selected snapshot, but replace its actual source payload.
    for name, raw in collected.source.source_files.items():
        path = unrelated / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        # Match the synthetic source manifest regardless of the caller's umask.
        path.chmod(0o644)
    (unrelated / "uv.lock").write_bytes(b"unrelated synthetic source")
    replacement = tmp_path / "unrelated.tar"
    pack_bundle(unrelated, replacement)
    archive = collected.root / collector.SOURCE_ARCHIVE
    archive.write_bytes(replacement.read_bytes())
    new_ref = {
        "path": collector.SOURCE_ARCHIVE,
        "sha256": gate.digest(archive.read_bytes()),
        "size": archive.stat().st_size,
    }
    receipt = collected.read(collector.SOURCE_RESULT)
    receipt["archive"] = new_ref
    collected.write(collector.SOURCE_RESULT, receipt)
    result = collected.read(collector.RESULT)
    result["source_archive"] = new_ref
    receipt_raw = (collected.root / collector.SOURCE_RESULT).read_bytes()
    result["source_receipt"].update(sha256=gate.digest(receipt_raw), size=len(receipt_raw))
    collected.write(collector.RESULT, result)
    provenance(collected)
    with pytest.raises(gate.GateError, match="file_binding_mismatch"):
        upload.finalize_upload(collected.root)
    assert not (collected.root / upload.UPLOAD / collector.RESULT).exists()
    assert not (collected.root / upload.UPLOAD / collector.SOURCE_ARCHIVE).exists()


def test_verify_images_is_read_only_without_collection_or_original_images(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate.write(collector.IMAGE_PREFIX + "/inventory.json", {"complete": False})
    upload.prepare_images(candidate.root)
    for path in (candidate.root / collector.IMAGE_PREFIX).glob("*.json"):
        path.unlink()
    assert not (candidate.root / collector.RESULT).exists()
    retained = {
        path: (path.read_bytes(), gate.BundleReader.identity(path.stat()))
        for path in candidate.root.rglob("*")
        if path.is_file()
    }
    original = gate.BundleReader.read

    def read(reader: gate.BundleReader, path: str) -> tuple[bytes, int]:
        assert path == upload.MANIFEST or path.startswith(
            upload.UPLOAD + "/" + collector.IMAGE_PREFIX + "/"
        )
        return original(reader, path)

    monkeypatch.setattr(gate.BundleReader, "read", read)
    assert upload.verify_images(candidate.root) == {
        "images_verified": 41,
        **dict.fromkeys(upload.FLAGS, False),
    }
    assert retained == {
        path: (path.read_bytes(), gate.BundleReader.identity(path.stat()))
        for path in candidate.root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("failed", [False, True])
def test_verify_images_allows_other_staging_after_finalization(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    if failed:

        def fail_copy(_reader: gate.BundleReader, _ref: upload.ArchiveRef) -> None:
            raise gate.GateError("synthetic_copy_failure")

        monkeypatch.setattr(upload, "copy_archive", fail_copy)
        with pytest.raises(gate.GateError, match="synthetic_copy_failure"):
            upload.finalize_upload(collected.root)
    else:
        upload.finalize_upload(collected.root)
    assert (collected.root / upload.UPLOAD / collector.RESULT).is_file()
    assert upload.verify_images(collected.root)["images_verified"] == 41


@pytest.mark.parametrize(
    "problem",
    ["changed", "missing", "extra-json", "extra-file", "extra-directory", "symlink", "hardlink"],
)
def test_verify_images_rejects_changes_without_full_collection(
    candidate: Acquisition, problem: str
) -> None:
    upload.prepare_images(candidate.root)
    path = candidate.root / upload.UPLOAD / collector.IMAGE_PREFIX / "api.scan.json"
    if problem == "changed":
        path.write_bytes(b"changed")
    elif problem == "missing":
        path.unlink()
    elif problem.startswith("extra-"):
        extra = (
            path.parent
            / {"extra-json": "extra.json", "extra-file": ".env", "extra-directory": "nested"}[
                problem
            ]
        )
        if problem == "extra-directory":
            extra.mkdir()
        else:
            extra.write_bytes(b"synthetic canary")
    elif problem == "symlink":
        path.unlink()
        path.symlink_to(candidate.root / collector.IMAGE_PREFIX / "api.scan.json")
    else:
        os.link(path, candidate.root / "image-alias")
    with pytest.raises(REJECTED):
        upload.verify_images(candidate.root)


@pytest.mark.parametrize("problem", ["duplicate", "path", "hash", "approval", "empty"])
def test_verify_images_requires_the_original_manifest(candidate: Acquisition, problem: str) -> None:
    upload.prepare_images(candidate.root)
    manifest = candidate.read(upload.MANIFEST)
    if problem == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif problem == "path":
        manifest["files"][0]["path"] = "elsewhere.json"
    elif problem == "hash":
        manifest["files"][0]["sha256"] = "f" * 64
    elif problem == "approval":
        manifest["security_approved"] = True
    else:
        manifest["files"] = []
    candidate.write(upload.MANIFEST, manifest)
    with pytest.raises(REJECTED):
        upload.verify_images(candidate.root)


def test_verify_images_rechecks_changes_during_read(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload.prepare_images(candidate.root)
    original = gate.BundleReader.read
    changed = False

    def read(reader: gate.BundleReader, path: str) -> tuple[bytes, int]:
        nonlocal changed
        raw = original(reader, path)
        if not changed and path.startswith(upload.UPLOAD + "/"):
            changed = True
            (candidate.root / path).write_bytes(b"changed during read")
        return raw

    monkeypatch.setattr(gate.BundleReader, "read", read)
    with pytest.raises(gate.GateError, match="file_changed"):
        upload.verify_images(candidate.root)


def test_verify_images_cli_requires_no_collection(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    upload.prepare_images(candidate.root)
    monkeypatch.setattr(
        sys, "argv", ["stage-release-upload", "verify-images", "--root", str(candidate.root)]
    )
    assert upload.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {"images_verified": 41, **dict.fromkeys(upload.FLAGS, False)}


@pytest.mark.parametrize(
    "args",
    [
        ["synthetic-private-canary"],
        ["verify-images", "--synthetic-private-canary"],
        ["finalize", "--unknown", "synthetic-private-canary"],
        ["prepare-images", "synthetic-private-canary"],
        ["verify-images", "--root"],
    ],
)
def test_cli_argument_failures_do_not_echo_values(
    args: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["stage-release-upload", *args])
    assert upload.main() == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "complete": False,
        "error": "upload_staging_failed",
        **dict.fromkeys(upload.FLAGS, False),
    }


@pytest.mark.parametrize("problem", ["hardlink", "permissions"])
def test_archive_output_is_private_and_single_linked(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    original = upload.new_file

    @contextmanager
    def mutate(reader: gate.BundleReader, path: str) -> Iterator[BinaryIO]:
        with original(reader, path) as handle:
            yield handle
            if path.endswith(".tar"):
                target = collected.root / path
                if problem == "hardlink":
                    os.link(target, collected.root / "archive-alias")
                else:
                    target.chmod(0o644)

    monkeypatch.setattr(upload, "new_file", mutate)
    with pytest.raises(gate.GateError, match="output_type_or_permissions"):
        upload.finalize_upload(collected.root)


@pytest.mark.parametrize("problem", ["empty", "total-budget"])
def test_prepare_bounds_collection(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    if problem == "empty":
        for path in (candidate.root / collector.IMAGE_PREFIX).glob("*.json"):
            path.unlink()
    else:
        monkeypatch.setattr(gate, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(gate.GateError):
        upload.prepare_images(candidate.root)
    assert not (candidate.root / upload.MANIFEST).exists()


@pytest.mark.parametrize("problem", ["changed", "extra-json", "extra-staged"])
def test_prepare_detects_input_and_output_races(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    original = upload.new_file
    changed = False

    @contextmanager
    def mutate(reader: gate.BundleReader, path: str) -> Iterator[BinaryIO]:
        nonlocal changed
        with original(reader, path) as handle:
            yield handle
        if not changed:
            changed = True
            target = {
                "changed": collector.IMAGE_PREFIX + "/api.scan.json",
                "extra-json": collector.IMAGE_PREFIX + "/extra.json",
                "extra-staged": upload.UPLOAD + "/extra.json",
            }[problem]
            candidate.write(target, b"synthetic change")

    monkeypatch.setattr(upload, "new_file", mutate)
    with pytest.raises(gate.GateError):
        upload.prepare_images(candidate.root)
    assert not (candidate.root / upload.MANIFEST).exists()


def test_cli_defaults_to_checkout_root(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(collected.root)
    monkeypatch.setattr(sys, "argv", ["stage-release-upload", "finalize"])
    assert upload.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["complete"] is True


@pytest.mark.parametrize("change", ["image", "source", "archive", "extra"])
def test_changes_during_final_copy_are_rejected(
    collected: Acquisition, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    original = upload.new_file
    changed = False

    @contextmanager
    def mutate(reader: gate.BundleReader, path: str) -> Iterator[BinaryIO]:
        nonlocal changed
        with original(reader, path) as handle:
            yield handle
        if not changed:
            changed = True
            paths = {
                "image": upload.UPLOAD + "/" + collector.IMAGE_PREFIX + "/api.scan.json",
                "source": collector.SOURCE_PREFIX + "/python-audit.json",
                "archive": collector.SOURCE_ARCHIVE,
                "extra": upload.UPLOAD + "/extra.json",
            }
            (collected.root / paths[change]).write_bytes(b"changed")

    monkeypatch.setattr(upload, "new_file", mutate)
    with pytest.raises(REJECTED):
        upload.finalize_upload(collected.root)


def test_cli_sanitizes_failure(
    candidate: Acquisition, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failed(_root: Path) -> dict[str, Any]:
        raise ValueError("synthetic-private-path-or-content")

    monkeypatch.setattr(upload, "finalize_upload", failed)
    monkeypatch.setattr(
        sys, "argv", ["stage-release-upload", "finalize", "--root", str(candidate.root)]
    )
    assert upload.main() == 1
    captured = capsys.readouterr()
    assert "synthetic-private" not in captured.out + captured.err
    assert json.loads(captured.out) == {
        "complete": False,
        "error": "upload_staging_failed",
        **dict.fromkeys(upload.FLAGS, False),
    }
