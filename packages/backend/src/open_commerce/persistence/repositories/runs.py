"""Run, snapshot, opportunity, and policy decision repositories."""

from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.events import ObservationSnapshot, Opportunity
from open_commerce.core.policy_types import PolicyDecision
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.actions import PolicyDecisionRecord
from open_commerce.persistence.models.runs import ObservationSnapshotRecord, OpportunityRecord


class SqlRunRepository:
    """Tenant-scoped repository for run records created by the controller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_snapshot(self, tenant_id: UUID, snapshot: ObservationSnapshot) -> None:
        """Persist an immutable observation snapshot."""

        if snapshot.tenant_id != tenant_id:
            raise ValueError("snapshot tenant does not match repository scope")
        self._session.add(
            ObservationSnapshotRecord(
                id=snapshot.id,
                tenant_id=tenant_id,
                goal_id=snapshot.goal_id,
                as_of=snapshot.as_of,
                data=cast(dict[str, object], snapshot.model_dump(mode="json")),
                content_hash=snapshot.content_hash,
                created_at=snapshot.as_of,
            ),
        )

    async def add_opportunity(self, tenant_id: UUID, opportunity: Opportunity) -> None:
        """Persist a detected opportunity."""

        if opportunity.tenant_id != tenant_id:
            raise ValueError("opportunity tenant does not match repository scope")
        self._session.add(
            OpportunityRecord(
                id=opportunity.id,
                tenant_id=tenant_id,
                goal_id=opportunity.goal_id,
                snapshot_id=opportunity.snapshot_id,
                type=opportunity.type,
                entity_refs=cast(dict[str, object], {"items": opportunity.entity_refs}),
                evidence=cast(dict[str, object], {"items": opportunity.evidence}),
                estimated_value_minor=opportunity.estimated_value_minor,
                currency=opportunity.currency,
                confidence=opportunity.confidence,
                detector_code=opportunity.diagnostic_code,
                status=opportunity.status,
                created_at=utc_now(),
            ),
        )

    async def add_policy_decision(
        self,
        tenant_id: UUID,
        action_id: UUID,
        policy_version_id: UUID | None,
        action_version_hash: str,
        decision: PolicyDecision,
    ) -> None:
        """Persist a policy decision payload for later trace display."""

        self._session.add(
            PolicyDecisionRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                action_id=action_id,
                policy_version_id=policy_version_id,
                action_version_hash=action_version_hash,
                outcome=decision.outcome.value,
                reason_codes=decision.reason_codes,
                evaluated_rules=[
                    cast(dict[str, object], rule.model_dump(mode="json"))
                    for rule in decision.evaluated_rules
                ],
                required_roles=[role.value for role in decision.required_approver_roles],
                valid_until=decision.valid_until,
                created_at=decision.valid_until,
            ),
        )
