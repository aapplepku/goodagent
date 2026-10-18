"""Regressions for the three retained capability-v1 deterministic day-zero failures."""

import json
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.capability_fixtures import execute_reviewed_run, prepare_case
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import ControllerRunRequest
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.telemetry.diagnostics import exception_diagnostic

from .test_capability_fixtures import CASES

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case_id", ["discount_margin_tradeoff", "inventory_constrained", "delayed_noisy_outcomes"]
)
async def test_retained_baseline_failure_runs_without_aborting_other_candidates(
    integration_settings: Settings, case_id: str
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    service = DurableControllerService(database)
    phase = "setup"
    failure = None
    try:
        case = next(c for c in CASES if c.id == case_id)
        setup = await prepare_case(database, tenant, case, 11, "deterministic")
        phase = "planning"
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=setup.goal.spec.id,
            request=ControllerRunRequest(execute_bounded_auto=False),
            idempotency_key="diagnostic:day:0",
        )
        completed = await service.process_run(tenant_id=tenant, run_id=run.id)
        if case_id == "delayed_noisy_outcomes":
            assert completed.summary["duplicate_candidates"]
        else:
            assert completed.summary["compiler_rejections"]
        phase = "reviewed_execution"
        await execute_reviewed_run(service, tenant, run.id)
    except Exception as exc:
        failure = {"case": case_id, "phase": phase, **exception_diagnostic(exc)}
    finally:
        await database.close()
    if failure is not None:
        pytest.fail(json.dumps(failure, sort_keys=True), pytrace=False)
