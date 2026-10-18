"""Catalog normalization for search indexing."""

from __future__ import annotations

import html
import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from open_commerce.core.types import canonical_hash
from open_commerce.search.models import ProductSearchDocument, SearchVariant
from open_commerce.simulator.models import ProductState

HTML_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
TEMPLATE_VERSION = "product-search-template-v4-images"


def clean_text(value: str) -> str:
    """Strip HTML and normalize whitespace."""

    without_tags = HTML_RE.sub(" ", html.unescape(value))
    return WHITESPACE_RE.sub(" ", without_tags).strip()


def product_document_from_simulator(
    *,
    tenant_id: UUID,
    product: ProductState,
    updated_at: datetime,
    source_version: str,
    instance_id: UUID | None = None,
) -> ProductSearchDocument:
    """Create a safe product search document from simulator product state."""

    available_variants = [
        variant for variant in product.variants if variant.available and variant.inventory > 0
    ]
    prices = [variant.price_minor for variant in product.variants]
    costs = [variant.cost_minor for variant in product.variants if variant.cost_minor > 0]
    min_price = min(prices)
    max_price = max(prices)
    average_cost = sum(costs) // len(costs) if costs else None
    unit_margin_rate = (
        (Decimal(min_price - average_cost) / Decimal(min_price)).quantize(Decimal("0.0001"))
        if average_cost is not None and min_price > 0
        else None
    )
    inventory_units = product.total_inventory
    inventory_bucket = _inventory_bucket(product)
    search_text = render_search_text(
        title=product.title,
        brand=product.brand,
        variant_skus=[variant.sku for variant in product.variants],
        category_path=[product.category],
        description=product.description_text,
        attributes=product.attributes,
        tags=product.tags,
    )
    content_hash = canonical_hash(
        {
            "template": TEMPLATE_VERSION,
            "tenant_id": tenant_id,
            "instance_id": instance_id,
            "product_id": product.id,
            "search_text": search_text,
            "min_price_minor": min_price,
            "max_price_minor": max_price,
            "inventory_units": inventory_units,
            "variants": [variant.model_dump(mode="json") for variant in product.variants],
            "popularity": product.popularity_score,
            "quality": product.quality_score,
            "inventory_bucket": inventory_bucket,
            "source_version": source_version,
        }
    )
    return ProductSearchDocument(
        tenant_id=tenant_id,
        instance_id=instance_id,
        variants=[
            SearchVariant(
                id=variant.id,
                price_minor=variant.price_minor,
                in_stock=variant.available and variant.inventory > 0,
            )
            for variant in product.variants
        ],
        product_id=product.id,
        variant_ids=[variant.id for variant in product.variants],
        title=product.title,
        description_text=clean_text(product.description_text),
        brand=product.brand,
        variant_skus=[variant.sku for variant in product.variants],
        category_path=[product.category],
        tags=product.tags,
        attributes=product.attributes,
        min_price_minor=min_price,
        max_price_minor=max_price,
        currency=product.variants[0].currency,
        in_stock=bool(available_variants),
        available_variant_count=len(available_variants),
        inventory_bucket=inventory_bucket,
        unit_margin_rate=unit_margin_rate,
        popularity_score=product.popularity_score,
        quality_score=product.quality_score,
        updated_at=updated_at,
        source_version=source_version,
        search_text=search_text,
        content_hash=content_hash,
    )


def render_search_text(
    *,
    title: str,
    brand: str | None,
    variant_skus: list[str],
    category_path: list[str],
    description: str,
    attributes: dict[str, str],
    tags: list[str],
) -> str:
    """Render the documented deterministic search text template."""

    attributes_text = ", ".join(f"{key}: {value}" for key, value in sorted(attributes.items()))
    return "\n".join(
        [
            clean_text(title),
            f"Brand: {clean_text(brand or '')}",
            f"Identifiers: {', '.join(sorted(variant_skus))}",
            f"Category: {' > '.join(category_path)}",
            f"Description: {clean_text(description)}",
            f"Attributes: {attributes_text}",
            f"Tags: {', '.join(sorted(tags))}",
        ]
    )


def _inventory_bucket(product: ProductState) -> str:
    if not any(v.available and v.inventory > 0 for v in product.variants):
        return "out"
    if product.low_stock:
        return "low"
    if product.excess_inventory:
        return "excess"
    return "normal"
