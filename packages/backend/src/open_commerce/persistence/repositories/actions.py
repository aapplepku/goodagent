"""Action and approval repository implementations."""

from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.actions import CompiledAction, compute_action_version_hash
from open_commerce.core.policy_types import Approval, ApprovalRequest
from open_commerce.persistence.models.actions import (
    ActionIntentRecord,
    ApprovalRecord,
    ApprovalRequestRecord,
    CompiledActionRecord,
)


class SqlActionRepository:
    """Tenant-scoped action repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_compiled(self, tenant_id: UUID, action: CompiledAction) -> None:
        """Persist a compiled action and its typed intent."""

        if action.tenant_id != tenant_id:
            raise ValueError("action tenant does not match repository scope")
        intent_id = uuid4()
        self._session.add(
            ActionIntentRecord(
                id=intent_id,
                tenant_id=tenant_id,
                goal_id=action.goal_id,
                run_id=action.run_id,
                type=action.intent.type,
                payload=cast(dict[str, object], action.intent.model_dump(mode="json")),
                rationale=action.intent.rationale,
                opportunity_ids=action.intent.opportunity_ids,
                actor=cast(dict[str, object], action.intent.requested_by.model_dump(mode="json")),
                created_at=action.intent.proposed_at,
            ),
        )
        self._session.add(
            CompiledActionRecord(
                id=action.id,
                tenant_id=tenant_id,
                goal_id=action.goal_id,
                run_id=action.run_id,
                intent_id=intent_id,
                type=action.intent.type,
                target_provider=cast(
                    dict[str, object], action.target_provider.model_dump(mode="json")
                ),
                normalized_parameters=action.normalized_parameters,
                preconditions=[
                    cast(dict[str, object], precondition.model_dump(mode="json"))
                    for precondition in action.preconditions
                ],
                expected_impact=cast(
                    dict[str, object], action.expected_impact.model_dump(mode="json")
                ),
                estimated_cost_minor=action.estimated_cost.amount_minor,
                currency=action.estimated_cost.currency,
                risk=cast(dict[str, object], action.risk.model_dump(mode="json")),
                rollback_plan=cast(dict[str, object], action.rollback_plan.model_dump(mode="json")),
                idempotency_key=action.idempotency_key,
                version_hash=compute_action_version_hash(action),
                status=action.status.value,
                expires_at=action.expires_at,
                budget_reservations=[
                    cast(dict[str, object], item.model_dump(mode="json"))
                    for item in action.budget_reservations
                ],
            ),
        )

    async def get_compiled(self, tenant_id: UUID, action_id: UUID) -> CompiledAction | None:
        """Load a compiled action only inside the provided tenant scope."""

        record = await self._session.scalar(
            select(CompiledActionRecord).where(
                CompiledActionRecord.tenant_id == tenant_id,
                CompiledActionRecord.id == action_id,
            ),
        )
        if record is None or record.intent_id is None:
            return None
        intent = await self._session.scalar(
            select(ActionIntentRecord).where(
                ActionIntentRecord.tenant_id == tenant_id,
                ActionIntentRecord.id == record.intent_id,
            ),
        )
        if intent is None:
            return None
        payload = {
            "id": record.id,
            "tenant_id": record.tenant_id,
            "goal_id": record.goal_id,
            "run_id": record.run_id,
            "intent": intent.payload,
            "target_provider": record.target_provider,
            "normalized_parameters": record.normalized_parameters,
            "preconditions": record.preconditions,
            "expected_impact": record.expected_impact,
            "estimated_cost": {
                "amount_minor": record.estimated_cost_minor,
                "currency": record.currency,
            },
            "budget_reservations": record.budget_reservations,
            "risk": record.risk,
            "rollback_plan": record.rollback_plan,
            "idempotency_key": record.idempotency_key,
            "expires_at": record.expires_at,
            "status": record.status,
        }
        return CompiledAction.model_validate(payload)

    async def transition(self, tenant_id: UUID, action_id: UUID, status: str) -> None:
        """Persist a validated action status transition."""

        await self._session.execute(
            update(CompiledActionRecord)
            .where(
                CompiledActionRecord.tenant_id == tenant_id,
                CompiledActionRecord.id == action_id,
            )
            .values(status=status),
        )


class SqlApprovalRepository:
    """Tenant-scoped approval repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_request(self, tenant_id: UUID, request: ApprovalRequest) -> None:
        """Persist an approval request."""

        if request.tenant_id != tenant_id:
            raise ValueError("approval request tenant does not match repository scope")
        self._session.add(
            ApprovalRequestRecord(
                id=request.id,
                tenant_id=tenant_id,
                action_id=request.action_id,
                action_version_hash=request.action_version_hash,
                required_roles=[role.value for role in request.required_roles],
                status=request.status,
                expires_at=request.expires_at,
                created_at=request.created_at,
            ),
        )

    async def add_approval(self, tenant_id: UUID, approval: Approval) -> None:
        """Persist an approval or rejection."""

        if approval.tenant_id != tenant_id:
            raise ValueError("approval tenant does not match repository scope")
        self._session.add(
            ApprovalRecord(
                id=approval.id,
                tenant_id=tenant_id,
                request_id=approval.request_id,
                actor_user_id=UUID(approval.actor.id),
                decision=approval.decision,
                comment=approval.comment,
                action_version_hash=approval.action_version_hash,
                decided_at=approval.decided_at,
            ),
        )
