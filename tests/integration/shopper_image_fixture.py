"""Attach tiny synthetic rasters only to the disposable browser journey catalog."""

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord, CatalogImportRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from tests.integration.merchant_browser_fixture import validate_fixture_environment


def validate_image_fixture(settings: Settings) -> Path:
    validate_fixture_environment(settings)
    expected = os.getenv("OPEN_COMMERCE_E2E_ASSET_DIRECTORY")
    directory = settings.asset_directory
    if (
        not expected
        or directory.is_symlink()
        or directory.resolve() != Path(expected).resolve()
        or directory.name != "shopper-welcome-assets"
        or not directory.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    ):
        raise RuntimeError("Image fixture requires the explicit temporary asset directory.")
    return directory


async def attach_images(database: RuntimeDatabase, tenant: UUID, catalog: UUID) -> list[str]:
    root = validate_image_fixture(database.settings)
    async with database.transaction(tenant, write=True) as session:
        store = await session.scalar(
            select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == tenant)
        )
        source = await session.scalar(
            select(CatalogImportRecord).where(
                CatalogImportRecord.tenant_id == tenant,
                CatalogImportRecord.catalog_id == catalog,
                CatalogImportRecord.status == "confirmed",
            )
        )
        job = await session.scalar(
            select(CatalogIndexJob).where(
                CatalogIndexJob.tenant_id == tenant, CatalogIndexJob.integration_id == catalog
            )
        )
        products = list(
            await session.scalars(
                select(Product)
                .where(Product.tenant_id == tenant, Product.integration_id == catalog)
                .order_by(Product.source_product_id)
            )
        )
        slug = await session.scalar(select(Tenant.slug).where(Tenant.id == tenant))
        if (
            not slug
            or store is None
            or store.published_catalog_id is not None
            or source is None
            or job is None
            or job.status != "ready"
            or job.lease_token is not None
            or job.lease_until is not None
            or {(product.source_product_id, product.title) for product in products}
            != {("mug", "Travel mug"), ("throw", "Soft cotton throw")}
            or any(product.primary_image_url for product in products)
        ):
            raise RuntimeError(
                "Only the unpublished, ready, image-free browser fixture is eligible."
            )
        urls = []
        for product, color in zip(products, ["teal", "gold"], strict=True):
            asset_id = uuid4()
            path = root / str(tenant) / f"{asset_id}.png"
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Synthetic color squares test delivery, not ingestion or product photography.
            Image.new("RGB", (16, 16), color).save(path)
            session.add(
                CatalogAssetRecord(
                    id=asset_id,
                    tenant_id=tenant,
                    import_id=source.id,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    created_at=utc_now(),
                )
            )
            product.primary_image_url = f"/api/runtime/v1/shopper/assets/{asset_id}?store={slug}"
            urls.append(product.primary_image_url)
        return urls


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", type=UUID, required=True)
    parser.add_argument("--catalog", type=UUID, required=True)
    args = parser.parse_args()
    settings = Settings(_env_file=None)
    validate_image_fixture(settings)
    database = RuntimeDatabase(settings)
    try:
        print(json.dumps({"assets": await attach_images(database, args.tenant, args.catalog)}))
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
