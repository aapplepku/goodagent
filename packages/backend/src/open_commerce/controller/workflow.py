"""Durable workflow bookkeeping, always inside the caller's tenant write transaction."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert

from open_commerce.controller.models import (
    ControllerNode,
    ControllerRunRecord,
    ControllerTraceEvent,
)
from open_commerce.core.enums import ActionStatus
from open_commerce.core.types import JsonObject, utc_now
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.controller import ControllerRepository


async def enqueue(
    repo: ControllerRepository,
    kind: str,
    *,
    goal_id: UUID | None = None,
    run_id: UUID | None = None,
    action_id: UUID | None = None,
) -> UUID:
    job_id = uuid5(NAMESPACE_URL, f"{repo.tenant_id}:job:{kind}:{goal_id}:{run_id}:{action_id}")
    await repo.session.execute(
        insert(WorkflowJob)
        .values(
            id=job_id,
            tenant_id=repo.tenant_id,
            kind=kind,
            goal_id=goal_id,
            run_id=run_id,
            action_id=action_id,
            status="pending",
            available_at=utc_now(),
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=[WorkflowJob.id])
    )
    return job_id


async def append_trace(
    repo: ControllerRepository,
    run: ControllerRunRecord,
    node: ControllerNode,
    message: str,
    details: JsonObject | None = None,
) -> None:
    sequence = len(run.trace) + 1
    event = ControllerTraceEvent(
        id=uuid5(NAMESPACE_URL, f"{run.id}:trace:{sequence}"),
        tenant_id=repo.tenant_id,
        run_id=run.id,
        sequence=sequence,
        node=node,
        occurred_at=utc_now(),
        message=message,
        details=details or {},
    )
    await repo.append_trace(event)
    run.trace.append(event)


async def refresh_run(repo: ControllerRepository, run_id: UUID) -> ControllerRunRecord:
    """Execution/approval work must finish before a planning cycle is complete."""
    await repo.session.flush()
    run = await repo.get_run(run_id)
    if run.status in {"cancelled", "failed"} or run.snapshot is None:
        return run
    if run.summary.get("planning_mode") == "model_backed":
        from open_commerce.controller.model_planning import checkpoint_for

        checkpoint = checkpoint_for(run)
        if checkpoint is None or checkpoint.status != "compiled":
            return run
    records = await repo.list_actions(run_id=run_id)
    statuses = [record.action.status for record in records]
    pending = sum(status == ActionStatus.AWAITING_APPROVAL for status in statuses)
    unfinished = {
        ActionStatus.APPROVED,
        ActionStatus.EXECUTABLE,
        ActionStatus.EXECUTING,
        ActionStatus.UNCERTAIN,
        ActionStatus.ROLLING_BACK,
    }
    old_status = run.status
    run.status = (
        "awaiting_approval"
        if pending
        else "running"
        if any(status in unfinished for status in statuses)
        else "completed"
    )
    run.summary.update(
        {
            "awaiting_approval_actions": pending,
            "unfinished_actions": sum(status in unfinished for status in statuses),
            "succeeded_actions": sum(
                status in {ActionStatus.SUCCEEDED, ActionStatus.EVALUATING, ActionStatus.COMPLETED}
                for status in statuses
            ),
        }
    )
    run.completed_at = (run.completed_at or utc_now()) if run.status == "completed" else None
    await repo.save_run(run)
    if old_status != run.status:
        await append_trace(
            repo,
            run,
            "summarize",
            "Run status derived from durable action records",
            {"previous_status": old_status, "status": run.status},
        )
    return run
