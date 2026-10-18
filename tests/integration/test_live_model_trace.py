"""Opt-in real-model development trace, never substituted with fixtures in CI."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.inference import InferenceJournal
from open_commerce.controller.model_goal_interpretation import interpret_with_model
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerRunRequest,
    GoalCreateRequest,
)
from open_commerce.core.enums import ActionStatus, GoalStatus
from open_commerce.core.money import Money
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("OPEN_COMMERCE_RUN_LIVE_MODEL") != "1",
        reason="explicit local model validation only",
    ),
]


async def test_real_model_goal_planning_execution_measurement_trace(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    report: dict[str, object] = {
        "kind": "development_smoke_not_decision_quality_evaluation",
        "source": "real_model",
        "tenant_id": str(tenant),
    }
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    try:
        interpretation = await interpret_with_model(
            InferenceJournal(database),
            tenant_id=tenant,
            seed=11,
            idempotency_key="interpret",
            text="Acquire 9000 new customers in 30 days with a $10000 budget. "
            "Daily budget $250. CAC <= $40; contribution margin >= 25%; maximum discount <= 15%.",
        )
        report["interpretation"] = interpretation.model_dump(mode="json")
        assert interpretation.interpretation_mode == "model_backed" and interpretation.inference_ref
        report["interpretation_passed"] = interpretation.status == "ready_for_review"
        # A separate, predeclared typed-goal planner test, never an interpreter fallback.
        report["planning_goal_source"] = (
            "independent_operator_reviewed_typed_fixture_not_model_interpretation"
        )
        draft = GoalCreateRequest(
            seed=11,
            objective_metric="new_customers",
            target_value=9000,
            horizon_days=30,
            budget=Money(amount_minor=1000000, currency="USD"),
            daily_budget=Money(amount_minor=25000, currency="USD"),
            planning_mode="model_backed",
        )
        draft.review_hash = draft.configuration_hash
        assert (
            draft.seed == 11 and draft.target_value == 9000 and draft.budget.amount_minor == 1000000
        )
        assert draft.review_hash == draft.configuration_hash
        goal = await service.create_goal(tenant_id=tenant, request=draft, idempotency_key="goal")
        report["goal_id"] = str(goal.spec.id)
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="activate",
        )
        for cycle in range(2):
            run = await service.run_goal(
                tenant_id=tenant,
                goal_id=goal.spec.id,
                request=ControllerRunRequest(),
                idempotency_key=f"cycle:{cycle}",
            )
            run = await service.process_run(tenant_id=tenant, run_id=run.id)
            assert run.status != "failed", run.summary
            records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
            for record in records:
                if record.action.status == ActionStatus.AWAITING_APPROVAL:
                    await service.approve_action(
                        tenant_id=tenant,
                        action_id=record.action.id,
                        request=ActionApprovalRequest(
                            action_version_hash=record.action_version_hash
                        ),
                        actor_roles={"operator"},
                        decision="approve",
                        idempotency_key=f"approve:{record.action.id}",
                    )
                    executed = await service.execute_action(
                        tenant_id=tenant,
                        action_id=record.action.id,
                        idempotency_key=f"execute:{record.action.id}",
                    )
                    again = await service.execute_action(
                        tenant_id=tenant,
                        action_id=record.action.id,
                        idempotency_key=f"execute:{record.action.id}",
                    )
                    assert again.execution_result == executed.execution_result
            await service.simulator_service.advance(
                tenant_id=tenant,
                instance_id=goal.simulator_instance_id,
                hours=24 * 4,
                idempotency_key=f"advance:{cycle}",
            )
            for record in records:
                await JobRunner(database, tenant).run(
                    uuid5(NAMESPACE_URL, f"{record.action.id}:measure")
                )
            current_goal = await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
            if current_goal.spec.status != GoalStatus.ACTIVE:
                report["replanning_stopped"] = current_goal.spec.status.value
                break
        report["goals"] = (await service.list_goals(tenant_id=tenant)).model_dump(mode="json")
        report["runs"] = (await service.list_runs(tenant_id=tenant)).model_dump(mode="json")
        report["actions"] = (
            await service.list_actions(tenant_id=tenant, goal_id=goal.spec.id)
        ).model_dump(mode="json")
        report["status"] = "passed"
    except BaseException as exc:
        report["status"], report["error"] = "failed", type(exc).__name__
        report["runs"] = (await service.list_runs(tenant_id=tenant)).model_dump(mode="json")
        raise
    finally:
        async with database.transaction(tenant) as session:
            calls = list(
                await session.scalars(
                    select(InferenceCall)
                    .where(InferenceCall.tenant_id == tenant)
                    .order_by(InferenceCall.created_at)
                )
            )
            report["inference_calls"] = [
                {
                    "id": str(c.id),
                    "scope": c.scope,
                    "status": c.status,
                    "request_hash": c.request_hash,
                    "reserved_tokens": c.reserved_tokens,
                    "request": c.request_data,
                    "response": c.response_data,
                    "error_code": c.error_code,
                }
                for c in calls
            ]
        output = Path(os.environ["OPEN_COMMERCE_MODEL_TRACE_OUTPUT"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        await database.close()
