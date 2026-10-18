"""Tenant-scoped persistence for immutable CSV catalog versions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.models import CatalogIndexState, CatalogIndexStatus, CatalogProductInput
from open_commerce.catalog.scope import current_catalog
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.persistence.models.catalog import InventorySnapshot, Product, ProductVariant
from open_commerce.persistence.models.integrations import Integration
from open_commerce.persistence.models.search import CatalogIndexJob

CSV_CATALOG_PROVIDER = "manager_csv"


async def stage_catalog_upload(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    filename: str,
    source_version: str,
    products: list[CatalogProductInput],
) -> CatalogIndexStatus:
    """Persist one content-addressed catalog and queue its reconstructable index."""

    integration_id = uuid5(NAMESPACE_URL, f"open-commerce:catalog:{tenant_id}:{source_version}")
    existing = await session.scalar(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.id == integration_id,
        )
    )
    if existing is not None:
        return await catalog_index_status(
            session, tenant_id=tenant_id, integration_id=integration_id
        )

    now = utc_now()
    integration = Integration(
        id=integration_id,
        tenant_id=tenant_id,
        provider=CSV_CATALOG_PROVIDER,
        external_account_id=source_version,
        display_name=filename,
        mode="read_only",
        status="queued",
        capabilities={"catalog_read": True, "search_index": True},
        non_secret_config={
            "filename": filename,
            "source_version": source_version,
            "product_count": len(products),
        },
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(integration)
    await session.flush()
    inventory_snapshots: list[InventorySnapshot] = []
    for item in products:
        product_id = uuid5(integration_id, f"product:{item.source_product_id}")
        product = Product(
            id=product_id,
            tenant_id=tenant_id,
            integration_id=integration_id,
            source_product_id=item.source_product_id,
            title=item.title,
            handle=item.source_product_id,
            description_text=item.description_text,
            brand=item.brand,
            category_path=item.category_path,
            tags=item.tags,
            status="active",
            attributes=item.attributes,
            primary_image_url=item.primary_image_url,
            product_url=None,
            source_updated_at=item.source_updated_at,
            synced_at=now,
            content_hash=canonical_hash(item),
            version=1,
        )
        session.add(product)
        for variant in item.variants:
            variant_id = uuid5(product_id, f"variant:{variant.source_variant_id}")
            session.add(
                ProductVariant(
                    id=variant_id,
                    tenant_id=tenant_id,
                    product_id=product_id,
                    source_variant_id=variant.source_variant_id,
                    sku=variant.sku,
                    title=variant.title,
                    option_values=variant.option_values,
                    price_minor=variant.price_minor,
                    compare_at_price_minor=None,
                    cost_minor=None,
                    currency=variant.currency,
                    available=variant.available,
                    source_updated_at=item.source_updated_at,
                    content_hash=canonical_hash(variant),
                    version=1,
                )
            )
            if variant.inventory_quantity is not None:
                inventory_snapshots.append(
                    InventorySnapshot(
                        id=uuid5(variant_id, f"inventory:{source_version}"),
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        variant_id=variant_id,
                        source_location_id=None,
                        available_quantity=variant.inventory_quantity,
                        on_hand_quantity=variant.inventory_quantity,
                        observed_at=now,
                    )
                )
    await session.flush()
    session.add_all(inventory_snapshots)
    await session.flush()
    job = CatalogIndexJob(
        id=uuid5(integration_id, "search-index"),
        tenant_id=tenant_id,
        integration_id=integration_id,
        source_version=source_version,
        status="queued",
        product_count=len(products),
        indexed_product_count=0,
        attempts=0,
        failures=0,
        available_at=now,
        lease_until=None,
        lease_token=None,
        completed_at=None,
        safe_error=None,
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(job)
    await session.flush()
    return _status(job, integration)


async def catalog_index_status(
    session: AsyncSession, *, tenant_id: UUID, integration_id: UUID | None = None
) -> CatalogIndexStatus:
    scope = current_catalog.get()
    if scope is not None:
        if scope.tenant_id != tenant_id or (
            integration_id is not None and integration_id != scope.catalog_id
        ):
            raise ValueError("Catalog status scope does not match tenant publication")
        integration_id = scope.catalog_id
    query = (
        select(CatalogIndexJob, Integration)
        .join(
            Integration,
            (Integration.id == CatalogIndexJob.integration_id)
            & (Integration.tenant_id == CatalogIndexJob.tenant_id),
        )
        .where(CatalogIndexJob.tenant_id == tenant_id)
        .order_by(CatalogIndexJob.created_at.desc(), CatalogIndexJob.id.desc())
        .limit(1)
    )
    if integration_id is not None:
        query = query.where(CatalogIndexJob.integration_id == integration_id)
    row = (await session.execute(query)).first()
    status = _status(*row) if row is not None else CatalogIndexStatus()
    if scope is not None:
        status.filename = None
    active = await active_catalog_integration(session, tenant_id=tenant_id)
    if active is not None:
        status.serving_catalog_id = active.id
        status.serving_product_count = int(str(active.non_secret_config.get("product_count", 0)))
    return status


async def active_catalog_integration(
    session: AsyncSession, *, tenant_id: UUID
) -> Integration | None:
    scope = current_catalog.get()
    if scope is not None:
        if scope.tenant_id != tenant_id:
            raise ValueError("Catalog scope does not match tenant")
        scoped: Integration | None = await session.scalar(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.id == scope.catalog_id,
                Integration.provider == CSV_CATALOG_PROVIDER,
            )
        )
        return scoped
    result = await session.scalar(
        select(Integration)
        .where(
            Integration.tenant_id == tenant_id,
            Integration.provider == CSV_CATALOG_PROVIDER,
            Integration.status == "active",
        )
        .order_by(Integration.last_successful_sync_at.desc(), Integration.id.desc())
        .limit(1)
    )
    return result


async def catalog_records(
    session: AsyncSession, *, tenant_id: UUID, integration_id: UUID
) -> list[tuple[Product, list[ProductVariant], dict[UUID, int]]]:
    products = list(
        await session.scalars(
            select(Product)
            .where(
                Product.tenant_id == tenant_id,
                Product.integration_id == integration_id,
                Product.status == "active",
            )
            .order_by(Product.source_product_id, Product.id)
        )
    )
    product_ids = [item.id for item in products]
    variants: dict[UUID, list[ProductVariant]] = defaultdict(list)
    inventory: dict[UUID, int] = {}
    if product_ids:
        variant_rows = list(
            await session.scalars(
                select(ProductVariant)
                .where(
                    ProductVariant.tenant_id == tenant_id,
                    ProductVariant.product_id.in_(product_ids),
                )
                .order_by(ProductVariant.product_id, ProductVariant.source_variant_id)
            )
        )
        for variant in variant_rows:
            variants[variant.product_id].append(variant)
        inventory_rows = await session.execute(
            select(InventorySnapshot.variant_id, InventorySnapshot.available_quantity).where(
                InventorySnapshot.tenant_id == tenant_id,
                InventorySnapshot.integration_id == integration_id,
            )
        )
        inventory = {variant_id: quantity for variant_id, quantity in inventory_rows}
    return [(product, variants[product.id], inventory) for product in products]


async def activate_catalog(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    integration_id: UUID,
    indexed_count: int,
    completed_at: datetime,
) -> None:
    integrations = list(
        await session.scalars(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.provider == CSV_CATALOG_PROVIDER,
            )
        )
    )
    for integration in integrations:
        if integration.id == integration_id:
            integration.status = "active"
            integration.last_successful_sync_at = completed_at
            integration.updated_at = completed_at
        elif integration.status == "active":
            integration.status = "superseded"
            integration.updated_at = completed_at
    job = await session.scalar(
        select(CatalogIndexJob).where(
            CatalogIndexJob.tenant_id == tenant_id,
            CatalogIndexJob.integration_id == integration_id,
        )
    )
    if job is None:
        raise ValueError("catalog index job not found")
    job.status = "ready"
    job.indexed_product_count = indexed_count
    job.completed_at = completed_at
    job.lease_until = None
    job.lease_token = None
    job.safe_error = None
    job.updated_at = completed_at
    for integration in integrations:
        if integration.id == integration_id:
            integration.non_secret_config = {
                **integration.non_secret_config,
                "source_version": job.source_version,
            }


def _status(job: CatalogIndexJob, integration: Integration) -> CatalogIndexStatus:
    safe_error = job.safe_error or {}
    return CatalogIndexStatus(
        status=cast(CatalogIndexState, job.status),
        job_id=job.id,
        catalog_id=job.integration_id,
        filename=str(integration.non_secret_config.get("filename") or integration.display_name),
        source_version=job.source_version,
        product_count=job.product_count,
        indexed_product_count=job.indexed_product_count,
        error_code=str(safe_error.get("code")) if safe_error.get("code") else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )
