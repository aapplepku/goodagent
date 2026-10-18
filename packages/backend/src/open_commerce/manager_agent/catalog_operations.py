"""Read normalized catalog facts once; derive bounded quality and stock reports."""

from collections import Counter, defaultdict
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, text

from open_commerce.catalog.persistence import active_catalog_integration
from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.operations_models import (
    CatalogAudit,
    CatalogAuditInput,
    CatalogFacts,
    CatalogProductFact,
    CatalogVariantFact,
    OperationsAction,
    ProductIssue,
    StockIssue,
    StockReview,
    StockReviewInput,
)
from open_commerce.persistence.models.catalog import InventorySnapshot, Product, ProductVariant
from open_commerce.persistence.models.commerce import InventoryReservationRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase

PRODUCT_LIMIT = 10000
VARIANT_LIMIT = 50000


async def catalog_facts(db: RuntimeDatabase, tenant: UUID) -> CatalogFacts:
    now = utc_now()
    result = CatalogFacts(checked_at=now)
    async with db.transaction(tenant) as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        active = await active_catalog_integration(session, tenant_id=tenant)
        if active is None:
            return result
        result.catalog_id = active.id
        result.source_version = str(active.non_secret_config.get("source_version") or "")
        scope = (
            Product.tenant_id == tenant,
            Product.integration_id == active.id,
            Product.status == "active",
        )
        result.product_count = int(
            await session.scalar(select(func.count()).select_from(Product).where(*scope)) or 0
        )
        products = await session.execute(
            select(
                Product.id,
                Product.source_product_id,
                Product.title,
                func.length(func.trim(Product.description_text)) == 0,
                func.length(func.trim(func.coalesce(Product.primary_image_url, ""))) == 0,
                Product.attributes["image_failed"].as_boolean().is_(True),
                func.coalesce(func.cardinality(Product.category_path), 0) == 0,
            )
            .where(*scope)
            .order_by(Product.source_product_id, Product.id)
            .limit(PRODUCT_LIMIT)
        )
        result.products = [
            CatalogProductFact(
                id=row[0],
                product_id=redact_model_text(row[1])[:240],
                title=redact_model_text(row[2])[:160],
                missing_description=row[3],
                missing_image=row[4],
                image_failed=row[5],
                missing_category=row[6],
            )
            for row in products
        ]
        join = (ProductVariant.product_id == Product.id) & (ProductVariant.tenant_id == tenant)
        result.variant_count = int(
            await session.scalar(
                select(func.count()).select_from(Product).join(ProductVariant, join).where(*scope)
            )
            or 0
        )
        # Latest observation and active holds are selected independently to avoid fan-out counts.
        stock_scope = (
            InventorySnapshot.tenant_id == tenant,
            InventorySnapshot.integration_id == active.id,
            InventorySnapshot.variant_id == ProductVariant.id,
            InventorySnapshot.observed_at <= now,
        )
        quantity = (
            select(InventorySnapshot.available_quantity)
            .where(*stock_scope)
            .order_by(InventorySnapshot.observed_at.desc(), InventorySnapshot.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        observed_at = (
            select(InventorySnapshot.observed_at)
            .where(*stock_scope)
            .order_by(InventorySnapshot.observed_at.desc(), InventorySnapshot.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        reserved = (
            select(func.coalesce(func.sum(InventoryReservationRecord.quantity), 0))
            .where(
                InventoryReservationRecord.tenant_id == tenant,
                InventoryReservationRecord.catalog_variant_id == ProductVariant.id,
                InventoryReservationRecord.status == "active",
                InventoryReservationRecord.expires_at > now,
            )
            .scalar_subquery()
        )
        variants = await session.execute(
            select(
                ProductVariant.product_id,
                ProductVariant.source_variant_id,
                ProductVariant.sku,
                ProductVariant.price_minor,
                ProductVariant.cost_minor,
                ProductVariant.compare_at_price_minor,
                ProductVariant.available,
                quantity,
                observed_at,
                reserved,
            )
            .join(Product, join)
            .where(*scope, ProductVariant.tenant_id == tenant)
            .order_by(
                Product.source_product_id, ProductVariant.source_variant_id, ProductVariant.id
            )
            .limit(VARIANT_LIMIT)
        )
        result.variants = [
            CatalogVariantFact(
                product_id=row[0],
                variant_id=redact_model_text(row[1])[:240],
                sku=row[2],
                price_minor=row[3],
                cost_minor=row[4],
                compare_at_price_minor=row[5],
                available=row[6],
                observed_quantity=row[7],
                observed_at=row[8],
                reserved_quantity=row[9],
            )
            for row in variants
        ]
        result.coverage_complete = (
            result.product_count <= PRODUCT_LIMIT and result.variant_count <= VARIANT_LIMIT
        )
    return result


def audit_catalog(facts: CatalogFacts, args: CatalogAuditInput) -> CatalogAudit:
    counts: Counter[str] = Counter()
    examples: list[ProductIssue] = []
    products = {product.id: product for product in facts.products}
    variants_by_product: dict[UUID, int] = defaultdict(int)
    skus = Counter(
        variant.sku.strip().casefold()
        for variant in facts.variants
        if variant.sku and variant.sku.strip()
    )
    for variant in facts.variants:
        variants_by_product[variant.product_id] += 1
        issues = []
        if not variant.sku or not variant.sku.strip():
            issues.append("missing_sku")
        elif skus[variant.sku.strip().casefold()] > 1:
            issues.append("duplicate_sku")
        if variant.price_minor <= 0:
            issues.append("nonpositive_price_review")
        if variant.cost_minor is not None and variant.price_minor < variant.cost_minor:
            issues.append("price_below_recorded_cost")
        if (
            variant.compare_at_price_minor is not None
            and variant.compare_at_price_minor <= variant.price_minor
        ):
            issues.append("compare_at_not_above_price")
        counts.update(issues)
        product = products.get(variant.product_id)
        if issues and product:
            examples.append(
                ProductIssue(
                    product_id=product.product_id,
                    title=product.title,
                    variant_id=variant.variant_id,
                    issues=issues,
                )
            )
    for product in facts.products:
        issues = [
            key
            for key in ("missing_description", "missing_image", "image_failed", "missing_category")
            if getattr(product, key)
        ]
        if facts.coverage_complete and not variants_by_product[product.id]:
            issues.append("no_variants")
        counts.update(issues)
        if issues:
            examples.append(
                ProductIssue(product_id=product.product_id, title=product.title, issues=issues)
            )
    actions = []
    if facts.catalog_id is None:
        actions.append(
            OperationsAction(
                priority="high",
                topic="catalog",
                evidence="No indexed catalog is available.",
                next_step=(
                    "Upload and confirm products in Store setup, then wait for "
                    "indexing verification."
                ),
                execution="owner_control",
            )
        )
    elif counts:
        actions.append(
            OperationsAction(
                priority="medium",
                topic="catalog_quality",
                evidence=(
                    f"{sum(counts.values())} quality flags across checked product and "
                    f"variant records."
                ),
                next_step=(
                    "Review the affected IDs, correct the source CSV, then preview and "
                    "approve its replacement. Zero prices may be intentional."
                ),
                execution="owner_control",
            )
        )
    return CatalogAudit(
        catalog_id=facts.catalog_id,
        source_version=facts.source_version,
        checked_at=facts.checked_at,
        product_count=facts.product_count,
        variant_count=facts.variant_count,
        products_checked=len(facts.products),
        variants_checked=len(facts.variants),
        coverage_complete=facts.coverage_complete,
        issue_counts=dict(counts),
        examples=examples[: args.limit],
        examples_truncated=len(examples) > args.limit,
        next_actions=actions,
    )


def review_stock(facts: CatalogFacts, args: StockReviewInput) -> StockReview:
    counts: Counter[str] = Counter()
    examples: list[StockIssue] = []
    affected = 0
    products = {product.id: product for product in facts.products}
    for variant in facts.variants:
        quantity = variant.observed_quantity
        sellable = max(0, quantity - variant.reserved_quantity) if quantity is not None else None
        stale = (
            variant.observed_at is not None
            and variant.observed_at < facts.checked_at - timedelta(hours=args.stale_after_hours)
        )
        state = (
            "unavailable"
            if not variant.available
            else "unknown"
            if sellable is None
            else "out"
            if sellable == 0
            else "low"
            if sellable <= args.low_stock_threshold
            else "healthy"
        )
        counts[state] += 1
        if stale:
            counts["stale"] += 1
        if state in {"low", "out"} and not stale and variant.observed_at is not None:
            counts["fresh_low_or_out"] += 1
        product = products.get(variant.product_id)
        if state != "healthy" or stale:
            affected += 1
            if product:
                examples.append(
                    StockIssue(
                        product_id=product.product_id,
                        title=product.title,
                        variant_id=variant.variant_id,
                        state=state,
                        observed_quantity=quantity,
                        reserved_quantity=variant.reserved_quantity,
                        sellable_quantity=sellable,
                        observed_at=variant.observed_at,
                        stale=stale,
                    )
                )
    actions = []
    if counts["fresh_low_or_out"]:
        actions.append(
            OperationsAction(
                priority="high",
                topic="stock",
                evidence=(
                    f"{counts['fresh_low_or_out']} variants have recent "
                    f"low/out-of-stock observations after local holds."
                ),
                next_step=(
                    "Verify these quantities in your inventory source before planning "
                    "replenishment or promoting them. No stock write is available."
                ),
                execution="source_system",
            )
        )
    if counts["unknown"] or counts["stale"]:
        actions.append(
            OperationsAction(
                priority="medium",
                topic="stock_freshness",
                evidence=(
                    f"{counts['unknown']} unknown and {counts['stale']} stale variant "
                    f"stock observations."
                ),
                next_step=(
                    "Obtain a current inventory export and review a replacement "
                    "catalog; do not treat unknown stock as available."
                ),
                execution="source_system",
            )
        )
    examples.sort(
        key=lambda item: (
            {"out": 0, "unavailable": 1, "low": 2, "unknown": 3, "healthy": 4}[item.state],
            item.product_id,
            item.variant_id,
        )
    )
    return StockReview(
        catalog_id=facts.catalog_id,
        checked_at=facts.checked_at,
        variant_count=facts.variant_count,
        variants_checked=len(facts.variants),
        coverage_complete=facts.coverage_complete,
        low_stock_threshold=args.low_stock_threshold,
        stale_after_hours=args.stale_after_hours,
        counts=dict(counts),
        examples=examples[: args.limit],
        examples_truncated=affected > min(len(examples), args.limit),
        next_actions=actions,
    )
