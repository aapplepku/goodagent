"""Application service for deterministic controller, policy, and approvals."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.detectors import build_observation_snapshot, detect_opportunities
from open_commerce.controller.executor import ControllerExecutor
from open_commerce.controller.merchandising_planner import plan_merchandising, select_merchandising
from open_commerce.controller.models import (
    CONTROLLER_GRAPH,
    PROVIDER_WRITE_NODE,
    ActionApprovalRequest,
    ActionAuditEntry,
    ActionAuditResponse,
    ActionListResponse,
    ActionNotFoundError,
    ApprovalError,
    ControllerActionRecord,
    ControllerGraphResponse,
    ControllerNode,
    ControllerPolicyConfig,
    ControllerRunRecord,
    ControllerRunRequest,
    ControllerTraceEvent,
    GoalCreateRequest,
    GoalListResponse,
    GoalNotFoundError,
    GoalProgressResponse,
    GoalRecord,
    GoalUpdateRequest,
    KillSwitchResponse,
    MeasurementSchedule,
    PolicyHistoryEntry,
    PolicyHistoryResponse,
    PolicyUpdateRequest,
    PolicyValidateRequest,
    PolicyValidationResponse,
    PolicyViolationError,
    RunEventListResponse,
    RunListResponse,
    RunNotFoundError,
    RunTraceResponse,
    action_status_for_policy,
)
from open_commerce.controller.objectives import assess_goal
from open_commerce.controller.planner import DeterministicModelProvider, ModelProvider
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.controller.portfolio import select_portfolio
from open_commerce.core.actions import CompiledAction, transition_action
from open_commerce.core.enums import (
    ActionStatus,
    ActorRole,
    Capability,
    ExecutionStatus,
    GoalStatus,
    MetricName,
    PolicyOutcome,
)
from open_commerce.core.goals import (
    AutonomyPolicy,
    BudgetSpec,
    EvaluationSchedule,
    GoalSpec,
    HorizonSpec,
)
from open_commerce.core.money import Money
from open_commerce.core.policy_types import Approval, ApprovalRequest
from open_commerce.core.types import ActorRef, JsonObject, canonical_hash, utc_now
from open_commerce.simulator.engine import latest_runtime_metric
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.service import SimulatorService


class ControllerService:
    """In-process controller runtime for zero-credential simulator demos."""

    def __init__(
        self,
        *,
        simulator_service: SimulatorService | None = None,
        policy_engine: PolicyEngine | None = None,
        model_provider: ModelProvider | None = None,
        compiler: ActionCompiler | None = None,
    ) -> None:
        self.simulator_service = simulator_service or SimulatorService()
        self.policy_engine = policy_engine or PolicyEngine()
        self.model_provider = model_provider or DeterministicModelProvider()
        self.compiler = compiler or ActionCompiler()
        self.executor = ControllerExecutor(
            simulator_service=self.simulator_service,
            policy_engine=self.policy_engine,
        )
        self._goals: dict[UUID, GoalRecord] = {}
        self._runs: dict[UUID, ControllerRunRecord] = {}
        self._actions: dict[UUID, ControllerActionRecord] = {}
        self._policies: dict[UUID, ControllerPolicyConfig] = {}
        self._policy_history: dict[UUID, list[PolicyHistoryEntry]] = {}
        self._goal_idempotency: dict[tuple[UUID, str], UUID] = {}
        self._run_idempotency: dict[tuple[UUID, UUID, str], UUID] = {}
        self._mutation_idempotency: dict[tuple[UUID, str, str, str], UUID] = {}

    def graph(self) -> ControllerGraphResponse:
        """Return the documented graph and side-effect boundary."""

        return ControllerGraphResponse(
            nodes=list(CONTROLLER_GRAPH),
            provider_write_node=PROVIDER_WRITE_NODE,
            side_effect_boundaries={
                "read_only_nodes": [
                    "load_goal_and_policy",
                    "build_snapshot",
                    "detect_opportunities",
                    "reconcile",
                    "schedule_measurement",
                    "summarize",
                ],
                "proposal_only_nodes": [
                    "generate_hypotheses",
                    "generate_action_intents",
                    "compile_actions",
                    "estimate",
                    "evaluate_policy",
                    "select_portfolio",
                    "persist_proposals",
                    "approval_interrupt",
                ],
                "provider_write_node": PROVIDER_WRITE_NODE,
            },
        )

    def get_policy(self, *, tenant_id: UUID) -> ControllerPolicyConfig:
        """Return a tenant policy, creating safe defaults on first read."""

        existing = self._policies.get(tenant_id)
        if existing is not None:
            return existing
        policy = ControllerPolicyConfig(tenant_id=tenant_id, updated_at=utc_now())
        self._policies[tenant_id] = policy
        return policy

    def update_policy(
        self,
        *,
        tenant_id: UUID,
        request: PolicyUpdateRequest,
        idempotency_key: str,
    ) -> ControllerPolicyConfig:
        """Patch a tenant policy idempotently."""

        cached = self._mutation_idempotency.get((tenant_id, "policy", "update", idempotency_key))
        if cached is not None:
            return self.get_policy(tenant_id=tenant_id)
        current = self.get_policy(tenant_id=tenant_id)
        previous_hash = canonical_hash(current)
        update = request.model_dump(exclude_none=True)
        update["policy_version"] = current.policy_version + 1
        update["updated_at"] = utc_now()
        policy = current.model_copy(update=update)
        self._policies[tenant_id] = policy
        self._policy_history.setdefault(tenant_id, []).append(
            PolicyHistoryEntry(
                version=policy.policy_version,
                changed_at=policy.updated_at,
                idempotency_key=idempotency_key,
                previous_hash=previous_hash,
                new_hash=canonical_hash(policy),
            )
        )
        self._mutation_idempotency[(tenant_id, "policy", "update", idempotency_key)] = tenant_id
        return policy

    def validate_policy(
        self,
        *,
        tenant_id: UUID,
        request: PolicyValidateRequest,
    ) -> PolicyValidationResponse:
        """Dry-run validate a tenant policy patch."""

        current = self.get_policy(tenant_id=tenant_id)
        candidate = current.model_copy(update=request.policy.model_dump(exclude_none=True))
        reason_codes: list[str] = []
        if candidate.search_boost_max_multiplier <= Decimal("0"):
            reason_codes.append("search_boost_multiplier")
        if candidate.discount_max_percentage > Decimal("0.50"):
            reason_codes.append("discount_max_percentage")
        return PolicyValidationResponse(
            valid=not reason_codes,
            reason_codes=reason_codes,
            effective_policy=candidate,
        )

    def policy_history(self, *, tenant_id: UUID) -> PolicyHistoryResponse:
        """Return tenant policy history."""

        return PolicyHistoryResponse(items=list(self._policy_history.get(tenant_id, [])))

    def set_kill_switch(
        self,
        *,
        tenant_id: UUID,
        enabled: bool,
        idempotency_key: str,
    ) -> KillSwitchResponse:
        """Enable or disable the tenant kill switch."""

        policy = self.update_policy(
            tenant_id=tenant_id,
            request=PolicyUpdateRequest(kill_switch_enabled=enabled),
            idempotency_key=f"kill-switch:{enabled}:{idempotency_key}",
        )
        return KillSwitchResponse(
            tenant_id=tenant_id,
            enabled=policy.kill_switch_enabled,
            updated_at=policy.updated_at,
        )

    def get_kill_switch(self, *, tenant_id: UUID) -> KillSwitchResponse:
        """Return current kill-switch state."""

        policy = self.get_policy(tenant_id=tenant_id)
        return KillSwitchResponse(
            tenant_id=tenant_id,
            enabled=policy.kill_switch_enabled,
            updated_at=policy.updated_at,
        )

    def create_goal(
        self,
        *,
        tenant_id: UUID,
        request: GoalCreateRequest,
        idempotency_key: str,
    ) -> GoalRecord:
        """Create or return an idempotent local-demo goal."""

        cached = self._goal_idempotency.get((tenant_id, idempotency_key))
        if cached is not None:
            return self._goal_for(tenant_id=tenant_id, goal_id=cached)

        created = self.simulator_service.create_instance(
            tenant_id=tenant_id,
            scenario_id=request.scenario_id,
            seed=request.seed,
            idempotency_key=f"controller-goal:{idempotency_key}",
        )
        goal_id = uuid5(NAMESPACE_URL, f"{tenant_id}:goal:{idempotency_key}")
        created_at = created.current_time
        horizon = HorizonSpec(
            start_at=created_at,
            end_at=created_at + timedelta(days=request.horizon_days),
        )
        goal = GoalSpec(
            id=goal_id,
            tenant_id=tenant_id,
            name=request.name,
            objective=request.resolved_objective(),
            horizon=horizon,
            budgets=[BudgetSpec(kind="goal", amount=request.budget, period=horizon)],
            merchandising=request.merchandising,
            constraints=request.resolved_constraints(),
            autonomy=AutonomyPolicy(
                default_mode=request.default_mode, per_action=request.per_action_modes
            ),
            allowed_action_types=request.allowed_action_types,
            evaluation_schedule=EvaluationSchedule(cadence="daily"),
            status=GoalStatus.DRAFT,
            created_at=created_at,
        )
        record = GoalRecord(
            spec=goal,
            planning_mode=request.planning_mode,
            soft_preferences=request.soft_preferences,
            scenario_id=request.scenario_id,
            simulator_instance_id=created.id,
            seed=request.seed,
            created_at=created_at,
            updated_at=created_at,
        )
        self._goals[goal_id] = record
        if request.merchandising is not None:
            from open_commerce.simulator.merchandising import initialize_merchandising

            state = self.simulator_service.get_full_state(
                tenant_id=tenant_id, instance_id=created.id
            )
            initialize_merchandising(state, tenant_id=tenant_id, constraints=request.merchandising)
        self._goal_idempotency[(tenant_id, idempotency_key)] = goal_id
        return record

    def list_goals(self, *, tenant_id: UUID) -> GoalListResponse:
        """List tenant goals."""

        records = [record for record in self._goals.values() if record.spec.tenant_id == tenant_id]
        return GoalListResponse(
            items=sorted(records, key=lambda item: (item.created_at, item.spec.name))
        )

    def get_goal(self, *, tenant_id: UUID, goal_id: UUID) -> GoalRecord:
        """Return a tenant goal."""

        return self._goal_for(tenant_id=tenant_id, goal_id=goal_id)

    def update_goal(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID,
        request: GoalUpdateRequest,
        idempotency_key: str,
    ) -> GoalRecord:
        """Patch a goal idempotently."""

        mutation_key = (tenant_id, str(goal_id), "goal-update", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        record = self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        from open_commerce.controller.goal_revision import revise_goal

        updated = revise_goal(record, request)
        if (updated.spec.merchandising is None) != (record.spec.merchandising is None):
            raise PolicyViolationError("Changing simulator profile requires a new goal")
        if updated.spec.merchandising is not None:
            state = self.simulator_service.get_full_state(
                tenant_id=tenant_id, instance_id=record.simulator_instance_id
            )
            if state.merchandising is None:
                raise PolicyViolationError("Merchandising state is unavailable")
            if (
                updated.spec.merchandising.promotion_cap_minor
                < state.merchandising.promotion_spent_minor
            ):
                raise PolicyViolationError("Promotion cap is below recorded redemptions")
            state.merchandising.constraints = updated.spec.merchandising.model_copy(deep=True)
        for action in self.list_actions(tenant_id=tenant_id, goal_id=goal_id).items:
            if action.action.status in {
                ActionStatus.COMPILED,
                ActionStatus.EXECUTABLE,
                ActionStatus.AWAITING_APPROVAL,
                ActionStatus.APPROVED,
            }:
                action.action.status = transition_action(
                    action.action.status, ActionStatus.CANCELLED
                )
                self._audit(
                    action,
                    "goal_revision_invalidated_proposal",
                    ActorRole.SYSTEM,
                    "Goal revision changed; review a new proposal",
                )
        self._goals[goal_id] = updated
        self._mutation_idempotency[mutation_key] = goal_id
        return updated

    def set_goal_status(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID,
        status: GoalStatus,
        idempotency_key: str,
    ) -> GoalRecord:
        """Set a goal workflow status idempotently."""

        mutation_key = (tenant_id, str(goal_id), f"goal-{status.value}", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        record = self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        updated = GoalRecord(
            spec=record.spec.model_copy(update={"status": status}),
            revision=record.revision,
            planning_mode=record.planning_mode,
            soft_preferences=record.soft_preferences,
            scenario_id=record.scenario_id,
            simulator_instance_id=record.simulator_instance_id,
            seed=record.seed,
            created_at=record.created_at,
            updated_at=utc_now(),
        )
        self._goals[goal_id] = updated
        self._mutation_idempotency[mutation_key] = goal_id
        return updated

    async def run_goal(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID,
        request: ControllerRunRequest,
        idempotency_key: str,
    ) -> ControllerRunRecord:
        """Run the deterministic controller graph for one active goal."""

        cached = self._run_idempotency.get((tenant_id, goal_id, idempotency_key))
        if cached is not None:
            return self._run_for(tenant_id=tenant_id, run_id=cached)
        goal_record = self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        if goal_record.planning_mode != "deterministic":
            raise PolicyViolationError("model-backed planning requires the durable runtime")
        if goal_record.spec.status != GoalStatus.ACTIVE:
            raise PolicyViolationError("goal must be active before it can run")
        state = self.simulator_service.get_full_state(
            tenant_id=tenant_id,
            instance_id=goal_record.simulator_instance_id,
        )
        run_id = uuid5(NAMESPACE_URL, f"{tenant_id}:{goal_id}:run:{idempotency_key}")
        run = ControllerRunRecord(
            id=run_id,
            tenant_id=tenant_id,
            goal_id=goal_id,
            simulator_instance_id=state.id,
            status="running",
            started_at=state.current_time,
            next_run_at=state.current_time + timedelta(days=1),
            summary={"goal_revision": goal_record.revision, "planning_mode": "deterministic"},
        )
        self._trace(run, "load_goal_and_policy", "Loaded goal and tenant policy")
        policy = self.get_policy(tenant_id=tenant_id)
        self._trace(run, "acquire_run_lock", "Acquired in-process goal run lock")
        snapshot = build_observation_snapshot(tenant_id=tenant_id, run_id=run_id, state=state)
        run.snapshot = snapshot
        self._trace(run, "build_snapshot", "Built read-only simulator observation snapshot")
        assessment = assess_goal(goal_record.spec, state)
        run.summary["goal_assessment"] = assessment.model_dump(mode="json")
        merch_plan = (
            plan_merchandising(goal=goal_record.spec, state=state, run_id=run_id)
            if goal_record.spec.merchandising
            else None
        )
        opportunities = (
            merch_plan.opportunities
            if merch_plan
            else detect_opportunities(snapshot, state, goal_record.spec, assessment)
        )
        run.opportunities = opportunities
        self._trace(
            run,
            "detect_opportunities",
            "Detected simulator opportunities",
            {"count": len(opportunities)},
        )
        hypotheses = (
            merch_plan.hypotheses
            if merch_plan
            else self.model_provider.generate_hypotheses(opportunities)
        )
        run.hypotheses = hypotheses
        self._trace(run, "generate_hypotheses", "Generated deterministic hypotheses")
        drafts = (
            merch_plan.drafts
            if merch_plan
            else self.model_provider.generate_intent_drafts(
                opportunities=opportunities,
                hypotheses=hypotheses,
            )
        )
        if merch_plan:
            run.summary["merchandising_decision"] = merch_plan.decision
        run.intent_drafts = drafts
        self._trace(
            run,
            "generate_action_intents",
            "Generated schema-bound action drafts",
            {"count": len(drafts)},
        )
        batch = self.compiler.compile_candidates(goal=goal_record.spec, state=state, drafts=drafts)
        run.summary["compiler_rejections"] = batch.rejections
        compiled = batch.actions
        self._trace(run, "compile_actions", "Compiled drafts into typed action proposals")
        self._trace(run, "estimate", "Attached deterministic impact and cost estimates")
        provider = self.simulator_service.provider_for(tenant_id=tenant_id, instance_id=state.id)
        capabilities = (await provider.capabilities()).capabilities
        records = [
            self._record_for_action(
                action=action,
                goal=goal_record.spec,
                policy=policy,
                state=state,
                capabilities=capabilities,
                actions_in_run=1 if merch_plan else len(compiled),
            )
            for action in compiled
        ]
        self._trace(run, "evaluate_policy", "Evaluated explicit policy rules")
        if merch_plan:
            selected = select_merchandising(
                merch_plan.decision,
                records,
                compiler_rejections=batch.rejections,
            )
            run.summary["merchandising_decision"] = merch_plan.decision
        else:
            selected = select_portfolio(records, max_actions=policy.max_actions_per_run)
        self._trace(
            run,
            "select_portfolio",
            "Selected bounded action portfolio",
            {"count": len(selected)},
        )
        for record in selected:
            self._actions[record.action.id] = record
        run.action_ids = [record.action.id for record in selected]
        self._trace(run, "persist_proposals", "Persisted controller proposals in local memory")
        if any(record.action.status == ActionStatus.AWAITING_APPROVAL for record in selected):
            self._trace(run, "approval_interrupt", "Paused actions that require approval")
        if request.execute_bounded_auto:
            for record in selected:
                if record.action.status == ActionStatus.EXECUTABLE:
                    await self.execute_action(
                        tenant_id=tenant_id,
                        action_id=record.action.id,
                        idempotency_key=f"auto:{run.id}:{record.action.id}",
                    )
            self._trace(run, "execute_actions", "Executed bounded-auto simulator actions")
            self._trace(run, "reconcile", "Reconciled bounded-auto simulator executions")
            self._trace(run, "schedule_measurement", "Scheduled post-action measurement windows")
        run.status = (
            "awaiting_approval"
            if any(record.action.status == ActionStatus.AWAITING_APPROVAL for record in selected)
            else "completed"
        )
        run.completed_at = state.current_time
        run.summary.update(self._run_summary(selected))
        self._trace(run, "summarize", "Summarized controller run")
        self._runs[run_id] = run
        self._run_idempotency[(tenant_id, goal_id, idempotency_key)] = run_id
        return run

    def list_runs(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID | None = None,
    ) -> RunListResponse:
        """List controller runs."""

        runs = [run for run in self._runs.values() if run.tenant_id == tenant_id]
        if goal_id is not None:
            runs = [run for run in runs if run.goal_id == goal_id]
        return RunListResponse(items=sorted(runs, key=lambda item: (item.started_at, str(item.id))))

    def get_run(self, *, tenant_id: UUID, run_id: UUID) -> ControllerRunRecord:
        """Return one controller run."""

        return self._run_for(tenant_id=tenant_id, run_id=run_id)

    def run_trace(self, *, tenant_id: UUID, run_id: UUID) -> RunTraceResponse:
        """Return ordered run trace events."""

        run = self._run_for(tenant_id=tenant_id, run_id=run_id)
        return RunTraceResponse(run_id=run_id, items=list(run.trace))

    def run_events(self, *, tenant_id: UUID, run_id: UUID) -> RunEventListResponse:
        """Return ordered run events."""

        run = self._run_for(tenant_id=tenant_id, run_id=run_id)
        return RunEventListResponse(run_id=run_id, items=list(run.trace))

    def cancel_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        idempotency_key: str,
    ) -> ControllerRunRecord:
        """Cancel a run idempotently."""

        mutation_key = (tenant_id, str(run_id), "run-cancel", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._run_for(tenant_id=tenant_id, run_id=run_id)
        run = self._run_for(tenant_id=tenant_id, run_id=run_id)
        run.status = "cancelled"
        run.completed_at = utc_now()
        self._trace(run, "summarize", "Run cancelled by local operator")
        self._mutation_idempotency[mutation_key] = run_id
        return run

    def resume_run(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        idempotency_key: str,
    ) -> ControllerRunRecord:
        """Mark a cancelled run as completed for local demo resumption."""

        mutation_key = (tenant_id, str(run_id), "run-resume", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._run_for(tenant_id=tenant_id, run_id=run_id)
        run = self._run_for(tenant_id=tenant_id, run_id=run_id)
        if run.status == "cancelled":
            run.status = "completed"
            self._trace(run, "summarize", "Run resumed for inspection")
        self._mutation_idempotency[mutation_key] = run_id
        return run

    def list_actions(
        self,
        *,
        tenant_id: UUID,
        goal_id: UUID | None = None,
        run_id: UUID | None = None,
        status: ActionStatus | None = None,
    ) -> ActionListResponse:
        """List tenant action records."""

        records = [
            record for record in self._actions.values() if record.action.tenant_id == tenant_id
        ]
        if goal_id is not None:
            records = [record for record in records if record.action.goal_id == goal_id]
        if run_id is not None:
            records = [record for record in records if record.action.run_id == run_id]
        if status is not None:
            records = [record for record in records if record.action.status == status]
        return ActionListResponse(
            items=sorted(records, key=lambda item: (item.created_at, str(item.action.id)))
        )

    def get_action(self, *, tenant_id: UUID, action_id: UUID) -> ControllerActionRecord:
        """Return one action record."""

        return self._action_for(tenant_id=tenant_id, action_id=action_id)

    def approve_action(
        self,
        *,
        tenant_id: UUID,
        action_id: UUID,
        request: ActionApprovalRequest,
        actor_roles: set[str],
        decision: str,
        idempotency_key: str,
    ) -> ControllerActionRecord:
        """Approve or reject an action idempotently."""

        mutation_key = (tenant_id, str(action_id), f"approval-{decision}", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._action_for(tenant_id=tenant_id, action_id=action_id)
        record = self._action_for(tenant_id=tenant_id, action_id=action_id)
        if request.action_version_hash != record.action.version_hash:
            raise ApprovalError("approval hash does not match current action version")
        goal = self._goal_for(tenant_id=tenant_id, goal_id=record.action.goal_id)
        run = self._run_for(tenant_id=tenant_id, run_id=record.action.run_id)
        if run.summary.get("goal_revision", 1) != goal.revision:
            raise ApprovalError("goal revision changed; a new proposal is required")
        if record.approval_request is None:
            raise ApprovalError("action does not have an approval request")
        roles = _actor_roles(actor_roles)
        if not roles.intersection(record.approval_request.required_roles):
            raise ApprovalError("actor lacks a required approver role")
        actor = ActorRef(type="user", id=request.actor_id, roles=actor_roles)
        approval = Approval(
            id=uuid5(NAMESPACE_URL, f"{action_id}:approval:{decision}:{idempotency_key}"),
            tenant_id=tenant_id,
            request_id=record.approval_request.id,
            actor=actor,
            decision=cast(str, "approved" if decision == "approve" else "rejected"),
            comment=request.comment,
            action_version_hash=request.action_version_hash,
            decided_at=utc_now(),
        )
        record.approval = approval
        record.approval_request.status = approval.decision
        if approval.decision == "approved":
            record.action.status = transition_action(
                record.action.status,
                ActionStatus.APPROVED,
            )
            message = "Action approved with matching version hash"
        else:
            record.action.status = transition_action(
                record.action.status,
                ActionStatus.DENIED,
            )
            message = "Action rejected with matching version hash"
        self._audit(record, "approval_recorded", ActorRole.OPERATOR, message)
        record.updated_at = utc_now()
        self._mutation_idempotency[mutation_key] = action_id
        return record

    async def execute_action(
        self,
        *,
        tenant_id: UUID,
        action_id: UUID,
        idempotency_key: str,
    ) -> ControllerActionRecord:
        """Execute an action idempotently through the controller executor."""

        mutation_key = (tenant_id, str(action_id), "execute", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._action_for(tenant_id=tenant_id, action_id=action_id)
        record = self._action_for(tenant_id=tenant_id, action_id=action_id)
        goal = self._goal_for(tenant_id=tenant_id, goal_id=record.action.goal_id)
        run = self._run_for(tenant_id=tenant_id, run_id=record.action.run_id)
        if run.summary.get("goal_revision", 1) != goal.revision:
            raise PolicyViolationError("goal revision changed; a new proposal is required")
        state = self.simulator_service.get_full_state(
            tenant_id=tenant_id,
            instance_id=goal.simulator_instance_id,
        )
        capabilities = (
            await self.simulator_service.provider_for(
                tenant_id=tenant_id,
                instance_id=state.id,
            ).capabilities()
        ).capabilities
        context = self._policy_context(
            action=record.action,
            goal=goal.spec,
            policy=self.get_policy(tenant_id=tenant_id),
            state=state,
            capabilities=capabilities,
            actions_in_run=1,
        )
        has_approval = (
            record.approval is not None
            and record.approval.decision == "approved"
            and record.approval.action_version_hash == record.action.version_hash
        )
        self._audit(record, "execution_attempted", ActorRole.SYSTEM, "Executor started")
        try:
            result, reconciliation = await self.executor.execute(
                record=record,
                context=context,
                has_matching_approval=has_approval,
            )
        except PolicyViolationError:
            self._audit(
                record,
                "execution_blocked",
                ActorRole.SYSTEM,
                "Policy blocked execution",
            )
            record.updated_at = utc_now()
            raise
        if result.status == ExecutionStatus.SUCCEEDED:
            record.measurement = self._measurement_for(record, state)
            self._audit(
                record,
                "execution_succeeded",
                ActorRole.SYSTEM,
                "Simulator write succeeded and reconciled",
                {
                    "provider_request_id": result.provider_request_id,
                    "reconciled": reconciliation is not None,
                },
            )
        else:
            self._audit(
                record,
                "execution_failed",
                ActorRole.SYSTEM,
                "Simulator write failed",
                {"status": result.status.value},
            )
        record.updated_at = utc_now()
        self._mutation_idempotency[mutation_key] = action_id
        return record

    def cancel_action(
        self,
        *,
        tenant_id: UUID,
        action_id: UUID,
        idempotency_key: str,
    ) -> ControllerActionRecord:
        """Cancel an action proposal idempotently."""

        mutation_key = (tenant_id, str(action_id), "cancel", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._action_for(tenant_id=tenant_id, action_id=action_id)
        record = self._action_for(tenant_id=tenant_id, action_id=action_id)
        record.action.status = transition_action(record.action.status, ActionStatus.CANCELLED)
        self._audit(record, "action_cancelled", ActorRole.OPERATOR, "Action cancelled")
        record.updated_at = utc_now()
        self._mutation_idempotency[mutation_key] = action_id
        return record

    async def rollback_action(
        self,
        *,
        tenant_id: UUID,
        action_id: UUID,
        idempotency_key: str,
    ) -> ControllerActionRecord:
        """Rollback a completed simulator action idempotently."""

        mutation_key = (tenant_id, str(action_id), "rollback", idempotency_key)
        cached = self._mutation_idempotency.get(mutation_key)
        if cached is not None:
            return self._action_for(tenant_id=tenant_id, action_id=action_id)
        record = self._action_for(tenant_id=tenant_id, action_id=action_id)
        result = await self.executor.rollback(record=record, idempotency_key=idempotency_key)
        self._audit(
            record,
            "rollback_executed",
            ActorRole.SYSTEM,
            "Simulator rollback completed",
            {"status": result.status.value},
        )
        record.updated_at = utc_now()
        self._mutation_idempotency[mutation_key] = action_id
        return record

    def action_audit(self, *, tenant_id: UUID, action_id: UUID) -> ActionAuditResponse:
        """Return action audit entries."""

        record = self._action_for(tenant_id=tenant_id, action_id=action_id)
        return ActionAuditResponse(action_id=action_id, items=list(record.audit))

    def goal_progress(self, *, tenant_id: UUID, goal_id: UUID) -> GoalProgressResponse:
        """Return a compact progress summary for one goal."""

        goal = self._goal_for(tenant_id=tenant_id, goal_id=goal_id)
        state = self.simulator_service.get_full_state(
            tenant_id=tenant_id,
            instance_id=goal.simulator_instance_id,
        )
        assessment = assess_goal(goal.spec, state)
        records = self.list_actions(tenant_id=tenant_id, goal_id=goal_id).items
        runs = self.list_runs(tenant_id=tenant_id, goal_id=goal_id).items
        latest_run_id = runs[-1].id if runs else None
        return GoalProgressResponse(
            goal_id=goal_id,
            tenant_id=tenant_id,
            status=goal.spec.status,
            objective_metric=goal.spec.objective.metric,
            current_value=assessment.current_value,
            assessment=assessment,
            target_value=goal.spec.objective.target,
            pending_approvals=sum(
                1 for record in records if record.action.status == ActionStatus.AWAITING_APPROVAL
            ),
            executable_actions=sum(
                1 for record in records if record.action.status == ActionStatus.EXECUTABLE
            ),
            denied_actions=sum(
                1 for record in records if record.action.status == ActionStatus.DENIED
            ),
            succeeded_actions=sum(
                1 for record in records if record.action.status == ActionStatus.SUCCEEDED
            ),
            latest_run_id=latest_run_id,
        )

    def _record_for_action(
        self,
        *,
        action: CompiledAction,
        goal: GoalSpec,
        policy: ControllerPolicyConfig,
        state: SimulatorState,
        capabilities: set[Capability],
        actions_in_run: int,
    ) -> ControllerActionRecord:
        context = self._policy_context(
            action=action,
            goal=goal,
            policy=policy,
            state=state,
            capabilities=capabilities,
            actions_in_run=actions_in_run,
        )
        decision = self.policy_engine.decide(context)
        action.status = action_status_for_policy(decision.outcome)
        approval_request = (
            ApprovalRequest(
                id=uuid5(NAMESPACE_URL, f"{action.id}:approval-request:{action.version_hash}"),
                tenant_id=action.tenant_id,
                action_id=action.id,
                action_version_hash=action.version_hash,
                required_roles=decision.required_approver_roles,
                status="pending",
                expires_at=action.expires_at,
                created_at=state.current_time,
            )
            if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL
            else None
        )
        record = ControllerActionRecord(
            action=action,
            action_version_hash=action.version_hash,
            policy_decision=decision,
            approval_request=approval_request,
            created_at=state.current_time,
            updated_at=state.current_time,
        )
        self._audit(
            record,
            "policy_evaluated",
            ActorRole.SYSTEM,
            f"Policy outcome: {decision.outcome.value}",
            {"reason_codes": decision.reason_codes},
        )
        return record

    def _policy_context(
        self,
        *,
        action: CompiledAction,
        goal: GoalSpec,
        policy: ControllerPolicyConfig,
        state: SimulatorState,
        capabilities: set[Capability],
        actions_in_run: int,
    ) -> PolicyContext:
        active_targets = {
            str(record.action.normalized_parameters.get("target_key", ""))
            for record in self._actions.values()
            if record.action.tenant_id == action.tenant_id
            and record.action.status
            in {ActionStatus.EXECUTABLE, ActionStatus.AWAITING_APPROVAL, ActionStatus.SUCCEEDED}
        }
        active_targets.discard(str(action.normalized_parameters.get("target_key", "")))
        recent_targets = {
            str(record.action.normalized_parameters.get("target_key", ""))
            for record in self._actions.values()
            if record.action.tenant_id == action.tenant_id
            and record.action.status in {ActionStatus.SUCCEEDED, ActionStatus.EVALUATING}
        }
        recent_targets.discard("")
        latest = latest_runtime_metric(state)
        sample_size = latest.sessions if latest is not None else _trailing_sessions(state)
        return PolicyContext(
            goal=goal,
            policy=policy,
            action=action,
            capabilities=capabilities,
            sample_size=sample_size,
            data_age_minutes={"catalog": 0, "inventory": 0, "orders": 0, "campaigns": 0},
            budget_remaining=self._remaining_budget(goal),
            actions_in_run=actions_in_run,
            active_target_keys=active_targets,
            recent_target_keys=recent_targets,
            decision_time=state.current_time,
            active_interventions=sum(
                record.action.id != action.id
                and record.action.tenant_id == action.tenant_id
                and record.action.goal_id == goal.id
                and record.action.status
                in {
                    ActionStatus.EXECUTING,
                    ActionStatus.UNCERTAIN,
                    ActionStatus.SUCCEEDED,
                    ActionStatus.EVALUATING,
                }
                and (record.measurement is None or record.measurement.ends_at > state.current_time)
                for record in self._actions.values()
            ),
        )

    def _remaining_budget(self, goal: GoalSpec) -> Money:
        budget = goal.budgets[0].amount if goal.budgets else Money(amount_minor=0, currency="USD")
        spent = sum(
            record.action.estimated_cost.amount_minor
            for record in self._actions.values()
            if record.action.goal_id == goal.id
            and record.action.status in {ActionStatus.SUCCEEDED, ActionStatus.EVALUATING}
        )
        return Money(amount_minor=max(0, budget.amount_minor - spent), currency=budget.currency)

    def _measurement_for(
        self,
        record: ControllerActionRecord,
        state: SimulatorState,
    ) -> MeasurementSchedule:
        metric_values = {item.value for item in MetricName}
        metric = (
            MetricName(record.action.expected_impact.metric)
            if record.action.expected_impact.metric in metric_values
            else MetricName.CONTRIBUTION_PROFIT
        )
        return MeasurementSchedule(
            action_id=record.action.id,
            starts_at=state.current_time,
            ends_at=state.current_time + timedelta(days=7),
            metric_names=[metric],
            baseline_ref=state.state_hash,
        )

    def _run_summary(self, records: list[ControllerActionRecord]) -> JsonObject:
        return {
            "proposed_actions": len(records),
            "denied_actions": sum(
                1 for record in records if record.action.status == ActionStatus.DENIED
            ),
            "awaiting_approval_actions": sum(
                1 for record in records if record.action.status == ActionStatus.AWAITING_APPROVAL
            ),
            "executable_actions": sum(
                1 for record in records if record.action.status == ActionStatus.EXECUTABLE
            ),
        }

    def _trace(
        self,
        run: ControllerRunRecord,
        node: ControllerNode,
        message: str,
        details: JsonObject | None = None,
    ) -> None:
        sequence = len(run.trace) + 1
        run.trace.append(
            ControllerTraceEvent(
                id=uuid5(NAMESPACE_URL, f"{run.id}:trace:{sequence}:{node}"),
                tenant_id=run.tenant_id,
                run_id=run.id,
                sequence=sequence,
                node=node,
                occurred_at=run.started_at,
                message=message,
                details=details or {},
            )
        )

    def _audit(
        self,
        record: ControllerActionRecord,
        event_type: str,
        actor_role: ActorRole,
        message: str,
        details: JsonObject | None = None,
    ) -> None:
        sequence = len(record.audit) + 1
        record.audit.append(
            ActionAuditEntry(
                id=uuid5(NAMESPACE_URL, f"{record.action.id}:audit:{sequence}:{event_type}"),
                tenant_id=record.action.tenant_id,
                action_id=record.action.id,
                event_type=event_type,
                actor_role=actor_role,
                message=message,
                occurred_at=utc_now(),
                details=details or {},
            )
        )

    def _goal_for(self, *, tenant_id: UUID, goal_id: UUID) -> GoalRecord:
        record = self._goals.get(goal_id)
        if record is None or record.spec.tenant_id != tenant_id:
            raise GoalNotFoundError(str(goal_id))
        return record

    def _run_for(self, *, tenant_id: UUID, run_id: UUID) -> ControllerRunRecord:
        run = self._runs.get(run_id)
        if run is None or run.tenant_id != tenant_id:
            raise RunNotFoundError(str(run_id))
        return run

    def _action_for(self, *, tenant_id: UUID, action_id: UUID) -> ControllerActionRecord:
        record = self._actions.get(action_id)
        if record is None or record.action.tenant_id != tenant_id:
            raise ActionNotFoundError(str(action_id))
        return record


def _actor_roles(values: set[str]) -> set[ActorRole]:
    roles: set[ActorRole] = set()
    for value in values:
        try:
            roles.add(ActorRole(value))
        except ValueError:
            continue
    return roles


def _trailing_sessions(state: SimulatorState) -> int:
    return sum(metric.sessions for metric in state.metrics[-7:])
