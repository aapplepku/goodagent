from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from open_commerce.core.money import Money
from open_commerce.search.models import (
    ProductSearchDocument,
    RankedCandidate,
    ScoreComponents,
)

BASE_TIME = datetime(2026, 9, 4, tzinfo=UTC)
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = UUID("00000000-0000-0000-0000-000000000002")


def make_document(
    product_id: str,
    *,
    tenant_id: UUID = TENANT_ID,
    title: str = "Trail Jacket",
    brand: str | None = "Northline",
    category: str = "outdoor",
    price_minor: int = 10_000,
    in_stock: bool = True,
    attributes: dict[str, str | int | bool | list[str]] | None = None,
    tags: list[str] | None = None,
    search_text: str | None = None,
    popularity_score: Decimal = Decimal("0.50"),
    quality_score: Decimal = Decimal("0.50"),
    inventory_bucket: Literal["out", "low", "normal", "excess"] = "normal",
    image_url: str | None = None,
) -> ProductSearchDocument:
    resolved_attributes = attributes or {
        "material": "nylon",
        "use_case": "travel",
        "color_family": "green",
    }
    resolved_tags = tags or [category, "travel"]
    resolved_text = search_text or (
        f"{title}\nBrand: {brand or ''}\nIdentifiers: TEST-{product_id}\n"
        f"Category: {category}\nDescription: {title} for travel shoppers.\n"
        f"Attributes: {resolved_attributes}\nTags: {', '.join(resolved_tags)}"
    )
    return ProductSearchDocument(
        tenant_id=tenant_id,
        product_id=product_id,
        variant_ids=[f"var_{product_id}_1"],
        title=title,
        description_text=f"{title} for travel shoppers.",
        brand=brand,
        image_url=image_url,
        variant_skus=[f"TEST-{product_id}"],
        category_path=[category],
        tags=resolved_tags,
        attributes=resolved_attributes,
        min_price_minor=price_minor,
        max_price_minor=price_minor,
        currency="USD",
        in_stock=in_stock,
        available_variant_count=1 if in_stock else 0,
        inventory_bucket=inventory_bucket if in_stock else "out",
        unit_margin_rate=Decimal("0.40"),
        popularity_score=popularity_score,
        quality_score=quality_score,
        updated_at=BASE_TIME,
        source_version="test:v1",
        search_text=resolved_text,
        content_hash=f"sha256:test-{tenant_id}-{product_id}",
    )


def make_ranked_candidate(
    *,
    product_id: str = "prod_test",
    category_path: list[str] | None = None,
    constraint_matches: dict[str, bool] | None = None,
    score: Decimal = Decimal("0.5"),
) -> RankedCandidate:
    components = ScoreComponents(
        relevance=score,
        sparse=score,
        dense=score,
        rrf=Decimal("0"),
        final=score,
    )
    return RankedCandidate(
        product_id=product_id,
        title="Test Product",
        price=Money(amount_minor=10_000, currency="USD"),
        brand="Northline",
        category_path=category_path or ["outdoor"],
        highlights=[],
        score=score,
        score_components=components,
        constraint_matches=constraint_matches or {"in_stock": True},
        branch_ranks={"sparse": 0, "dense": 0},
    )
