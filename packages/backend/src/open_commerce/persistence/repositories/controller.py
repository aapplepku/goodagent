"""Normalized controller persistence. Every query is scoped to the bound tenant."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.controller.goal_revision import configuration_for
from open_commerce.controller.models import (
    ActionAuditEntry,
    ActionNotFoundError,
    ControllerActionRecord,
    ControllerPolicyConfig,
    ControllerRunRecord,
    ControllerTraceEvent,
    GoalNotFoundError,
    GoalRecord,
    MeasurementOutcome,
    MeasurementSchedule,
    ObservationSnapshot,
    Opportunity,
    PolicyHistoryEntry,
    RunNotFoundError,
)
from open_commerce.core.enums import ActorRole
from open_commerce.core.policy_types import Approval, ApprovalRequest, PolicyDecision
from open_commerce.core.providers import ProviderResult, ReconciliationResult
from open_commerce.core.types import ActorRef, canonical_hash, utc_now
from open_commerce.persistence.models.actions import (
    ActionExecution,
    ActionReconciliation,
    ApprovalRecord,
    ApprovalRequestRecord,
    CompiledActionRecord,
    Intervention,
    InterventionOutcome,
    PolicyDecisionRecord,
)
from open_commerce.persistence.models.audit import AuditEventRecord
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.models.goals import Goal, GoalRevisionRecord, PolicyVersion
from open_commerce.persistence.models.identity import User
from open_commerce.persistence.models.runs import (
    GoalRun,
    GoalRunStep,
    ObservationSnapshotRecord,
    OpportunityRecord,
)
from open_commerce.persistence.models.workflow import TenantRuntime
from open_commerce.persistence.repositories.actions import SqlActionRepository
from open_commerce.persistence.repositories.goals import SqlGoalRepository
from open_commerce.simulator.durable import load_state


class ControllerRepository:
    """Use within RuntimeDatabase transactions; returned objects are detached domain values."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def policy_row(self) -> PolicyVersion:
        runtime = await self.session.scalar(
            select(TenantRuntime).where(
                TenantRuntime.tenant_id == self.tenant_id,
            )
        )
        if runtime is None:
            raise ValueError("tenant runtime has not been initialized")
        row = (
            await self.session.scalar(
                select(PolicyVersion).where(
                    PolicyVersion.tenant_id == self.tenant_id,
                    PolicyVersion.id == runtime.policy_version_id,
                )
            )
            if runtime.policy_version_id
            else None
        )
        if row is None:
            policy = ControllerPolicyConfig(tenant_id=self.tenant_id, updated_at=utc_now())
            row = await self.save_policy(policy)
        return row

    async def get_policy(self) -> ControllerPolicyConfig:
        return ControllerPolicyConfig.model_validate((await self.policy_row()).policy)

    async def save_policy(
        self, policy: ControllerPolicyConfig, history: PolicyHistoryEntry | None = None
    ) -> PolicyVersion:
        if policy.tenant_id != self.tenant_id:
            raise ValueError("policy tenant mismatch")
        runtime = await self.session.scalar(
            select(TenantRuntime).where(
                TenantRuntime.tenant_id == self.tenant_id,
            )
        )
        if runtime is None:
            raise ValueError("tenant runtime has not been initialized")
        row = PolicyVersion(
            id=uuid5(NAMESPACE_URL, f"{self.tenant_id}:policy:{policy.policy_version}"),
            tenant_id=self.tenant_id,
            scope_type="tenant",
            scope_id=self.tenant_id,
            version=policy.policy_version,
            policy=policy.model_dump(mode="json"),
            content_hash=canonical_hash(policy),
            created_at=policy.updated_at,
            history_data=history.model_dump(mode="json") if history else {},
        )
        self.session.add(row)
        await self.session.flush()
        runtime.policy_version_id = row.id
        return row

    async def policy_history(self) -> list[PolicyHistoryEntry]:
        rows = await self.session.scalars(
            select(PolicyVersion)
            .where(
                PolicyVersion.tenant_id == self.tenant_id,
            )
            .order_by(PolicyVersion.version)
        )
        return [
            PolicyHistoryEntry.model_validate(row.history_data) for row in rows if row.history_data
        ]

    async def get_goal(self, goal_id: UUID) -> GoalRecord:
        row = await self.session.scalar(
            select(Goal).where(
                Goal.tenant_id == self.tenant_id,
                Goal.id == goal_id,
            )
        )
        spec = await SqlGoalRepository(self.session).get(self.tenant_id, goal_id)
        if row is None or spec is None or row.simulator_instance_id is None:
            raise GoalNotFoundError(str(goal_id))
        state = await load_state(self.session, self.tenant_id, row.simulator_instance_id)
        return GoalRecord(
            spec=spec,
            revision=row.configuration_revision,
            planning_mode=row.planning_mode,
            soft_preferences=row.soft_preferences,
            scenario_id=state.scenario_id,
            simulator_instance_id=state.id,
            seed=state.seed,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def save_goal(self, goal: GoalRecord) -> None:
        await SqlGoalRepository(self.session).add(self.tenant_id, goal.spec)
        row = await self.session.scalar(
            select(Goal).where(
                Goal.tenant_id == self.tenant_id,
                Goal.id == goal.spec.id,
            )
        )
        assert row is not None
        row.simulator_instance_id = goal.simulator_instance_id
        row.configuration_revision = goal.revision
        row.planning_mode = goal.planning_mode
        row.soft_preferences = goal.soft_preferences
        row.updated_at = goal.updated_at
        row.policy_version_id = (await self.policy_row()).id
        await self.record_goal_revision(goal)

    async def record_goal_revision(self, goal: GoalRecord) -> None:
        if goal.spec.tenant_id != self.tenant_id:
            raise ValueError("goal revision tenant mismatch")
        existing = await self.session.scalar(
            select(GoalRevisionRecord).where(
                GoalRevisionRecord.tenant_id == self.tenant_id,
                GoalRevisionRecord.goal_id == goal.spec.id,
                GoalRevisionRecord.revision == goal.revision,
            )
        )
        configuration = configuration_for(goal)
        if existing is not None and existing.content_hash != canonical_hash(configuration):
            raise ValueError("goal configuration changed without a new review revision")
        if existing is None:
            self.session.add(
                GoalRevisionRecord(
                    tenant_id=self.tenant_id,
                    goal_id=goal.spec.id,
                    revision=goal.revision,
                    configuration=configuration,
                    content_hash=canonical_hash(configuration),
                    created_at=utc_now(),
                )
            )
            await self.session.flush()

    async def list_goals(self) -> list[GoalRecord]:
        ids = await self.session.scalars(
            select(Goal.id)
            .where(
                Goal.tenant_id == self.tenant_id,
                Goal.simulator_instance_id.is_not(None),
            )
            .order_by(Goal.created_at, Goal.id)
        )
        return [await self.get_goal(item) for item in ids]

    async def ensure_daily_budget(self, goal: GoalRecord, now: datetime) -> None:
        """Initialize one virtual UTC-day account inside the tenant write lock."""
        if goal.spec.tenant_id != self.tenant_id:
            raise ValueError("daily budget tenant mismatch")
        budget = next((item for item in goal.spec.budgets if item.kind == "daily"), None)
        if budget is None:
            raise ValueError("durable goals require a daily budget")
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        account = await self.session.scalar(
            select(BudgetAccountRecord).where(
                BudgetAccountRecord.tenant_id == self.tenant_id,
                BudgetAccountRecord.goal_id == goal.spec.id,
                BudgetAccountRecord.budget_kind == "daily",
                BudgetAccountRecord.period_start == start,
            )
        )
        if account is None:
            self.session.add(
                BudgetAccountRecord(
                    id=uuid5(NAMESPACE_URL, f"{goal.spec.id}:daily:{start.isoformat()}"),
                    tenant_id=self.tenant_id,
                    goal_id=goal.spec.id,
                    budget_kind="daily",
                    currency=budget.amount.currency,
                    allocated_minor=budget.amount.amount_minor,
                    period_start=start,
                    period_end=start + timedelta(days=1),
                    version=1,
                )
            )
            await self.session.flush()

    async def save_run(self, run: ControllerRunRecord) -> None:
        if run.tenant_id != self.tenant_id:
            raise ValueError("run tenant mismatch")
        row = await self.session.scalar(
            select(GoalRun).where(
                GoalRun.tenant_id == self.tenant_id,
                GoalRun.id == run.id,
            )
        )
        if row is None:
            row = GoalRun(
                id=run.id,
                tenant_id=self.tenant_id,
                goal_id=run.goal_id,
                thread_id=str(run.id),
                trigger="manual",
                started_at=run.started_at,
                policy_version_id=(await self.policy_row()).id,
            )
            self.session.add(row)
        row.status = run.status
        row.completed_at = run.completed_at
        row.runtime_data = run.model_dump(
            mode="json",
            exclude={
                "id",
                "tenant_id",
                "goal_id",
                "status",
                "started_at",
                "completed_at",
                "snapshot",
                "opportunities",
                "action_ids",
                "trace",
            },
        )
        await self.session.flush()
        if run.snapshot is not None and row.observation_snapshot_id is None:
            snapshot = run.snapshot
            self.session.add(
                ObservationSnapshotRecord(
                    id=snapshot.id,
                    tenant_id=self.tenant_id,
                    goal_id=run.goal_id,
                    as_of=snapshot.observed_at,
                    data=snapshot.model_dump(mode="json"),
                    content_hash=canonical_hash(snapshot),
                    created_at=utc_now(),
                )
            )
            row.observation_snapshot_id = snapshot.id
            await self.session.flush()
            for opportunity in run.opportunities:
                self.session.add(
                    OpportunityRecord(
                        id=opportunity.id,
                        tenant_id=self.tenant_id,
                        goal_id=run.goal_id,
                        snapshot_id=snapshot.id,
                        type=opportunity.type,
                        entity_refs={},
                        evidence={
                            "items": [item.model_dump(mode="json") for item in opportunity.evidence]
                        },
                        confidence=opportunity.confidence,
                        detector_code=opportunity.type,
                        status="detected",
                        data=opportunity.model_dump(mode="json"),
                    )
                )

    async def get_run(self, run_id: UUID) -> ControllerRunRecord:
        row = await self.session.scalar(
            select(GoalRun).where(
                GoalRun.tenant_id == self.tenant_id,
                GoalRun.id == run_id,
            )
        )
        if row is None:
            raise RunNotFoundError(str(run_id))
        snapshot = (
            await self.session.scalar(
                select(ObservationSnapshotRecord).where(
                    ObservationSnapshotRecord.tenant_id == self.tenant_id,
                    ObservationSnapshotRecord.id == row.observation_snapshot_id,
                )
            )
            if row.observation_snapshot_id
            else None
        )
        opportunities: Iterable[OpportunityRecord] = (
            await self.session.scalars(
                select(OpportunityRecord)
                .where(
                    OpportunityRecord.tenant_id == self.tenant_id,
                    OpportunityRecord.snapshot_id == row.observation_snapshot_id,
                )
                .order_by(OpportunityRecord.id)
            )
            if row.observation_snapshot_id
            else []
        )
        actions = await self.session.scalars(
            select(CompiledActionRecord.id)
            .where(
                CompiledActionRecord.tenant_id == self.tenant_id,
                CompiledActionRecord.run_id == run_id,
            )
            .order_by(CompiledActionRecord.created_at, CompiledActionRecord.id)
        )
        return ControllerRunRecord.model_validate(
            {
                **row.runtime_data,
                "id": row.id,
                "tenant_id": row.tenant_id,
                "goal_id": row.goal_id,
                "status": row.status,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "snapshot": ObservationSnapshot.model_validate(snapshot.data) if snapshot else None,
                "opportunities": [Opportunity.model_validate(item.data) for item in opportunities],
                "action_ids": list(actions),
                "trace": await self.trace(run_id),
            }
        )

    async def list_runs(self, goal_id: UUID | None = None) -> list[ControllerRunRecord]:
        query = select(GoalRun.id).where(GoalRun.tenant_id == self.tenant_id)
        if goal_id is not None:
            query = query.where(GoalRun.goal_id == goal_id)
        ids = await self.session.scalars(query.order_by(GoalRun.started_at, GoalRun.id))
        return [await self.get_run(item) for item in ids]

    async def append_trace(self, event: ControllerTraceEvent) -> None:
        if event.tenant_id != self.tenant_id:
            raise ValueError("trace tenant mismatch")
        self.session.add(
            GoalRunStep(
                id=event.id,
                tenant_id=self.tenant_id,
                run_id=event.run_id,
                sequence=event.sequence,
                node_name=event.node,
                status="completed",
                input_refs={},
                output_refs={"message": event.message, "details": event.details},
                trace_id=str(event.id),
                started_at=event.occurred_at,
                completed_at=event.occurred_at,
            )
        )
        await self.session.flush()

    async def trace(self, run_id: UUID) -> list[ControllerTraceEvent]:
        rows = await self.session.scalars(
            select(GoalRunStep)
            .where(
                GoalRunStep.tenant_id == self.tenant_id,
                GoalRunStep.run_id == run_id,
            )
            .order_by(GoalRunStep.sequence)
        )
        return [
            ControllerTraceEvent.model_validate(
                {
                    "id": row.id,
                    "tenant_id": row.tenant_id,
                    "run_id": row.run_id,
                    "sequence": row.sequence,
                    "node": row.node_name,
                    "occurred_at": row.started_at,
                    **row.output_refs,
                }
            )
            for row in rows
        ]

    async def find_action_by_idempotency(self, key: str) -> ControllerActionRecord | None:
        """Read an earlier logical command under the caller's tenant write lock."""
        action_id = await self.session.scalar(
            select(CompiledActionRecord.id).where(
                CompiledActionRecord.tenant_id == self.tenant_id,
                CompiledActionRecord.idempotency_key == key,
            )
        )
        return await self.get_action(action_id) if action_id is not None else None

    async def add_action(self, record: ControllerActionRecord) -> None:
        await SqlActionRepository(self.session).add_compiled(self.tenant_id, record.action)
        await self.session.flush()
        await self.add_policy_decision(
            record.action.id, record.action.version_hash, record.policy_decision
        )
        if record.approval_request is not None:
            approval = record.approval_request
            self.session.add(
                ApprovalRequestRecord(
                    id=approval.id,
                    tenant_id=self.tenant_id,
                    action_id=record.action.id,
                    action_version_hash=approval.action_version_hash,
                    policy_version_id=(await self.policy_row()).id,
                    required_roles=sorted(role.value for role in approval.required_roles),
                    status=approval.status,
                    expires_at=approval.expires_at,
                    created_at=approval.created_at,
                )
            )
        for entry in record.audit:
            self.append_audit(entry, record.action.run_id)

    async def add_policy_decision(
        self, action_id: UUID, version_hash: str, decision: PolicyDecision
    ) -> None:
        self.session.add(
            PolicyDecisionRecord(
                id=uuid4(),
                tenant_id=self.tenant_id,
                action_id=action_id,
                policy_version_id=(await self.policy_row()).id,
                action_version_hash=version_hash,
                outcome=decision.outcome.value,
                reason_codes=decision.reason_codes,
                evaluated_rules=[rule.model_dump(mode="json") for rule in decision.evaluated_rules],
                required_roles=sorted(role.value for role in decision.required_approver_roles),
                valid_until=decision.valid_until,
                created_at=utc_now(),
            )
        )

    async def get_action(self, action_id: UUID) -> ControllerActionRecord:
        action = await SqlActionRepository(self.session).get_compiled(self.tenant_id, action_id)
        row = await self.session.scalar(
            select(CompiledActionRecord).where(
                CompiledActionRecord.tenant_id == self.tenant_id,
                CompiledActionRecord.id == action_id,
            )
        )
        if action is None or row is None:
            raise ActionNotFoundError(str(action_id))
        policy = await self.session.scalar(
            select(PolicyDecisionRecord)
            .where(
                PolicyDecisionRecord.tenant_id == self.tenant_id,
                PolicyDecisionRecord.action_id == action_id,
            )
            .order_by(PolicyDecisionRecord.created_at.desc(), PolicyDecisionRecord.id.desc())
        )
        if policy is None:
            raise ValueError("action has no durable policy decision")
        policy_version = await self.session.scalar(
            select(PolicyVersion.version).where(
                PolicyVersion.tenant_id == self.tenant_id,
                PolicyVersion.id == policy.policy_version_id,
            )
        )
        request = await self.session.scalar(
            select(ApprovalRequestRecord)
            .where(
                ApprovalRequestRecord.tenant_id == self.tenant_id,
                ApprovalRequestRecord.action_id == action_id,
            )
            .order_by(ApprovalRequestRecord.created_at.desc())
        )
        approval = (
            await self.session.scalar(
                select(ApprovalRecord)
                .where(
                    ApprovalRecord.tenant_id == self.tenant_id,
                    ApprovalRecord.request_id == request.id,
                )
                .order_by(ApprovalRecord.decided_at.desc())
            )
            if request
            else None
        )
        approval_version = (
            await self.session.scalar(
                select(PolicyVersion.version).where(
                    PolicyVersion.tenant_id == self.tenant_id,
                    PolicyVersion.id == request.policy_version_id,
                )
            )
            if request
            else None
        )
        execution = await self.session.scalar(
            select(ActionExecution)
            .where(
                ActionExecution.tenant_id == self.tenant_id,
                ActionExecution.action_id == action_id,
                ActionExecution.request_summary["operation"].astext == "execute",
            )
            .order_by(ActionExecution.attempt.desc())
        )
        reconciliation = (
            await self.session.scalar(
                select(ActionReconciliation)
                .where(
                    ActionReconciliation.tenant_id == self.tenant_id,
                    ActionReconciliation.execution_id == execution.id,
                )
                .order_by(ActionReconciliation.reconciled_at.desc())
            )
            if execution
            else None
        )
        measurement = await self.session.scalar(
            select(Intervention).where(
                Intervention.tenant_id == self.tenant_id,
                Intervention.action_id == action_id,
            )
        )
        outcome = (
            await self.session.scalar(
                select(InterventionOutcome).where(
                    InterventionOutcome.tenant_id == self.tenant_id,
                    InterventionOutcome.intervention_id == measurement.id,
                )
            )
            if measurement
            else None
        )
        return ControllerActionRecord(
            action=action,
            action_version_hash=row.version_hash,
            policy_version=policy_version or 1,
            approval_policy_version=approval_version,
            policy_decision=PolicyDecision.model_validate(
                {
                    "outcome": policy.outcome,
                    "reason_codes": policy.reason_codes,
                    "evaluated_rules": policy.evaluated_rules,
                    "required_approver_roles": policy.required_roles,
                    "valid_until": policy.valid_until,
                }
            ),
            approval_request=ApprovalRequest.model_validate(
                {
                    "id": request.id,
                    "tenant_id": request.tenant_id,
                    "action_id": request.action_id,
                    "action_version_hash": request.action_version_hash,
                    "required_roles": request.required_roles,
                    "status": request.status,
                    "expires_at": request.expires_at,
                    "created_at": request.created_at,
                }
            )
            if request
            else None,
            approval=Approval(
                id=approval.id,
                tenant_id=self.tenant_id,
                request_id=approval.request_id,
                actor=ActorRef(type="user", id=str(approval.actor_user_id), roles=set()),
                decision=approval.decision,
                comment=approval.comment,
                action_version_hash=approval.action_version_hash,
                decided_at=approval.decided_at,
            )
            if approval
            else None,
            execution_result=ProviderResult.model_validate(execution.response_summary)
            if execution and execution.response_summary
            else None,
            reconciliation=ReconciliationResult.model_validate(reconciliation.details)
            if reconciliation
            else None,
            measurement=MeasurementSchedule.model_validate(measurement.monitor_spec)
            if measurement
            else None,
            outcome=MeasurementOutcome(
                id=outcome.id,
                evaluated_at=outcome.evaluated_at,
                metric_results=outcome.metric_results,
                method=outcome.method,
                sample_size=outcome.sample_size,
                conclusion=outcome.conclusion,
                guardrail_status=outcome.guardrail_status,
            )
            if outcome
            else None,
            audit=await self.action_audit(action_id),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_actions(
        self,
        *,
        goal_id: UUID | None = None,
        run_id: UUID | None = None,
        status: str | None = None,
    ) -> list[ControllerActionRecord]:
        query = select(CompiledActionRecord.id).where(
            CompiledActionRecord.tenant_id == self.tenant_id
        )
        if goal_id is not None:
            query = query.where(CompiledActionRecord.goal_id == goal_id)
        if run_id is not None:
            query = query.where(CompiledActionRecord.run_id == run_id)
        if status is not None:
            query = query.where(CompiledActionRecord.status == status)
        ids = await self.session.scalars(
            query.order_by(CompiledActionRecord.created_at, CompiledActionRecord.id)
        )
        return [await self.get_action(item) for item in ids]

    async def record_approval(self, approval: Approval) -> None:
        request = await self.session.scalar(
            select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.tenant_id == self.tenant_id,
                ApprovalRequestRecord.id == approval.request_id,
            )
        )
        if request is None or approval.tenant_id != self.tenant_id:
            raise ValueError("approval tenant mismatch")
        user_id = uuid5(NAMESPACE_URL, f"{self.tenant_id}:actor:{approval.actor.id}")
        # Identity records are global; tenant ownership is enforced by the approval's request FK.
        from sqlalchemy.dialects.postgresql import insert

        await self.session.execute(
            insert(User)
            .values(
                id=user_id,
                external_subject=f"{self.tenant_id}:{approval.actor.id}",
            )
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        self.session.add(
            ApprovalRecord(
                id=approval.id,
                tenant_id=self.tenant_id,
                request_id=approval.request_id,
                actor_user_id=user_id,
                decision=approval.decision,
                comment=approval.comment,
                action_version_hash=approval.action_version_hash,
                decided_at=approval.decided_at,
            )
        )
        request.status = approval.decision

    def append_audit(self, entry: ActionAuditEntry, run_id: UUID | None = None) -> None:
        if entry.tenant_id != self.tenant_id:
            raise ValueError("audit tenant mismatch")
        self.session.add(
            AuditEventRecord(
                id=entry.id,
                tenant_id=self.tenant_id,
                actor={"role": entry.actor_role.value},
                event_type=entry.event_type,
                entity_type="action",
                entity_id=entry.action_id,
                request_id=str(entry.id),
                run_id=run_id,
                safe_payload={"message": entry.message, "details": entry.details},
                occurred_at=entry.occurred_at,
            )
        )

    async def action_audit(self, action_id: UUID) -> list[ActionAuditEntry]:
        rows = await self.session.scalars(
            select(AuditEventRecord)
            .where(
                AuditEventRecord.tenant_id == self.tenant_id,
                AuditEventRecord.entity_type == "action",
                AuditEventRecord.entity_id == action_id,
            )
            .order_by(AuditEventRecord.occurred_at, AuditEventRecord.id)
        )
        return [
            ActionAuditEntry(
                id=row.id,
                tenant_id=self.tenant_id,
                action_id=action_id,
                event_type=row.event_type,
                actor_role=ActorRole(str(row.actor["role"])),
                message=str(row.safe_payload["message"]),
                details=cast(dict[str, object], row.safe_payload.get("details", {})),
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]
