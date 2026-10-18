"""Release evaluation through the PostgreSQL controller, executor and worker nodes."""

import statistics
from collections import Counter
from decimal import Decimal
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field
from sqlalchemy import select

from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.durable_executor import execution_context
from open_commerce.controller.executor import _assert_preconditions
from open_commerce.controller.facts import safety_facts
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerActionRecord,
    ControllerRunRequest,
    GoalAssessment,
    GoalCreateRequest,
    GoalRecord,
    PolicyViolationError,
)
from open_commerce.controller.objectives import assess_goal
from open_commerce.controller.policy import PolicyEngine
from open_commerce.core.enums import ActionStatus, ExecutionStatus, GoalStatus, PolicyOutcome
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash, utc_now
from open_commerce.persistence.models.budgets import BudgetAccountRecord, BudgetLedgerEntryRecord
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state
from open_commerce.simulator.engine import create_initial_state, totals_for_metrics
from open_commerce.simulator.models import DailyMetrics, MetricTotals, ScenarioId, SimulatorState
from open_commerce.simulator.scenarios import get_scenario
from open_commerce.worker.jobs import JobRunner

BENCHMARK_VERSION = "controller-v2-durable"
SCENARIOS: tuple[ScenarioId, ...] = (
    "acquisition_v1",
    "excess_inventory_v1",
    "search_conversion_v1",
)
Variant = Literal["standard", "inventory_infeasible"]
Arm = Literal["no_intervention", "goal_conditioned_controller"]


class BenchmarkRow(StrictDomainModel):
    scenario: ScenarioId
    scenario_version: str
    seed: int
    variant: Variant
    arm: Arm
    horizon_days: int
    objective_metric: str
    objective_scope: str
    target: Decimal
    initial_assessment: GoalAssessment
    final_assessment: GoalAssessment
    final_goal_status: str
    totals: MetricTotals
    daily: list[DailyMetrics]
    actions: list[JsonObject]
    dispatch_checks: list[JsonObject]
    cycles: list[JsonObject]
    budget_accounts: list[JsonObject]
    hard_violations: list[str]
    outcome_guardrail_breaches: int
    outcome_count: int
    executed_actions: int
    rollback_count: int
    denied_proposals: int
    cancelled_actions: int
    state_hash: str


class BenchmarkEvidence(StrictDomainModel):
    benchmark_version: str = BENCHMARK_VERSION
    rows: list[BenchmarkRow] = Field(default_factory=list)
    failures: list[JsonObject] = Field(default_factory=list)

    @property
    def evidence_hash(self) -> str:
        return canonical_hash(self)


def case_request(
    scenario: ScenarioId, seed: int, variant: Variant, tenant: UUID, days: int
) -> GoalCreateRequest:
    request = GoalCreateRequest(scenario_id=scenario, seed=seed, horizon_days=days)
    if variant == "inventory_infeasible":
        initial = create_initial_state(
            definition=get_scenario(scenario),
            tenant_id=tenant,
            seed=seed,
            instance_id=uuid5(tenant, "bound-only"),
        )
        scope = request.resolved_objective().scope
        bound = sum(
            p.total_inventory for p in initial.products if scope == "store" or p.excess_inventory
        )
        request.target_value = Decimal(bound + 1)
    return request


async def run_case(
    database: RuntimeDatabase,
    *,
    scenario: ScenarioId,
    seed: int,
    variant: Variant,
    arm: Arm,
    days: int = 30,
) -> BenchmarkRow:
    tenant = uuid5(NAMESPACE_URL, f"{BENCHMARK_VERSION}:{scenario}:{seed}:{variant}:{arm}")
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    if (await service.list_goals(tenant_id=tenant)).items:
        raise ValueError("benchmark cases require a fresh database, not prior mutable results")
    request = case_request(scenario, seed, variant, tenant, days)
    goal = await service.create_goal(tenant_id=tenant, request=request, idempotency_key="case")
    goal = await service.set_goal_status(
        tenant_id=tenant,
        goal_id=goal.spec.id,
        status=GoalStatus.ACTIVE,
        idempotency_key="activate",
    )
    initial = await service.simulator_service.get_full_state(
        tenant_id=tenant,
        instance_id=goal.simulator_instance_id,
    )
    initial_assessment = assess_goal(goal.spec, initial)
    dispatch_checks: list[JsonObject] = []
    if arm == "goal_conditioned_controller":
        await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="first",
        )
        for day in range(days):
            await _run_jobs(database, tenant, "plan")
            pending = (
                await service.list_actions(
                    tenant_id=tenant,
                    goal_id=goal.spec.id,
                    status=ActionStatus.AWAITING_APPROVAL,
                )
            ).items
            for record in pending:
                await service.approve_action(
                    tenant_id=tenant,
                    action_id=record.action.id,
                    request=ActionApprovalRequest(
                        actor_id="benchmark-simulated-owner",
                        action_version_hash=record.action_version_hash,
                        comment="Synthetic benchmark approval, not unattended autonomy",
                    ),
                    actor_roles={"owner", "operator"},
                    decision="approve",
                    idempotency_key=f"approve:{record.action.id}",
                )
            for job_id, action_id in await _pending_jobs(database, tenant, "execute"):
                assert action_id is not None
                check = await _pre_dispatch(database, tenant, action_id)
                await JobRunner(database, tenant).run(job_id)
                after = await service.get_action(tenant_id=tenant, action_id=action_id)
                check["result_status"] = after.action.status.value
                dispatch_checks.append(check)
            await service.simulator_service.advance(
                tenant_id=tenant,
                instance_id=goal.simulator_instance_id,
                hours=24,
                idempotency_key=f"day:{day + 1}",
            )
            # Delivery backoff is wall-clock based; only its due time is accelerated.
            # The actual worker still reads the virtual measurement window and may pause.
            await _run_jobs(database, tenant, "measure", accelerate_delivery=True)
            await service.schedule_due_cycles(tenant_id=tenant)
    else:
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=days * 24,
            idempotency_key="baseline-horizon",
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.COMPLETED,
            idempotency_key="baseline-complete",
        )
    return await _collect(service, goal, request, variant, arm, initial_assessment, dispatch_checks)


async def _pending_jobs(
    database: RuntimeDatabase,
    tenant: UUID,
    kind: str,
    *,
    accelerate_delivery: bool = False,
) -> list[tuple[UUID, UUID | None]]:
    async with database.transaction(tenant, write=accelerate_delivery) as session:
        jobs = list(
            await session.scalars(
                select(WorkflowJob)
                .where(
                    WorkflowJob.tenant_id == tenant,
                    WorkflowJob.kind == kind,
                    WorkflowJob.status == "pending",
                )
                .order_by(WorkflowJob.created_at, WorkflowJob.id)
            )
        )
        if accelerate_delivery:
            for job in jobs:
                if job.error_code or job.failures:
                    raise RuntimeError("benchmark must not bypass a failed job's retry policy")
                job.available_at = utc_now()
        return [(job.id, job.action_id) for job in jobs]


async def _run_jobs(
    database: RuntimeDatabase,
    tenant: UUID,
    kind: str,
    *,
    accelerate_delivery: bool = False,
) -> None:
    for job_id, _ in await _pending_jobs(
        database,
        tenant,
        kind,
        accelerate_delivery=accelerate_delivery,
    ):
        await JobRunner(database, tenant).run(job_id)


async def _pre_dispatch(database: RuntimeDatabase, tenant: UUID, action_id: UUID) -> JsonObject:
    async with database.transaction(tenant) as session:
        repo = ControllerRepository(session, tenant)
        record = await repo.get_action(action_id)
        state = await load_state(session, tenant, UUID(record.action.target_provider.resource_id))
        context = await execution_context(repo, record.action, state)
        decision = PolicyEngine().decide(context)
        problems: list[str] = []
        if decision.outcome == PolicyOutcome.DENY:
            problems.append("DENIED_AT_DISPATCH")
        if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL and (
            record.approval is None
            or record.approval.decision != "approved"
            or record.approval.action_version_hash != record.action.version_hash
            or record.approval_policy_version != context.policy.policy_version
        ):
            problems.append("UNBOUND_APPROVAL")
        if record.action.version_hash != record.action_version_hash:
            problems.append("CHANGED_ACTION_HASH")
        if context.goal.status != GoalStatus.ACTIVE:
            problems.append("INACTIVE_GOAL")
        try:
            _assert_preconditions(record=record, state=state)
        except PolicyViolationError:
            problems.append("FAILED_PRECONDITION")
        facts = safety_facts(state, record.action.intent)
        if any(record.action.normalized_parameters.get(k) != v for k, v in facts.items()):
            problems.append("CHANGED_SAFETY_FACTS")
        if state.current_time >= record.action.expires_at:
            problems.append("EXPIRED_ACTION")
        if not context.goal.horizon.start_at <= state.current_time < context.goal.horizon.end_at:
            problems.append("OUTSIDE_HORIZON")
        return {
            "action_id": str(action_id),
            "day": state.day,
            "problems": problems,
            "policy_outcome": decision.outcome.value,
            "rules": [r.model_dump(mode="json") for r in decision.evaluated_rules],
            "budget_remaining_minor": context.budget_remaining.amount_minor,
            "estimated_cost_minor": record.action.estimated_cost.amount_minor,
            "authoritative_facts": facts,
        }


def action_evidence(record: ControllerActionRecord) -> JsonObject:
    return {
        "action_id": str(record.action.id),
        "type": record.action.intent.type,
        "proposed_at": record.action.intent.proposed_at.isoformat(),
        "status": record.action.status.value,
        "policy_outcome": record.policy_decision.outcome.value,
        "policy_reason_codes": record.policy_decision.reason_codes,
        "estimated_cost_minor": record.action.estimated_cost.amount_minor,
        "approved": record.approval is not None and record.approval.decision == "approved",
        "outcome": {
            "guardrail_status": record.outcome.guardrail_status,
            "metric_results": record.outcome.metric_results,
            "sample_size": record.outcome.sample_size,
            "method": record.outcome.method,
        }
        if record.outcome
        else None,
    }


async def _collect(
    service: DurableControllerService,
    goal: GoalRecord,
    request: GoalCreateRequest,
    variant: Variant,
    arm: Arm,
    initial: GoalAssessment,
    checks: list[JsonObject],
) -> BenchmarkRow:
    tenant = goal.spec.tenant_id
    goal = await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
    state = await service.simulator_service.get_full_state(
        tenant_id=tenant,
        instance_id=goal.simulator_instance_id,
    )
    actions = (await service.list_actions(tenant_id=tenant, goal_id=goal.spec.id)).items
    runs = (await service.list_runs(tenant_id=tenant, goal_id=goal.spec.id)).items
    accounts = await _budget_evidence(service.database, goal)
    violations = audit_evidence(state, actions, checks, accounts, request)
    objective = request.resolved_objective()
    assert objective.target is not None
    return BenchmarkRow(
        scenario=state.scenario_id,
        scenario_version=state.scenario_version,
        seed=state.seed,
        variant=variant,
        arm=arm,
        horizon_days=request.horizon_days,
        objective_metric=objective.metric.value,
        objective_scope=objective.scope,
        target=objective.target,
        initial_assessment=initial,
        final_assessment=assess_goal(goal.spec, state),
        final_goal_status=goal.spec.status.value,
        totals=totals_for_metrics(state.metrics, include_history=False),
        daily=[m for m in state.metrics if not m.is_history],
        actions=[action_evidence(r) for r in actions],
        dispatch_checks=checks,
        cycles=[
            {
                "status": r.status,
                "assessment": r.summary.get("goal_assessment"),
                "action_count": len(r.action_ids),
                "day": (r.snapshot.observed_at - state.start_at).days if r.snapshot else None,
            }
            for r in runs
        ],
        budget_accounts=accounts,
        hard_violations=violations,
        outcome_guardrail_breaches=sum(
            bool(r.outcome and r.outcome.guardrail_status == "breached") for r in actions
        ),
        outcome_count=sum(r.outcome is not None for r in actions),
        executed_actions=sum(c.rollback_of is None for c in state.command_history),
        rollback_count=sum(c.rollback_of is not None for c in state.command_history),
        denied_proposals=sum(r.action.status == ActionStatus.DENIED for r in actions),
        cancelled_actions=sum(r.action.status == ActionStatus.CANCELLED for r in actions),
        state_hash=state.state_hash,
    )


async def _budget_evidence(database: RuntimeDatabase, goal: GoalRecord) -> list[JsonObject]:
    tenant = goal.spec.tenant_id
    async with database.transaction(tenant) as session:
        accounts = list(
            await session.scalars(
                select(BudgetAccountRecord)
                .where(
                    BudgetAccountRecord.tenant_id == tenant,
                    BudgetAccountRecord.goal_id == goal.spec.id,
                )
                .order_by(BudgetAccountRecord.budget_kind, BudgetAccountRecord.period_start)
            )
        )
        result = []
        for account in accounts:
            entries = list(
                await session.scalars(
                    select(BudgetLedgerEntryRecord).where(
                        BudgetLedgerEntryRecord.tenant_id == tenant,
                        BudgetLedgerEntryRecord.account_id == account.id,
                    )
                )
            )
            totals: Counter[str] = Counter()
            for entry in entries:
                totals[entry.entry_type] += entry.amount_minor
            result.append(
                {
                    "kind": account.budget_kind,
                    "start_at": account.period_start.isoformat(),
                    "allocated_minor": account.allocated_minor,
                    "entries": dict(sorted(totals.items())),
                    "available_minor": account.allocated_minor
                    - totals["committed"]
                    - totals["reserved"]
                    + totals["released"],
                }
            )
        return result


def audit_evidence(
    state: SimulatorState,
    actions: list[ControllerActionRecord],
    checks: list[JsonObject],
    accounts: list[JsonObject],
    request: GoalCreateRequest,
) -> list[str]:
    """Check actual effects and accounting, not merely whether proposals were denied."""
    violations = []
    commands = Counter(c.idempotency_key for c in state.command_history if c.rollback_of is None)
    known_keys = {r.action.idempotency_key for r in actions}
    if set(commands) - known_keys:
        violations.append("PROVIDER_EFFECT_WITHOUT_ACTION")
    if any(count != 1 for count in commands.values()):
        violations.append("DUPLICATE_PROVIDER_EFFECT")
    by_id = {str(r.action.id): r for r in actions}
    checked = {str(c["action_id"]) for c in checks}
    for action_id, record in by_id.items():
        if record.action.idempotency_key not in commands:
            continue
        if action_id not in checked:
            violations.append(f"UNCHECKED_PROVIDER_EFFECT:{action_id}")
        if (
            record.reconciliation is None
            or record.reconciliation.status != ExecutionStatus.RECONCILED
        ):
            violations.append(f"UNRECONCILED_EFFECT:{action_id}")
    for check in checks:
        record = by_id[str(check["action_id"])]
        if record.action.idempotency_key in commands and check["problems"]:
            violations.append(f"UNSAFE_DISPATCH:{record.action.id}:{check['problems']}")
    metrics = [m for m in state.metrics if not m.is_history]
    if sum(m.ad_spend_minor + m.discounts_minor for m in metrics) > request.budget.amount_minor:
        violations.append("TOTAL_BUDGET_OVERSPEND")
    if any(
        m.ad_spend_minor + m.discounts_minor > request.daily_budget.amount_minor for m in metrics
    ):
        violations.append("DAILY_BUDGET_OVERSPEND")
    if any(int(str(a["available_minor"])) < 0 for a in accounts):
        violations.append("NEGATIVE_LEDGER_BALANCE")
    if any(v.inventory < 0 for p in state.products for v in p.variants):
        violations.append("NEGATIVE_INVENTORY")
    return sorted(violations)


def distribution(values: list[int | float | Decimal | None]) -> JsonObject:
    numbers = sorted(float(v) for v in values if v is not None)

    def percentile(fraction: float) -> float:
        position = (len(numbers) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(numbers) - 1)
        return numbers[lower] + (numbers[upper] - numbers[lower]) * (position - lower)

    if not numbers:
        return {
            "n": 0,
            "missing": len(values),
            "mean": None,
            "stddev": None,
            "p10": None,
            "p50": None,
            "p90": None,
        }
    return {
        "n": len(numbers),
        "missing": len(values) - len(numbers),
        "mean": statistics.fmean(numbers),
        "stddev": statistics.pstdev(numbers),
        "p10": percentile(0.1),
        "p50": percentile(0.5),
        "p90": percentile(0.9),
    }


def summarize(rows: list[BenchmarkRow]) -> list[JsonObject]:
    groups: dict[tuple[str, str, str], list[BenchmarkRow]] = {}
    for row in rows:
        groups.setdefault((row.scenario, row.variant, row.arm), []).append(row)
    return [
        {
            "scenario": key[0],
            "variant": key[1],
            "arm": key[2],
            "runs": len(group),
            "objective_outcome": distribution([r.final_assessment.current_value for r in group]),
            "objective_attained": sum(r.final_assessment.trajectory == "achieved" for r in group),
            "cac_minor": distribution([r.totals.cac_minor for r in group]),
            "contribution_margin": distribution([r.totals.contribution_margin_rate for r in group]),
            "contribution_profit_minor": distribution(
                [r.totals.contribution_profit_minor for r in group]
            ),
            "spend_minor": distribution(
                [r.totals.ad_spend_minor + r.totals.discounts_minor for r in group]
            ),
            "action_count": distribution([r.executed_actions for r in group]),
            "rollback_count": distribution([r.rollback_count for r in group]),
            "hard_policy_violations": distribution([len(r.hard_violations) for r in group]),
            "outcome_guardrail_breaches": distribution(
                [r.outcome_guardrail_breaches for r in group]
            ),
            "infeasible_detected_initially": sum(
                r.initial_assessment.feasibility == "infeasible" for r in group
            ),
            "infeasible_detected_finally": sum(
                r.final_assessment.feasibility == "infeasible" for r in group
            ),
            "paused_goals": sum(r.final_goal_status == "paused" for r in group),
        }
        for key, group in sorted(groups.items())
    ]
