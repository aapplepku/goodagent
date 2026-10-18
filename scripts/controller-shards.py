"""Bound hosted evaluation jobs without reducing the release benchmark or its checks."""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from open_commerce.controller.benchmark import BenchmarkEvidence, BenchmarkRow, summarize
from open_commerce.controller.benchmark_command import source_fingerprint

REFERENCE = Path("examples/eval/results/controller-v2-durable.json.gz")
SHARDS = 4
SEEDS_PER_SHARD = 25


def read(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return cast(dict[str, Any], json.loads(gzip.decompress(data) if path.suffix == ".gz" else data))


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def seeds_for(shard: int) -> list[int]:
    if not 0 <= shard < SHARDS:
        raise ValueError("shard must be in 0..3")
    return list(range(shard * SEEDS_PER_SHARD, (shard + 1) * SEEDS_PER_SHARD))


def identity(row: BenchmarkRow) -> tuple[str, str, int, str]:
    return row.scenario, row.variant, row.seed, row.arm


def validate(payload: dict[str, Any], expected_rows: list[BenchmarkRow]) -> BenchmarkEvidence:
    if payload.get("complete") is not True or payload.get("horizon_days") != 30:
        raise ValueError("incomplete or shortened benchmark")
    evidence = BenchmarkEvidence.model_validate(
        {key: payload[key] for key in ("benchmark_version", "rows", "failures")}
    )
    expected = {identity(row): row for row in expected_rows}
    actual = {identity(row): row for row in evidence.rows}
    if len(actual) != len(evidence.rows) or actual.keys() != expected.keys():
        raise ValueError("missing, duplicate or unexpected benchmark cases")
    if evidence.failures or any(row.hard_violations for row in evidence.rows):
        raise ValueError("benchmark contains failures or hard violations")
    if actual != expected:
        raise ValueError("non-timing benchmark rows differ from the committed reference")
    if payload.get("quality_evidence_hash") != evidence.evidence_hash:
        raise ValueError("benchmark evidence hash mismatch")
    if payload.get("summary") != summarize(evidence.rows):
        raise ValueError("benchmark summary does not match its rows")
    if sorted(payload.get("seeds", [])) != sorted({row.seed for row in expected_rows}):
        raise ValueError("declared seed coverage differs from actual cases")
    return evidence


def reference_rows() -> list[BenchmarkRow]:
    reference = read(REFERENCE)
    rows = [BenchmarkRow.model_validate(row) for row in reference["rows"]]
    expected = {
        (scenario, variant, seed, arm)
        for scenario in ("acquisition_v1", "excess_inventory_v1", "search_conversion_v1")
        for variant in ("standard", "inventory_infeasible")
        for seed in range(100)
        for arm in ("no_intervention", "goal_conditioned_controller")
    }
    if {identity(row) for row in rows} != expected:
        raise ValueError("committed reference lacks the complete 1,200-case release matrix")
    validate(reference, rows)
    return rows


def run_shard(shard: int, output: Path) -> None:
    seeds = seeds_for(shard)
    rows = [row for row in reference_rows() if row.seed in seeds]
    reference = output / "controller-shard-reference.json"
    write(reference, {"quality_evidence_hash": BenchmarkEvidence(rows=rows).evidence_hash})
    for arm in ("primary", "reproduction"):
        destination = output / f"controller-{arm}.json.gz"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "open_commerce.cli",
                "controller",
                "evaluate",
                "--seeds",
                ",".join(map(str, seeds)),
                "--days",
                "30",
                "--concurrency",
                "2",
                "--verify",
                str(reference),
                "--output",
                str(destination),
            ],
            check=True,
        )
        validate(read(destination), rows)
        reference = destination


def assemble(directory: Path, output: Path, expected_sha: str) -> dict[str, Any]:
    reference = reference_rows()
    fingerprint = source_fingerprint(Path.cwd())
    roots = sorted(path.parent for path in directory.rglob("controller-primary.json.gz"))
    if (
        len(roots) != SHARDS
        or len(list(directory.rglob("controller-reproduction.json.gz"))) != SHARDS
    ):
        raise ValueError("exactly four primary and four reproduction artifacts are required")
    collected: dict[str, list[BenchmarkRow]] = {"primary": [], "reproduction": []}
    timings: dict[str, list[dict[str, Any]]] = {"primary": [], "reproduction": []}
    sources = []
    seen_shards = set()
    for root in roots:
        provenance = read(root / "ci-evidence/provenance.json")
        if (
            not provenance.get("commit_matches")
            or provenance.get("commit_sha") != expected_sha
            or provenance.get("expected_commit_sha") != expected_sha
        ):
            raise ValueError("shard was not generated from the exact candidate SHA")
        declared = {item["path"]: item["sha256"] for item in provenance["files"]}
        primary = read(root / "controller-primary.json.gz")
        shard = next((i for i in range(SHARDS) if primary["seeds"] == seeds_for(i)), None)
        if shard is None or shard in seen_shards:
            raise ValueError("missing, overlapping or duplicate seed shard")
        seen_shards.add(shard)
        expected = [row for row in reference if row.seed in seeds_for(shard)]
        for arm in collected:
            path = root / f"controller-{arm}.json.gz"
            if (
                declared.get(f".opencommerce/{path.name}")
                != hashlib.sha256(path.read_bytes()).hexdigest()
            ):
                raise ValueError("shard bytes do not match hosted provenance")
            payload = read(path)
            if payload["environment"]["source_fingerprint"] != fingerprint:
                raise ValueError("shard deployment source differs from the candidate")
            evidence = validate(payload, expected)
            collected[arm].extend(evidence.rows)
            timings[arm].extend(payload["timings"])
        sources.append({"shard": shard, "provenance": provenance})
    order = {identity(row): index for index, row in enumerate(reference)}
    results = {}
    for arm, rows in collected.items():
        rows.sort(key=lambda row: order[identity(row)])
        evidence = BenchmarkEvidence(rows=rows)
        payload = {
            "complete": True,
            **evidence.model_dump(mode="json"),
            "horizon_days": 30,
            "seeds": list(range(100)),
            "coverage": "release_seed_sweep",
            "quality_evidence_hash": evidence.evidence_hash,
            "summary": summarize(rows),
            "timings": timings[arm],
            "commit_sha": expected_sha,
            "case_execution": "four isolated hosted PostgreSQL jobs; 25 seeds each",
            "hosted_shards": sources,
        }
        validate(payload, reference)
        write(output / f"controller-{arm}.json.gz", payload)
        results[arm] = evidence.evidence_hash
    if results["primary"] != results["reproduction"]:
        raise ValueError("independent full reproduction differs")
    result = {"commit_sha": expected_sha, "cases_per_sweep": len(reference), "hashes": results}
    write(output / "controller-assembly.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--shard", type=int, required=True)
    run.add_argument("--output", type=Path, default=Path(".opencommerce"))
    merge = commands.add_parser("assemble")
    merge.add_argument("--directory", type=Path, required=True)
    merge.add_argument("--output", type=Path, default=Path(".opencommerce"))
    merge.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    if args.command == "run":
        run_shard(args.shard, args.output)
    else:
        print(json.dumps(assemble(args.directory, args.output, args.expected_sha), indent=2))


if __name__ == "__main__":
    main()
