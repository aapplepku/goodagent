"""Checkpointed raster preparation before a catalog becomes searchable."""

import asyncio
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord, CatalogImportRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.catalog_images import (
    CatalogImageProvider,
    ImageIngestionError,
    SafeCatalogImages,
)


async def prepare_asset_batch(
    database: RuntimeDatabase,
    tenant: UUID,
    catalog: UUID,
    job_id: UUID,
    lease: UUID,
    provider: CatalogImageProvider | None = None,
) -> bool:
    provider = provider or SafeCatalogImages()
    async with database.transaction(tenant) as session:
        source = await session.scalar(
            select(CatalogImportRecord.id)
            .where(
                CatalogImportRecord.tenant_id == tenant,
                CatalogImportRecord.catalog_id == catalog,
            )
            .limit(1)
        )
        if source is None:
            return True  # Legacy imports retain their existing image contract.
        products = list(
            await session.scalars(
                select(Product)
                .where(
                    Product.tenant_id == tenant,
                    Product.integration_id == catalog,
                    Product.attributes["safe_image_pending"].as_boolean().is_(True),
                )
                .order_by(Product.id)
                .limit(4)
            )
        )
    if not products:
        return True
    for product in products:
        asset_id = uuid4()
        data: bytes | None = None
        try:
            data = await provider.fetch(product.primary_image_url or "")
        except ImageIngestionError:
            pass
        directory = database.settings.asset_directory / str(tenant)
        path = directory / f"{asset_id}.png"
        if data is not None:
            await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True, mode=0o700)
            await asyncio.to_thread(path.write_bytes, data)
        async with database.transaction(tenant, write=True) as session:
            current = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == tenant,
                    CatalogIndexJob.id == job_id,
                    CatalogIndexJob.lease_token == lease,
                )
            )
            if current is None:
                if data is not None:
                    await asyncio.to_thread(path.unlink, missing_ok=True)
                return False
            item = await session.scalar(
                select(Product).where(
                    Product.tenant_id == tenant,
                    Product.integration_id == catalog,
                    Product.id == product.id,
                )
            )
            if item is None:
                return False
            item.attributes = {
                **item.attributes,
                "safe_image_pending": False,
                "image_failed": data is None,
            }
            item.primary_image_url = None
            if data is not None:
                session.add(
                    CatalogAssetRecord(
                        id=asset_id,
                        tenant_id=tenant,
                        import_id=source,
                        sha256=sha256(data).hexdigest(),
                        created_at=utc_now(),
                    )
                )
                slug = await session.scalar(select(Tenant.slug).where(Tenant.id == tenant))
                item.primary_image_url = f"/api/runtime/v1/shopper/assets/{asset_id}?store={slug}"
    return False
