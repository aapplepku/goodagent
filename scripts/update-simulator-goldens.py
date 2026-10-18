"""Explicitly regenerate every simulator reference after reviewing an engine change."""

import json
from pathlib import Path

from open_commerce.simulator.golden import run_golden_suite
from open_commerce.simulator.models import ENGINE_VERSION


def main() -> None:
    results = run_golden_suite()
    payload = {
        "engine_version": ENGINE_VERSION,
        "results": [
            {
                "scenario_id": item.scenario_id,
                "seed": item.seed,
                "days": item.days,
                "result_hash": item.result_hash,
                "totals": item.totals.model_dump(mode="json"),
            }
            for item in results
        ],
    }
    path = Path(__file__).resolve().parents[1] / (
        "packages/backend/src/open_commerce/simulator/golden_reference.json"
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Generated {len(results)} complete reference cases for {ENGINE_VERSION}: {path}")


if __name__ == "__main__":
    main()
