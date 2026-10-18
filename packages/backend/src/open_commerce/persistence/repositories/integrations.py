"""Integration repository implementation."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.providers import CapabilitySet
from open_commerce.persistence.models.integrations import Integration


class SqlIntegrationRepository:
    """Tenant-scoped integration metadata repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def capabilities(self, tenant_id: UUID, integration_id: UUID) -> CapabilitySet | None:
        """Return provider capabilities for one tenant integration."""

        integration = await self._session.scalar(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.id == integration_id,
            ),
        )
        if integration is None:
            return None
        return CapabilitySet.model_validate(integration.capabilities)
