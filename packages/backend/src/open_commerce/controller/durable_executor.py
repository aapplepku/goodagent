"""PostgreSQL-backed execution with commit boundaries and recovery by receipt."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from open_commerce.controller.executor import _assert_preconditions, _dispatch
from open_commerce.controller.facts import safety_facts
from open_commerce.controller.models import (
    ActionAuditEntry,
    ControllerActionRecord,
    MeasurementSchedule,
    PolicyViolationError,
)
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.core.actions import CompiledAction, transition_action
from open_commerce.core.enums import (
    ActionStatus,
    ActorRole,
    ConstraintOperator,
    ExecutionStatus,
    GoalStatus,
    MetricName,
    PolicyOutcome,
)
from open_commerce.core.money import Money
from open_commerce.core.providers import ExecutionRef, ProviderResult
from open_commerce.core.types import JsonObject, SafeError, utc_now
from open_commerce.persistence.models.actions import (
    ActionExecution,
    ActionReconciliation,
    CompiledActionRecord,
    Intervention,
)
from open_commerce.persistence.models.budgets import BudgetAccountRecord, BudgetLedgerEntryRecord
from open_commerce.persistence.models.simulator import SimulatorCommandRecordModel
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.budgets import SqlBudgetRepository
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state
from open_commerce.simulator.engine import totals_for_metrics
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.provider import SimulatorProvider
from open_commerce.simulator.scenarios import SIMULATOR_CAPABILITIES


async def budget_accounts(
    repo: ControllerRepository, action: CompiledAction, state: SimulatorState
) -> list[BudgetAccountRecord]:
    rows = await repo.session.scalars(
        select(BudgetAccountRecord).where(
            BudgetAccountRecord.tenant_id == repo.tenant_id,
            BudgetAccountRecord.goal_id == action.goal_id,
            BudgetAccountRecord.period_start <= state.current_time,
            BudgetAccountRecord.period_end > state.current_time,
        )
    )
    return list(rows)


async def execution_context(
    repo: ControllerRepository, action: CompiledAction, state: SimulatorState
) -> PolicyContext:
    """Read policy facts in the same transaction as the execution decision."""
    goal = await repo.get_goal(action.goal_id)
    policy = await repo.get_policy()
    accounts = await budget_accounts(repo, action, state)
    balances = []
    ledger = SqlBudgetRepository(repo.session)
    for account in accounts:
        balance = await ledger.available_minor(repo.tenant_id, account.id)
        entries = await repo.session.scalars(
            select(BudgetLedgerEntryRecord).where(
                BudgetLedgerEntryRecord.tenant_id == repo.tenant_id,
                BudgetLedgerEntryRecord.account_id == account.id,
                BudgetLedgerEntryRecord.action_id == action.id,
            )
        )
        own = list(entries)
        balance += sum(item.amount_minor for item in own if item.entry_type == "reserved")
        balance -= sum(item.amount_minor for item in own if item.entry_type == "released")
        balances.append(max(0, balance))
    records = await repo.list_actions(goal_id=action.goal_id)
    others = [item for item in records if item.action.id != action.id]
    active_records = [
        item
        for item in others
        if item.action.status
        in {
            ActionStatus.EXECUTING,
            ActionStatus.UNCERTAIN,
            ActionStatus.SUCCEEDED,
            ActionStatus.EVALUATING,
        }
        and (item.measurement is None or item.measurement.ends_at > state.current_time)
    ]
    active = {
        str(item.action.normalized_parameters.get("target_key", "")) for item in active_records
    }
    age = max(0, int((state.current_time - action.intent.proposed_at).total_seconds() // 60))
    return PolicyContext(
        goal=goal.spec,
        policy=policy,
        action=action,
        capabilities=SIMULATOR_CAPABILITIES,
        sample_size=sum(item.sessions for item in state.metrics[-7:]),
        data_age_minutes={
            source: age for source in ("catalog", "inventory", "orders", "campaigns")
        },
        budget_remaining=Money(
            amount_minor=min(balances, default=0), currency=action.estimated_cost.currency
        ),
        actions_in_run=sum(item.action.run_id == action.run_id for item in records) or 1,
        active_target_keys=active,
        recent_target_keys=active,
        decision_time=state.current_time,
        active_interventions=len(active_records),
    )


class DurableExecutor:
    """Only this path persists provider effects for durable controller actions.

    The simulator's state and receipt share a transaction. A crash can leave a
    prepared attempt or a committed receipt, never an unrecorded simulator effect.
    The latter is reconciled, not dispatched again. No live-provider semantics
    are implied by this local transaction guarantee.
    """

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def execute(
        self, *, tenant_id: UUID, action_id: UUID, idempotency_key: str
    ) -> ControllerActionRecord:
        return await self._operate(tenant_id, action_id, idempotency_key, rollback=False)

    async def rollback_action(
        self, *, tenant_id: UUID, action_id: UUID, idempotency_key: str
    ) -> ControllerActionRecord:
        return await self._operate(tenant_id, action_id, idempotency_key, rollback=True)

    async def _operate(
        self, tenant_id: UUID, action_id: UUID, key: str, *, rollback: bool
    ) -> ControllerActionRecord:
        scope = f"action:{action_id}:{'rollback' if rollback else 'execute'}"
        async with self.database.transaction(tenant_id, write=True) as session:
            requests = RequestRepository(session, tenant_id)
            replay = await requests.replay(scope=scope, key=key, request={})
            if replay is not None:
                return ControllerActionRecord.model_validate(replay)
            repo = ControllerRepository(session, tenant_id)
            record = await repo.get_action(action_id)
            attempt = await self._attempt(repo, action_id, rollback=rollback)
            if attempt is None:
                state = await load_state(
                    session, tenant_id, UUID(record.action.target_provider.resource_id)
                )
                if rollback:
                    self._validate_rollback(record)
                    await self._set_status(repo, action_id, ActionStatus.ROLLBACK_PROPOSED)
                    await self._set_status(repo, action_id, ActionStatus.ROLLING_BACK)
                else:
                    await self._validate_execute(repo, record, state)
                    for account in await budget_accounts(repo, record.action, state):
                        if account.currency != record.action.estimated_cost.currency:
                            raise PolicyViolationError("budget currency mismatch")
                        await SqlBudgetRepository(session).reserve(
                            tenant_id,
                            account.id,
                            record.action.estimated_cost.amount_minor,
                            f"{action_id}:reserve",
                            action_id,
                        )
                    if record.action.status == ActionStatus.APPROVED:
                        await self._set_status(repo, action_id, ActionStatus.EXECUTABLE)
                    await self._set_status(repo, action_id, ActionStatus.EXECUTING)
                attempt = ActionExecution(
                    id=uuid5(
                        NAMESPACE_URL,
                        f"{action_id}:attempt:{'rollback' if rollback else 'execute'}",
                    ),
                    tenant_id=tenant_id,
                    action_id=action_id,
                    attempt=2 if rollback else 1,
                    status="prepared",
                    request_summary={
                        "operation": "rollback" if rollback else "execute",
                        "action_hash": record.action.version_hash,
                    },
                    before_state={},
                    started_at=utc_now(),
                )
                session.add(attempt)
                self._audit(
                    repo, record, "execution_prepared", "Durable execution attempt prepared"
                )
            attempt_id = attempt.id
        await self._after_prepare(attempt_id)
        await self._provider_phase(tenant_id, action_id, rollback=rollback)
        await self._after_provider_commit(attempt_id)
        return await self._finalize(tenant_id, action_id, key, scope, rollback=rollback)

    async def _validate_execute(
        self, repo: ControllerRepository, record: ControllerActionRecord, state: SimulatorState
    ) -> None:
        action = record.action
        if (
            action.target_provider.provider_type != "simulator"
            or action.target_provider.integration_id is not None
        ):
            raise PolicyViolationError("this release only executes simulator targets")
        if action.version_hash != record.action_version_hash:
            raise PolicyViolationError("compiled action hash changed")
        for name, value in safety_facts(state, action.intent).items():
            if action.normalized_parameters.get(name) != value:
                raise PolicyViolationError("authoritative safety facts changed after compilation")
        if state.current_time >= action.expires_at or utc_now() >= record.created_at + timedelta(
            hours=24
        ):
            raise PolicyViolationError("action expired")
        context = await execution_context(repo, action, state)
        goal_record = await repo.get_goal(action.goal_id)
        source_run = await repo.get_run(action.run_id)
        if source_run.summary.get("goal_revision", 1) != goal_record.revision:
            raise PolicyViolationError("goal revision changed after proposal review")
        context = replace(
            context, deployment_kill_switch=self.database.settings.deployment_kill_switch
        )
        if context.goal.status != GoalStatus.ACTIVE:
            raise PolicyViolationError("goal is not active")
        if not context.goal.horizon.start_at <= state.current_time < context.goal.horizon.end_at:
            raise PolicyViolationError("goal execution horizon has ended or not started")
        decision = PolicyEngine().decide(context)
        await repo.add_policy_decision(action.id, action.version_hash, decision)
        if decision.outcome == PolicyOutcome.DENY:
            raise PolicyViolationError("policy denied action: " + ", ".join(decision.reason_codes))
        if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL:
            approval = record.approval
            if (
                approval is None
                or approval.decision != "approved"
                or approval.action_version_hash != action.version_hash
                or record.approval_policy_version != context.policy.policy_version
            ):
                raise PolicyViolationError("matching action and policy approval is required")
        _assert_preconditions(record=record, state=state)

    @staticmethod
    def _validate_rollback(record: ControllerActionRecord) -> None:
        if (
            not record.action.rollback_plan.available
            or record.execution_result is None
            or record.execution_result.provider_request_id is None
            or record.reconciliation is None
            or record.reconciliation.status != ExecutionStatus.RECONCILED
        ):
            raise PolicyViolationError(
                "rollback requires a reconciled execution and rollback metadata"
            )

    async def _provider_phase(self, tenant_id: UUID, action_id: UUID, *, rollback: bool) -> None:
        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ControllerRepository(session, tenant_id)
            record = await repo.get_action(action_id)
            attempt = await self._attempt(repo, action_id, rollback=rollback)
            if attempt is None:
                raise PolicyViolationError("execution was not prepared")
            # A recorded response is always reconciled before considering another dispatch.
            if attempt.response_summary is not None:
                return
            state = await load_state(
                session, tenant_id, UUID(record.action.target_provider.resource_id)
            )
            provider = SimulatorProvider(state)
            if rollback:
                self._validate_rollback(record)
                assert record.execution_result and record.execution_result.provider_request_id
                result = await provider.rollback(
                    execution_id=UUID(record.execution_result.provider_request_id),
                    idempotency_key=f"{action_id}:rollback",
                )
            else:
                try:
                    await self._validate_execute(repo, record, state)
                except PolicyViolationError:
                    result = ProviderResult(
                        status=ExecutionStatus.FAILED,
                        before_state={},
                        error=SafeError(
                            code="PRECONDITION_OR_POLICY_CHANGED",
                            message="Execution stopped by current safety checks",
                        ),
                    )
                else:
                    result = await _dispatch(provider=provider, record=record)
            if result.status == ExecutionStatus.SUCCEEDED:
                await SqlSimulatorRepository(session).save_state(provider.state)
                receipt = next(
                    item
                    for item in provider.state.command_history
                    if str(item.execution_id) == result.provider_request_id
                )
                session.add(
                    SimulatorCommandRecordModel(
                        id=receipt.execution_id,
                        tenant_id=tenant_id,
                        instance_id=state.id,
                        idempotency_key=receipt.idempotency_key,
                        action_type=receipt.action_type,
                        status=receipt.status.value,
                        before_state=receipt.before_state,
                        after_state=receipt.after_state,
                        rollback_state=receipt.rollback_state,
                        rollback_of=receipt.rollback_of,
                        created_at=receipt.created_at,
                    )
                )
            attempt.status = "provider_recorded"
            attempt.response_summary = result.model_dump(mode="json")
            attempt.before_state = result.before_state
            attempt.after_state = result.after_state
            attempt.provider_request_id = result.provider_request_id
            attempt.provider_resource_id = result.provider_resource_id
            self._audit(
                repo,
                record,
                "provider_result_recorded",
                "Provider result committed with simulator state",
            )

    async def _finalize(
        self, tenant_id: UUID, action_id: UUID, key: str, scope: str, *, rollback: bool
    ) -> ControllerActionRecord:
        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ControllerRepository(session, tenant_id)
            record = await repo.get_action(action_id)
            attempt = await self._attempt(repo, action_id, rollback=rollback)
            if attempt is None or attempt.response_summary is None:
                raise PolicyViolationError("provider result is not recorded")
            if attempt.completed_at is not None:
                return record
            result = ProviderResult.model_validate(attempt.response_summary)
            state = await load_state(
                session, tenant_id, UUID(record.action.target_provider.resource_id)
            )
            if result.provider_request_id:
                reconciliation = await SimulatorProvider(state).reconcile(
                    ExecutionRef(
                        execution_id=UUID(result.provider_request_id),
                        tenant_id=tenant_id,
                        action_id=action_id,
                        provider=record.action.target_provider,
                    )
                )
                session.add(
                    ActionReconciliation(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        execution_id=attempt.id,
                        observed_remote_state=reconciliation.observed_remote_state,
                        outcome=reconciliation.status.value,
                        reconciled_at=utc_now(),
                        details=reconciliation.model_dump(mode="json"),
                    )
                )
                result.status = (
                    ExecutionStatus.SUCCEEDED
                    if reconciliation.status == ExecutionStatus.RECONCILED
                    else ExecutionStatus.UNCERTAIN
                )
            elif result.status == ExecutionStatus.SUCCEEDED:
                result.status = ExecutionStatus.UNCERTAIN
            succeeded = result.status == ExecutionStatus.SUCCEEDED
            uncertain = result.status == ExecutionStatus.UNCERTAIN
            target = (
                (ActionStatus.ROLLED_BACK if succeeded else ActionStatus.ROLLBACK_FAILED)
                if rollback
                else (
                    ActionStatus.SUCCEEDED
                    if succeeded
                    else ActionStatus.UNCERTAIN
                    if uncertain
                    else ActionStatus.FAILED
                )
            )
            if rollback and uncertain:
                # Keep the durable rollback attempt pending until its effect is reconciled.
                target = ActionStatus.ROLLING_BACK
            await self._set_status(repo, action_id, target)
            attempt.status = result.status.value
            attempt.response_summary = result.model_dump(mode="json")
            attempt.completed_at = None if uncertain else utc_now()
            if (not rollback and not uncertain and not succeeded) or (rollback and succeeded):
                ledger = SqlBudgetRepository(session)
                reservations = await session.scalars(
                    select(BudgetLedgerEntryRecord).where(
                        BudgetLedgerEntryRecord.tenant_id == tenant_id,
                        BudgetLedgerEntryRecord.action_id == action_id,
                        BudgetLedgerEntryRecord.entry_type == "reserved",
                    )
                )
                for reservation in reservations:
                    outstanding = await ledger.outstanding_minor(
                        tenant_id, reservation.account_id, action_id
                    )
                    await ledger.release(
                        tenant_id,
                        reservation.account_id,
                        outstanding,
                        f"{action_id}:release:"
                        f"{'rollback' if rollback else 'failed'}:{reservation.id}",
                        action_id,
                    )
            if not rollback and succeeded:
                await self._schedule_measurement(repo, record, state)
            if rollback and succeeded:
                intervention = await session.scalar(
                    select(Intervention).where(
                        Intervention.tenant_id == tenant_id, Intervention.action_id == action_id
                    )
                )
                if intervention:
                    intervention.status = "rolled_back"
            self._audit(
                repo,
                record,
                "execution_reconciled"
                if succeeded
                else "execution_unresolved"
                if uncertain
                else "execution_failed",
                "Execution result checked against current target state",
            )
            await session.flush()
            from open_commerce.controller.workflow import append_trace, refresh_run

            run = await refresh_run(repo, record.action.run_id)
            await append_trace(
                repo,
                run,
                "reconcile",
                "Provider effect checked against authoritative state",
                {"action_id": str(action_id), "status": target.value, "rollback": rollback},
            )
            updated = await repo.get_action(action_id)
            if not uncertain:
                requests = RequestRepository(session, tenant_id)
                if await requests.replay(scope=scope, key=key, request={}) is None:
                    requests.remember(scope=scope, key=key, request={}, response=updated)
            return updated

    @staticmethod
    async def _attempt(
        repo: ControllerRepository, action_id: UUID, *, rollback: bool
    ) -> ActionExecution | None:
        attempt: ActionExecution | None = await repo.session.scalar(
            select(ActionExecution).where(
                ActionExecution.tenant_id == repo.tenant_id,
                ActionExecution.action_id == action_id,
                ActionExecution.attempt == (2 if rollback else 1),
            )
        )
        return attempt

    @staticmethod
    async def _set_status(
        repo: ControllerRepository, action_id: UUID, target: ActionStatus
    ) -> None:
        row = await repo.session.scalar(
            select(CompiledActionRecord).where(
                CompiledActionRecord.tenant_id == repo.tenant_id,
                CompiledActionRecord.id == action_id,
            )
        )
        if row is None:
            raise PolicyViolationError("action not found")
        if row.status != target.value:
            row.status = transition_action(ActionStatus(row.status), target).value
            row.updated_at = utc_now()

    @staticmethod
    def _audit(
        repo: ControllerRepository, record: ControllerActionRecord, event: str, message: str
    ) -> None:
        repo.append_audit(
            ActionAuditEntry(
                id=uuid4(),
                tenant_id=repo.tenant_id,
                action_id=record.action.id,
                event_type=event,
                actor_role=ActorRole.SYSTEM,
                message=message,
                occurred_at=utc_now(),
            ),
            record.action.run_id,
        )

    @staticmethod
    async def _schedule_measurement(
        repo: ControllerRepository, record: ControllerActionRecord, state: SimulatorState
    ) -> None:
        goal = await repo.get_goal(record.action.goal_id)
        policy = await repo.get_policy()
        prior = [item for item in state.metrics if not item.is_history][-7:]
        baseline_kind: Literal["recent_runtime", "historical_prior"] = (
            "recent_runtime" if prior else "historical_prior"
        )
        prior = prior or [item for item in state.metrics if item.is_history][-7:]
        floors = [policy.discount_minimum_margin_rate]
        ceilings: list[int] = []
        for constraint in goal.spec.constraints:
            if not constraint.hard:
                continue
            if (
                constraint.metric == MetricName.CONTRIBUTION_MARGIN_RATE
                and constraint.operator in {ConstraintOperator.GTE, ConstraintOperator.GT}
                and isinstance(constraint.value, Decimal)
            ):
                floors.append(constraint.value)
            if (
                constraint.metric == MetricName.CAC
                and constraint.operator in {ConstraintOperator.LTE, ConstraintOperator.LT}
                and isinstance(constraint.value, Money)
            ):
                ceilings.append(constraint.value.amount_minor)
        metric = next(
            (item for item in MetricName if item.value == record.action.expected_impact.metric),
            MetricName.CONTRIBUTION_PROFIT,
        )
        schedule = MeasurementSchedule(
            action_id=record.action.id,
            starts_at=state.current_time,
            ends_at=min(state.current_time + timedelta(days=7), goal.spec.horizon.end_at),
            metric_names=[metric],
            baseline_ref=state.state_hash,
            baseline_totals=cast(
                JsonObject, totals_for_metrics(prior, include_history=True).model_dump(mode="json")
            ),
            baseline_kind=baseline_kind,
            margin_floor=max(floors),
            cac_ceiling_minor=min(ceilings) if ceilings else None,
        )
        repo.session.add(
            Intervention(
                id=uuid5(NAMESPACE_URL, f"{record.action.id}:intervention"),
                tenant_id=repo.tenant_id,
                action_id=record.action.id,
                starts_at=schedule.starts_at,
                ends_at=schedule.ends_at,
                primary_metric=metric.value,
                monitor_spec=schedule.model_dump(mode="json"),
                status="active",
            )
        )
        repo.session.add(
            WorkflowJob(
                id=uuid5(NAMESPACE_URL, f"{record.action.id}:measure"),
                tenant_id=repo.tenant_id,
                kind="measure",
                action_id=record.action.id,
                goal_id=record.action.goal_id,
                run_id=record.action.run_id,
                instance_id=state.id,
                status="pending",
                available_at=utc_now(),
                attempts=0,
            )
        )

    async def _after_prepare(self, attempt_id: UUID) -> None:
        """Commit boundary overridden only by fault-injection test subclasses."""

    async def _after_provider_commit(self, attempt_id: UUID) -> None:
        """Commit boundary overridden only by fault-injection test subclasses."""
