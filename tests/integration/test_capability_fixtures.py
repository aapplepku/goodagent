"""Registered case setup uses observed history and actual prior execution evidence."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.capability_fixtures import CapabilityCase, prepare_case
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration
CASES = [
    CapabilityCase.model_validate(c)
    for c in json.loads(Path("examples/eval/capability-v1/cases.json").read_text())
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
async def test_registered_fixture_setup_is_real_and_balanced(
    integration_settings: Settings, case: CapabilityCase
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        left = await prepare_case(database, uuid4(), case, 11, "no_intervention")
        right = await prepare_case(database, uuid4(), case, 11, "deterministic")
        assert left.observable_world_hash == right.observable_world_hash
        assert left.starting_budgets == right.starting_budgets
        assert left.incremental_target == right.incremental_target
        assert left.initial_objective_value == right.initial_objective_value
        assert all(left.checks.values()), left.checks
        assert left.goal.revision == 2
        assert (
            left.goal.spec.horizon.end_at - left.goal.spec.horizon.start_at
        ).days == 10 + left.start_day
    finally:
        await database.close()
