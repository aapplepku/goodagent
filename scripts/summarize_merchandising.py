"""Derive compact merchandising evidence without rerunning or selecting winning arms."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/eval/merchandising-v1"


def interval(values: list[float]) -> list[float]:
    if len(values) != 3:
        raise ValueError("Registered descriptive interval requires exactly three paired draws")
    center = mean(values)
    half = 4.302652729911275 * stdev(values) / 3**0.5
    return [center - half, center + half]


def summarize() -> dict[str, Any]:
    directory = DATA / "results/infrastructure-recovery"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    prior = directory.parent / manifest["recovery"]["prior_run"]
    if (
        hashlib.sha256((prior / "manifest.json").read_bytes()).hexdigest()
        != (manifest["recovery"]["prior_manifest_sha256"])
    ):
        raise ValueError("Retained first-pass manifest changed")
    raw: dict[tuple[str, int, str], dict[str, Any]] = {}
    provenance = []
    for source in (prior, directory):
        index = json.loads((source / "manifest.json").read_bytes())
        if (
            hashlib.sha256((source / "sources.json.gz").read_bytes()).hexdigest()
            != (index["source_archive_sha256"])
        ):
            raise ValueError("Evaluation source archive changed")
        for artifact in index["artifacts"]:
            path = source / artifact["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                raise ValueError("Raw rollout changed")
            row = json.loads(gzip.decompress(path.read_bytes()))
            if "summary" not in row:
                continue
            identity = row["case"], row["seed"], row["arm"]
            if identity in raw:
                raise ValueError("Reproduction is not an independent comparison")
            raw[identity] = row
            provenance.append({**artifact, "path": str(path.relative_to(ROOT))})
    if len(raw) != 54 or len(manifest["rows"]) != 54:
        raise ValueError("Expected all 54 registered arms")
    cases: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for row in raw.values():
        counts.update(row["counts"])
        totals["controller_errors"] += len(row["errors"])
        for key in (
            "hard_policy_violations",
            "known_unit_floor_breaches",
            "combined_discount_breaches",
        ):
            value = row["summary"][key]
            totals[key] += len(value) if isinstance(value, list) else value
        totals["model_calls"] += row["summary"]["model_calls"]
    for case, comparison in sorted(manifest["comparisons"].items()):
        pairs = comparison["pairs"]
        if len(pairs) != 3 or not all(p["matched_sessions"] for p in pairs):
            raise ValueError("Unmatched incoming opportunities")
        arms = {}
        coverage = []
        for arm in ("no_intervention", "deterministic"):
            rows = [raw[case, seed, arm] for seed in (11, 23, 47)]
            fields = (
                "contribution_profit_minor",
                "profit_per_eligible_session_minor",
                "conversion_rate",
                "orders",
                "units",
                "net_average_order_value_minor",
                "promotion_redemption_value_minor",
                "search_authored_family_precision",
                "pdp_eligibility_rate",
                "ad_spend_minor",
            )
            arms[arm] = {field: mean(r["summary"][field] for r in rows) for field in fields}
            if arm == "no_intervention":
                for row in rows:
                    products = row["warmup_conditions"]["products"]
                    coverage.append(
                        {
                            "seed": row["seed"],
                            "eligible_sessions": row["warmup_conditions"]["eligible_sessions"],
                            "observed_exposure_gap_product_ids": [
                                k for k, p in products.items() if p["observed_exposure_gap"]
                            ],
                            "high_exposure_low_conversion_product_ids": [
                                k for k, p in products.items() if p["high_exposure_low_conversion"]
                            ],
                        }
                    )
        cases[case] = {
            "arm_means": arms,
            "mean_profit_delta_minor": comparison["mean_profit_delta_minor"],
            "descriptive_t95_profit_delta_minor": comparison[
                "descriptive_95_percent_t_interval_minor"
            ],
            "mean_profit_per_session_delta_minor": mean(
                p["profit_per_session_delta_minor"] for p in pairs
            ),
            "descriptive_t95_profit_per_session_delta_minor": interval(
                [p["profit_per_session_delta_minor"] for p in pairs]
            ),
            "paired_differences": [
                {k: v for k, v in p.items() if k != "product_deltas"} for p in pairs
            ],
            "observed_case_coverage": coverage,
        }
    trajectory = raw["overstock_exposure", 11, "deterministic"]
    start = trajectory["initial_observed_state"]["current_time"][:10]
    actions = trajectory["actions"]
    affected = {
        change["product_id"]
        for record in actions
        for change in record["action"]["intent"].get("changes", [])
    }
    merch = trajectory["final_state"]["merchandising"]
    batches = {
        key: batch
        for key, batch in merch["serving_log"].items()
        if batch["day"] >= start and affected.intersection(batch["product_ids"])
    }
    keys = {key for batch in batches.values() for key in batch["order_keys"]}
    return {
        "protocol": "merchandising-v1",
        "completed_arms": 54,
        "distinct_cases": 9,
        "seeds": [11, 23, 47],
        "recovery": manifest["recovery"],
        "counts": dict(counts),
        "safety_totals": dict(totals),
        "cases": cases,
        "raw_artifacts": provenance,
        "trajectory": {
            "label": "Registered overstock seed 11, deterministic; unfavorable store-profit delta",
            "goal": trajectory["goal"],
            "actions": actions,
            "decisions": [
                {"id": d["id"], "status": d["status"], "summary": d["summary"]}
                for d in trajectory["decisions"]
            ],
            "serving_batches_exposing_affected_products": batches,
            "referenced_redemptions": {k: v for k, v in merch["redemptions"].items() if k in keys},
            "bounded_post_day_observations": trajectory["observations"],
            "measured_outcomes": trajectory["summary"],
        },
        "limitations": [
            "Nine authored synthetic cases, three paired seeds; not merchant evidence.",
            "Seed 47 was held out, not the underlying case mechanisms or catalog families.",
            "Descriptive t intervals with df=2 are not calibrated generalization intervals.",
            "Zero differences in all-wait cases do not establish planner competence.",
            "Search/PDP changes were not selected in these runs; workflow tests are separate.",
            "Scenario names do not prove intended conditions; observed coverage is reported.",
            "Only the PDP API cold-index bypass changed after these rollouts; "
            "simulator serving is unchanged.",
            "No generative model calls; hardware, energy and operator costs are unmeasured.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = DATA / "summary.json"
    encoded = (json.dumps(summarize(), sort_keys=True, indent=2) + "\n").encode()
    if args.check:
        if output.read_bytes() != encoded:
            raise SystemExit("Merchandising summary differs from retained raw evidence")
    else:
        output.write_bytes(encoded)
    print("Verified 54 arms, artifact hashes, matched sessions and non-duplicated recovery")


if __name__ == "__main__":
    main()
