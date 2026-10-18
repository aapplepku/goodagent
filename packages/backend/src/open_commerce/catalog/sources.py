"""Read-only provider boundary for normalized catalog snapshots."""

from typing import Protocol

from open_commerce.catalog.models import CatalogProductInput
from open_commerce.core.types import StrictDomainModel


class CatalogConnection(StrictDomainModel):
    configured: bool
    connected: bool
    provider: str = "shopify"
    shop: str | None = None
    detail: str


class CatalogSource(Protocol):
    async def check(self) -> CatalogConnection: ...
    async def fetch_catalog(self) -> list[CatalogProductInput]: ...


class CatalogSourceError(ValueError):
    """Safe provider error without response bodies, access tokens or arbitrary URLs."""
