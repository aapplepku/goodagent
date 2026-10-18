"""Tenant/account-scoped persistence for the local commerce runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.commerce.errors import CommerceNotFoundError
from open_commerce.persistence.models.catalog import InventorySnapshot, Product, ProductVariant
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
    ShopperCartLineRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.models.integrations import Integration


@dataclass(frozen=True)
class CatalogSelection:
    product: Product
    variant: ProductVariant
    inventory: InventorySnapshot | None


class CommerceRepository:
    """All methods apply tenant scope and shopper methods also apply account scope."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def open_cart(
        self, *, account_id: UUID, for_update: bool = False
    ) -> ShopperCartRecord | None:
        query = select(ShopperCartRecord).where(
            ShopperCartRecord.tenant_id == self.tenant_id,
            ShopperCartRecord.account_id == account_id,
            ShopperCartRecord.status == "open",
        )
        if for_update:
            query = query.with_for_update()
        return cast(ShopperCartRecord | None, await self.session.scalar(query))

    async def create_cart(
        self, *, cart_id: UUID, account_id: UUID, currency: str, now: datetime
    ) -> ShopperCartRecord:
        row = ShopperCartRecord(
            id=cart_id,
            tenant_id=self.tenant_id,
            account_id=account_id,
            status="open",
            currency=currency,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def cart_by_id(
        self, *, account_id: UUID, cart_id: UUID, for_update: bool = False
    ) -> ShopperCartRecord:
        query = select(ShopperCartRecord).where(
            ShopperCartRecord.tenant_id == self.tenant_id,
            ShopperCartRecord.account_id == account_id,
            ShopperCartRecord.id == cart_id,
        )
        if for_update:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            raise CommerceNotFoundError("Cart was not found")
        return row

    async def cart_lines(self, *, account_id: UUID, cart_id: UUID) -> list[ShopperCartLineRecord]:
        return list(
            await self.session.scalars(
                select(ShopperCartLineRecord)
                .where(
                    ShopperCartLineRecord.tenant_id == self.tenant_id,
                    ShopperCartLineRecord.account_id == account_id,
                    ShopperCartLineRecord.cart_id == cart_id,
                )
                .order_by(ShopperCartLineRecord.created_at, ShopperCartLineRecord.id)
            )
        )

    async def cart_line(
        self, *, account_id: UUID, cart_id: UUID, line_id: UUID
    ) -> ShopperCartLineRecord:
        row = await self.session.scalar(
            select(ShopperCartLineRecord).where(
                ShopperCartLineRecord.tenant_id == self.tenant_id,
                ShopperCartLineRecord.account_id == account_id,
                ShopperCartLineRecord.cart_id == cart_id,
                ShopperCartLineRecord.id == line_id,
            )
        )
        if row is None:
            raise CommerceNotFoundError("Cart item was not found")
        return row

    async def cart_line_for_variant(
        self, *, account_id: UUID, cart_id: UUID, variant_id: UUID
    ) -> ShopperCartLineRecord | None:
        return cast(
            ShopperCartLineRecord | None,
            await self.session.scalar(
                select(ShopperCartLineRecord).where(
                    ShopperCartLineRecord.tenant_id == self.tenant_id,
                    ShopperCartLineRecord.account_id == account_id,
                    ShopperCartLineRecord.cart_id == cart_id,
                    ShopperCartLineRecord.catalog_variant_id == variant_id,
                )
            ),
        )

    async def catalog_selection(
        self, *, source_product_id: str, source_variant_id: str | None = None
    ) -> CatalogSelection:
        from open_commerce.catalog.persistence import active_catalog_integration

        integration = await active_catalog_integration(self.session, tenant_id=self.tenant_id)
        if integration is None:
            raise CommerceNotFoundError("Catalog unavailable")
        choices = list(
            await self.session.scalars(
                select(ProductVariant.source_variant_id)
                .join(
                    Product,
                    (Product.id == ProductVariant.product_id)
                    & (Product.tenant_id == ProductVariant.tenant_id),
                )
                .where(
                    Product.tenant_id == self.tenant_id,
                    Product.integration_id == integration.id,
                    Product.source_product_id == source_product_id,
                )
            )
        )
        if len(choices) > 1 and source_variant_id is None:
            raise CommerceNotFoundError("Choose a product variant before adding it to your cart.")
        row = (
            await self.session.execute(
                select(Product, ProductVariant)
                .join(
                    Integration,
                    (Integration.id == Product.integration_id)
                    & (Integration.tenant_id == Product.tenant_id),
                )
                .join(
                    ProductVariant,
                    (ProductVariant.product_id == Product.id)
                    & (ProductVariant.tenant_id == Product.tenant_id),
                )
                .where(
                    Product.tenant_id == self.tenant_id,
                    Product.source_product_id == source_product_id,
                    Product.status == "active",
                    Integration.id == integration.id,
                    Integration.provider == "manager_csv",
                    ProductVariant.available.is_(True),
                    ProductVariant.source_variant_id
                    == (source_variant_id or (choices[0] if choices else "")),
                )
                .order_by(ProductVariant.source_variant_id, ProductVariant.id)
                .limit(1)
            )
        ).first()
        if row is None:
            raise CommerceNotFoundError("Product is not available in the active catalog")
        product, variant = row
        inventory = await self.latest_inventory(variant_id=variant.id)
        return CatalogSelection(product=product, variant=variant, inventory=inventory)

    async def current_variant(
        self, *, product_id: UUID, variant_id: UUID
    ) -> CatalogSelection | None:
        from open_commerce.catalog.persistence import active_catalog_integration

        integration = await active_catalog_integration(self.session, tenant_id=self.tenant_id)
        if integration is None:
            return None
        row = (
            await self.session.execute(
                select(Product, ProductVariant)
                .join(
                    Integration,
                    (Integration.id == Product.integration_id)
                    & (Integration.tenant_id == Product.tenant_id),
                )
                .join(
                    ProductVariant,
                    (ProductVariant.product_id == Product.id)
                    & (ProductVariant.tenant_id == Product.tenant_id),
                )
                .where(
                    Product.tenant_id == self.tenant_id,
                    Product.id == product_id,
                    ProductVariant.id == variant_id,
                    Product.status == "active",
                    ProductVariant.available.is_(True),
                    Integration.id == integration.id,
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        product, variant = row
        return CatalogSelection(
            product=product,
            variant=variant,
            inventory=await self.latest_inventory(variant_id=variant.id),
        )

    async def latest_inventory(self, *, variant_id: UUID) -> InventorySnapshot | None:
        return cast(
            InventorySnapshot | None,
            await self.session.scalar(
                select(InventorySnapshot)
                .where(
                    InventorySnapshot.tenant_id == self.tenant_id,
                    InventorySnapshot.variant_id == variant_id,
                )
                .order_by(InventorySnapshot.observed_at.desc(), InventorySnapshot.id.desc())
                .limit(1)
            ),
        )

    async def reserved_quantities(
        self,
        *,
        variant_ids: list[UUID],
        now: datetime,
        excluding_checkout_id: UUID | None = None,
    ) -> dict[UUID, int]:
        if not variant_ids:
            return {}
        query = (
            select(
                InventoryReservationRecord.catalog_variant_id,
                func.sum(InventoryReservationRecord.quantity),
            )
            .where(
                InventoryReservationRecord.tenant_id == self.tenant_id,
                InventoryReservationRecord.catalog_variant_id.in_(variant_ids),
                InventoryReservationRecord.status == "active",
                InventoryReservationRecord.expires_at > now,
            )
            .group_by(InventoryReservationRecord.catalog_variant_id)
        )
        if excluding_checkout_id is not None:
            query = query.where(InventoryReservationRecord.checkout_id != excluding_checkout_id)
        rows = await self.session.execute(query)
        return {variant_id: int(quantity or 0) for variant_id, quantity in rows}

    async def add_line(
        self,
        *,
        line_id: UUID,
        cart: ShopperCartRecord,
        account_id: UUID,
        selection: CatalogSelection,
        quantity: int,
        now: datetime,
    ) -> ShopperCartLineRecord:
        row = ShopperCartLineRecord(
            id=line_id,
            tenant_id=self.tenant_id,
            account_id=account_id,
            cart_id=cart.id,
            catalog_product_id=selection.product.id,
            catalog_variant_id=selection.variant.id,
            source_product_id=selection.product.source_product_id,
            source_variant_id=selection.variant.source_variant_id,
            title=selection.product.title,
            variant_title=selection.variant.title,
            image_url=selection.product.primary_image_url,
            quantity=quantity,
            unit_price_minor=selection.variant.price_minor,
            currency=selection.variant.currency,
            catalog_version=selection.variant.version,
            created_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete_line(self, row: ShopperCartLineRecord) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def invalidate_checkout(self, *, cart: ShopperCartRecord, now: datetime) -> None:
        processing = await self.session.scalar(
            select(PaymentAttemptRecord.id).where(
                PaymentAttemptRecord.tenant_id == self.tenant_id,
                PaymentAttemptRecord.cart_id == cart.id,
                PaymentAttemptRecord.status == "processing",
            )
        )
        if processing is not None:
            from open_commerce.commerce.errors import CommerceConflictError

            raise CommerceConflictError("Checkout is processing; the cart cannot be changed")
        await self.session.execute(
            update(InventoryReservationRecord)
            .where(
                InventoryReservationRecord.tenant_id == self.tenant_id,
                InventoryReservationRecord.cart_id == cart.id,
                InventoryReservationRecord.status == "active",
            )
            .values(
                status="released",
                release_reason="cart_changed",
                updated_at=now,
                version=InventoryReservationRecord.version + 1,
            )
        )
        await self.session.execute(
            update(PaymentAttemptRecord)
            .where(
                PaymentAttemptRecord.tenant_id == self.tenant_id,
                PaymentAttemptRecord.cart_id == cart.id,
                PaymentAttemptRecord.status.in_(
                    ["requires_confirmation", "requires_payment_method"]
                ),
            )
            .values(
                status="cancelled",
                updated_at=now,
                version=PaymentAttemptRecord.version + 1,
            )
        )

    async def expire_reservations(self, *, now: datetime) -> None:
        await self.session.execute(
            update(InventoryReservationRecord)
            .where(
                InventoryReservationRecord.tenant_id == self.tenant_id,
                InventoryReservationRecord.status == "active",
                InventoryReservationRecord.expires_at <= now,
            )
            .values(
                status="expired",
                release_reason="reservation_expired",
                updated_at=now,
                version=InventoryReservationRecord.version + 1,
            )
        )

    async def payment_for_cart_version(
        self, *, cart_id: UUID, cart_version: int
    ) -> PaymentAttemptRecord | None:
        return cast(
            PaymentAttemptRecord | None,
            await self.session.scalar(
                select(PaymentAttemptRecord).where(
                    PaymentAttemptRecord.tenant_id == self.tenant_id,
                    PaymentAttemptRecord.cart_id == cart_id,
                    PaymentAttemptRecord.cart_version == cart_version,
                )
            ),
        )

    async def payment(
        self, *, account_id: UUID, payment_id: UUID, for_update: bool = False
    ) -> PaymentAttemptRecord:
        query = select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.tenant_id == self.tenant_id,
            PaymentAttemptRecord.account_id == account_id,
            PaymentAttemptRecord.id == payment_id,
        )
        if for_update:
            query = query.with_for_update()
        row = await self.session.scalar(query)
        if row is None:
            raise CommerceNotFoundError("Checkout was not found")
        return row

    async def reservations_for_checkout(
        self, *, account_id: UUID, checkout_id: UUID
    ) -> list[InventoryReservationRecord]:
        return list(
            await self.session.scalars(
                select(InventoryReservationRecord)
                .where(
                    InventoryReservationRecord.tenant_id == self.tenant_id,
                    InventoryReservationRecord.account_id == account_id,
                    InventoryReservationRecord.checkout_id == checkout_id,
                )
                .order_by(InventoryReservationRecord.created_at, InventoryReservationRecord.id)
            )
        )

    async def account_orders(
        self, *, account_id: UUID, limit: int, offset: int
    ) -> list[ShopperOrderRecord]:
        return list(
            await self.session.scalars(
                select(ShopperOrderRecord)
                .where(
                    ShopperOrderRecord.tenant_id == self.tenant_id,
                    ShopperOrderRecord.account_id == account_id,
                )
                .order_by(ShopperOrderRecord.created_at.desc(), ShopperOrderRecord.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    async def order_for_payment(
        self, *, account_id: UUID, payment_id: UUID
    ) -> ShopperOrderRecord | None:
        return cast(
            ShopperOrderRecord | None,
            await self.session.scalar(
                select(ShopperOrderRecord).where(
                    ShopperOrderRecord.tenant_id == self.tenant_id,
                    ShopperOrderRecord.account_id == account_id,
                    ShopperOrderRecord.payment_attempt_id == payment_id,
                )
            ),
        )

    async def overview_records(
        self, *, now: datetime
    ) -> tuple[
        list[tuple[Product, ProductVariant, InventorySnapshot | None]],
        list[InventoryReservationRecord],
        list[ShopperOrderRecord],
        list[PaymentAttemptRecord],
    ]:
        catalog_rows = list(
            (
                await self.session.execute(
                    select(Product, ProductVariant)
                    .join(
                        Integration,
                        (Integration.id == Product.integration_id)
                        & (Integration.tenant_id == Product.tenant_id),
                    )
                    .join(
                        ProductVariant,
                        (ProductVariant.product_id == Product.id)
                        & (ProductVariant.tenant_id == Product.tenant_id),
                    )
                    .where(
                        Product.tenant_id == self.tenant_id,
                        Product.status == "active",
                        Integration.status == "active",
                    )
                    .order_by(Product.title, ProductVariant.title)
                )
            ).all()
        )
        inventory_rows: list[tuple[Product, ProductVariant, InventorySnapshot | None]] = []
        for product, variant in catalog_rows:
            inventory_rows.append(
                (product, variant, await self.latest_inventory(variant_id=variant.id))
            )
        reservations = list(
            await self.session.scalars(
                select(InventoryReservationRecord)
                .where(InventoryReservationRecord.tenant_id == self.tenant_id)
                .order_by(
                    InventoryReservationRecord.created_at.desc(),
                    InventoryReservationRecord.id.desc(),
                )
                .limit(100)
            )
        )
        orders = list(
            await self.session.scalars(
                select(ShopperOrderRecord)
                .where(ShopperOrderRecord.tenant_id == self.tenant_id)
                .order_by(ShopperOrderRecord.created_at.desc(), ShopperOrderRecord.id.desc())
                .limit(50)
            )
        )
        payments = list(
            await self.session.scalars(
                select(PaymentAttemptRecord)
                .where(PaymentAttemptRecord.tenant_id == self.tenant_id)
                .order_by(PaymentAttemptRecord.created_at.desc(), PaymentAttemptRecord.id.desc())
                .limit(50)
            )
        )
        return inventory_rows, reservations, orders, payments
