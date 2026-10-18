"""Atomic reviewed revisions; completed effects and old evidence are never erased."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from open_commerce.controller.goal_revision import revise_goal
from open_commerce.controller.models import (
    ActionAuditEntry,
    GoalRecord,
    GoalUpdateRequest,
    PolicyViolationError,
)
from open_commerce.core.enums import ActionStatus, ActorRole
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.actions import ApprovalRequestRecord
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.actions import SqlActionRepository
from open_commerce.persistence.repositories.budgets import SqlBudgetRepository
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.simulator.durable import load_state


async def apply_goal_revision(
    repo: ControllerRepository, goal: GoalRecord, request: GoalUpdateRequest, virtual_time: datetime
) -> GoalRecord:
    updated = revise_goal(goal, request)
    if (updated.spec.merchandising is None) != (goal.spec.merchandising is None):
        raise PolicyViolationError("changing simulator profiles requires a fresh goal")
    if updated.spec.merchandising is not None:
        state = await load_state(repo.session, repo.tenant_id, goal.simulator_instance_id)
        if state.merchandising is None:
            raise PolicyViolationError("merchandising state is missing")
        if (
            updated.spec.merchandising.promotion_cap_minor
            < state.merchandising.promotion_spent_minor
        ):
            raise PolicyViolationError("promotion cap cannot remove redeemed capacity")
        state.merchandising.constraints = updated.spec.merchandising.model_copy(deep=True)
        await SqlSimulatorRepository(repo.session).save_state(state)
    if updated.spec.horizon.end_at <= virtual_time:
        raise PolicyViolationError("revised horizon must end after current simulator time")
    records = await repo.list_actions(goal_id=goal.spec.id)
    if any(
        record.action.status
        in {ActionStatus.EXECUTING, ActionStatus.UNCERTAIN, ActionStatus.ROLLING_BACK}
        for record in records
    ):
        raise PolicyViolationError("recover in-flight effects before revising the goal")
    await repo.record_goal_revision(goal)
    configured = {budget.kind: budget.amount for budget in updated.spec.budgets}
    accounts = await repo.session.scalars(
        select(BudgetAccountRecord).where(
            BudgetAccountRecord.tenant_id == repo.tenant_id,
            BudgetAccountRecord.goal_id == goal.spec.id,
            BudgetAccountRecord.period_end > virtual_time,
        )
    )
    ledger = SqlBudgetRepository(repo.session)
    for account in accounts:
        amount = configured[account.budget_kind]
        used = account.allocated_minor - await ledger.available_minor(repo.tenant_id, account.id)
        if amount.currency != account.currency or amount.amount_minor < used:
            raise PolicyViolationError("revised budget cannot remove spent or reserved capacity")
        account.allocated_minor = amount.amount_minor
        if account.budget_kind == "goal":
            account.period_end = updated.spec.horizon.end_at
        account.version += 1
    for record in records:
        if record.action.status not in {
            ActionStatus.COMPILED,
            ActionStatus.EXECUTABLE,
            ActionStatus.AWAITING_APPROVAL,
            ActionStatus.APPROVED,
        }:
            continue
        await SqlActionRepository(repo.session).transition(
            repo.tenant_id, record.action.id, "cancelled"
        )
        if record.approval_request is not None:
            approval = await repo.session.scalar(
                select(ApprovalRequestRecord).where(
                    ApprovalRequestRecord.tenant_id == repo.tenant_id,
                    ApprovalRequestRecord.id == record.approval_request.id,
                )
            )
            if approval is not None and approval.status == "pending":
                approval.status = "expired"
        repo.append_audit(
            ActionAuditEntry(
                id=uuid4(),
                tenant_id=repo.tenant_id,
                action_id=record.action.id,
                event_type="goal_revision_invalidated_proposal",
                actor_role=ActorRole.SYSTEM,
                message="Reviewed goal changed; a fresh proposal and approval are required",
                occurred_at=utc_now(),
                details={"previous_revision": goal.revision, "new_revision": updated.revision},
            ),
            record.action.run_id,
        )
    for run in await repo.list_runs(goal.spec.id):
        if run.status not in {"queued", "running", "awaiting_approval"}:
            continue
        run.status, run.completed_at = "cancelled", utc_now()
        run.summary["cancellation_reason"] = "goal_revision_changed"
        await repo.save_run(run)
    jobs = await repo.session.scalars(
        select(WorkflowJob).where(
            WorkflowJob.tenant_id == repo.tenant_id,
            WorkflowJob.goal_id == goal.spec.id,
            WorkflowJob.kind.in_(["plan", "execute", "cycle"]),
            WorkflowJob.status == "pending",
        )
    )
    for job in jobs:
        job.status = "cancelled"
    await repo.save_goal(updated)
    return updated
