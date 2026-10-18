"""Goal-conditioned evidence and outcomes reload from PostgreSQL, not process caches."""

from decimal import Decimal
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import ControllerRunRequest, GoalCreateRequest
from open_commerce.core.enums import GoalStatus
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.engine import totals_for_metrics

pytestmark = pytest.mark.integration


async def test_objective_assessment_proposals_and_progress_survive_restart(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    try:
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(
                scenario_id="excess_inventory_v1", target_value=Decimal("10000")
            ),
            idempotency_key="goal",
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="run",
        )
        run = await service.process_run(tenant_id=tenant, run_id=run.id)
        assert {draft.action_type.value for draft in run.intent_drafts} == {
            "create_discount",
            "set_search_boost",
        }
        assessment = run.summary["goal_assessment"]
        await database.close()
        database = RuntimeDatabase(integration_settings)
        service = DurableControllerService(database)
        replay = await service.process_run(tenant_id=tenant, run_id=run.id)
        assert replay.summary["goal_assessment"] == assessment
        assert replay.action_ids == run.action_ids
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=48,
            idempotency_key="advance",
        )
        state = await service.simulator_service.get_full_state(
            tenant_id=tenant, instance_id=goal.simulator_instance_id
        )
        progress = await service.goal_progress(tenant_id=tenant, goal_id=goal.spec.id)
        expected = sum(
            v.initial_inventory - v.inventory
            for p in state.products
            if p.excess_inventory
            for v in p.variants
        )
        assert progress.current_value == expected > 0
        assert progress.current_value is not None
        assert (
            progress.current_value
            < totals_for_metrics(state.metrics, include_history=False).units_sold
        )
        assert progress.assessment is not None and progress.assessment.scope == "excess_inventory"
    finally:
        await database.close()


async def test_infeasible_goal_persists_explanation_without_write_jobs(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    try:
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(target_value=Decimal("999999999")),
            idempotency_key="impossible",
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(execute_bounded_auto=True),
            idempotency_key="run",
        )
        run = await service.process_run(tenant_id=tenant, run_id=run.id)
        assert run.action_ids == []
        assert run.opportunities[0].type == "guardrail_review"
        await database.close()
        database = RuntimeDatabase(integration_settings)
        progress = await DurableControllerService(database).goal_progress(
            tenant_id=tenant, goal_id=goal.spec.id
        )
        assert progress.assessment is not None
        assert progress.assessment.feasibility == "infeasible"
        assert progress.pending_approvals == progress.executable_actions == 0
    finally:
        await database.close()
