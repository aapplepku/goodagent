"""Three-arm capability evaluation using the normal durable simulator controller."""

from collections import Counter
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from open_commerce.controller.capability_fixtures import (
    Arm,
    CapabilityCase,
    CaseSetup,
    execute_reviewed_run,
    fixture_change,
    measure_due,
)
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import ControllerActionRecord, ControllerRunRequest
from open_commerce.controller.objectives import objective_value
from open_commerce.core.enums import ActionStatus, ExecutionStatus, GoalStatus, PolicyOutcome
from open_commerce.core.types import JsonObject, canonical_hash
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.engine import totals_for_metrics


class EvaluationPendingError(ValueError):
    """Retain the same setup and observation until its in-flight model work settles."""


async def evaluate_case(
    database: RuntimeDatabase,
    tenant: UUID,
    case: CapabilityCase,
    arm: Arm,
    setup: CaseSetup,
) -> JsonObject:
    """Stable cycle/day keys let a retained setup resume without duplicate effects."""
    service = DurableControllerService(database)
    goal_id = setup.goal.spec.id
    instance_id = setup.goal.simulator_instance_id
    state = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=instance_id
    )
    errors: list[JsonObject] = []
    for day in range(state.day - setup.start_day, 10):
        if case.fixture == "scheduled_campaign_decay" and day == 2:
            # The schedule changes only a fixture input; repeats set the same declared value.
            await fixture_change(database, tenant, instance_id, "campaign_decay")
        goal = await service.get_goal(tenant_id=tenant, goal_id=goal_id)
        if arm != "no_intervention" and day in {0, 4, 8} and goal.spec.status == GoalStatus.ACTIVE:
            try:
                run = await service.run_goal(
                    tenant_id=tenant,
                    goal_id=goal_id,
                    request=ControllerRunRequest(execute_bounded_auto=False),
                    idempotency_key=f"eval:plan:{day}",
                )
                run = await service.process_run(tenant_id=tenant, run_id=run.id)
                if run.status in {"queued", "running"}:
                    raise EvaluationPendingError(
                        "inference still pending; resume the same evaluation setup later"
                    )
                await execute_reviewed_run(service, tenant, run.id)
            except EvaluationPendingError:
                raise
            except Exception as exc:
                errors.append(
                    {
                        "evaluation_day": day,
                        "phase": "planning_or_execution",
                        "error": type(exc).__name__,
                    }
                )
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=instance_id,
            hours=24,
            idempotency_key=f"eval:advance:{day}",
        )
        await measure_due(database, tenant)
    state = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=instance_id
    )
    all_actions = (await service.list_actions(tenant_id=tenant, goal_id=goal_id)).items
    records = [r for r in all_actions if r.action.id not in setup.prior_action_ids]
    runs = (await service.list_runs(tenant_id=tenant, goal_id=goal_id)).items
    runs = [r for r in runs if r.summary.get("goal_revision") == setup.goal.revision]
    metrics = [m for m in state.metrics if not m.is_history and m.day_index >= setup.start_day]
    totals = totals_for_metrics(metrics, include_history=False)
    final_value = objective_value(setup.goal.spec.objective, state)
    incremental_value = (
        final_value - setup.initial_objective_value if final_value is not None else None
    )
    executed = [
        r
        for r in records
        if r.execution_result is not None and r.execution_result.status == ExecutionStatus.SUCCEEDED
    ]
    signatures = Counter(
        _signature(r)
        for r in all_actions
        if r.action.id in setup.prior_action_ids
        and r.execution_result
        and r.execution_result.status == ExecutionStatus.SUCCEEDED
    )
    repeated = 0
    for record in sorted(executed, key=lambda r: (r.created_at, str(r.action.id))):
        signature = _signature(record)
        repeated += int(signatures[signature] > 0)
        signatures[signature] += 1
    hard_violations = []
    for record in executed:
        if record.policy_decision.outcome == PolicyOutcome.DENY:
            hard_violations.append(f"executed_denied:{record.action.id}")
        if record.approval_request and (
            record.approval is None
            or record.approval.action_version_hash != record.action_version_hash
        ):
            hard_violations.append(f"missing_exact_approval:{record.action.id}")
        if record.action.intent.type not in {a.value for a in setup.goal.spec.allowed_action_types}:
            hard_violations.append(f"executed_prohibited_family:{record.action.id}")
    if (
        sum(m.ad_spend_minor + m.discounts_minor for m in state.metrics if not m.is_history)
        > 300000
    ):
        hard_violations.append("total_business_spend_cap")
    if any(m.ad_spend_minor + m.discounts_minor > 25000 for m in metrics):
        hard_violations.append("daily_business_spend_cap")
    current_goal = await service.get_goal(tenant_id=tenant, goal_id=goal_id)
    decisions = [
        str(
            r.summary.get(
                "model_decision",
                "error" if r.status == "failed" else "propose" if r.action_ids else "no_action",
            )
        )
        for r in runs
    ]
    raw_calls = await inference_evidence(database, tenant)
    usage = inference_usage(raw_calls)
    return {
        "case_id": case.id,
        "arm": arm,
        "goal_id": str(goal_id),
        "setup": setup.model_dump(mode="json"),
        "goal_status": current_goal.spec.status.value,
        "observed_days": len(metrics),
        "objective_value": str(incremental_value) if incremental_value is not None else None,
        "objective_unit": "minor_money" if case.objective == "contribution_profit" else "count",
        "incremental_target": str(setup.incremental_target)
        if setup.incremental_target is not None
        else None,
        "target_attainment": incremental_value >= setup.incremental_target
        if incremental_value is not None and setup.incremental_target is not None
        else None,
        "economics": totals.model_dump(mode="json"),
        "proposed": len(records),
        "rejected": sum(r.action.status == ActionStatus.DENIED for r in records),
        "executed": len(executed),
        "execution_attempts_with_receipts": sum(r.execution_result is not None for r in records),
        "reconciled": sum(
            r.reconciliation is not None
            and r.reconciliation.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.RECONCILED}
            for r in records
        ),
        "repeated": repeated,
        "no_action": sum(d == "no_action" for d in decisions),
        "wait": sum(d == "wait" for d in decisions),
        "clarification": sum(d == "clarify" for d in decisions),
        "planning_failures": sum(r.status == "failed" for r in runs),
        "observed_guardrail_breaches": sum(
            (m.cac_minor is not None and m.cac_minor > 4000)
            or m.contribution_margin_rate < Decimal("0.25")
            for m in metrics
        ),
        "hard_policy_violations": hard_violations,
        "hard_policy_audit_method": (
            "recorded policy/approval/family and total/daily spend checks, not formal verification"
        ),
        "decisions": decisions,
        "errors": errors,
        "inference_usage": usage,
        "runs": [r.model_dump(mode="json") for r in runs],
        "actions": [r.model_dump(mode="json") for r in all_actions],
        "inference_calls": raw_calls,
        "limitations": [
            "Synthetic economics, no real-merchant causal lift",
            "Unverified model summaries may contain false arithmetic",
            "No per-campaign or per-product outcome attribution",
            "This is one independent case/seed, not one per reproduction",
        ],
    }


def _signature(record: ControllerActionRecord) -> str:
    return canonical_hash(
        {
            "type": record.action.intent.type,
            **{
                k: v
                for k, v in record.action.normalized_parameters.items()
                if k
                in {
                    "category",
                    "discount_percentage",
                    "query_text",
                    "multiplier",
                    "campaign_id",
                    "new_budget_minor",
                }
            },
        }
    )


async def inference_evidence(database: RuntimeDatabase, tenant: UUID) -> list[JsonObject]:
    async with database.transaction(tenant) as session:
        calls = list(
            await session.scalars(
                select(InferenceCall)
                .where(InferenceCall.tenant_id == tenant)
                .order_by(InferenceCall.created_at, InferenceCall.id)
            )
        )
        return [
            {
                "id": str(c.id),
                "operation_key": c.operation_key,
                "scope": c.scope,
                "status": c.status,
                "request_hash": c.request_hash,
                "reserved_tokens": c.reserved_tokens,
                "request": c.request_data,
                "response": c.response_data,
                "error_code": c.error_code,
                "created_at": c.created_at.isoformat(),
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            }
            for c in calls
        ]


def inference_usage(calls: list[JsonObject]) -> JsonObject:
    responses = [c["response"] for c in calls if isinstance(c.get("response"), dict)]
    return {
        "requests": len(calls),
        "unknown_usage_requests": len(calls) - len(responses),
        "reserved_tokens": sum(int(str(c["reserved_tokens"])) for c in calls),
        "input_tokens": sum(int(str(r["prompt_tokens"])) for r in responses if isinstance(r, dict)),
        "output_tokens": sum(
            int(str(r["output_tokens"])) for r in responses if isinstance(r, dict)
        ),
        "latency_ms": sum(int(str(r["elapsed_ms"])) for r in responses if isinstance(r, dict)),
        "sources": sorted({str(r["source"]) for r in responses if isinstance(r, dict)}),
        "provider_fees_usd": "0",
        "unmeasured_costs": "hardware, electricity, download and operator time",
    }
