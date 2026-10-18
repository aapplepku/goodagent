"""Durable controller application service shared by API and workers."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel
from sqlalchemy import select

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.detectors import build_observation_snapshot, detect_opportunities
from open_commerce.controller.merchandising_planner import (
    PLANNER_VERSION as MERCHANDISING_PLANNER_VERSION,
)
from open_commerce.controller.merchandising_planner import plan_merchandising, select_merchandising
from open_commerce.controller.models import (
    CONTROLLER_GRAPH,
    PROVIDER_WRITE_NODE,
    ActionApprovalRequest,
    ActionAuditEntry,
    ActionAuditResponse,
    ActionListResponse,
    ApprovalError,
    ControllerActionRecord,
    ControllerGraphResponse,
    ControllerPolicyConfig,
    ControllerRunRecord,
    ControllerRunRequest,
    ControllerTraceEvent,
    GoalCreateRequest,
    GoalListResponse,
    GoalProgressResponse,
    GoalRecord,
    GoalUpdateRequest,
    KillSwitchResponse,
    PolicyHistoryEntry,
    PolicyHistoryResponse,
    PolicyUpdateRequest,
    PolicyValidateRequest,
    PolicyValidationResponse,
    PolicyViolationError,
    RunEventListResponse,
    RunListResponse,
    RunTraceResponse,
    action_status_for_policy,
)
from open_commerce.controller.objectives import assess_goal
from open_commerce.controller.planner import DeterministicModelProvider
from open_commerce.controller.policy import PolicyEngine
from open_commerce.controller.portfolio import select_portfolio
from open_commerce.controller.workflow import append_trace, enqueue, refresh_run
from open_commerce.core.actions import transition_action
from open_commerce.core.enums import (
    ActionStatus,
    ActorRole,
    GoalStatus,
    PolicyOutcome,
)
from open_commerce.core.goals import (
    AutonomyPolicy,
    BudgetSpec,
    EvaluationSchedule,
    GoalSpec,
    HorizonSpec,
)
from open_commerce.core.policy_types import Approval, ApprovalRequest
from open_commerce.core.types import ActorRef, JsonObject, canonical_hash, utc_now
from open_commerce.persistence.models.actions import ApprovalRequestRecord
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.models.goals import Goal
from open_commerce.persistence.models.runs import GoalRun
from open_commerce.persistence.repositories.actions import SqlActionRepository
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import DurableSimulatorService, load_state


class DurableControllerService:
    """All operations reload PostgreSQL records; workflows carry stable IDs."""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database
        self.simulator_service = DurableSimulatorService(database)

    async def _query[T](
        self, tenant_id: UUID, query: Callable[[ControllerRepository], Awaitable[T]]
    ) -> T:
        async with self.database.transaction(tenant_id) as session:
            return await query(ControllerRepository(session, tenant_id))

    async def _mutate[T: BaseModel](
        self,
        tenant_id: UUID,
        scope: str,
        key: str,
        request: object,
        model: type[T],
        change: Callable[[ControllerRepository], Awaitable[T]],
    ) -> T:
        async with self.database.transaction(tenant_id, write=True) as session:
            requests = RequestRepository(session, tenant_id)
            cached = await requests.replay(scope=scope, key=key, request=request)
            if cached is not None:
                return model.model_validate(cached)
            result = await change(ControllerRepository(session, tenant_id))
            requests.remember(scope=scope, key=key, request=request, response=result)
            return result

    def graph(self) -> ControllerGraphResponse:
        return ControllerGraphResponse(
            nodes=list(CONTROLLER_GRAPH),
            provider_write_node=PROVIDER_WRITE_NODE,
            side_effect_boundaries={
                "workflow_state": "PostgreSQL job, goal, run and action IDs",
                "provider_write_node": PROVIDER_WRITE_NODE,
                "durability": "PostgreSQL domain records; Redis delivery is recoverable",
            },
        )

    async def get_policy(self, *, tenant_id: UUID) -> ControllerPolicyConfig:
        async with self.database.transaction(tenant_id, write=True) as session:
            return await ControllerRepository(session, tenant_id).get_policy()

    async def update_policy(
        self, *, tenant_id: UUID, request: PolicyUpdateRequest, idempotency_key: str
    ) -> ControllerPolicyConfig:
        async def change(repo: ControllerRepository) -> ControllerPolicyConfig:
            current = await repo.get_policy()
            policy = ControllerPolicyConfig.model_validate(
                {
                    **current.model_dump(),
                    **request.model_dump(exclude_none=True),
                    "policy_version": current.policy_version + 1,
                    "updated_at": utc_now(),
                }
            )
            await repo.save_policy(
                policy,
                PolicyHistoryEntry(
                    version=policy.policy_version,
                    changed_at=policy.updated_at,
                    idempotency_key=idempotency_key,
                    previous_hash=canonical_hash(current),
                    new_hash=canonical_hash(policy),
                ),
            )
            return policy

        return await self._mutate(
            tenant_id, "policy:update", idempotency_key, request, ControllerPolicyConfig, change
        )

    async def validate_policy(
        self, *, tenant_id: UUID, request: PolicyValidateRequest
    ) -> PolicyValidationResponse:
        current = await self.get_policy(tenant_id=tenant_id)
        candidate = ControllerPolicyConfig.model_validate(
            {
                **current.model_dump(),
                **request.policy.model_dump(exclude_none=True),
            }
        )
        return PolicyValidationResponse(valid=True, reason_codes=[], effective_policy=candidate)

    async def policy_history(self, *, tenant_id: UUID) -> PolicyHistoryResponse:
        return PolicyHistoryResponse(
            items=await self._query(tenant_id, lambda repo: repo.policy_history())
        )

    async def set_kill_switch(
        self, *, tenant_id: UUID, enabled: bool, idempotency_key: str
    ) -> KillSwitchResponse:
        policy = await self.update_policy(
            tenant_id=tenant_id,
            request=PolicyUpdateRequest(kill_switch_enabled=enabled),
            idempotency_key=f"kill:{enabled}:{idempotency_key}",
        )
        return KillSwitchResponse(
            tenant_id=tenant_id, enabled=policy.kill_switch_enabled, updated_at=policy.updated_at
        )

    async def get_kill_switch(self, *, tenant_id: UUID) -> KillSwitchResponse:
        policy = await self.get_policy(tenant_id=tenant_id)
        return KillSwitchResponse(
            tenant_id=tenant_id, enabled=policy.kill_switch_enabled, updated_at=policy.updated_at
        )

    async def create_goal(
        self, *, tenant_id: UUID, request: GoalCreateRequest, idempotency_key: str
    ) -> GoalRecord:
        if (
            request.planning_mode == "model_backed"
            and request.review_hash != request.configuration_hash
        ):
            raise PolicyViolationError("model-backed goals require exact review of a typed draft")

        async def change(repo: ControllerRepository) -> GoalRecord:
            state = await self.simulator_service.create_in_transaction(
                repo.session,
                tenant_id=tenant_id,
                scenario_id=request.scenario_id,
                seed=request.seed,
                idempotency_key=f"goal:{idempotency_key}",
            )
            horizon = HorizonSpec(
                start_at=state.current_time,
                end_at=state.current_time + timedelta(days=request.horizon_days),
            )
            goal = GoalSpec(
                id=uuid5(NAMESPACE_URL, f"{tenant_id}:goal:{idempotency_key}"),
                tenant_id=tenant_id,
                name=request.name,
                objective=request.resolved_objective(),
                horizon=horizon,
                budgets=[
                    BudgetSpec(kind="goal", amount=request.budget, period=horizon),
                    BudgetSpec(kind="daily", amount=request.daily_budget, period=horizon),
                ],
                constraints=request.resolved_constraints(),
                autonomy=AutonomyPolicy(
                    default_mode=request.default_mode, per_action=request.per_action_modes
                ),
                allowed_action_types=request.allowed_action_types,
                evaluation_schedule=EvaluationSchedule(cadence="daily"),
                status=GoalStatus.DRAFT,
                created_at=state.current_time,
                merchandising=request.merchandising,
            )
            record = GoalRecord(
                spec=goal,
                planning_mode=request.planning_mode,
                soft_preferences=request.soft_preferences,
                scenario_id=request.scenario_id,
                simulator_instance_id=state.id,
                seed=request.seed,
                created_at=goal.created_at,
                updated_at=goal.created_at,
            )
            await repo.save_goal(record)
            if request.merchandising is not None:
                from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
                from open_commerce.simulator.merchandising import initialize_merchandising

                full_state = await load_state(repo.session, tenant_id, state.id)
                initialize_merchandising(
                    full_state, tenant_id=tenant_id, constraints=request.merchandising
                )
                await SqlSimulatorRepository(repo.session).save_state(full_state)
            repo.session.add(
                BudgetAccountRecord(
                    id=uuid5(NAMESPACE_URL, f"{goal.id}:budget:goal"),
                    tenant_id=tenant_id,
                    goal_id=goal.id,
                    budget_kind="goal",
                    currency=request.budget.currency,
                    allocated_minor=request.budget.amount_minor,
                    period_start=horizon.start_at,
                    period_end=horizon.end_at,
                    version=1,
                )
            )
            await repo.ensure_daily_budget(record, state.current_time)
            return record

        return await self._mutate(
            tenant_id, "goal:create", idempotency_key, request, GoalRecord, change
        )

    async def get_goal(self, *, tenant_id: UUID, goal_id: UUID) -> GoalRecord:
        return await self._query(tenant_id, lambda repo: repo.get_goal(goal_id))

    async def list_goals(self, *, tenant_id: UUID) -> GoalListResponse:
        return GoalListResponse(items=await self._query(tenant_id, lambda repo: repo.list_goals()))

    async def update_goal(
        self, *, tenant_id: UUID, goal_id: UUID, request: GoalUpdateRequest, idempotency_key: str
    ) -> GoalRecord:
        async def change(repo: ControllerRepository) -> GoalRecord:
            from open_commerce.controller.durable_goals import apply_goal_revision

            record = await repo.get_goal(goal_id)
            state = await load_state(repo.session, tenant_id, record.simulator_instance_id)
            return await apply_goal_revision(repo, record, request, state.current_time)

        return await self._mutate(
            tenant_id, f"goal:{goal_id}:update", idempotency_key, request, GoalRecord, change
        )

    async def set_goal_status(
        self, *, tenant_id: UUID, goal_id: UUID, status: GoalStatus, idempotency_key: str
    ) -> GoalRecord:
        async def change(repo: ControllerRepository) -> GoalRecord:
            record = await repo.get_goal(goal_id)
            if status == GoalStatus.ACTIVE and record.planning_mode == "model_backed":
                from open_commerce.controller.ollama import OllamaBackend

                OllamaBackend(self.database.settings).require_enabled()
            if (
                record.spec.status in {GoalStatus.ARCHIVED, GoalStatus.COMPLETED}
                and status != record.spec.status
            ):
                raise PolicyViolationError("terminal goal cannot be reactivated")
            record.spec.status = status
            record.updated_at = utc_now()
            await repo.save_goal(record)
            return record

        return await self._mutate(
            tenant_id,
            f"goal:{goal_id}:status",
            idempotency_key,
            {"status": status},
            GoalRecord,
            change,
        )

    async def run_goal(
        self, *, tenant_id: UUID, goal_id: UUID, request: ControllerRunRequest, idempotency_key: str
    ) -> ControllerRunRecord:
        async def change(repo: ControllerRepository) -> ControllerRunRecord:
            goal = await repo.get_goal(goal_id)
            policy = await repo.get_policy()
            if goal.spec.status != GoalStatus.ACTIVE or policy.kill_switch_enabled:
                raise PolicyViolationError("active goal and disabled kill switch required")
            active = await repo.session.scalar(
                select(GoalRun).where(
                    GoalRun.tenant_id == tenant_id,
                    GoalRun.goal_id == goal_id,
                    GoalRun.status.in_(["queued", "running", "awaiting_approval"]),
                )
            )
            if active is not None:
                return await repo.get_run(active.id)
            state = await load_state(repo.session, tenant_id, goal.simulator_instance_id)
            if state.current_time >= goal.spec.horizon.end_at:
                raise PolicyViolationError("goal horizon ended")
            run = ControllerRunRecord(
                id=uuid5(NAMESPACE_URL, f"{tenant_id}:{goal_id}:run:{idempotency_key}"),
                tenant_id=tenant_id,
                goal_id=goal_id,
                simulator_instance_id=state.id,
                status="queued",
                started_at=utc_now(),
                next_run_at=state.current_time + timedelta(days=1),
                summary={
                    "execute_bounded_auto": request.execute_bounded_auto,
                    "goal_revision": goal.revision,
                    "planning_mode": goal.planning_mode,
                },
            )
            await repo.save_run(run)
            await enqueue(repo, "plan", goal_id=goal_id, run_id=run.id)
            return run

        return await self._mutate(
            tenant_id, f"goal:{goal_id}:run", idempotency_key, request, ControllerRunRecord, change
        )

    async def process_run(self, *, tenant_id: UUID, run_id: UUID) -> ControllerRunRecord:
        """A retryable planning node. Proposals and its checkpoint commit atomically."""
        from open_commerce.controller.durable_executor import execution_context
        from open_commerce.controller.model_planning import ModelPlanningService, checkpoint_for

        initial = await self.get_run(tenant_id=tenant_id, run_id=run_id)
        model_backed = initial.summary.get("planning_mode") == "model_backed"
        if model_backed:
            prepared = await ModelPlanningService(self.database).prepare(
                tenant_id=tenant_id, run_id=run_id
            )
            checkpoint = checkpoint_for(prepared)
            if checkpoint is None or checkpoint.status != "ready":
                return prepared

        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ControllerRepository(session, tenant_id)
            run = await repo.get_run(run_id)
            checkpoint = checkpoint_for(run)
            if (
                (run.snapshot is not None and not model_backed)
                or run.status in {"completed", "cancelled", "failed"}
                or (model_backed and checkpoint is not None and checkpoint.status != "ready")
            ):
                return run
            goal = await repo.get_goal(run.goal_id)
            policy = await repo.get_policy()
            if goal.planning_mode != ("model_backed" if model_backed else "deterministic"):
                raise PolicyViolationError("run planning mode no longer matches the goal")
            if policy.kill_switch_enabled or goal.spec.status != GoalStatus.ACTIVE:
                run.status = "cancelled"
                run.completed_at = utc_now()
                await repo.save_run(run)
                return run
            if run.summary.get("goal_revision", 1) != goal.revision:
                run.status, run.completed_at = "cancelled", utc_now()
                run.summary["cancellation_reason"] = "goal_revision_changed"
                await repo.save_run(run)
                return run
            state = await load_state(session, tenant_id, run.simulator_instance_id)
            if model_backed and (
                checkpoint is None or checkpoint.observation_version != state.state_hash
            ):
                return await ModelPlanningService._stop(repo, run, "STALE_MODEL_BEFORE_COMPILATION")
            await repo.ensure_daily_budget(goal, state.current_time)
            run.status = "running"
            assessment = assess_goal(goal.spec, state)
            run.summary["goal_assessment"] = assessment.model_dump(mode="json")
            if not model_backed:
                run.snapshot = build_observation_snapshot(
                    tenant_id=tenant_id, run_id=run_id, state=state
                )
                if goal.spec.merchandising is not None:
                    plan = plan_merchandising(goal=goal.spec, state=state, run_id=run.id)
                    run.opportunities, run.hypotheses = plan.opportunities, plan.hypotheses
                    run.intent_drafts = plan.drafts
                    run.summary["merchandising_decision"] = plan.decision
                else:
                    run.opportunities = detect_opportunities(
                        run.snapshot, state, goal.spec, assessment
                    )
                    planner = DeterministicModelProvider()
                    run.hypotheses = planner.generate_hypotheses(run.opportunities)
                    run.intent_drafts = planner.generate_intent_drafts(
                        opportunities=run.opportunities, hypotheses=run.hypotheses
                    )
            await repo.save_run(run)
            records = []
            try:
                batch = ActionCompiler().compile_candidates(
                    goal=goal.spec, state=state, drafts=run.intent_drafts
                )
            except ValueError:
                if model_backed:
                    return await ModelPlanningService._stop(
                        repo, run, "MODEL_PROPOSAL_COMPILATION_REJECTED"
                    )
                raise
            run.summary["compiler_rejections"] = batch.rejections
            duplicates: list[JsonObject] = []
            run.summary["duplicate_candidates"] = duplicates
            for action in batch.actions:
                previous = await repo.find_action_by_idempotency(action.idempotency_key)
                if previous is not None:
                    duplicates.append(
                        {
                            "draft_id": str(
                                next(
                                    draft.id
                                    for draft in run.intent_drafts
                                    if draft.opportunity_ids == action.intent.opportunity_ids
                                )
                            ),
                            "action_type": action.intent.type,
                            "previous_action_id": str(previous.action.id),
                            "previous_status": previous.action.status.value,
                            "reason": "DUPLICATE_LOGICAL_ACTION",
                        }
                    )
                    continue
                if model_backed:
                    action.intent.requested_by = ActorRef(
                        type="agent", id="model-backed-planner-v1", roles={"system"}
                    )
                    action.expected_impact.assumptions = [
                        (
                            "Authoritative unit economics; demand response and profit lift unknown"
                            if goal.spec.merchandising is not None
                            else "Fixed compiler heuristic, not model-predicted or calibrated lift"
                        ),
                        "Local model proposed the action; simulator evidence only",
                    ]
                    action.risk.reasons = [
                        "Confidence unavailable; zero sentinel forces review",
                        "Untrusted model proposal",
                    ]
                context = await execution_context(repo, action, state)
                context = replace(
                    context, deployment_kill_switch=self.database.settings.deployment_kill_switch
                )
                decision = PolicyEngine().decide(context)
                action.status = action_status_for_policy(decision.outcome)
                approval = (
                    ApprovalRequest(
                        id=uuid5(NAMESPACE_URL, f"{action.id}:approval:{action.version_hash}"),
                        tenant_id=tenant_id,
                        action_id=action.id,
                        action_version_hash=action.version_hash,
                        required_roles=decision.required_approver_roles,
                        status="pending",
                        expires_at=action.expires_at,
                        created_at=utc_now(),
                    )
                    if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL
                    else None
                )
                record = ControllerActionRecord(
                    action=action,
                    action_version_hash=action.version_hash,
                    policy_decision=decision,
                    policy_version=policy.policy_version,
                    approval_policy_version=policy.policy_version if approval else None,
                    approval_request=approval,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                records.append(record)
            merchandising_decision = run.summary.get("merchandising_decision")
            if (
                isinstance(merchandising_decision, dict)
                and merchandising_decision.get("planner_version") == MERCHANDISING_PLANNER_VERSION
                and not model_backed
            ):
                selected = select_merchandising(
                    merchandising_decision,
                    records,
                    compiler_rejections=batch.rejections,
                    duplicates=duplicates,
                )
                run.summary["merchandising_decision"] = merchandising_decision
            else:
                selected = select_portfolio(records, max_actions=policy.max_actions_per_run)
            for record in selected:
                await repo.add_action(record)
                repo.append_audit(
                    _audit(record, "policy_evaluated", "Proposal policy evaluated"), run_id
                )
                if record.action.status == ActionStatus.EXECUTABLE and run.summary.get(
                    "execute_bounded_auto"
                ):
                    await enqueue(
                        repo,
                        "execute",
                        goal_id=run.goal_id,
                        run_id=run_id,
                        action_id=record.action.id,
                    )
            await session.flush()
            run.action_ids = [record.action.id for record in selected]
            if model_backed and checkpoint is not None:
                checkpoint.status = "compiled"
                run.summary["model_planning"] = checkpoint.model_dump(mode="json")
            run.summary.update(
                {
                    "proposed_actions": len(selected),
                    "denied_actions": sum(
                        record.action.status == ActionStatus.DENIED for record in selected
                    ),
                    "awaiting_approval_actions": sum(
                        record.action.status == ActionStatus.AWAITING_APPROVAL
                        for record in selected
                    ),
                    "executable_actions": sum(
                        record.action.status == ActionStatus.EXECUTABLE for record in selected
                    ),
                }
            )
            await repo.save_run(run)
            for node, message in (
                ("load_goal_and_policy", "Loaded authoritative goal and policy"),
                ("acquire_run_lock", "Serialized planning with the PostgreSQL tenant lock"),
                ("build_snapshot", "Recorded the observation snapshot"),
                ("detect_opportunities", "Recorded evidence-backed opportunities"),
                (
                    "generate_hypotheses",
                    "Recorded model decision evidence"
                    if model_backed
                    else "Generated deterministic hypotheses",
                ),
                ("generate_action_intents", "Validated typed candidate intents"),
                ("compile_actions", "Compiled proposals against current state"),
                (
                    "estimate",
                    "Recorded known unit economics; profit response unknown"
                    if goal.spec.merchandising
                    else "Attached deterministic impact intervals",
                ),
                ("evaluate_policy", "Evaluated action policies"),
                ("select_portfolio", "Selected a bounded portfolio"),
                ("persist_proposals", "Committed proposals before execution or approval"),
                ("approval_interrupt", "Pending approvals retain the same run ID"),
                ("summarize", "Planning cycle recorded"),
            ):
                event = ControllerTraceEvent.model_validate(
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "run_id": run_id,
                        "sequence": len(run.trace) + 1,
                        "node": node,
                        "occurred_at": utc_now(),
                        "message": message,
                        "details": {},
                    }
                )
                await repo.append_trace(event)
                run.trace.append(event)
            return await refresh_run(repo, run.id)

    async def get_run(self, *, tenant_id: UUID, run_id: UUID) -> ControllerRunRecord:
        return await self._query(tenant_id, lambda repo: repo.get_run(run_id))

    async def schedule_due_cycles(self, *, tenant_id: UUID) -> int:
        """Virtual-time scheduler; restart recovery depends only on PostgreSQL records."""
        async with self.database.transaction(tenant_id) as session:
            goal_ids = list(
                await session.scalars(
                    select(Goal.id)
                    .where(Goal.tenant_id == tenant_id, Goal.status == "active")
                    .order_by(Goal.id)
                )
            )
        queued = 0
        for goal_id in goal_ids:
            async with self.database.transaction(tenant_id, write=True) as session:
                repo = ControllerRepository(session, tenant_id)
                goal = await repo.get_goal(goal_id)
                policy = await repo.get_policy()
                if (
                    goal.spec.status != GoalStatus.ACTIVE
                    or policy.kill_switch_enabled
                    or self.database.settings.deployment_kill_switch
                ):
                    continue
                latest_id = await session.scalar(
                    select(GoalRun.id)
                    .where(
                        GoalRun.tenant_id == tenant_id,
                        GoalRun.goal_id == goal_id,
                    )
                    .order_by(GoalRun.started_at.desc(), GoalRun.id.desc())
                    .limit(1)
                )
                if latest_id is None:
                    continue  # An explicit first run starts the controller.
                state = await load_state(session, tenant_id, goal.simulator_instance_id)
                await self._expire_proposals(repo, latest_id, state.current_time)
                latest = await refresh_run(repo, latest_id)
                if latest.status != "completed":
                    continue
                if state.current_time >= goal.spec.horizon.end_at:
                    goal.spec.status = GoalStatus.COMPLETED
                    goal.updated_at = utc_now()
                    await repo.save_goal(goal)
                    continue
                if latest.next_run_at is None or state.current_time < latest.next_run_at:
                    continue
                run_key = f"scheduled:{state.generation}:{state.current_time.isoformat()}"
                execute_auto = latest.summary.get("execute_bounded_auto") is True
            await self.run_goal(
                tenant_id=tenant_id,
                goal_id=goal_id,
                request=ControllerRunRequest(execute_bounded_auto=execute_auto),
                idempotency_key=run_key,
            )
            queued += 1
        return queued

    @staticmethod
    async def _expire_proposals(
        repo: ControllerRepository,
        run_id: UUID,
        virtual_time: datetime,
    ) -> None:
        for record in await repo.list_actions(run_id=run_id):
            if record.action.status not in {
                ActionStatus.AWAITING_APPROVAL,
                ActionStatus.APPROVED,
                ActionStatus.EXECUTABLE,
            }:
                continue
            if (
                virtual_time < record.action.expires_at
                and utc_now() < record.created_at + timedelta(hours=24)
            ):
                continue
            await SqlActionRepository(repo.session).transition(
                repo.tenant_id,
                record.action.id,
                ActionStatus.EXPIRED.value,
            )
            if record.approval_request:
                approval = await repo.session.scalar(
                    select(ApprovalRequestRecord).where(
                        ApprovalRequestRecord.tenant_id == repo.tenant_id,
                        ApprovalRequestRecord.id == record.approval_request.id,
                    )
                )
                if approval is not None and approval.status == "pending":
                    approval.status = "expired"
            repo.append_audit(
                _audit(record, "action_expired", "Proposal expired without execution"),
                run_id,
            )

    async def cancel_unstarted_action(self, *, tenant_id: UUID, action_id: UUID) -> None:
        """A failed worker safety gate cannot leave the parent run stuck as running."""
        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ControllerRepository(session, tenant_id)
            record = await repo.get_action(action_id)
            if record.action.status not in {ActionStatus.APPROVED, ActionStatus.EXECUTABLE}:
                return
            await SqlActionRepository(session).transition(
                tenant_id,
                action_id,
                ActionStatus.CANCELLED.value,
            )
            repo.append_audit(
                _audit(record, "safety_gate_closed", "Execution cancelled before dispatch"),
                record.action.run_id,
            )
            await refresh_run(repo, record.action.run_id)

    async def list_runs(self, *, tenant_id: UUID, goal_id: UUID | None = None) -> RunListResponse:
        return RunListResponse(
            items=await self._query(tenant_id, lambda repo: repo.list_runs(goal_id))
        )

    async def run_trace(self, *, tenant_id: UUID, run_id: UUID) -> RunTraceResponse:
        run = await self.get_run(tenant_id=tenant_id, run_id=run_id)
        return RunTraceResponse(run_id=run_id, items=run.trace)

    async def run_events(self, *, tenant_id: UUID, run_id: UUID) -> RunEventListResponse:
        run = await self.get_run(tenant_id=tenant_id, run_id=run_id)
        return RunEventListResponse(run_id=run_id, items=run.trace)

    async def cancel_run(
        self, *, tenant_id: UUID, run_id: UUID, idempotency_key: str
    ) -> ControllerRunRecord:
        async def change(repo: ControllerRepository) -> ControllerRunRecord:
            run = await repo.get_run(run_id)
            run.status = "cancelled"
            run.completed_at = utc_now()
            for record in await repo.list_actions(run_id=run_id):
                if record.action.status in {
                    ActionStatus.COMPILED,
                    ActionStatus.EXECUTABLE,
                    ActionStatus.AWAITING_APPROVAL,
                    ActionStatus.APPROVED,
                }:
                    await SqlActionRepository(repo.session).transition(
                        tenant_id, record.action.id, "cancelled"
                    )
            await repo.save_run(run)
            return run

        return await self._mutate(
            tenant_id, f"run:{run_id}:cancel", idempotency_key, {}, ControllerRunRecord, change
        )

    async def resume_run(
        self, *, tenant_id: UUID, run_id: UUID, idempotency_key: str
    ) -> ControllerRunRecord:
        async def change(repo: ControllerRepository) -> ControllerRunRecord:
            run = await repo.get_run(run_id)
            if run.status == "cancelled":
                raise PolicyViolationError(
                    "cancelled runs cannot execute; start a new planning cycle"
                )
            for record in await repo.list_actions(run_id=run_id):
                if record.action.status == ActionStatus.APPROVED or (
                    record.action.status == ActionStatus.EXECUTABLE
                    and run.summary.get("execute_bounded_auto")
                ):
                    await enqueue(
                        repo,
                        "execute",
                        goal_id=run.goal_id,
                        run_id=run.id,
                        action_id=record.action.id,
                    )
            return await refresh_run(repo, run_id)

        return await self._mutate(
            tenant_id, f"run:{run_id}:resume", idempotency_key, {}, ControllerRunRecord, change
        )

    async def get_action(self, *, tenant_id: UUID, action_id: UUID) -> ControllerActionRecord:
        return await self._query(tenant_id, lambda repo: repo.get_action(action_id))

    async def list_actions(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID | None = None,
        run_id: UUID | None = None,
        status: ActionStatus | None = None,
    ) -> ActionListResponse:
        return ActionListResponse(
            items=await self._query(
                tenant_id,
                lambda repo: repo.list_actions(
                    goal_id=goal_id,
                    run_id=run_id,
                    status=status.value if status else None,
                ),
            )
        )

    async def approve_action(
        self,
        *,
        tenant_id: UUID,
        action_id: UUID,
        request: ActionApprovalRequest,
        actor_roles: set[str],
        decision: str,
        idempotency_key: str,
    ) -> ControllerActionRecord:
        async def change(repo: ControllerRepository) -> ControllerActionRecord:
            record = await repo.get_action(action_id)
            policy = await repo.get_policy()
            goal = await repo.get_goal(record.action.goal_id)
            run = await repo.get_run(record.action.run_id)
            if run.summary.get("goal_revision", 1) != goal.revision:
                raise ApprovalError("goal revision changed; a new proposal is required")
            if decision not in {"approve", "reject"}:
                raise ApprovalError("unknown approval decision")
            if (
                record.approval_request is None
                or record.action.status != ActionStatus.AWAITING_APPROVAL
            ):
                raise ApprovalError("action is not awaiting approval")
            if request.action_version_hash != record.action.version_hash:
                raise ApprovalError("approval hash does not match current action version")
            if record.approval_policy_version != policy.policy_version:
                raise ApprovalError("policy changed; a new proposal is required")
            if not actor_roles.intersection(
                role.value for role in record.approval_request.required_roles
            ):
                raise ApprovalError("actor lacks required approver role")
            state = await load_state(
                repo.session, tenant_id, UUID(record.action.target_provider.resource_id)
            )
            if (
                state.current_time >= record.action.expires_at
                or utc_now() >= record.created_at + timedelta(hours=24)
            ):
                raise ApprovalError("approval request expired")
            approval = Approval(
                id=uuid4(),
                tenant_id=tenant_id,
                request_id=record.approval_request.id,
                actor=ActorRef(type="user", id=request.actor_id, roles=actor_roles),
                decision="approved" if decision == "approve" else "rejected",
                comment=request.comment,
                action_version_hash=request.action_version_hash,
                decided_at=utc_now(),
            )
            await repo.record_approval(approval)
            status = transition_action(
                record.action.status,
                ActionStatus.APPROVED if decision == "approve" else ActionStatus.DENIED,
            )
            await SqlActionRepository(repo.session).transition(tenant_id, action_id, status.value)
            repo.append_audit(
                _audit(
                    record,
                    "approval_recorded",
                    f"Action {approval.decision}",
                    actor_role=ActorRole.OWNER if "owner" in actor_roles else ActorRole.OPERATOR,
                ),
                record.action.run_id,
            )
            await repo.session.flush()
            run = await repo.get_run(record.action.run_id)
            if decision == "approve":
                await enqueue(
                    repo, "execute", goal_id=run.goal_id, run_id=run.id, action_id=action_id
                )
            await append_trace(
                repo,
                run,
                "approval_interrupt",
                "Approval decision persisted; same run resumed",
                {"action_id": str(action_id), "decision": approval.decision},
            )
            await refresh_run(repo, run.id)
            return await repo.get_action(action_id)

        return await self._mutate(
            tenant_id,
            f"action:{action_id}:approval:{decision}",
            idempotency_key,
            {"request": request, "roles": actor_roles},
            ControllerActionRecord,
            change,
        )

    async def cancel_action(
        self, *, tenant_id: UUID, action_id: UUID, idempotency_key: str
    ) -> ControllerActionRecord:
        async def change(repo: ControllerRepository) -> ControllerActionRecord:
            record = await repo.get_action(action_id)
            status = transition_action(record.action.status, ActionStatus.CANCELLED)
            await SqlActionRepository(repo.session).transition(tenant_id, action_id, status.value)
            repo.append_audit(
                _audit(record, "action_cancelled", "Proposal cancelled"), record.action.run_id
            )
            await refresh_run(repo, record.action.run_id)
            return await repo.get_action(action_id)

        return await self._mutate(
            tenant_id,
            f"action:{action_id}:cancel",
            idempotency_key,
            {},
            ControllerActionRecord,
            change,
        )

    async def execute_action(
        self, *, tenant_id: UUID, action_id: UUID, idempotency_key: str
    ) -> ControllerActionRecord:
        from open_commerce.controller.durable_executor import DurableExecutor

        return await DurableExecutor(self.database).execute(
            tenant_id=tenant_id, action_id=action_id, idempotency_key=idempotency_key
        )

    async def rollback_action(
        self, *, tenant_id: UUID, action_id: UUID, idempotency_key: str
    ) -> ControllerActionRecord:
        from open_commerce.controller.durable_executor import DurableExecutor

        return await DurableExecutor(self.database).rollback_action(
            tenant_id=tenant_id, action_id=action_id, idempotency_key=idempotency_key
        )

    async def action_audit(self, *, tenant_id: UUID, action_id: UUID) -> ActionAuditResponse:
        record = await self.get_action(tenant_id=tenant_id, action_id=action_id)
        return ActionAuditResponse(action_id=action_id, items=record.audit)

    async def goal_progress(self, *, tenant_id: UUID, goal_id: UUID) -> GoalProgressResponse:
        goal = await self.get_goal(tenant_id=tenant_id, goal_id=goal_id)
        state = await self.simulator_service.get_full_state(
            tenant_id=tenant_id, instance_id=goal.simulator_instance_id
        )
        assessment = assess_goal(goal.spec, state)
        records = (await self.list_actions(tenant_id=tenant_id, goal_id=goal_id)).items
        runs = (await self.list_runs(tenant_id=tenant_id, goal_id=goal_id)).items
        return GoalProgressResponse(
            goal_id=goal_id,
            tenant_id=tenant_id,
            status=goal.spec.status,
            objective_metric=goal.spec.objective.metric,
            current_value=assessment.current_value,
            assessment=assessment,
            target_value=goal.spec.objective.target,
            pending_approvals=sum(
                item.action.status == ActionStatus.AWAITING_APPROVAL for item in records
            ),
            executable_actions=sum(
                item.action.status == ActionStatus.EXECUTABLE for item in records
            ),
            denied_actions=sum(item.action.status == ActionStatus.DENIED for item in records),
            succeeded_actions=sum(item.action.status == ActionStatus.SUCCEEDED for item in records),
            latest_run_id=runs[-1].id if runs else None,
        )


def _audit(
    record: ControllerActionRecord,
    event_type: str,
    message: str,
    *,
    actor_role: ActorRole = ActorRole.SYSTEM,
) -> ActionAuditEntry:
    return ActionAuditEntry(
        id=uuid4(),
        tenant_id=record.action.tenant_id,
        action_id=record.action.id,
        event_type=event_type,
        actor_role=actor_role,
        message=message,
        occurred_at=utc_now(),
    )
