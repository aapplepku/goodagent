"""Verify retained three-arm evidence and report paired results without winning imputation."""

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ARMS = {"no_intervention", "frozen_v1", "revised"}
REGISTERED = {
    "development": (
        ("crowded_boots", "compatible_panels", "bounded_offer", "thin_history"),
        (71,),
    ),
    "held_out": (
        ("crowded_storage", "compatible_outdoors", "offer_with_alternatives", "satisfactory_stock"),
        (107, 131, 163),
    ),
}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def setup_hash(raw: dict[str, Any]) -> str:
    world = {k: v for k, v in raw["initial_world"].items() if k not in {"id", "tenant_id"}}
    spec = raw["goal"]["spec"]
    return hashlib.sha256(
        canonical(
            {
                "world": world,
                "objective": spec["objective"],
                "allowed": spec["allowed_action_types"],
                "merchandising": spec["merchandising"],
            }
        )
    ).hexdigest()


def metrics(raw: dict[str, Any]) -> dict[str, int | float]:
    summary = raw["summary"]
    return {
        "contribution_profit_minor": summary["contribution_profit_minor"],
        "profit_per_eligible_session_minor": summary["profit_per_eligible_session_minor"],
        "excess_units_sold": sum(
            p["units"] for p in summary["products"].values() if p["excess_inventory"]
        ),
        "search_attributed_purchases": sum(
            day["metrics"]["search_attributed_purchases"] for day in raw["observations"]
        ),
        "units": summary["units"],
        "orders": summary["orders"],
        "eligible_sessions": summary["eligible_sessions"],
        "net_revenue_minor": summary["net_revenue_minor"],
        "promotion_redemption_value_minor": summary["promotion_redemption_value_minor"],
    }


def arm_summary(raw: dict[str, Any], artifact: str) -> dict[str, Any]:
    if "error" in raw:
        return {k: raw[k] for k in ("case", "seed", "arm", "error")}
    reasons: Counter[str] = Counter()
    dispositions: Counter[str] = Counter()
    selections, assessments = [], []
    for index, run in enumerate(raw["decisions"]):
        decision = run["summary"]["merchandising_decision"]
        candidates = decision.get("candidates", [])
        reasons.update(reason for c in candidates for reason in c["reason_codes"])
        dispositions.update(c["disposition"] for c in candidates)
        selections.append(
            {
                "cycle": index,
                "run_id": run["id"],
                "kind": decision["kind"],
                "selected": decision.get("selected_key"),
                "compiled_alternatives": [
                    {
                        "key": c["key"],
                        "selected": c["selected"],
                        "compiler": c["compiler_result"],
                        "policy": c["policy_result"],
                        "disposition": c["disposition"],
                        "reasons": c["reason_codes"],
                    }
                    for c in candidates
                    if c["candidate_generated"] and c["key"] != "unchanged"
                ],
                "full_candidate_count": len(candidates),
            }
        )
        for c in candidates:
            assessment = c["evidence"].get("assessment") or c["evidence"].get(
                "prior_complement_outcome"
            )
            if assessment:
                assessments.append(
                    {
                        "cycle": index,
                        "candidate": c["key"],
                        "classification": c["classification"],
                        "assessment": assessment,
                        "selected": c["selected"],
                        "reasons": c["reason_codes"],
                    }
                )
    executed = [a for a in raw["actions"] if a["action"]["status"] == "succeeded"]
    targets: Counter[str] = Counter()
    reversals = []
    measurement_states: Counter[str] = Counter()
    for a in executed:
        intent = a["action"]["intent"]
        action_type = intent["type"]
        target = (
            canonical(
                {
                    "type": action_type,
                    "scope": intent.get("product_scope"),
                    "variants": sorted(c["variant_id"] for c in intent.get("changes", [])),
                    "discount": intent.get("provider_discount_id"),
                }
            )
            .decode()
            .strip()
        )
        targets[target] += 1
        if action_type == "disable_discount" or (
            action_type == "set_recommendation_policy"
            and intent["controls"]["strategy"] == "alternatives"
        ):
            reversals.append({"action_id": a["action"]["id"], "type": action_type})
        if a.get("outcome"):
            measurement_states[str(a["outcome"]["guardrail_status"])] += 1
        elif a.get("measurement"):
            measurement_states["pending"] += 1
        if action_type == "set_variant_price" and any(
            c["new_price"]["amount_minor"] != c["current_price"]["amount_minor"]
            and c["new_price"]["amount_minor"]
            == raw["final_state"]["merchandising"]["prices"][c["variant_id"]][
                "reference_price_minor"
            ]
            for c in intent["changes"]
        ):
            reversals.append({"action_id": a["action"]["id"], "type": "price_restore_to_reference"})
    summary = raw["summary"]
    return {
        "case": raw["case"],
        "seed": raw["seed"],
        "arm": raw["arm"],
        "artifact": artifact,
        "setup_sha256": setup_hash(raw),
        "objective": raw["goal"]["spec"]["objective"],
        "metrics": metrics(raw),
        "counts": raw["counts"],
        "no_execution_days": len(raw["observations"])
        - len({a["action"]["intent"]["source_run_id"] for a in executed}),
        "errors": raw["errors"],
        "candidate_reason_occurrences": dict(sorted(reasons.items())),
        "candidate_dispositions": dict(sorted(dispositions.items())),
        "selection_traces": selections,
        "reassessments": assessments,
        "executed_families": dict(Counter(a["action"]["intent"]["type"] for a in executed)),
        "repeated_same_family_target": {k: v for k, v in targets.items() if v > 1},
        "explicit_stop_or_reversal": reversals,
        "expiry_reversions": {
            "price_versions": {
                k: v["version"]
                for k, v in raw["final_state"]["merchandising"]["prices"].items()
                if v["version"]
            },
            "pdp_version": raw["final_state"]["merchandising"]["recommendation_policy"]["version"],
        },
        "measurement_status_counts": dict(measurement_states),
        "safety_paused_days": (
            sum(d["goal_status"] != "active" for d in raw["observations"])
            if all("goal_status" in d for d in raw["observations"])
            else None
        ),
        "guardrails": {
            k: summary[k]
            for k in (
                "known_unit_floor_breaches",
                "combined_discount_breaches",
                "hard_policy_violations",
                "negative_aggregate_profit_days",
                "aggregate_net_margin_below_unit_floor_days",
            )
        },
        "model_calls": raw["model_calls"],
    }


def summarize(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    archive = (directory / "sources.json.gz").read_bytes()
    if hashlib.sha256(archive).hexdigest() != manifest["source_archive_sha256"]:
        raise ValueError("source archive digest mismatch")
    source = json.loads(gzip.decompress(archive))
    if {p: hashlib.sha256(v.encode()).hexdigest() for p, v in source.items()} != manifest[
        "source_hashes"
    ]:
        raise ValueError("archived source bytes do not match registration")
    rows: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    groups: dict[tuple[str, int], dict[str, Any]] = defaultdict(dict)
    for entry in manifest["artifacts"]:
        filename = entry["path"]
        if Path(filename).name != filename:
            raise ValueError("artifact path escapes evaluation")
        content = (directory / filename).read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError("raw artifact digest mismatch")
        raw = json.loads(gzip.decompress(content))
        row = arm_summary(raw, filename)
        group = groups[(row["case"], row["seed"])]
        if row["arm"] in group:
            raise ValueError("duplicate arm cannot count as an independent case")
        group[row["arm"]] = row
        rows.append(row)
    cases, seeds = REGISTERED[manifest["split"]]
    incomplete = [
        {"case": case, "seed": seed, "reason": "registered case has no retained arms"}
        for case in cases
        for seed in seeds
        if (case, seed) not in groups
    ]
    for (case, seed), arms in groups.items():
        if set(arms) != ARMS or any(a.get("error") or a.get("errors") for a in arms.values()):
            incomplete.append({"case": case, "seed": seed, "reason": "missing or failed arm"})
            continue
        if len({a["setup_sha256"] for a in arms.values()}) != 1:
            raise ValueError(f"unmatched initial world/permissions: {case}/{seed}")
        if len({a["metrics"]["eligible_sessions"] for a in arms.values()}) != 1:
            raise ValueError(f"unmatched incoming shopping opportunities: {case}/{seed}")
        for left, right in (
            ("revised", "no_intervention"),
            ("frozen_v1", "no_intervention"),
            ("revised", "frozen_v1"),
        ):
            pairs.append(
                {
                    "case": case,
                    "seed": seed,
                    "comparison": f"{left}-minus-{right}",
                    "differences": {
                        k: v - arms[right]["metrics"][k] for k, v in arms[left]["metrics"].items()
                    },
                }
            )
    aggregates = []
    for case, comparison in sorted({(p["case"], p["comparison"]) for p in pairs}):
        subset = [p for p in pairs if (p["case"], p["comparison"]) == (case, comparison)]
        values = {}
        for metric in subset[0]["differences"]:
            data = [float(p["differences"][metric]) for p in subset]
            average = mean(data)
            half = 4.302652730 * stdev(data) / math.sqrt(3) if len(data) == 3 else None
            values[metric] = {
                "mean": average,
                "descriptive_95pct_t_interval": None
                if half is None
                else [average - half, average + half],
            }
        aggregates.append(
            {"case": case, "comparison": comparison, "n": len(subset), "metrics": values}
        )
    return {
        "split": manifest["split"],
        "frozen_commit": manifest["frozen_commit"],
        "raw_manifest_sha256": hashlib.sha256(
            (directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "rows": rows,
        "pairs": pairs,
        "condition_summaries": aggregates,
        "incomplete": incomplete,
        "complete_registered_comparison": not incomplete,
        "uncertainty": (
            "Three registered seeds only; descriptive paired t intervals, no population or "
            "causal generalization. Development replays are not new independent cases."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a summary")
    result = summarize(args.directory)
    args.output.write_bytes(gzip.compress(canonical(result), mtime=0))
    if args.require_complete and not result["complete_registered_comparison"]:
        raise SystemExit("Incomplete or failed registered comparison; partial summary retained")
    print(
        json.dumps(
            {
                "rows": len(result["rows"]),
                "pairs": len(result["pairs"]),
                "incomplete": result["incomplete"],
            }
        )
    )
