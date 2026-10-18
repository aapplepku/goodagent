"""Transactional request replay with payload-conflict detection."""

from typing import cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.types import canonical_hash
from open_commerce.persistence.models.workflow import IdempotencyRecord


class IdempotencyConflictError(ValueError):
    """A key was reused for a materially different operation."""


class RequestRepository:
    """Use within a tenant-serialized write transaction, including the actual mutation."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def replay(self, *, scope: str, key: str, request: object) -> dict[str, object] | None:
        if not key or len(key) > 200:
            raise ValueError("idempotency key must contain 1 to 200 characters")
        row = await self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == self.tenant_id,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.key == key,
            )
        )
        if row is None:
            return None
        if row.fingerprint != canonical_hash(request):
            raise IdempotencyConflictError("idempotency key already used with different input")
        return row.response

    def remember(self, *, scope: str, key: str, request: object, response: BaseModel) -> None:
        self.session.add(
            IdempotencyRecord(
                tenant_id=self.tenant_id,
                scope=scope,
                key=key,
                fingerprint=canonical_hash(request),
                response=cast(dict[str, object], response.model_dump(mode="json")),
            )
        )
