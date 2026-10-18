"""Archived evidence stays intact and tied to its recorded images and snapshot."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

ARCHIVES = sorted(Path("security/reports").glob("*/manifest.json"))
SERVICES = {"api", "migrate", "worker", "web", "postgres", "redis", "qdrant"}


@pytest.mark.parametrize("manifest_path", ARCHIVES, ids=lambda path: path.parent.name)
def test_security_archive_hashes_and_cross_references(manifest_path: Path) -> None:
    archive = manifest_path.parent
    manifest = json.loads(manifest_path.read_bytes())
    contents: dict[str, bytes] = {}
    for record in manifest["files"]:
        path = Path(record["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert str(path) not in contents
        compressed = (archive / path).read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == record["compressed_sha256"]
        assert compressed[4:8] == bytes(4), "gzip timestamps must be deterministic"
        data = gzip.decompress(compressed)
        assert hashlib.sha256(data).hexdigest() == record["uncompressed_sha256"]
        contents[str(path)] = data
    assert set(contents) == {str(path.relative_to(archive)) for path in archive.rglob("*.gz")}

    images = json.loads(contents["images/inventory.json.gz"])
    proof = json.loads(contents["images/runtime-proof.json.gz"])
    gate = json.loads(contents["images/dispositions.json.gz"])
    source = json.loads(contents["source/inventory.json.gz"])
    assert images["complete"] and proof["complete"] and source["complete"]
    assert gate["passed"] and source["passed"]
    for inventory in (images, proof):
        services = [item["service"] for item in inventory["images"]]
        assert len(services) == len(SERVICES) and set(services) == SERVICES
    proof_ids = {item["service"]: item["image_id"] for item in proof["images"]}
    for item in images["images"]:
        assert item["image_id"] == proof_ids[item["service"]]
        for key in ("scan", "sbom"):
            data = contents[f"images/{item[key]}.gz"]
            assert hashlib.sha256(data).hexdigest() == item[f"{key}_sha256"]
    for field, name in (
        ("assessment_sha256", "images/assessments.json.gz"),
        ("runtime_proof_sha256", "images/runtime-proof.json.gz"),
    ):
        assert gate[field] == hashlib.sha256(contents[name]).hexdigest()
    for item in source["reports"]:
        assert item["exit_code"] == 0
        data = contents[f"source/{item['report']}.gz"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
    if "reviewed_records_sha256" in gate:
        assert (
            gate["reviewed_records_sha256"]
            == hashlib.sha256(contents["images/reviewed-findings.json.gz"]).hexdigest()
        )
    snapshot = json.loads(contents["source/source-files.json.gz"])
    assert snapshot, "archive must identify the actual scanned source"


def test_release_paths_and_generated_requirement_comments_are_portable() -> None:
    import runpy

    runpy.run_path("scripts/check-release-paths.py")["main"]()
