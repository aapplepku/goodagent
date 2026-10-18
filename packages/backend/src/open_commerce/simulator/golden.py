"""Golden simulator run helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from uuid import UUID

from open_commerce.core.types import canonical_hash
from open_commerce.simulator.engine import totals_for_metrics
from open_commerce.simulator.models import ENGINE_VERSION, MetricTotals
from open_commerce.simulator.service import SimulatorService

GOLDEN_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class GoldenResult:
    """Stable golden result line."""

    scenario_id: str
    seed: int
    days: int
    result_hash: str
    totals: MetricTotals


def run_golden_suite() -> list[GoldenResult]:
    """Run deterministic golden scenarios and return result hashes."""

    cases = [
        ("acquisition_v1", 42, 30),
        ("excess_inventory_v1", 42, 30),
        ("search_conversion_v1", 42, 30),
    ]
    return [
        _run_case(scenario_id=scenario_id, seed=seed, days=days)
        for scenario_id, seed, days in cases
    ]


def verify_golden_suite() -> list[GoldenResult]:
    """Compare every case with the versioned, generated reference artifact."""

    results = run_golden_suite()
    reference = json.loads(files(__package__).joinpath("golden_reference.json").read_text())
    if reference["engine_version"] != ENGINE_VERSION:
        raise SystemExit("golden engine version does not match the current engine")
    expected = {
        (item["scenario_id"], item["seed"], item["days"]): item["result_hash"]
        for item in reference["results"]
    }
    if set(expected) != {(item.scenario_id, item.seed, item.days) for item in results}:
        raise SystemExit("golden case set does not match the current suite")
    mismatches = [
        result
        for result in results
        if expected[(result.scenario_id, result.seed, result.days)] != result.result_hash
    ]
    if mismatches:
        details = ", ".join(
            f"{item.scenario_id}/seed={item.seed}/days={item.days}: {item.result_hash}"
            for item in mismatches
        )
        raise SystemExit(f"simulator golden mismatch: {details}")
    return results


def _run_case(*, scenario_id: str, seed: int, days: int) -> GoldenResult:
    service = SimulatorService()
    created = service.create_instance(
        tenant_id=GOLDEN_TENANT_ID,
        scenario_id=scenario_id,
        seed=seed,
        idempotency_key=f"golden-create:{scenario_id}:{seed}",
    )
    service.advance(
        tenant_id=GOLDEN_TENANT_ID,
        instance_id=created.id,
        hours=days * 24,
        idempotency_key=f"golden-run:{scenario_id}:{seed}:{days}",
    )
    state = service.get_full_state(tenant_id=GOLDEN_TENANT_ID, instance_id=created.id)
    totals = totals_for_metrics(state.metrics, include_history=False)
    result_hash = canonical_hash(
        {
            "scenario_id": scenario_id,
            "scenario_version": state.scenario_version,
            "seed": seed,
            "days": days,
            "state_hash": state.state_hash,
            "totals": totals,
        }
    )
    return GoldenResult(
        scenario_id=scenario_id,
        seed=seed,
        days=days,
        result_hash=result_hash,
        totals=totals,
    )
