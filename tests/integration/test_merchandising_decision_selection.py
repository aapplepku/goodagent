"""Authored observations exercise real v2 selection, not autonomous effectiveness."""

from uuid import uuid4

import pytest
from scripts.merchandising_decision_fixtures import batch, history

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ApprovalError,
    ControllerRunRequest,
    GoalCreateRequest,
    PolicyUpdateRequest,
    PolicyViolationError,
)
from open_commerce.core.enums import ActionStatus, ActionType, GoalStatus
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import RecommendationRequest
from open_commerce.simulator.durable import load_state

pytestmark = pytest.mark.integration


async def test_v2_selected_nonzero_pdp_revision_requires_exact_approval_and_reaches_serving(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    search = DurableSearchService(database)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        service = DurableControllerService(database)
        goal = await service.create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(
                merchandising=MerchandisingConstraints(),
                allowed_action_types={ActionType.NO_OP, ActionType.SET_RECOMMENDATION_POLICY},
            ),
            idempotency_key="create",
        )
        await service.update_policy(
            tenant_id=tenant,
            request=PolicyUpdateRequest(allowed_action_types=goal.spec.allowed_action_types),
            idempotency_key="review-policy",
        )
        async with database.transaction(tenant, write=True) as session:
            state = await load_state(session, tenant, goal.simulator_instance_id)
            history(state)
            assert state.merchandising is not None
            state.merchandising.recommendation_policy.version = 4
            pair = state.merchandising.compatibility[0]
            for day in range(4):
                batch(state, pair.complement_product_id, day=day, orders=2)
                batch(
                    state,
                    pair.complement_product_id,
                    day=day,
                    anchor=pair.anchor_product_id,
                    displayed=False,
                    version=4,
                )
            await SqlSimulatorRepository(session).save_state(state)
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
        run = await service.process_run(tenant_id=tenant, run_id=run.id)
        decision = run.summary["merchandising_decision"]
        assert isinstance(decision, dict)
        assert decision["planner_version"] == "merchandising-deterministic-v2"
        assert decision["selected_key"] == "pdp:complements"
        records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
        assert len(records) == 1
        record = records[0]
        assert record.action.status == ActionStatus.AWAITING_APPROVAL
        assert record.action.intent.type == "set_recommendation_policy"
        assert record.action.intent.expected_version == 4
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
        executed = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="execute"
        )
        assert executed.action.status == ActionStatus.SUCCEEDED
        result = await search.recommendations(
            tenant_id=tenant,
            request=RecommendationRequest(
                goal_context_id=goal.spec.id,
                anchor_product_ids=[pair.anchor_product_id],
                debug=True,
            ),
        )
        assert result.policy_version == 5 and result.strategy == "complements"
        assert pair.complement_product_id in {r.product_id for r in result.results}
        replay = await service.execute_action(
            tenant_id=tenant, action_id=record.action.id, idempotency_key="replay"
        )
        assert replay.execution_result == executed.execution_result
    finally:
        await search.close()
        await database.close()
