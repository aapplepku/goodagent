"""Leased PostgreSQL jobs delivered through a disposable Redis queue."""

import json
from datetime import timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from arq.connections import ArqRedis
from sqlalchemy import literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import activate_catalog
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.measurement import assess_window
from open_commerce.controller.models import (
    ActionAuditEntry,
    MeasurementSchedule,
    PolicyViolationError,
)
from open_commerce.controller.workflow import append_trace
from open_commerce.core.enums import ActionStatus, ActorRole, GoalStatus
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.runs import ManagerRunService
from open_commerce.persistence.models.actions import Intervention, InterventionOutcome
from open_commerce.persistence.models.goals import Goal
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.integrations import Integration
from open_commerce.persistence.models.manager_runs import ManagerRunRecord
from open_commerce.persistence.models.ranking import RankingModelRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.service import RankingService
from open_commerce.search.durable import DurableSearchService
from open_commerce.simulator.durable import load_state


def serialize_job(value: dict[str, object]) -> bytes:
    """ARQ's default pickle codec is deliberately not used."""
    return json.dumps(
        value, default=lambda item: type(item).__name__, separators=(",", ":")
    ).encode()


def deserialize_job(value: bytes) -> dict[str, object]:
    if len(value) > 16384:
        raise ValueError("job envelope exceeds limit")
    payload: object = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("job envelope must be an object")
    return cast(dict[str, object], payload)


class JobRunner:
    """A worker is explicitly assigned one tenant in this local-demo release."""

    def __init__(
        self,
        database: RuntimeDatabase,
        tenant_id: UUID,
        *,
        lease_seconds: float | None = None,
        search_service: DurableSearchService | None = None,
    ) -> None:
        self.database = database
        self.tenant_id = tenant_id
        self.lease_seconds = (
            database.settings.worker_job_timeout_seconds + 30
            if lease_seconds is None
            else lease_seconds
        )
        self.search_service = search_service

    async def publish_due(self, redis: ArqRedis) -> int:
        async with self.database.transaction(self.tenant_id) as session:
            ranking_jobs = list(
                await session.scalars(
                    select(RankingModelRecord)
                    .where(
                        RankingModelRecord.tenant_id == self.tenant_id,
                        or_(
                            RankingModelRecord.status == "queued",
                            (RankingModelRecord.status == "running")
                            & (RankingModelRecord.lease_until <= utc_now()),
                        ),
                    )
                    .limit(10)
                )
            )
        for ranking_job in ranking_jobs:
            await redis.enqueue_job(
                "process_ranking_job",
                str(self.tenant_id),
                str(ranking_job.id),
                _job_id=f"ranking:{ranking_job.id}:{int(utc_now().timestamp()) // 30}",
                _expires=60,
            )
        if self.database.settings.runtime_profile == "legacy_demo":
            await DurableControllerService(self.database).schedule_due_cycles(
                tenant_id=self.tenant_id
            )
        async with self.database.transaction(self.tenant_id) as session:
            rows = list(
                await session.scalars(
                    select(WorkflowJob)
                    .where(
                        WorkflowJob.tenant_id == self.tenant_id,
                        literal(self.database.settings.runtime_profile == "legacy_demo"),
                        WorkflowJob.available_at <= utc_now(),
                        or_(
                            WorkflowJob.status == "pending",
                            (WorkflowJob.status == "running")
                            & (WorkflowJob.lease_until <= utc_now()),
                        ),
                    )
                    .order_by(WorkflowJob.available_at, WorkflowJob.id)
                    .limit(50)
                )
            )
        for row in rows:
            await redis.enqueue_job(
                "process_workflow_job",
                str(self.tenant_id),
                str(row.id),
                _job_id=f"workflow:{row.id}:{row.attempts}:{int(utc_now().timestamp()) // 30}",
                _expires=60,
            )
        async with self.database.transaction(self.tenant_id) as session:
            catalog_rows = list(
                await session.scalars(
                    select(CatalogIndexJob)
                    .where(
                        CatalogIndexJob.tenant_id == self.tenant_id,
                        CatalogIndexJob.available_at <= utc_now(),
                        or_(
                            CatalogIndexJob.status == "queued",
                            (CatalogIndexJob.status == "running")
                            & (CatalogIndexJob.lease_until <= utc_now()),
                        ),
                    )
                    .order_by(CatalogIndexJob.available_at, CatalogIndexJob.id)
                    .limit(10)
                )
            )
        for catalog_job in catalog_rows:
            await redis.enqueue_job(
                "process_catalog_index_job",
                str(self.tenant_id),
                str(catalog_job.id),
                _job_id=(
                    f"catalog-index:{catalog_job.id}:{catalog_job.attempts}:"
                    f"{int(utc_now().timestamp()) // 30}"
                ),
                _expires=60,
            )
        async with self.database.transaction(self.tenant_id) as session:
            runs = list(
                await session.scalars(
                    select(ManagerRunRecord)
                    .where(
                        ManagerRunRecord.tenant_id == self.tenant_id,
                        ManagerRunRecord.available_at <= utc_now(),
                        or_(
                            ManagerRunRecord.status.in_(["queued", "waiting"]),
                            (ManagerRunRecord.status == "running")
                            & (ManagerRunRecord.lease_until <= utc_now()),
                        ),
                    )
                    .limit(20)
                )
            )
        for run in runs:
            await redis.enqueue_job(
                "process_manager_run",
                str(self.tenant_id),
                str(run.id),
                _job_id=f"manager:{run.id}:{int(utc_now().timestamp()) // 3}",
                _expires=30,
            )
        return len(rows) + len(catalog_rows) + len(runs) + len(ranking_jobs)

    async def run(self, job_id: UUID) -> bool:
        async with self.database.transaction(self.tenant_id, write=True) as session:
            job = await self._get(session, job_id)
            if job is None or job.status in {"completed", "cancelled", "dead_letter"}:
                return False
            if job.available_at > utc_now() or (
                job.lease_until and job.lease_until > utc_now() and job.status == "running"
            ):
                return False
            token = uuid4()
            job.lease_token = token
            job.lease_until = utc_now() + timedelta(seconds=self.lease_seconds)
            job.status = "running"
            job.attempts += 1
            job.updated_at = utc_now()
        try:
            done = await self._dispatch(job)
        except PolicyViolationError:
            if job.action_id:
                await DurableControllerService(self.database).cancel_unstarted_action(
                    tenant_id=self.tenant_id,
                    action_id=job.action_id,
                )
            await self._finish(job_id, token, "cancelled", "SAFETY_GATE_CLOSED")
            return False
        except Exception as exc:
            await self._finish(
                job_id,
                token,
                "pending",
                type(exc).__name__,
            )
            raise
        await self._finish(job_id, token, "completed" if done else "pending", None)
        return done

    async def run_catalog_index(self, job_id: UUID) -> bool:
        """Lease, build, and atomically activate one uploaded catalog index."""

        async with self.database.transaction(self.tenant_id, write=True) as session:
            job = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == self.tenant_id,
                    CatalogIndexJob.id == job_id,
                )
            )
            if job is None or job.status in {"ready", "failed"}:
                return False
            if job.available_at > utc_now() or (
                job.lease_until and job.lease_until > utc_now() and job.status == "running"
            ):
                return False
            token = uuid4()
            job.status = "running"
            job.lease_token = token
            job.lease_until = utc_now() + timedelta(seconds=self.lease_seconds)
            job.attempts += 1
            job.updated_at = utc_now()
            integration_id = job.integration_id
            source_version = job.source_version
            expected_count = job.product_count
        service = self.search_service or DurableSearchService(self.database)
        try:
            from open_commerce.stores.assets import prepare_asset_batch

            if not await prepare_asset_batch(
                self.database, self.tenant_id, integration_id, job_id, token
            ):
                async with self.database.transaction(self.tenant_id, write=True) as session:
                    pending = await session.scalar(
                        select(CatalogIndexJob).where(
                            CatalogIndexJob.tenant_id == self.tenant_id,
                            CatalogIndexJob.id == job_id,
                            CatalogIndexJob.lease_token == token,
                        )
                    )
                    if pending is not None:
                        pending.status = "queued"
                        pending.lease_token = None
                        pending.lease_until = None
                        pending.available_at = utc_now()
                return False
            count = await service.prepare_uploaded_catalog_index(
                tenant_id=self.tenant_id,
                integration_id=integration_id,
                source_version=source_version,
            )
            if count != expected_count:
                raise ValueError("catalog index count does not match the staged snapshot")
            completed_at = utc_now()
            async with self.database.transaction(self.tenant_id, write=True) as session:
                current = await session.scalar(
                    select(CatalogIndexJob).where(
                        CatalogIndexJob.tenant_id == self.tenant_id,
                        CatalogIndexJob.id == job_id,
                        CatalogIndexJob.lease_token == token,
                    )
                )
                if current is None:
                    return False
                await activate_catalog(
                    session,
                    tenant_id=self.tenant_id,
                    integration_id=integration_id,
                    indexed_count=count,
                    completed_at=completed_at,
                )
            return True
        except Exception as exc:
            await self._finish_catalog_failure(job_id, token, type(exc).__name__)
            raise
        finally:
            if self.search_service is None:
                await service.close()

    async def _finish_catalog_failure(self, job_id: UUID, token: UUID, code: str) -> None:
        async with self.database.transaction(self.tenant_id, write=True) as session:
            job = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == self.tenant_id,
                    CatalogIndexJob.id == job_id,
                )
            )
            if job is None or job.lease_token != token:
                return
            job.failures += 1
            terminal = job.failures >= 5
            job.status = "failed" if terminal else "queued"
            job.safe_error = {
                "code": code[:120],
                "message": "Catalog indexing failed without exposing source data.",
                "retryable": not terminal,
            }
            job.lease_until = None
            job.lease_token = None
            job.available_at = utc_now() + timedelta(seconds=min(60, 2**job.failures))
            job.updated_at = utc_now()
            if terminal:
                integration = await session.scalar(
                    select(Integration).where(
                        Integration.tenant_id == self.tenant_id,
                        Integration.id == job.integration_id,
                    )
                )
                if integration is not None:
                    integration.status = "failed"
                    integration.updated_at = utc_now()

    async def _dispatch(self, job: WorkflowJob) -> bool:
        service = DurableControllerService(self.database)
        if job.kind == "plan" and job.run_id:
            run = await service.process_run(tenant_id=self.tenant_id, run_id=job.run_id)
            if run.summary.get("planning_mode") == "model_backed" and run.status == "running":
                from open_commerce.controller.model_planning import checkpoint_for

                checkpoint = checkpoint_for(run)
                return checkpoint is not None and checkpoint.status == "compiled"
            return True
        if job.kind in {"execute", "reconcile"} and job.action_id:
            record = await service.execute_action(
                tenant_id=self.tenant_id,
                action_id=job.action_id,
                idempotency_key=f"workflow:{job.id}",
            )
            return record.action.status != ActionStatus.UNCERTAIN
        if job.kind == "measure" and job.action_id and job.instance_id and job.goal_id:
            return await self._measure(job)
        raise ValueError("unsupported or incomplete workflow job")

    async def _measure(self, job: WorkflowJob) -> bool:
        assert job.action_id is not None and job.instance_id is not None and job.goal_id is not None
        async with self.database.transaction(self.tenant_id, write=True) as session:
            intervention = await session.scalar(
                select(Intervention).where(
                    Intervention.tenant_id == self.tenant_id,
                    Intervention.action_id == job.action_id,
                )
            )
            if intervention is None or intervention.status in {"measured", "rolled_back"}:
                return True
            state = await load_state(session, self.tenant_id, job.instance_id)
            schedule = MeasurementSchedule.model_validate(intervention.monitor_spec)
            assessment = assess_window(schedule, state)
            breached = bool(assessment.reason_codes)
            goal_status = await session.scalar(
                select(Goal.status).where(Goal.tenant_id == self.tenant_id, Goal.id == job.goal_id)
            )
            archived_early = (
                goal_status == GoalStatus.ARCHIVED.value and state.current_time < schedule.ends_at
            )
            if not breached and not archived_early and state.current_time < schedule.ends_at:
                return False
            repo = ControllerRepository(session, self.tenant_id)
            record = await repo.get_action(job.action_id)
            goal = await repo.get_goal(record.action.goal_id)
            run = await repo.get_run(record.action.run_id)
            status = (
                "breached"
                if breached
                else "insufficient_data"
                if archived_early
                else "clear"
                if assessment.enough_data
                else "insufficient_data"
            )
            results = {
                **assessment.totals.model_dump(mode="json"),
                "reason_codes": assessment.reason_codes,
                "window_start_at": schedule.starts_at.isoformat(),
                "window_end_at": min(schedule.ends_at, state.current_time).isoformat(),
                "baseline_kind": schedule.baseline_kind,
                "baseline_totals": schedule.baseline_totals,
                "minimum_sample": schedule.minimum_sample,
                "minimum_days": schedule.minimum_days,
                "review_required": breached,
                "rollback_recommended_for_review": breached
                and record.action.rollback_plan.available,
            }
            if archived_early:
                results["termination_reason"] = "goal_archived"
            session.add(
                InterventionOutcome(
                    id=uuid5(NAMESPACE_URL, f"{intervention.id}:outcome"),
                    tenant_id=self.tenant_id,
                    intervention_id=intervention.id,
                    evaluated_at=utc_now(),
                    metric_results=results,
                    method="observational_window_not_causal",
                    sample_size=assessment.totals.sessions,
                    conclusion=(
                        "Aggregate outcomes include other interventions; no causal attribution. "
                        + (
                            "Guardrail breach requires human review before further execution."
                            if breached
                            else "Goal archived before the window ended; no safety conclusion."
                            if archived_early
                            else "Sample threshold not met; no safety conclusion."
                            if not assessment.enough_data
                            else "Configured guardrails did not breach in this observed window."
                        )
                    ),
                    guardrail_status=status,
                )
            )
            intervention.status = "measured"
            if breached and goal.spec.status == GoalStatus.ACTIVE:
                goal.spec.status = GoalStatus.PAUSED
                goal.updated_at = utc_now()
                await repo.save_goal(goal)
            run.summary["measurement_review_required"] = (
                bool(run.summary.get("measurement_review_required")) or breached
            )
            await repo.save_run(run)
            await append_trace(
                repo,
                run,
                "schedule_measurement",
                "Persisted observed outcome and guardrail assessment",
                {
                    "action_id": str(job.action_id),
                    "guardrail_status": status,
                    "reason_codes": assessment.reason_codes,
                    "goal_status": goal.spec.status.value,
                },
            )
            repo.append_audit(
                ActionAuditEntry(
                    id=uuid5(NAMESPACE_URL, f"{intervention.id}:measurement-audit"),
                    tenant_id=self.tenant_id,
                    action_id=job.action_id,
                    event_type="outcome_measured",
                    actor_role=ActorRole.SYSTEM,
                    message="Observed outcome persisted; no causal lift claimed",
                    occurred_at=utc_now(),
                    details={"guardrail_status": status, "reason_codes": assessment.reason_codes},
                ),
                record.action.run_id,
            )
            return True

    async def _get(self, session: AsyncSession, job_id: UUID) -> WorkflowJob | None:
        job: WorkflowJob | None = await session.scalar(
            select(WorkflowJob).where(
                WorkflowJob.tenant_id == self.tenant_id, WorkflowJob.id == job_id
            )
        )
        return job

    async def _finish(self, job_id: UUID, token: UUID, status: str, error: str | None) -> None:
        async with self.database.transaction(self.tenant_id, write=True) as session:
            job = await self._get(session, job_id)
            if job is None or job.lease_token != token:
                return
            if error and status == "pending":
                job.failures += 1
                if job.failures >= 10:
                    status = "dead_letter"
            elif error is None:
                job.failures = 0
            job.status = status
            job.error_code = error
            job.lease_until = None
            job.lease_token = None
            job.available_at = utc_now() + timedelta(
                seconds=min(60, 2 ** min(job.failures, 6)) if error else 5
            )
            job.updated_at = utc_now()


async def process_workflow_job(ctx: dict[str, object], tenant_id: str, job_id: str) -> bool:
    runner = await runner_for_store(ctx, tenant_id)
    if runner.database.settings.runtime_profile != "legacy_demo":
        return False
    return await runner.run(UUID(job_id))


async def process_catalog_index_job(ctx: dict[str, object], tenant_id: str, job_id: str) -> bool:
    runner = await runner_for_store(ctx, tenant_id)
    return await runner.run_catalog_index(UUID(job_id))


async def process_ranking_job(ctx: dict[str, object], tenant_id: str, job_id: str) -> bool:
    runner = await runner_for_store(ctx, tenant_id)
    return await RankingService(runner.database).run(runner.tenant_id, UUID(job_id))


async def process_manager_run(ctx: dict[str, object], tenant_id: str, job_id: str) -> bool:
    from open_commerce.runtime_services import manager_service

    runner = await runner_for_store(ctx, tenant_id)
    search = DurableSearchService(runner.database)
    try:
        return await ManagerRunService(runner.database).process(
            tenant_id=runner.tenant_id,
            run_id=UUID(job_id),
            service=manager_service(runner.database, search),
        )
    finally:
        await search.close()


async def runner_for_store(ctx: dict[str, object], raw_tenant: str) -> JobRunner:
    runner = ctx["runner"]
    if not isinstance(runner, JobRunner):
        raise ValueError("Worker is not configured")
    tenant_id = UUID(raw_tenant)
    if runner.database.settings.runtime_profile == "legacy_demo":
        if tenant_id != runner.tenant_id:
            raise ValueError("Worker tenant mismatch")
        return runner
    async with runner.database.transaction(tenant_id) as session:
        eligible = await session.scalar(
            select(StoreSetupRecord.tenant_id)
            .join(Tenant)
            .where(
                StoreSetupRecord.tenant_id == tenant_id,
                Tenant.id == tenant_id,
                Tenant.status == "active",
            )
        )
    if eligible is None:
        raise ValueError("Worker store is unavailable")
    return JobRunner(runner.database, tenant_id)
