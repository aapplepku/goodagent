"""Synthetic proposal fixtures exercise real approval, durable recovery and Qdrant serving."""

import os
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.durable_executor import DurableExecutor
from open_commerce.controller.merchandising_planner import MerchandisingPlan, plan_merchandising
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ApprovalError,
    ControllerRunRequest,
    GoalCreateRequest,
    IntentDraft,
    PolicyUpdateRequest,
    PolicyViolationError,
)
from open_commerce.core.enums import ActionStatus, ActionType, GoalStatus
from open_commerce.core.goals import GoalSpec
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.core.types import JsonObject
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import RecommendationRequest
from open_commerce.simulator.models import SimulatorState

pytestmark = pytest.mark.integration


async def test_pdp_serves_fresh_authoritative_catalog_without_search_rebuild(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    from open_commerce.search.errors import SearchContextNotFoundError

    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    search = DurableSearchService(database)
    rebuild = AsyncMock(side_effect=AssertionError("PDP must not rebuild vector search"))
    monkeypatch.setattr(search, "prepare_state_index", rebuild)
    try:
        await database.initialize_tenant(tenant)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(merchandising=MerchandisingConstraints()),
            idempotency_key="pdp-no-index",
        )
        request = RecommendationRequest(
            goal_context_id=goal.spec.id,
            anchor_product_ids=["merch_wall_chargers_1"],
            debug=True,
        )
        result = await search.recommendations(tenant_id=tenant, request=request)
        assert result.strategy == "alternatives" and result.results
        assert all(all(row.constraint_matches.values()) for row in result.results)
        rebuild.assert_not_awaited()
        with pytest.raises(SearchContextNotFoundError):
            await search.recommendations(tenant_id=uuid4(), request=request)
    finally:
        await search.close()
        await database.close()


async def test_result_evaluation_recomputes_semantics_price_and_uniqueness(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    from open_commerce.search.index import _ranked_candidate
    from open_commerce.search.models import EvaluateSearchRequest
    from open_commerce.search.parser import parse_search_intent
    from open_commerce.search.service import documents_from_simulator_state

    database = RuntimeDatabase(integration_settings)
    search = DurableSearchService(database)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        controller = DurableControllerService(database)
        goal = await controller.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(merchandising=MerchandisingConstraints()),
            idempotency_key="evaluation-authority",
        )
        state = await controller.simulator_service.get_full_state(
            tenant_id=tenant, instance_id=goal.simulator_instance_id
        )
        intent = parse_search_intent("qzxv")
        document = documents_from_simulator_state(state)[0]
        candidate = _ranked_candidate(
            document=document,
            intent=intent,
            filters=intent.required_filters,
            ranks={"dense_score": Decimal(1)},
            rules=[],
            mode="dense",
            learned_semantics=True,
        )
        # Controlled embeddings test the evaluation boundary, not search quality.
        monkeypatch.setattr(search.embedding_provider, "model_id", "test-semantic-evidence")
        monkeypatch.setattr(
            search.embedding_provider, "embed_documents", AsyncMock(return_value=[[1.0, 0.0]])
        )
        query = AsyncMock(return_value=[1.0, 0.0])
        monkeypatch.setattr(search.embedding_provider, "embed_query", query)
        request = EvaluateSearchRequest(
            query="qzxv", goal_context_id=goal.spec.id, results=[candidate]
        )
        result = await search.evaluate(tenant_id=tenant, request=request)
        assert not result.hard_constraint_violations
        candidate.price.amount_minor = 1
        result = await search.evaluate(tenant_id=tenant, request=request)
        assert "displayed_price" in result.hard_constraint_violations
        query.return_value = [0.0, 1.0]
        result = await search.evaluate(tenant_id=tenant, request=request)
        assert "relevance" in result.hard_constraint_violations
        request.results.append(candidate)
        result = await search.evaluate(tenant_id=tenant, request=request)
        assert "unique_product" in result.hard_constraint_violations
    finally:
        await search.close()
        await database.close()


@pytest.mark.parametrize(
    "action_type", [ActionType.SET_VARIANT_PRICE, ActionType.SET_RECOMMENDATION_POLICY]
)
@pytest.mark.parametrize("backend", ["hash", "minilm"])
async def test_exact_approval_crash_restart_serving_measurement_and_rollback(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    action_type: ActionType,
    backend: str,
) -> None:
    if backend == "minilm" and not os.environ.get("OPEN_COMMERCE_TEST_MINILM_DIRECTORY"):
        pytest.skip("Explicit verified local MiniLM installation required")
    settings = integration_settings.model_copy(
        update={
            "search_embedding_backend": backend,
            "search_model_directory": Path(os.environ["OPEN_COMMERCE_TEST_MINILM_DIRECTORY"])
            if backend == "minilm"
            else None,
        }
    )
    database = RuntimeDatabase(settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)

    def fixture_proposal(
        *, goal: GoalSpec, state: SimulatorState, run_id: UUID
    ) -> MerchandisingPlan:
        plan = plan_merchandising(goal=goal, state=state, run_id=run_id)
        product = next(p for p in state.products if p.id == "merch_wall_chargers_1")
        variant = product.variants[0]
        parameters: JsonObject = (
            {
                "product_id": product.id,
                "variant_id": variant.id,
                "new_price_minor": variant.price_minor * 95 // 100,
                "expected_version": 0,
                "duration_hours": 48,
            }
            if action_type == ActionType.SET_VARIANT_PRICE
            else {
                "controls": {"strategy": "complements"},
                "expected_version": 0,
                "duration_hours": 48,
            }
        )
        plan.drafts = [
            IntentDraft(
                id=uuid4(),
                tenant_id=tenant,
                run_id=run_id,
                hypothesis_id=uuid4(),
                opportunity_ids=[],
                action_type=action_type,
                rationale="Synthetic workflow fixture, not evaluated planner quality",
                confidence=Decimal(0),
                parameters=parameters,
            )
        ]
        plan.decision = {
            "planner_version": "synthetic-workflow-fixture-v1",
            "kind": "manual_fixture_not_controller_selection",
        }
        return plan

    monkeypatch.setattr("open_commerce.controller.durable.plan_merchandising", fixture_proposal)
    try:
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(merchandising=MerchandisingConstraints()),
            idempotency_key="create",
        )
        with pytest.raises(ValueError, match="whole UTC days"):
            await service.simulator_service.advance(
                tenant_id=tenant,
                instance_id=goal.simulator_instance_id,
                hours=1,
                idempotency_key="partial-day-rejected",
            )
        await service.update_policy(
            tenant_id=tenant,
            request=PolicyUpdateRequest(allowed_action_types=goal.spec.allowed_action_types),
            idempotency_key="review-policy",
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="activate",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="run",
        )
        await service.process_run(tenant_id=tenant, run_id=run.id)
        records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
        assert len(records) == 1
        record = records[0]
        assert record.action.status == ActionStatus.AWAITING_APPROVAL, record.policy_decision
        with pytest.raises(PolicyViolationError):
            await service.execute_action(
                tenant_id=tenant, action_id=record.action.id, idempotency_key="unapproved"
            )
        with pytest.raises(ApprovalError):
            await service.approve_action(
                tenant_id=tenant,
                action_id=record.action.id,
                request=ActionApprovalRequest(action_version_hash="0" * 64),
                actor_roles={"owner", "operator"},
                decision="approve",
                idempotency_key="wrong-hash",
            )
        await service.approve_action(
            tenant_id=tenant,
            action_id=record.action.id,
            request=ActionApprovalRequest(action_version_hash=record.action_version_hash),
            actor_roles={"owner", "operator"},
            decision="approve",
            idempotency_key="approve",
        )

        class Interrupted(DurableExecutor):
            async def _after_provider_commit(self, attempt_id: UUID) -> None:
                raise RuntimeError("injected after committed simulator receipt")

        with pytest.raises(RuntimeError, match="injected"):
            await Interrupted(database).execute(
                tenant_id=tenant, action_id=record.action.id, idempotency_key="dispatch"
            )
    finally:
        await database.close()
    restarted = RuntimeDatabase(settings)
    search = DurableSearchService(restarted)
    try:
        service = DurableControllerService(restarted)
        result = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="dispatch"
        )
        assert result.action.status == ActionStatus.SUCCEEDED
        assert result.reconciliation is not None
        assert result.measurement is not None
        replay = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="redelivery"
        )
        assert replay.execution_result == result.execution_result
        response = await search.recommendations(
            tenant_id=tenant,
            request=RecommendationRequest(
                goal_context_id=goal.spec.id,
                anchor_product_ids=["merch_wall_chargers_1"],
                debug=True,
            ),
        )
        if action_type == ActionType.SET_RECOMMENDATION_POLICY:
            assert response.policy_version == 1 and response.strategy == "complements"
            assert response.results and all(
                "charging_cables" in r.product_id for r in response.results
            )
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=24,
            idempotency_key="observed-day",
        )
        state = await service.simulator_service.get_full_state(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
        )
        assert state.metrics[-1].orders > 0
        assert state.merchandising is not None
        assert len(state.command_history) == 1
        observed_state = state.model_dump(mode="json")
        if action_type == ActionType.SET_RECOMMENDATION_POLICY:
            assert any(
                batch.policy_version == 1 and batch.order_keys
                for batch in state.merchandising.serving_log.values()
                if batch.surface == "product_detail"
            )
        rolled = await service.rollback_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="rollback"
        )
        assert rolled.action.status == ActionStatus.ROLLED_BACK
        state = await service.simulator_service.get_full_state(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
        )
        assert len(state.command_history) == 2
        assert state.merchandising is not None
        if action_type == ActionType.SET_RECOMMENDATION_POLICY:
            assert state.merchandising.recommendation_policy.version == 2
            assert state.merchandising.recommendation_policy.controls.strategy == "alternatives"
        if directory := os.environ.get("OPEN_COMMERCE_WORKFLOW_EVIDENCE_DIRECTORY"):
            import gzip
            import hashlib
            import json

            output = Path(directory) / f"{backend}-{action_type.value}.json.gz"
            if output.exists():
                raise ValueError("Do not replace retained workflow evidence")
            output.parent.mkdir(parents=True, exist_ok=True)
            evidence = {
                "kind": "synthetic proposal fixture; not planner quality or comparative lift",
                "backend": backend,
                "goal": goal.model_dump(mode="json"),
                "recovered_execution": result.model_dump(mode="json"),
                "served_pdp": response.model_dump(mode="json"),
                "observed_state": observed_state,
                "rollback": rolled.model_dump(mode="json"),
                "state_after_rollback": state.model_dump(mode="json"),
                "source_hashes": {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(Path("packages/backend/src").rglob("*.py"))
                },
                "fixture_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }
            output.write_bytes(
                gzip.compress(
                    (json.dumps(evidence, sort_keys=True, indent=2) + "\n").encode(), mtime=0
                )
            )
    finally:
        await search.close()
        await restarted.close()
