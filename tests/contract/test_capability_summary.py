"""Do not summarize changed, incomplete or duplicate comparison records as valid evidence."""

import json
from pathlib import Path

import pytest
from scripts.summarize_capability_evaluation import ARMS, COUNTS, summarize

from open_commerce.core.types import canonical_hash


def reports(tmp_path: Path) -> Path:
    config = {"protocol_version": "test", "split": "development"}
    (tmp_path / "freeze.json").write_text(json.dumps({"configuration": config}))
    (tmp_path / "cases").mkdir()
    for index, arm in enumerate(ARMS):
        row = {
            "case_id": "paired",
            "seed": 11,
            "arm": arm,
            "status": "complete",
            "freeze_hash": canonical_hash(config),
            "objective_unit": "count",
            "objective_value": str(10 + index),
            "incremental_target": "20",
            "target_attainment": False,
            "errors": [],
            "hard_policy_violations": [],
            "runs": [],
            "inference_calls": [],
            "economics": {"ad_spend_minor": 100, "contribution_profit_minor": 200},
            "setup": {
                "observable_world_hash": "same",
                "starting_budgets": [],
                "incremental_target": "20",
            },
            **dict.fromkeys(COUNTS, 0),
            "inference_usage": {
                **dict.fromkeys(
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
                "sources": [],
            },
        }
        (tmp_path / "cases" / f"{arm}.json").write_text(json.dumps(row))
    return tmp_path


def test_paired_summary_keeps_units_and_does_not_invent_confidence(tmp_path: Path) -> None:
    result = summarize(reports(tmp_path))
    assert result["case_seed_pairs"] == 1
    assert result["comparisons"][0]["paired_differences"]["no_intervention"]["objective"] == "2"
    assert result["comparisons"][0]["paired_differences"]["deterministic"]["objective"] == "1"
    assert result["uncertainty"]["interval"] is None


@pytest.mark.parametrize("change", ["missing", "duplicate", "freeze", "inputs"])
def test_incomplete_or_changed_comparisons_fail_closed(tmp_path: Path, change: str) -> None:
    reports(tmp_path)
    path = tmp_path / "cases/model_backed.json"
    row = json.loads(path.read_text())
    if change == "missing":
        path.unlink()
    elif change == "duplicate":
        (tmp_path / "cases/duplicate.json").write_text(path.read_text())
    else:
        if change == "freeze":
            row["freeze_hash"] = "changed"
        else:
            row["setup"]["observable_world_hash"] = "changed"
        path.write_text(json.dumps(row))
    with pytest.raises(ValueError):
        summarize(tmp_path)
