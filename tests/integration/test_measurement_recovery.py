"""Outcome review and pause are durable and do not dispatch a speculative rollback."""

from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import func, select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import (
    ControllerRunRequest,
    GoalCreateRequest,
    PolicyUpdateRequest,
)
from open_commerce.core.enums import GoalStatus
from open_commerce.persistence.models.actions import InterventionOutcome
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner

from .test_durable_controller import approve, prepared_goal
from .test_worker_retries import make_due

pytestmark = pytest.mark.integration


async def test_archived_goal_closes_measurement_without_losing_history(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    try:
        tenant, run_id, action_id = await prepared_goal(database, "set_campaign_budget")
        service = DurableControllerService(database)
        await approve(database, tenant, action_id)
        action = await service.execute_action(
            tenant_id=tenant, action_id=action_id, idempotency_key="execute"
        )
        run_before = await service.get_run(tenant_id=tenant, run_id=run_id)
        job_id = uuid5(NAMESPACE_URL, f"{action_id}:measure")
        assert not await JobRunner(database, tenant).run(job_id)
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=action.action.goal_id,
            status=GoalStatus.ARCHIVED,
            idempotency_key="archive",
        )
        await database.close()
        database = RuntimeDatabase(integration_settings)
        await make_due(database, tenant, job_id)
        assert await JobRunner(database, tenant).run(job_id)
        await database.close()
        database = RuntimeDatabase(integration_settings)
        assert not await JobRunner(database, tenant).run(job_id)
        service = DurableControllerService(database)
        restored = await service.get_action(tenant_id=tenant, action_id=action_id)
        assert restored.execution_result == action.execution_result
        assert restored.approval == action.approval
        assert restored.outcome is not None
        assert restored.outcome.guardrail_status == "insufficient_data"
        assert restored.outcome.metric_results["termination_reason"] == "goal_archived"
        assert restored.outcome.metric_results["review_required"] is False
        assert len([item for item in restored.audit if item.event_type == "outcome_measured"]) == 1
        run_after = await service.get_run(tenant_id=tenant, run_id=run_id)
        assert run_after.trace[: len(run_before.trace)] == run_before.trace
        goal = await service.get_goal(tenant_id=tenant, goal_id=action.action.goal_id)
        assert goal.spec.status == GoalStatus.ARCHIVED
    finally:
        await database.close()


@pytest.mark.parametrize("hours", [24, 48])
async def test_measurement_persists_inconclusive_or_breach_across_restart(
    integration_settings: Settings, hours: int
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    try:
        service = DurableControllerService(database)
        await service.update_policy(
            tenant_id=tenant,
            request=PolicyUpdateRequest(discount_minimum_margin_rate=Decimal("0.999")),
            idempotency_key="strict-monitor",
        )
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(
                scenario_id="search_conversion_v1",
                target_value=Decimal("10000"),
                horizon_days=hours // 24,
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
        assert len(run.action_ids) == 1
        action_id = run.action_ids[0]
        await approve(database, tenant, action_id)
        await service.execute_action(
            tenant_id=tenant, action_id=action_id, idempotency_key="execute"
        )
        job_id = uuid5(NAMESPACE_URL, f"{action_id}:measure")
        assert not await JobRunner(database, tenant).run(job_id)
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=hours,
            idempotency_key="advance",
        )
        before = await service.simulator_service.get_full_state(
            tenant_id=tenant, instance_id=goal.simulator_instance_id
        )
        await database.close()
        database = RuntimeDatabase(integration_settings)
        service = DurableControllerService(database)
        await make_due(database, tenant, job_id)
        assert await JobRunner(database, tenant).run(job_id)
        assert not await JobRunner(database, tenant).run(job_id)
        await database.close()
        database = RuntimeDatabase(integration_settings)
        service = DurableControllerService(database)
        record = await service.get_action(tenant_id=tenant, action_id=action_id)
        assert record.measurement is not None
        assert record.measurement.baseline_kind == "historical_prior"
        assert record.measurement.baseline_totals["sessions"]
        assert record.outcome is not None
        assert record.outcome.guardrail_status == (
            "breached" if hours == 48 else "insufficient_data"
        )
        assert record.outcome.method == "observational_window_not_causal"
        assert record.outcome.metric_results["review_required"] == (hours == 48)
        assert len([entry for entry in record.audit if entry.event_type == "outcome_measured"]) == 1
        current_goal = await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
        assert current_goal.spec.status == (GoalStatus.PAUSED if hours == 48 else GoalStatus.ACTIVE)
        after = await service.simulator_service.get_full_state(
            tenant_id=tenant, instance_id=goal.simulator_instance_id
        )
        assert after.command_history == before.command_history
        async with database.transaction(tenant) as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(InterventionOutcome)
                    .where(InterventionOutcome.tenant_id == tenant)
                )
                == 1
            )
    finally:
        await database.close()
