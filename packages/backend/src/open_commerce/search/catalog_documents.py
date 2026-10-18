"""Build search documents from authoritative normalized catalog records."""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from open_commerce.core.types import canonical_hash
from open_commerce.persistence.models.catalog import Product, ProductVariant
from open_commerce.search.models import ProductSearchDocument, SearchVariant
from open_commerce.search.normalization import TEMPLATE_VERSION, clean_text, render_search_text


def document_from_catalog_records(
    *,
    tenant_id: UUID,
    integration_id: UUID,
    source_version: str,
    product: Product,
    variants: list[ProductVariant],
    inventory: dict[UUID, int],
) -> ProductSearchDocument:
    """Compile one database product into a scoped, reconstructable search document."""

    if product.tenant_id != tenant_id or product.integration_id != integration_id:
        raise ValueError("catalog product scope mismatch")
    if not variants:
        raise ValueError("catalog product has no variants")
    if any(item.tenant_id != tenant_id or item.product_id != product.id for item in variants):
        raise ValueError("catalog variant scope mismatch")
    prices = [item.price_minor for item in variants]
    available = [item for item in variants if item.available and inventory.get(item.id, 1) > 0]
    inventory_units = sum(inventory.get(item.id, 0) for item in variants)
    attributes = {
        key: value
        for key, value in product.attributes.items()
        if key not in {"popularity_score", "quality_score"}
        and isinstance(value, str | int | bool | list)
    }
    popularity = _score(product.attributes.get("popularity_score"), Decimal("0.5"))
    quality = _score(product.attributes.get("quality_score"), None)
    search_text = render_search_text(
        title=product.title,
        brand=product.brand,
        variant_skus=[item.sku for item in variants if item.sku],
        category_path=product.category_path,
        description=product.description_text,
        attributes={key: str(value) for key, value in attributes.items()},
        tags=product.tags,
    )
    document_payload = {
        "template": TEMPLATE_VERSION,
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "source_version": source_version,
        "product_hash": product.content_hash,
        "variant_hashes": [item.content_hash for item in variants],
        "search_text": search_text,
    }
    return ProductSearchDocument(
        tenant_id=tenant_id,
        instance_id=integration_id,
        variants=[
            SearchVariant(
                id=item.source_variant_id,
                price_minor=item.price_minor,
                in_stock=item in available,
            )
            for item in variants
        ],
        product_id=product.source_product_id,
        variant_ids=[item.source_variant_id for item in variants],
        title=product.title,
        description_text=clean_text(product.description_text),
        brand=product.brand,
        image_url=product.primary_image_url,
        variant_skus=[item.sku for item in variants if item.sku],
        category_path=product.category_path,
        tags=product.tags,
        attributes=attributes,
        min_price_minor=min(prices),
        max_price_minor=max(prices),
        currency=variants[0].currency,
        in_stock=bool(available),
        available_variant_count=len(available),
        inventory_bucket=(
            "out"
            if not available
            else "low"
            if inventory and inventory_units <= 5
            else "excess"
            if inventory_units >= 100
            else "normal"
        ),
        unit_margin_rate=None,
        popularity_score=popularity,
        quality_score=quality,
        updated_at=product.source_updated_at,
        source_version=source_version,
        search_text=search_text,
        content_hash=canonical_hash(document_payload),
    )


def _score(value: object, default: Decimal | None) -> Decimal | None:
    if value is None:
        return default
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return default
    return parsed if Decimal("0") <= parsed <= Decimal("1") else default
