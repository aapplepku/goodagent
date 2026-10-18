"""Public reporting rejects partial, stale or selectively summarized evidence."""

import copy
import json
import runpy
from pathlib import Path

import pytest

render = runpy.run_path("scripts/render-controller-report.py")["render"]
SMOKE = json.loads(Path("examples/eval/results/controller-v2-smoke.json").read_bytes())


def test_complete_smoke_can_only_render_with_explicit_nonrelease_flag() -> None:
    with pytest.raises(ValueError, match="100 seeds"):
        render(SMOKE)
    report = render(SMOKE, allow_smoke=True)
    assert "SMOKE ONLY" in report
    assert report.count("### ") == 12
    assert "no_intervention" in report and "inventory_infeasible" in report
    assert "Hard-policy violations: **0**" in report


@pytest.mark.parametrize("tamper", ["incomplete", "failed_case", "raw", "summary", "seed"])
def test_incomplete_or_tampered_evidence_cannot_be_reported(tamper: str) -> None:
    data = copy.deepcopy(SMOKE)
    if tamper == "incomplete":
        data["complete"] = False
    elif tamper == "failed_case":
        data["failures"] = [{"error_type": "TimeoutError"}]
    elif tamper == "raw":
        data["rows"][0]["executed_actions"] += 1
    elif tamper == "summary":
        data["summary"][0]["action_count"]["mean"] = 100
    else:
        data["seeds"] += [999]
    with pytest.raises(ValueError):
        render(data, allow_smoke=True)
