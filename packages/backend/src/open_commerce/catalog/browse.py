"""Bounded database reads; browse and search share the verified active integration."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import aliased

from open_commerce.catalog.browse_models import (
    CatalogBrowseProduct,
    CatalogBrowseQuery,
    CatalogBrowseResponse,
    CatalogVariant,
    PublishedCatalog,
)
from open_commerce.catalog.persistence import active_catalog_integration, catalog_index_status
from open_commerce.catalog.scope import current_catalog
from open_commerce.core.money import Money
from open_commerce.persistence.models.catalog import InventorySnapshot, Product, ProductVariant
from open_commerce.persistence.models.commerce import InventoryReservationRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.repositories.commerce import CommerceRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase


class CatalogBrowseService:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def browse(self, *, tenant_id: UUID, query: CatalogBrowseQuery) -> CatalogBrowseResponse:
        async with self.database.transaction(tenant_id) as session:
            # Keep source identity, facets, counts and products on one publication snapshot.
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            indexing = await catalog_index_status(session, tenant_id=tenant_id)
            integration = await active_catalog_integration(session, tenant_id=tenant_id)
            response = CatalogBrowseResponse(
                catalog=None,
                indexing=indexing,
                categories=[],
                items=[],
                total=0,
                offset=0,
                limit=query.limit,
            )
            if integration is None:
                return response

            scope = (
                Product.tenant_id == tenant_id,
                Product.integration_id == integration.id,
                Product.status == "active",
            )
            category = func.coalesce(
                Product.category_path[func.cardinality(Product.category_path)], ""
            )
            response.categories = list(
                await session.scalars(
                    select(category).where(*scope, category != "").distinct().order_by(category)
                )
            )
            product_count = int(
                await session.scalar(select(func.count()).select_from(Product).where(*scope)) or 0
            )
            response.catalog = PublishedCatalog(
                id=integration.id,
                filename=str(
                    integration.non_secret_config.get("filename") or integration.display_name
                ),
                source_version=str(integration.non_secret_config.get("source_version") or ""),
                product_count=product_count,
                published_at=integration.last_successful_sync_at,
            )
            if current_catalog.get() is not None:
                response.catalog.filename = str(
                    await session.scalar(select(Tenant.display_name).where(Tenant.id == tenant_id))
                    or "Store products"
                )
            filters = list(scope)
            if query.product_id:
                filters.append(Product.source_product_id == query.product_id)
            if query.category:
                filters.append(category == query.category)
            stock = (
                select(InventorySnapshot.available_quantity)
                .where(
                    InventorySnapshot.tenant_id == tenant_id,
                    InventorySnapshot.integration_id == integration.id,
                    InventorySnapshot.variant_id == ProductVariant.id,
                )
                .order_by(InventorySnapshot.observed_at.desc(), InventorySnapshot.id)
                .limit(1)
            )
            holds = select(func.coalesce(func.sum(InventoryReservationRecord.quantity), 0)).where(
                InventoryReservationRecord.tenant_id == tenant_id,
                InventoryReservationRecord.catalog_variant_id == ProductVariant.id,
                InventoryReservationRecord.status == "active",
                InventoryReservationRecord.expires_at > datetime.now(UTC),
            )
            purchasable = ProductVariant.available.is_(True) & (
                stock.scalar_subquery() > holds.scalar_subquery()
            )
            if query.in_stock:
                filters.append(
                    Product.id.in_(
                        select(ProductVariant.product_id).where(
                            ProductVariant.tenant_id == tenant_id,
                            purchasable,
                        )
                    )
                )
            if query.q.strip():
                value = query.q.strip()
                filters.append(
                    or_(
                        Product.title.icontains(value, autoescape=True),
                        Product.brand.icontains(value, autoescape=True),
                        Product.source_product_id.icontains(value, autoescape=True),
                    )
                )
            response.total = int(
                await session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
            )
            response.offset = query.offset if query.offset < response.total else 0

            # Show an in-stock variant when one exists; cart selection remains explicit.
            ranked = (
                select(
                    ProductVariant,
                    func.row_number()
                    .over(
                        partition_by=ProductVariant.product_id,
                        order_by=(
                            purchasable.desc().nullslast(),
                            ProductVariant.available.desc(),
                            ProductVariant.source_variant_id,
                            ProductVariant.id,
                        ),
                    )
                    .label("position"),
                )
                .where(ProductVariant.tenant_id == tenant_id)
                .subquery()
            )
            variant = aliased(ProductVariant, ranked)
            observed = (
                select(InventorySnapshot.available_quantity)
                .where(
                    InventorySnapshot.tenant_id == tenant_id,
                    InventorySnapshot.integration_id == integration.id,
                    InventorySnapshot.variant_id == variant.id,
                )
                .order_by(InventorySnapshot.observed_at.desc(), InventorySnapshot.id)
                .limit(1)
                .scalar_subquery()
            )
            title = func.lower(Product.title)
            rows = list(
                (
                    await session.execute(
                        select(Product, variant, observed)
                        .join(
                            variant,
                            (variant.product_id == Product.id)
                            & (variant.tenant_id == Product.tenant_id)
                            & (ranked.c.position == 1),
                        )
                        .where(*filters)
                        .order_by(
                            variant.price_minor
                            if query.sort == "price_asc"
                            else variant.price_minor.desc()
                            if query.sort == "price_desc"
                            else title.desc()
                            if query.sort == "title_desc"
                            else title,
                            Product.source_product_id,
                            Product.id,
                        )
                        .offset(response.offset)
                        .limit(query.limit)
                    )
                ).all()
            )
            reserved = await CommerceRepository(session, tenant_id).reserved_quantities(
                variant_ids=[item.id for _, item, _ in rows],
                now=datetime.now(UTC),
            )
            for product, item, quantity in rows:
                variants = list(
                    (
                        await session.execute(
                            select(ProductVariant, stock.scalar_subquery())
                            .where(
                                ProductVariant.tenant_id == tenant_id,
                                ProductVariant.product_id == product.id,
                            )
                            .order_by(ProductVariant.source_variant_id)
                        )
                    ).all()
                )
                variant_holds = await CommerceRepository(session, tenant_id).reserved_quantities(
                    variant_ids=[v.id for v, _ in variants], now=datetime.now(UTC)
                )
                available: Literal["unknown", "available", "out_of_stock"] = (
                    "unknown" if quantity is None else "available"
                )
                if not item.available or (
                    quantity is not None and quantity <= reserved.get(item.id, 0)
                ):
                    available = "out_of_stock"
                provenance = product.attributes.get("data_provenance")
                response.items.append(
                    CatalogBrowseProduct(
                        variants=[
                            CatalogVariant(
                                id=v.source_variant_id,
                                title=v.title,
                                options=v.option_values,
                                price=Money(amount_minor=v.price_minor, currency=v.currency),
                                available=v.available
                                and count is not None
                                and count > variant_holds.get(v.id, 0),
                                availability=(
                                    "out_of_stock"
                                    if not v.available
                                    or (count is not None and count <= variant_holds.get(v.id, 0))
                                    else "unknown"
                                    if count is None
                                    else "available"
                                ),
                            )
                            for v, count in variants
                        ],
                        product_id=product.source_product_id,
                        title=product.title,
                        description=product.description_text,
                        brand=product.brand,
                        category=product.category_path[-1] if product.category_path else "",
                        image_url=product.primary_image_url,
                        variant_id=item.source_variant_id,
                        price=Money(amount_minor=item.price_minor, currency=item.currency),
                        availability=available,
                        provenance=provenance[:500] if isinstance(provenance, str) else None,
                    )
                )
            return response
