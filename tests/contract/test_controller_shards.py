"""Sharding changes scheduling only; incomplete or changed evidence cannot pass."""

import copy
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

from open_commerce.controller.benchmark import BenchmarkEvidence, BenchmarkRow, summarize

SCRIPT = runpy.run_path("scripts/controller-shards.py")
SMOKE = json.loads(Path("examples/eval/results/controller-v2-smoke.json").read_bytes())


def payload(rows: list[BenchmarkRow]) -> dict[str, Any]:
    evidence = BenchmarkEvidence(rows=rows)
    return {
        "complete": True,
        **evidence.model_dump(mode="json"),
        "horizon_days": 30,
        "seeds": sorted({row.seed for row in rows}),
        "quality_evidence_hash": evidence.evidence_hash,
        "summary": summarize(rows),
        "timings": [],
        "environment": {"source_fingerprint": "source"},
    }


@pytest.fixture
def row() -> BenchmarkRow:
    return BenchmarkRow.model_validate(SMOKE["rows"][0])


def test_seed_partitions_preserve_all_100_seeds_once() -> None:
    seeds = [seed for shard in range(4) for seed in SCRIPT["seeds_for"](shard)]
    assert seeds == list(range(100))
    for invalid in (-1, 4):
        with pytest.raises(ValueError):
            SCRIPT["seeds_for"](invalid)


@pytest.mark.parametrize(
    "tamper",
    [
        "incomplete",
        "horizon",
        "missing",
        "duplicate",
        "failure",
        "hard",
        "row",
        "hash",
        "summary",
        "seeds",
    ],
)
def test_changed_or_partial_shard_fails(row: BenchmarkRow, tamper: str) -> None:
    data = payload([row])
    if tamper == "incomplete":
        data["complete"] = False
    elif tamper == "horizon":
        data["horizon_days"] = 3
    elif tamper == "missing":
        data["rows"] = []
    elif tamper == "duplicate":
        data["rows"] *= 2
    elif tamper == "failure":
        data["failures"] = [{"error_type": "TimeoutError"}]
    elif tamper == "hard":
        data["rows"][0]["hard_violations"] = ["BUDGET"]
    elif tamper == "row":
        data["rows"][0]["executed_actions"] += 1
    elif tamper == "hash":
        data["quality_evidence_hash"] = "wrong"
    elif tamper == "summary":
        data["summary"] = []
    else:
        data["seeds"] = [999]
    with pytest.raises(ValueError):
        SCRIPT["validate"](data, [row])


def test_full_committed_reference_still_has_1200_cases() -> None:
    assert len(SCRIPT["reference_rows"]()) == 1200


def test_run_verifies_committed_subset_then_independent_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: BenchmarkRow
) -> None:
    run = SCRIPT["run_shard"]
    row = row.model_copy(update={"seed": 0})
    monkeypatch.setitem(run.__globals__, "reference_rows", lambda: [row])
    commands = []

    def invoke(command: list[str], *, check: bool) -> None:
        assert check
        commands.append(command)
        SCRIPT["write"](Path(command[command.index("--output") + 1]), payload([row]))

    monkeypatch.setattr(run.__globals__["subprocess"], "run", invoke)
    run(0, tmp_path)
    assert len(commands) == 2
    for command in commands:
        assert command[command.index("--days") + 1] == "30"
        assert command[command.index("--seeds") + 1] == ",".join(map(str, range(25)))
    first = Path(commands[0][commands[0].index("--verify") + 1])
    assert (
        SCRIPT["read"](first)["quality_evidence_hash"]
        == BenchmarkEvidence(rows=[row]).evidence_hash
    )
    assert commands[1][commands[1].index("--verify") + 1] == str(
        tmp_path / "controller-primary.json.gz"
    )


@pytest.fixture
def shards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: BenchmarkRow) -> Path:
    merge = SCRIPT["assemble"]
    rows = [row.model_copy(update={"seed": seed}) for seed in range(100)]
    monkeypatch.setitem(merge.__globals__, "reference_rows", lambda: rows)
    monkeypatch.setitem(merge.__globals__, "source_fingerprint", lambda _: "source")
    for index in range(4):
        root = tmp_path / f"shard-{index}"
        files = []
        for arm in ("primary", "reproduction"):
            path = root / f"controller-{arm}.json.gz"
            SCRIPT["write"](path, payload(rows[index * 25 : (index + 1) * 25]))
            files.append(
                {
                    "path": f".opencommerce/{path.name}",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        SCRIPT["write"](
            root / "ci-evidence/provenance.json",
            {
                "commit_matches": True,
                "commit_sha": "candidate",
                "expected_commit_sha": "candidate",
                "files": files,
            },
        )
    return tmp_path


def test_assembly_verifies_both_full_sweeps(shards: Path) -> None:
    result = SCRIPT["assemble"](shards, shards / "assembled", "candidate")
    assert result["cases_per_sweep"] == 100  # Fixture reduces rows, not production seed coverage.
    assert result["hashes"]["primary"] == result["hashes"]["reproduction"]


@pytest.mark.parametrize(
    "tamper", ["missing", "sha", "duplicate", "source", "bytes", "reproduction"]
)
def test_assembly_rejects_invalid_hosted_artifacts(shards: Path, tamper: str) -> None:
    root = shards / "shard-0"
    path = root / "controller-reproduction.json.gz"
    provenance_path = root / "ci-evidence/provenance.json"
    provenance = SCRIPT["read"](provenance_path)
    if tamper == "missing":
        path.unlink()
    elif tamper == "sha":
        provenance["commit_sha"] = "another-commit"
    elif tamper == "duplicate":
        for arm in ("primary", "reproduction"):
            other = shards / "shard-1" / f"controller-{arm}.json.gz"
            SCRIPT["write"](root / other.name, SCRIPT["read"](other))
        provenance = copy.deepcopy(SCRIPT["read"](shards / "shard-1/ci-evidence/provenance.json"))
    elif tamper == "bytes":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        data = SCRIPT["read"](path)
        if tamper == "source":
            data["environment"]["source_fingerprint"] = "different-source"
        else:
            data["rows"][0]["executed_actions"] += 1
        SCRIPT["write"](path, data)
        provenance["files"][1]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    SCRIPT["write"](provenance_path, provenance)
    with pytest.raises(ValueError):
        SCRIPT["assemble"](shards, shards / "assembled", "candidate")
