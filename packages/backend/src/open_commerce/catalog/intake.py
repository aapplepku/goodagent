"""Configured read-only catalog intake feeds the existing verified indexing pipeline."""

from uuid import UUID

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.catalog.persistence import stage_catalog_upload
from open_commerce.catalog.sources import CatalogConnection, CatalogSource, CatalogSourceError
from open_commerce.core.types import canonical_hash
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.shopify_catalog import ShopifyCatalogProvider


class CatalogIntake:
    def __init__(self, database: RuntimeDatabase, provider: CatalogSource | None = None) -> None:
        self.database, self.provider = database, provider

    def source(self, tenant_id: UUID) -> CatalogSource:
        settings = self.database.settings
        if tenant_id != settings.local_tenant_id:
            raise CatalogSourceError(
                "This connector is configured for a different local workspace."
            )
        if self.provider:
            return self.provider
        if (
            not settings.shopify_catalog_enabled
            or not settings.shopify_shop_domain
            or not settings.shopify_admin_access_token
        ):
            raise CatalogSourceError(
                "Shopify is not connected. Configure a read-only test-store token "
                "outside chat, or upload a Shopify CSV."
            )
        return ShopifyCatalogProvider(
            settings.shopify_shop_domain, settings.shopify_admin_access_token
        )

    async def check(self, tenant_id: UUID) -> CatalogConnection:
        try:
            provider = self.source(tenant_id)
        except CatalogSourceError as exc:
            return CatalogConnection(configured=False, connected=False, detail=str(exc))
        try:
            return await provider.check()
        except CatalogSourceError as exc:
            return CatalogConnection(configured=True, connected=False, detail=str(exc))

    async def load(self, tenant_id: UUID, key: str) -> CatalogIndexStatus:
        provider = self.source(tenant_id)
        request = {"provider": "shopify", "shop": self.database.settings.shopify_shop_domain}
        async with self.database.transaction(tenant_id, write=True) as session:
            cached = await RequestRepository(session, tenant_id).replay(
                scope="catalog:shopify", key=key, request=request
            )
            if cached:
                return CatalogIndexStatus.model_validate(cached)
        try:
            products = await provider.fetch_catalog()
        except TimeoutError as exc:
            raise CatalogSourceError(
                "Shopify import timed out; the previous catalog was retained."
            ) from exc
        fingerprint = canonical_hash({"source": request, "products": products})
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope="catalog:shopify", key=key, request=request)
            if cached:
                return CatalogIndexStatus.model_validate(cached)
            result = await stage_catalog_upload(
                session,
                tenant_id=tenant_id,
                filename="Shopify catalog",
                source_version=fingerprint,
                products=products,
            )
            receipts.remember(scope="catalog:shopify", key=key, request=request, response=result)
            return result
