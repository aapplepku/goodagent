"""The browser-only synthetic image hook refuses other catalog states in real SQL."""

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.runtime_db import RuntimeDatabase
from tests.integration.shopper_image_fixture import attach_images
from tests.integration.test_catalog_setup_continuity import (
    StoreFixture,
    catalog_store,  # noqa: F401 -- shared real-SQL fixture
)

pytestmark = pytest.mark.integration
CSV = (
    b"product_id,title,price,currency,inventory_quantity,updated_at\n"
    b"mug,Travel mug,15,USD,20,2026-10-01T00:00:00Z\n"
    b"throw,Soft cotton throw,35,USD,30,2026-10-01T00:00:00Z\n"
)


@pytest.mark.parametrize(
    "state", ["eligible", "foreign", "missing", "queued", "leased", "published", "wrong_products"]
)
async def test_welcome_image_fixture_only_changes_expected_unpublished_catalog(
    catalog_store: StoreFixture,  # noqa: F811 -- pytest fixture injection
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    state: str,
) -> None:
    store = catalog_store
    root = tmp_path / "shopper-welcome-assets"
    settings = store.database.settings.model_copy(update={"asset_directory": root})
    monkeypatch.setenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", "1")
    monkeypatch.setenv("OPEN_COMMERCE_E2E_ASSET_DIRECTORY", str(root))
    database = RuntimeDatabase(settings)
    try:
        content = (
            CSV.replace(b"Travel mug", b"Another product") if state == "wrong_products" else CSV
        )
        candidate = await store.confirmed("welcome-fixture.csv", content, ready=state != "queued")
        assert candidate.catalog_id
        if state == "published":
            await store.publish(candidate.catalog_id, "fixture-publication")
        elif state == "leased":
            async with database.transaction(store.tenant, write=True) as session:
                job = await session.scalar(
                    select(CatalogIndexJob).where(
                        CatalogIndexJob.tenant_id == store.tenant,
                        CatalogIndexJob.integration_id == candidate.catalog_id,
                    )
                )
                assert job
                job.lease_token = uuid4()
        if state == "eligible":
            urls = await attach_images(database, store.tenant, candidate.catalog_id)
            assert len(urls) == 2 and len(set(urls)) == 2
            async with database.transaction(store.tenant) as session:
                assets = list(
                    await session.scalars(
                        select(CatalogAssetRecord).where(
                            CatalogAssetRecord.tenant_id == store.tenant,
                            CatalogAssetRecord.import_id == candidate.id,
                        )
                    )
                )
                assert len(assets) == 2
                for asset in assets:
                    path = root / str(store.tenant) / f"{asset.id}.png"
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == asset.sha256
            before = {str(path): path.read_bytes() for path in root.rglob("*.png")}
            with pytest.raises(RuntimeError, match="unpublished, ready, image-free"):
                await attach_images(database, store.tenant, candidate.catalog_id)
            assert {str(path): path.read_bytes() for path in root.rglob("*.png")} == before
        else:
            with pytest.raises(RuntimeError, match="unpublished, ready, image-free"):
                await attach_images(
                    database,
                    uuid4() if state == "foreign" else store.tenant,
                    uuid4() if state == "missing" else candidate.catalog_id,
                )
            assert not root.exists()
            async with database.transaction(store.tenant) as session:
                assert not list(
                    await session.scalars(
                        select(CatalogAssetRecord).where(
                            CatalogAssetRecord.tenant_id == store.tenant
                        )
                    )
                )
                assert all(
                    image is None
                    for image in await session.scalars(
                        select(Product.primary_image_url).where(Product.tenant_id == store.tenant)
                    )
                )
    finally:
        await database.close()
