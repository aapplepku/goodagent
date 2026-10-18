"""Catalog repository implementation."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.persistence.models.catalog import Product


class SqlCatalogRepository:
    """Tenant-scoped catalog repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_products(self, tenant_id: UUID) -> int:
        """Count products for one tenant only."""

        result = await self._session.scalar(
            select(func.count()).select_from(Product).where(Product.tenant_id == tenant_id),
        )
        return int(result or 0)
