"""Audit append service."""

from uuid import UUID

from open_commerce.application.repositories import AuditRepository
from open_commerce.core.errors import TenantScopeError
from open_commerce.core.events import AuditEvent


class AuditService:
    """Append audit events without exposing update/delete operations."""

    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def append(self, tenant_id: UUID, event: AuditEvent) -> None:
        """Append an event after asserting tenant scope."""

        if event.tenant_id != tenant_id:
            raise TenantScopeError("audit event tenant does not match repository scope")
        await self._repository.append(tenant_id, event)
