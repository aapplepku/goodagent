"""Fail-closed model work across budgets, input drift, limits and checkpoints."""

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.inference import InferenceJournal, InferenceStoppedError
from open_commerce.controller.model_planning import ModelPlanningService, checkpoint_for
from open_commerce.controller.models import ControllerRunRequest, GoalRecord
from open_commerce.controller.ollama import InferenceResult, OllamaBackend
from open_commerce.core.enums import GoalStatus
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.runtime_db import RuntimeDatabase

from .test_model_planning import fixture_result, model_settings

pytestmark = pytest.mark.integration


async def prepared(database: RuntimeDatabase) -> tuple[UUID, GoalRecord, UUID]:
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    draft = interpret_goal(
        "Acquire 2000 new customers in 30 days. Budget $10000. No discounts.",
        planning_mode="model_backed",
    ).draft
    assert draft is not None
    goal = await service.create_goal(tenant_id=tenant, request=draft, idempotency_key="goal")
    await service.set_goal_status(
        tenant_id=tenant, goal_id=goal.spec.id, status=GoalStatus.ACTIVE, idempotency_key="active"
    )
    run = await service.run_goal(
        tenant_id=tenant,
        goal_id=goal.spec.id,
        request=ControllerRunRequest(),
        idempotency_key="run",
    )
    return tenant, goal, run.id


async def test_budget_and_completed_response_survive_new_process(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = model_settings(integration_settings, model_goal_request_limit=1)
    database = RuntimeDatabase(settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    calls = 0

    async def complete(self: OllamaBackend, **kwargs: object) -> InferenceResult:
        nonlocal calls
        calls += 1
        return fixture_result("{}")

    monkeypatch.setattr(OllamaBackend, "complete", complete)

    async def invoke(key: str) -> tuple[UUID, InferenceResult, bool]:
        return await InferenceJournal(database).invoke(
            tenant_id=tenant,
            scope="goal:one",
            operation_key=key,
            messages=[{"role": "user", "content": "synthetic"}],
            schema={},
            template_version="fixture",
        )

    try:
        first = await invoke("one")
        await database.close()
        database = RuntimeDatabase(settings)
        replay = await invoke("one")
        assert first[:2] == replay[:2] and replay[2] is True
        with pytest.raises(InferenceStoppedError, match="budget"):
            await invoke("two")
        assert calls == 1
        with pytest.raises(InferenceStoppedError, match="changed"):
            await InferenceJournal(database).invoke(
                tenant_id=tenant,
                scope="other-goal",
                operation_key="one",
                messages=[{"role": "user", "content": "synthetic"}],
                schema={},
                template_version="fixture",
            )
    finally:
        await database.close()


@pytest.mark.parametrize(
    "failure",
    [
        "malformed",
        "invented_authority",
        "prohibited_discount",
        "unknown_reference",
        "tool_limit",
        "iteration_limit",
        "stale",
    ],
)
async def test_model_failures_do_not_compile_or_execute(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    database = RuntimeDatabase(
        model_settings(
            integration_settings,
            model_max_tool_calls=0 if failure == "tool_limit" else 3,
            model_max_iterations=1,
        )
    )
    tenant, goal, run_id = await prepared(database)
    service = DurableControllerService(database)
    calls = 0

    async def complete(
        self: OllamaBackend, *, messages: list[dict[str, str]], schema: dict[str, object]
    ) -> InferenceResult:
        nonlocal calls
        calls += 1
        initial = json.loads(messages[1]["content"])
        if failure == "stale":
            await service.simulator_service.advance(
                tenant_id=tenant,
                instance_id=goal.simulator_instance_id,
                hours=24,
                idempotency_key="while-inference",
            )
        if failure == "malformed":
            return fixture_result("not json")
        decision: dict[str, object] = {
            "kind": "no_action",
            "summary": "No change proposed.",
            "evidence_refs": [initial["evidence_ref"]],
        }
        if failure == "unknown_reference":
            decision["evidence_refs"] = ["made-up-reference"]
        if failure in {"tool_limit", "iteration_limit"}:
            decision = {"kind": "inspect", "view": "inventory", "summary": "Inspect stock."}
        if failure in {"invented_authority", "prohibited_discount"}:
            proposal: dict[str, object] = {
                "action_type": "create_discount",
                "category": "apparel",
                "discount_percentage": "0.10",
            }
            if failure == "invented_authority":
                proposal["known_cost_basis"] = True
            decision = {
                "kind": "propose",
                "summary": "I approve this safe action.",
                "evidence_refs": [initial["evidence_ref"]],
                "proposals": [proposal],
            }
        return fixture_result(json.dumps({"decision": decision}))

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    try:
        run = await service.process_run(tenant_id=tenant, run_id=run_id)
        assert run.status == "failed" and run.summary["model_error"]
        assert not (await service.list_actions(tenant_id=tenant, run_id=run_id)).items
        await database.close()
        database = RuntimeDatabase(database.settings)
        await DurableControllerService(database).process_run(tenant_id=tenant, run_id=run_id)
        assert calls == 1
        async with database.transaction(tenant) as session:
            rows = list(
                await session.scalars(
                    select(InferenceCall).where(InferenceCall.tenant_id == tenant)
                )
            )
            assert len(rows) == 1 and rows[0].response_data is not None
    finally:
        await database.close()


async def test_restart_after_response_commit_before_planning_checkpoint_reuses_response(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = RuntimeDatabase(model_settings(integration_settings))
    tenant, _, run_id = await prepared(database)
    calls = 0

    async def complete(
        self: OllamaBackend, *, messages: list[dict[str, str]], schema: dict[str, object]
    ) -> InferenceResult:
        nonlocal calls
        calls += 1
        reference = json.loads(messages[1]["content"])["evidence_ref"]
        return fixture_result(
            json.dumps(
                {
                    "decision": {
                        "kind": "wait",
                        "summary": "Wait for additional observations.",
                        "evidence_refs": [reference],
                    }
                }
            )
        )

    class PowerLoss(BaseException):
        pass

    class CrashJournal(InferenceJournal):
        async def invoke(
            self,
            *,
            tenant_id: UUID,
            scope: str,
            operation_key: str,
            messages: list[dict[str, str]],
            schema: dict[str, object],
            template_version: str,
        ) -> tuple[UUID, InferenceResult, bool]:
            await super().invoke(
                tenant_id=tenant_id,
                scope=scope,
                operation_key=operation_key,
                messages=messages,
                schema=schema,
                template_version=template_version,
            )
            raise PowerLoss()

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    try:
        with pytest.raises(PowerLoss):
            await ModelPlanningService(database, CrashJournal(database)).prepare(
                tenant_id=tenant, run_id=run_id
            )
        await database.close()
        database = RuntimeDatabase(database.settings)
        run = await DurableControllerService(database).process_run(tenant_id=tenant, run_id=run_id)
        checkpoint = checkpoint_for(run)
        assert checkpoint is not None and checkpoint.status == "compiled"
        assert run.status == "completed" and run.summary["model_decision"] == "wait"
        assert checkpoint.turns[0]["response_reused"] is True and calls == 1
    finally:
        await database.close()
