"""Keep example contracts and generated pre-launch measurements reproducible."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from open_commerce.controller.models import GoalCreateRequest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("source", sorted((ROOT / "examples/goals").glob("*.json")))
def test_documented_goal_is_a_valid_typed_request(source: Path) -> None:
    request = GoalCreateRequest.model_validate(json.loads(source.read_text()))
    assert request.seed == 42
    assert request.default_mode == "approval_required"


def test_benchmark_overview_matches_all_reference_evidence() -> None:
    subprocess.run(
        [sys.executable, "scripts/render-preview-benchmarks.py", "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
