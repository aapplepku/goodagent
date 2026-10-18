"""The release harness must execute and reproduce actual durable simulator effects."""

import pytest

from open_commerce.config import Settings
from open_commerce.controller.benchmark import run_case
from open_commerce.controller.benchmark_command import scratch_database
from open_commerce.core.types import canonical_hash

pytestmark = pytest.mark.integration


async def test_durable_benchmark_executes_and_reproduces(integration_settings: Settings) -> None:
    hashes = []
    for _ in range(2):
        async with scratch_database(integration_settings) as database:
            row = await run_case(
                database,
                scenario="acquisition_v1",
                seed=42,
                variant="standard",
                arm="goal_conditioned_controller",
                days=3,
            )
            assert row.hard_violations == []
            assert row.executed_actions > 0
            assert row.outcome_count > 0
            assert len(row.daily) == 3
            assert row.dispatch_checks
            assert all(check["rules"] for check in row.dispatch_checks)
            hashes.append(canonical_hash(row))
            with pytest.raises(ValueError, match="fresh database"):
                await run_case(
                    database,
                    scenario="acquisition_v1",
                    seed=42,
                    variant="standard",
                    arm="goal_conditioned_controller",
                    days=3,
                )
    assert hashes[0] == hashes[1]
