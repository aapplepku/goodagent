"""Audit repository implementation."""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.events import AuditEvent
from open_commerce.persistence.models.audit import AuditEventRecord


class SqlAuditRepository:
    """Append-only audit repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, tenant_id: UUID, event: AuditEvent) -> None:
        """Append a safe audit event."""

        if event.tenant_id != tenant_id:
            raise ValueError("audit tenant does not match repository scope")
        self._session.add(
            AuditEventRecord(
                id=event.id,
                tenant_id=tenant_id,
                actor=cast(dict[str, object], event.actor.model_dump(mode="json")),
                event_type=event.event_type.value,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                request_id=event.request_id,
                run_id=event.run_id,
                safe_payload=event.safe_payload,
                previous_event_hash=event.previous_event_hash,
                event_hash=event.event_hash,
                occurred_at=event.occurred_at,
            ),
        )

    async def list_for_entity(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> list[AuditEvent]:
        """List audit events for one tenant/entity."""

        records = await self._session.scalars(
            select(AuditEventRecord)
            .where(
                AuditEventRecord.tenant_id == tenant_id,
                AuditEventRecord.entity_type == entity_type,
                AuditEventRecord.entity_id == entity_id,
            )
            .order_by(AuditEventRecord.occurred_at),
        )
        return [
            AuditEvent.model_validate(
                {
                    "id": record.id,
                    "tenant_id": record.tenant_id,
                    "actor": record.actor,
                    "event_type": record.event_type,
                    "entity_type": record.entity_type,
                    "entity_id": record.entity_id,
                    "request_id": record.request_id,
                    "run_id": record.run_id,
                    "safe_payload": record.safe_payload,
                    "previous_event_hash": record.previous_event_hash,
                    "event_hash": record.event_hash,
                    "occurred_at": record.occurred_at,
                },
            )
            for record in records
        ]
