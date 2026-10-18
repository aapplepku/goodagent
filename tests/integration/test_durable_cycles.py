"""Real database approval continuation and virtual-time scheduling regressions."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import ControllerRunRequest, GoalCreateRequest
from open_commerce.core.enums import ActionStatus, ActionType, GoalStatus
from open_commerce.persistence.models.actions import Intervention, InterventionOutcome
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner

from .test_durable_controller import approve

pytestmark = pytest.mark.integration


async def jobs_of_kind(database: RuntimeDatabase, tenant_id: UUID, kind: str) -> list[UUID]:
    async with database.transaction(tenant_id) as session:
        return list(
            await session.scalars(
                select(WorkflowJob.id)
                .where(
                    WorkflowJob.tenant_id == tenant_id,
                    WorkflowJob.kind == kind,
                    WorkflowJob.status == "pending",
                )
                .order_by(WorkflowJob.created_at, WorkflowJob.id)
            )
        )


async def test_approval_resumes_same_run_and_completion_waits_for_execution(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant_id,
            request=GoalCreateRequest(allowed_action_types={ActionType.SET_CAMPAIGN_BUDGET}),
            idempotency_key="goal",
        )
        await service.set_goal_status(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        queued = await service.run_goal(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="run",
        )
        runner = JobRunner(database, tenant_id)
        for job_id in await jobs_of_kind(database, tenant_id, "plan"):
            assert await runner.run(job_id)
        records = (await service.list_actions(tenant_id=tenant_id, run_id=queued.id)).items
        action = next(
            item for item in records if item.action.status == ActionStatus.AWAITING_APPROVAL
        )
        await approve(database, tenant_id, action.action.id)
        approved = await service.get_run(tenant_id=tenant_id, run_id=queued.id)
        assert approved.status == "running"
        assert approved.completed_at is None
        await database.close()
        database = RuntimeDatabase(integration_settings)
        service = DurableControllerService(database)
        for key in ("resume-one", "resume-two"):
            resumed = await service.resume_run(
                tenant_id=tenant_id,
                run_id=queued.id,
                idempotency_key=key,
            )
            assert resumed.id == queued.id and resumed.status == "running"
        execute_jobs = await jobs_of_kind(database, tenant_id, "execute")
        assert len(execute_jobs) == 1
        runner = JobRunner(database, tenant_id)
        assert await runner.run(execute_jobs[0])
        assert not await runner.run(execute_jobs[0])
        completed = await service.get_run(tenant_id=tenant_id, run_id=queued.id)
        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert completed.summary["succeeded_actions"] == 1
        assert any(event.node == "reconcile" for event in completed.trace)
    finally:
        await database.close()


async def test_repeated_cycles_reload_ids_and_measure_after_database_restart(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant_id,
            request=GoalCreateRequest(
                horizon_days=8,
                allowed_action_types={ActionType.SET_CAMPAIGN_BUDGET},
            ),
            idempotency_key="goal",
        )
        await service.set_goal_status(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        await service.run_goal(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="first",
        )
        for day in range(8):
            runner = JobRunner(database, tenant_id)
            for job_id in await jobs_of_kind(database, tenant_id, "plan"):
                assert await runner.run(job_id)
            records = (await service.list_actions(tenant_id=tenant_id, goal_id=goal.spec.id)).items
            for record in records:
                if record.action.status == ActionStatus.AWAITING_APPROVAL:
                    await approve(database, tenant_id, record.action.id)
            for job_id in await jobs_of_kind(database, tenant_id, "execute"):
                await runner.run(job_id)
            await service.simulator_service.advance(
                tenant_id=tenant_id,
                instance_id=goal.simulator_instance_id,
                hours=24,
                idempotency_key=f"day-{day}",
            )
            # Recovery performs no in-memory reconstruction or ad-hoc job injection.
            await database.close()
            database = RuntimeDatabase(integration_settings)
            service = DurableControllerService(database)
            await service.schedule_due_cycles(tenant_id=tenant_id)
            assert await service.schedule_due_cycles(tenant_id=tenant_id) == 0
        runs = (await service.list_runs(tenant_id=tenant_id, goal_id=goal.spec.id)).items
        assert len(runs) == 8
        assert all(run.status == "completed" and run.snapshot is not None for run in runs)
        assert len({run.id for run in runs}) == 8
        assert (
            await service.get_goal(tenant_id=tenant_id, goal_id=goal.spec.id)
        ).spec.status == GoalStatus.COMPLETED
        runner = JobRunner(database, tenant_id)
        for job_id in await jobs_of_kind(database, tenant_id, "measure"):
            await runner.run(job_id)
        async with database.transaction(tenant_id) as session:
            outcomes = list(
                await session.scalars(
                    select(InterventionOutcome).where(
                        InterventionOutcome.tenant_id == tenant_id,
                    )
                )
            )
            assert outcomes
            assert all(item.sample_size is not None and item.sample_size > 0 for item in outcomes)
            assert all(item.method == "observational_window_not_causal" for item in outcomes)
            interventions = list(
                await session.scalars(
                    select(Intervention).where(
                        Intervention.tenant_id == tenant_id,
                    )
                )
            )
            assert all(
                item.ends_at is not None and item.ends_at <= goal.spec.horizon.end_at
                for item in interventions
            )
            assert len(outcomes) == len(interventions)
    finally:
        await database.close()


async def test_expired_approval_cannot_stall_next_virtual_day(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant_id,
            request=GoalCreateRequest(),
            idempotency_key="goal",
        )
        await service.set_goal_status(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        queued = await service.run_goal(
            tenant_id=tenant_id,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="first",
        )
        await service.process_run(tenant_id=tenant_id, run_id=queued.id)
        await service.simulator_service.advance(
            tenant_id=tenant_id,
            instance_id=goal.simulator_instance_id,
            hours=24,
            idempotency_key="day",
        )
        assert await service.schedule_due_cycles(tenant_id=tenant_id) == 1
        actions = (await service.list_actions(tenant_id=tenant_id, run_id=queued.id)).items
        assert any(item.action.status == ActionStatus.EXPIRED for item in actions)
        assert not any(item.action.status == ActionStatus.SUCCEEDED for item in actions)
        assert (await service.get_run(tenant_id=tenant_id, run_id=queued.id)).status == "completed"
    finally:
        await database.close()
