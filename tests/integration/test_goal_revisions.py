"""Reviewed revisions persist and cannot reuse an earlier exact approval."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ApprovalError,
    ControllerRunRequest,
    GoalUpdateRequest,
    PolicyViolationError,
)
from open_commerce.core.enums import ActionStatus, ActionType, GoalStatus, MetricName
from open_commerce.persistence.models.budgets import BudgetAccountRecord
from open_commerce.persistence.models.goals import GoalRevisionRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration


async def test_changed_goal_invalidates_approval_and_preserves_revision_evidence(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    try:
        service = DurableControllerService(database)
        interpretation = interpret_goal(
            "Acquire 9000 new customers in 30 days with a $2000 budget. "
            "Daily budget $200. CAC <= $22; margin >= 31%; discounts <= 7.5%."
        )
        assert interpretation.draft is not None
        goal = await service.create_goal(
            tenant_id=tenant, request=interpretation.draft, idempotency_key="create"
        )
        assert goal.revision == 1
        assert next(
            c.value for c in goal.spec.constraints if c.metric == MetricName.DISCOUNT_RATE
        ) == Decimal("0.075")
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
        action = next(
            r
            for r in (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
            if r.action.status == ActionStatus.AWAITING_APPROVAL
        )
        approval = ActionApprovalRequest(action_version_hash=action.action_version_hash)
        await service.approve_action(
            tenant_id=tenant,
            action_id=action.action.id,
            request=approval,
            actor_roles={"owner", "operator"},
            decision="approve",
            idempotency_key="approval",
        )
        revised_draft = interpret_goal(
            "Acquire 1234 new customers in 17 days with a $1234.56 budget. "
            "Daily budget $100. No discounts. Only search boosts."
        ).draft
        assert revised_draft is not None
        request = GoalUpdateRequest(expected_revision=1, replacement=revised_draft)
        updated = await service.update_goal(
            tenant_id=tenant, goal_id=goal.spec.id, request=request, idempotency_key="revise"
        )
        assert updated.revision == 2 and updated.spec.status == GoalStatus.DRAFT
        assert updated.spec.allowed_action_types == {ActionType.SET_SEARCH_BOOST}
        assert updated.spec.objective.target == 1234
        assert (updated.spec.horizon.end_at - updated.spec.horizon.start_at).days == 17
        await database.close()
        database = RuntimeDatabase(integration_settings)
        service = DurableControllerService(database)
        reloaded = await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
        assert reloaded.revision == 2
        # Persistence preserves typed field values, not HorizonSpec/TimeWindow subclass identity.
        assert reloaded.spec.model_dump() == updated.spec.model_dump()
        cancelled = await service.get_action(tenant_id=tenant, action_id=action.action.id)
        assert cancelled.action.status == ActionStatus.CANCELLED
        assert cancelled.approval is not None
        assert any(
            item.event_type == "goal_revision_invalidated_proposal" for item in cancelled.audit
        )
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="reactivate",
        )
        with pytest.raises(ApprovalError, match="goal revision"):
            await service.approve_action(
                tenant_id=tenant,
                action_id=action.action.id,
                request=approval,
                actor_roles={"owner", "operator"},
                decision="approve",
                idempotency_key="stale-approval",
            )
        with pytest.raises(PolicyViolationError, match="goal revision"):
            await service.execute_action(
                tenant_id=tenant, action_id=action.action.id, idempotency_key="stale-execute"
            )
        with pytest.raises(PolicyViolationError, match="revision"):
            await service.update_goal(
                tenant_id=tenant,
                goal_id=goal.spec.id,
                request=request,
                idempotency_key="stale-edit",
            )
        async with database.transaction(tenant) as session:
            revisions = list(
                await session.scalars(
                    select(GoalRevisionRecord)
                    .where(
                        GoalRevisionRecord.tenant_id == tenant,
                        GoalRevisionRecord.goal_id == goal.spec.id,
                    )
                    .order_by(GoalRevisionRecord.revision)
                )
            )
            assert [r.revision for r in revisions] == [1, 2]
            assert revisions[0].content_hash != revisions[1].content_hash
            account = await session.scalar(
                select(BudgetAccountRecord).where(
                    BudgetAccountRecord.tenant_id == tenant,
                    BudgetAccountRecord.goal_id == goal.spec.id,
                    BudgetAccountRecord.budget_kind == "goal",
                )
            )
            assert account is not None and account.allocated_minor == 123456
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.transaction(tenant, write=True) as session:
                await session.execute(
                    text("DELETE FROM goal_revisions WHERE tenant_id = :tenant"), {"tenant": tenant}
                )
    finally:
        await database.close()
