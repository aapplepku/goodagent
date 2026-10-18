"""Summarize complete matched arms without treating reproductions as independent cases."""

import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

from open_commerce.core.types import canonical_hash

ARMS = ("no_intervention", "deterministic", "model_backed")
COUNTS = (
    "proposed",
    "rejected",
    "executed",
    "repeated",
    "no_action",
    "wait",
    "clarification",
    "planning_failures",
    "observed_guardrail_breaches",
)


def summarize(directory: Path) -> dict[str, Any]:
    freeze = json.loads((directory / "freeze.json").read_text())
    configuration = freeze["configuration"]
    expected_hash = canonical_hash(configuration)
    grouped: dict[tuple[str, int], dict[str, Any]] = defaultdict(dict)
    for path in sorted((directory / "cases").glob("*.json")):
        row = json.loads(path.read_text())
        if row["status"] != "complete" or row["freeze_hash"] != expected_hash:
            raise ValueError("incomplete or changed evaluation record")
        key = (row["case_id"], row["seed"])
        if row["arm"] not in ARMS or row["arm"] in grouped[key]:
            raise ValueError("unknown arm or duplicate case/seed; reproductions are not new cases")
        grouped[key][row["arm"]] = row
    if not grouped:
        raise ValueError("no completed comparisons")
    aggregates: dict[str, Any] = {}
    for arm in ARMS:
        aggregates[arm] = {
            **dict.fromkeys(COUNTS, 0),
            "runtime_errors": 0,
            "hard_policy_violations": 0,
            "targets_met": 0,
            "targeted_cases": 0,
            "tool_calls": 0,
            "inference_usage": dict.fromkeys(
                (
                    "requests",
                    "unknown_usage_requests",
                    "reserved_tokens",
                    "input_tokens",
                    "output_tokens",
                    "latency_ms",
                ),
                0,
            ),
        }
    comparisons = []
    latencies: list[int] = []
    sources: set[str] = set()
    for (case_id, seed), arms in sorted(grouped.items()):
        if set(arms) != set(ARMS):
            raise ValueError("all three arms are required for every case/seed")
        baseline = arms["no_intervention"]
        for row in arms.values():
            if (
                any(
                    row["setup"][key] != baseline["setup"][key]
                    for key in ("observable_world_hash", "starting_budgets", "incremental_target")
                )
                or row["objective_unit"] != baseline["objective_unit"]
            ):
                raise ValueError("unmatched inputs or incompatible objective units")
            totals = aggregates[row["arm"]]
            for field in COUNTS:
                totals[field] += row[field]
            totals["runtime_errors"] += len(row["errors"])
            totals["hard_policy_violations"] += len(row["hard_policy_violations"])
            totals["targets_met"] += row["target_attainment"] is True
            totals["targeted_cases"] += row["target_attainment"] is not None
            totals["tool_calls"] += sum(
                len(run.get("summary", {}).get("model_planning", {}).get("tools", []))
                for run in row["runs"]
            )
            for field in totals["inference_usage"]:
                totals["inference_usage"][field] += row["inference_usage"][field]
            sources.update(row["inference_usage"]["sources"])
            for call in row["inference_calls"]:
                if call.get("response"):
                    latencies.append(call["response"]["elapsed_ms"])
        model = arms["model_backed"]
        comparisons.append(
            {
                "case_id": case_id,
                "seed": seed,
                "unit": model["objective_unit"],
                "incremental_target": model["incremental_target"],
                "objectives": {a: arms[a]["objective_value"] for a in ARMS},
                "target_attainment": {a: arms[a]["target_attainment"] for a in ARMS},
                "economics": {a: arms[a]["economics"] for a in ARMS},
                "paired_differences": {
                    a: {
                        "objective": str(
                            Decimal(model["objective_value"]) - Decimal(arms[a]["objective_value"])
                        ),
                        "ad_spend_minor": model["economics"]["ad_spend_minor"]
                        - arms[a]["economics"]["ad_spend_minor"],
                        "contribution_profit_minor": model["economics"]["contribution_profit_minor"]
                        - arms[a]["economics"]["contribution_profit_minor"],
                    }
                    for a in ARMS[:2]
                },
                "errors": {a: arms[a]["errors"] for a in ARMS},
            }
        )
    return {
        "protocol_version": configuration["protocol_version"],
        "split": configuration["split"],
        "freeze_hash": expected_hash,
        "case_seed_pairs": len(grouped),
        "distinct_cases": len({k[0] for k in grouped}),
        "seeds": sorted({k[1] for k in grouped}),
        "arm_totals": aggregates,
        "comparisons": comparisons,
        "model_sources": sorted(sources),
        "latency_ms": {
            "median": median(latencies) if latencies else None,
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "uncertainty": {
            "interval": None,
            "reason": (
                "Purposively selected heterogeneous cases share seed conditions. One seed "
                "per split is insufficient for calibrated generalization intervals; no pooled "
                "mixed-unit effect or causal merchant claim."
            ),
        },
        "cost": {
            "provider_fees_usd": "0",
            "unmeasured": "hardware, electricity, download and operator time",
        },
        "limitations": [
            "A completed trajectory can contain runtime errors; "
            "counts and per-case errors are retained.",
            "Target attainment alone is not evidence of useful intervention.",
            "Unverified model summaries can be factually wrong; "
            "no action is not proof of competent restraint.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
