"""Model decisions remain proposals; recovery does not repeat inference or execution."""

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.inference import (
    InferenceJournal,
    InferencePendingError,
    InferenceStoppedError,
)
from open_commerce.controller.model_planning import checkpoint_for
from open_commerce.controller.models import ActionApprovalRequest, ControllerRunRequest
from open_commerce.controller.ollama import InferenceResult, OllamaBackend
from open_commerce.core.enums import ActionStatus, GoalStatus
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration
DIGEST = "sha256:" + "a" * 64


def model_settings(settings: Settings, **overrides: object) -> Settings:
    return settings.model_copy(
        update={
            "model_enabled": True,
            "model_local_only_attested": True,
            "model_digest": DIGEST,
            **overrides,
        }
    )


def fixture_result(content: str) -> InferenceResult:
    return InferenceResult(
        content=content,
        model_id="qwen3:4b",
        model_digest=DIGEST,
        server_version="fixture",
        prompt_tokens=100,
        output_tokens=20,
        elapsed_ms=5,
        source="replay",
    )


async def test_model_proposal_reuses_completed_inference_and_existing_exact_executor(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = RuntimeDatabase(model_settings(integration_settings))
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    calls = 0

    async def complete(
        self: OllamaBackend, *, messages: list[dict[str, str]], schema: dict[str, object]
    ) -> InferenceResult:
        nonlocal calls
        calls += 1
        data = json.loads(messages[1]["content"])
        assert "quality_score" not in json.dumps(messages)
        assert "seed" not in data
        decision: dict[str, object]
        if calls == 1:
            decision = {
                "kind": "inspect",
                "view": "inventory",
                "summary": "Inspect observed stock.",
            }
        else:
            evidence = json.loads(messages[-1]["content"])["read_only_tool_result"]
            decision = {
                "kind": "propose",
                "summary": "Propose a bounded apparel relevance boost.",
                "evidence_refs": [evidence["evidence_ref"]],
                "proposals": [
                    {"action_type": "set_search_boost", "category": "apparel", "multiplier": "1.10"}
                ],
            }
        return fixture_result(json.dumps({"decision": decision}))

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    try:
        service = DurableControllerService(database)
        draft = interpret_goal(
            "Acquire 9000 new customers in 30 days with a $10000 budget.",
            planning_mode="model_backed",
        ).draft
        assert draft is not None
        goal = await service.create_goal(tenant_id=tenant, request=draft, idempotency_key="goal")
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="active",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="run",
        )
        planned = await service.process_run(tenant_id=tenant, run_id=run.id)
        assert planned.status == "awaiting_approval", planned.summary
        checkpoint = checkpoint_for(planned)
        assert checkpoint is not None and checkpoint.status == "compiled"
        assert len(checkpoint.turns) == 2 and len(checkpoint.tools) == 1
        assert calls == 2
        await database.close()
        database = RuntimeDatabase(model_settings(integration_settings))
        service = DurableControllerService(database)
        restarted = await service.process_run(tenant_id=tenant, run_id=run.id)
        assert restarted.action_ids == planned.action_ids and calls == 2
        record = await service.get_action(tenant_id=tenant, action_id=planned.action_ids[0])
        assert record.action.status == ActionStatus.AWAITING_APPROVAL
        assert record.action.intent.requested_by.id == "model-backed-planner-v1"
        assert record.action.risk.confidence == 0
        await service.approve_action(
            tenant_id=tenant,
            action_id=record.action.id,
            request=ActionApprovalRequest(action_version_hash=record.action_version_hash),
            actor_roles={"operator"},
            decision="approve",
            idempotency_key="approve",
        )
        executed = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="execute"
        )
        replay = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="execute"
        )
        assert executed.execution_result is not None
        assert replay.execution_result == executed.execution_result
        async with database.transaction(tenant) as session:
            rows = list(
                await session.scalars(
                    select(InferenceCall).where(InferenceCall.tenant_id == tenant)
                )
            )
            assert len(rows) == 2 and all(r.status == "completed" for r in rows)
            assert all(r.response_data and r.response_data["source"] == "replay" for r in rows)
    finally:
        await database.close()


async def test_inference_reservation_survives_crash_without_automatic_reissue(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = RuntimeDatabase(model_settings(integration_settings))
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    count = 0

    class SimulatedPowerLoss(BaseException):
        pass

    async def crash(self: OllamaBackend, **kwargs: object) -> InferenceResult:
        nonlocal count
        count += 1
        raise SimulatedPowerLoss()

    monkeypatch.setattr(OllamaBackend, "complete", crash)

    async def invoke() -> None:
        await InferenceJournal(database).invoke(
            tenant_id=tenant,
            scope="goal:fixture",
            operation_key="run:fixture:0",
            messages=[{"role": "user", "content": "synthetic"}],
            schema={},
            template_version="fixture-v1",
        )

    try:
        with pytest.raises(SimulatedPowerLoss):
            await invoke()
        with pytest.raises(InferencePendingError):
            await invoke()
        assert count == 1
        # Move the test clock, not immutable journal evidence.
        monkeypatch.setattr(
            "open_commerce.controller.inference.utc_now", lambda: utc_now() + timedelta(minutes=5)
        )
        with pytest.raises(InferenceStoppedError, match="uncertain"):
            await invoke()
        with pytest.raises(InferenceStoppedError, match="uncertain"):
            await invoke()
        assert count == 1
        async with database.transaction(tenant) as session:
            row = await session.scalar(
                select(InferenceCall).where(InferenceCall.tenant_id == tenant)
            )
            assert row is not None and row.status == "uncertain" and row.reserved_tokens > 0
        with pytest.raises(DBAPIError, match="immutable"):
            async with database.transaction(tenant, write=True) as session:
                row = await session.scalar(
                    select(InferenceCall).where(InferenceCall.tenant_id == tenant)
                )
                assert row is not None
                row.status = "dispatched"
    finally:
        await database.close()
