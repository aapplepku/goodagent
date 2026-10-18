"""Read-only diagnosis and comparison integrity; no positive outcome requirement."""

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from scripts.summarize_merchandising_decisions import summarize

ROOT = Path("examples/eval/merchandising-decisions-v2")


def test_registered_protocol_and_frozen_v1_remain_exact() -> None:
    assert hashlib.sha256((ROOT / "protocol.md").read_bytes()).hexdigest() == (
        "af7ae6eb13655beab4f99885afa383f9de10cd6d8f8a07d9cd07b019e38758d1"
    )
    assert hashlib.sha256((ROOT / "protocol-amendment-1.md").read_bytes()).hexdigest() == (
        "3f801ff613e50d5774cb1d18d19fe7a69586cdc458574fa14b2bf5d2fd122f04"
    )
    assert hashlib.sha256(Path("scripts/merchandising_v1_frozen.py").read_bytes()).hexdigest() == (
        "d10569cc8f3cee53a205ea2e0b5698ee4302fa79023a6287c997784fb8121252"
    )


def test_diagnostic_is_paired_but_not_a_complete_registered_comparison() -> None:
    result = summarize(ROOT / "results/development-thin-first")
    assert len(result["rows"]) == 3 and len(result["pairs"]) == 3
    assert not result["complete_registered_comparison"]
    assert all(p["differences"]["contribution_profit_minor"] == 0 for p in result["pairs"])
    assert all(r["model_calls"] == 0 for r in result["rows"])
    assert all(s["n"] == 1 for s in result["condition_summaries"])
    assert all(
        m["descriptive_95pct_t_interval"] is None
        for s in result["condition_summaries"]
        for m in s["metrics"].values()
    )


@pytest.mark.parametrize("target", ["raw", "source", "duplicate"])
def test_changed_or_duplicated_evidence_fails_closed(tmp_path: Path, target: str) -> None:
    shutil.copytree(ROOT / "results/development-thin-first", tmp_path / "copy")
    directory = tmp_path / "copy"
    manifest_file = directory / "manifest.json"
    manifest = json.loads(manifest_file.read_bytes())
    if target == "raw":
        (directory / manifest["artifacts"][0]["path"]).write_bytes(b"changed")
    elif target == "source":
        archive = gzip.compress(b"{}", mtime=0)
        (directory / "sources.json.gz").write_bytes(archive)
        manifest["source_archive_sha256"] = hashlib.sha256(archive).hexdigest()
    else:
        manifest["artifacts"].append(manifest["artifacts"][0])
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        summarize(directory)


def test_distinct_price_targets_are_not_reported_as_repeated_interventions() -> None:
    result = summarize(ROOT / "results/development-three-arm")
    row = next(r for r in result["rows"] if r["case"] == "bounded_offer" and r["arm"] == "revised")
    assert row["executed_families"]["set_variant_price"] == 4
    assert not any("set_variant_price" in key for key in row["repeated_same_family_target"])
    assert row["no_execution_days"] == 6
    frozen = next(
        r for r in result["rows"] if r["case"] == "bounded_offer" and r["arm"] == "frozen_v1"
    )
    assert frozen["no_execution_days"] == 7
    assert (
        row["metrics"]["contribution_profit_minor"] < frozen["metrics"]["contribution_profit_minor"]
    )


def test_registered_held_out_summary_matches_complete_retained_evidence() -> None:
    directory = ROOT / "results/held-out-first"
    result = summarize(directory)
    committed = json.loads(gzip.decompress((directory / "summary.json.gz").read_bytes()))
    assert result == committed
    assert result["complete_registered_comparison"] and not result["incomplete"]
    assert result["frozen_commit"] == "e11c226f60b0d1895726ae20887a6044a4d4f948"
    assert len(result["rows"]) == 36 and len(result["pairs"]) == 36
    assert all(row["model_calls"] == 0 for row in result["rows"])
