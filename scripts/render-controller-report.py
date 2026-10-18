"""Render every scenario/variant/arm directly from validated controller evidence."""

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

from open_commerce.controller.benchmark import SCENARIOS, BenchmarkEvidence, summarize

METRICS = (
    "objective_outcome",
    "cac_minor",
    "contribution_margin",
    "contribution_profit_minor",
    "spend_minor",
    "action_count",
    "rollback_count",
    "hard_policy_violations",
    "outcome_guardrail_breaches",
)


def render(data: dict[str, Any], *, allow_smoke: bool = False) -> str:
    if not data.get("complete") or data.get("failures"):
        raise ValueError("report requires complete evidence with no failed cases")
    evidence = BenchmarkEvidence.model_validate(
        {key: data[key] for key in ("benchmark_version", "rows", "failures")}
    )
    if evidence.evidence_hash != data["quality_evidence_hash"]:
        raise ValueError("raw evidence hash does not match")
    seeds = data["seeds"]
    days = data["horizon_days"]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("seed set is empty or contains duplicates")
    cases = {
        (scenario, variant, seed, arm)
        for scenario in SCENARIOS
        for variant in ("standard", "inventory_infeasible")
        for seed in seeds
        for arm in ("no_intervention", "goal_conditioned_controller")
    }
    actual = {(r.scenario, r.variant, r.seed, r.arm) for r in evidence.rows}
    if actual != cases or len(evidence.rows) != len(cases):
        raise ValueError("scenario, variant or matched-arm coverage is incomplete")
    if any(row.horizon_days != days or len(row.daily) != days for row in evidence.rows):
        raise ValueError("rows do not cover the declared horizon")
    full = len(seeds) >= 100 and days == 30
    if not full and not allow_smoke:
        raise ValueError("public release report requires 100 seeds and 30 days")
    summary = summarize(evidence.rows)
    if summary != data["summary"]:
        raise ValueError("summary differs from the raw evidence")
    violations = sum(len(row.hard_violations) for row in evidence.rows)
    lines = [
        "# Controller Benchmark v2" + (" (SMOKE ONLY)" if not full else ""),
        "",
        "Synthetic, approval-assisted controller evaluation. Not merchant or causal-lift evidence.",
        "",
        f"Coverage: {len(seeds)} seeds per scenario, {days} virtual days, "
        f"{len(evidence.rows)} matched scenario/variant/arm rows.",
        f"Hard-policy violations: **{violations}**. "
        + (
            "The hard-policy gate fails."
            if violations
            else "This gate alone is not release approval."
        ),
        f"Non-timing evidence: `{evidence.evidence_hash}`.",
        f"Source fingerprint: `{data['environment']['source_fingerprint']}`.",
        "",
        "## Environment",
        "",
        "```json",
        json.dumps(data["environment"], sort_keys=True, indent=2),
        "```",
        "",
        "## Results",
        "",
        "All arms and variants are retained, including no-action and unfavorable outcomes.",
        "Money and CAC use integer minor units; margin is a fraction. Missing CAC is counted.",
        "Dispersion is population standard deviation; percentiles are linearly interpolated.",
    ]
    for group in summary:
        matching = [
            r
            for r in evidence.rows
            if (r.scenario, r.variant, r.arm) == (group["scenario"], group["variant"], group["arm"])
        ]
        first = matching[0]
        lines.extend(
            [
                "",
                f"### {group['scenario']} / {group['variant']} / {group['arm']}",
                "",
                f"Objective: `{first.objective_metric}` in `{first.objective_scope}`. "
                "Per-seed targets are retained in the raw rows.",
                f"Runs: {group['runs']}; objective attained: {group['objective_attained']}; "
                f"initial/final infeasibility: {group['infeasible_detected_initially']}/"
                f"{group['infeasible_detected_finally']}; paused: {group['paused_goals']}.",
                "| Metric | n | Missing | Mean | Stddev | p10 | p50 | p90 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for metric in METRICS:
            values = group[metric]
            assert isinstance(values, dict)
            cells = [
                str(values[key]) if values[key] is not None else "undefined"
                for key in ("n", "missing", "mean", "stddev", "p10", "p50", "p90")
            ]
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Interpretation and reproduction",
            "",
            "A default goal can already be on track without intervention. Such rows cannot prove",
            "the safety or benefit of an unexercised action. Observed economic guardrail breaches",
            "are reported separately from hard dispatch/budget violations. Baseline infeasibility",
            "is a read-only assessment, not baseline planning. No fixed-rule arm is implemented.",
            "",
            "[Methods and reproduction commands](controller-v2.md).",
            "[Raw release evidence](../../examples/eval/results/controller-v2-durable.json.gz).",
            "Independent reproduction status is recorded in ../IMPLEMENTATION_STATUS.md, not",
            "inferred from this generated report. Renderer: scripts/render-controller-report.py.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path("examples/eval/results/controller-v2-durable.json.gz")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/benchmarks/controller-v2-results.md")
    )
    args = parser.parse_args()
    raw = args.source.read_bytes()
    data = json.loads(gzip.decompress(raw) if args.source.suffix == ".gz" else raw)
    report = render(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
