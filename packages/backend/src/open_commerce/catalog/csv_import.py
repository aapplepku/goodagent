"""Bounded provider-neutral CSV normalization for searchable catalog fields."""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol

from pydantic import ValidationError

from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput


class CatalogProfile(Protocol):
    @property
    def dataset_kind(self) -> str: ...

    @property
    def missing_required(self) -> list[str]: ...

    @property
    def detected_mappings(self) -> dict[str, str]: ...


_LIST_SPLIT = re.compile(r"[|,]")
_CATEGORY_SPLIT = re.compile(r"\s*(?:>|/)\s*")
_ATTRIBUTE_NAME = re.compile(r"[^a-z0-9_]+")
_RESERVED = {
    "product_id",
    "title",
    "description",
    "brand",
    "category",
    "variant_id",
    "sku",
    "price",
    "currency",
    "inventory_quantity",
    "image_url",
    "updated_at",
    "tags",
    "popularity_score",
    "average_rating",
    "review_count",
    "related_product_ids",
}


def normalize_catalog_csv(*, csv_text: str, profile: CatalogProfile) -> list[CatalogProductInput]:
    """Compile a validated CSV into bounded product snapshots."""

    if profile.dataset_kind != "catalog" or profile.missing_required:
        raise CatalogCSVError("Catalog columns must be mapped before indexing")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""), strict=True)
    mappings = profile.detected_mappings
    mapped_headers = set(mappings.values())
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    try:
        for raw in reader:
            if None in raw:
                raise CatalogCSVError("CSV row has more values than the header")
            row = {key: (value or "").strip() for key, value in raw.items()}
            product_id = _required(row, mappings["product_id"], "product_id")
            grouped[_bounded(product_id, 240, "product_id")].append(row)
    except csv.Error as exc:
        raise CatalogCSVError("CSV could not be normalized") from exc
    if not grouped:
        raise CatalogCSVError("Catalog must contain at least one product row")

    products: list[CatalogProductInput] = []
    for product_id, rows in grouped.items():
        first = rows[0]
        title = _bounded(_required(first, mappings["title"], "title"), 500, "title")
        description = _optional(first, mappings.get("description"), 4000)
        brand = _optional(first, mappings.get("brand"), 160) or None
        category = _optional(first, mappings.get("category"), 500)
        tags = _split(_optional(first, mappings.get("tags"), 1000), limit=40)
        updated_at = _timestamp(_optional(first, mappings.get("updated_at"), 80))
        attributes: dict[str, str | int | bool | list[str]] = {
            key: value for key, value in _attributes(first, mapped_headers).items()
        }
        popularity = _score(_optional(first, mappings.get("popularity_score"), 40), scale=100)
        rating = _score(_optional(first, mappings.get("average_rating"), 40), scale=5)
        if popularity is not None:
            attributes["popularity_score"] = str(popularity)
        if rating is not None:
            attributes["quality_score"] = str(rating)
        review_count = _nonnegative_int(
            _optional(first, mappings.get("review_count"), 40), allow_empty=True
        )
        if review_count is not None:
            attributes["review_count"] = review_count
        related = _split(_optional(first, mappings.get("related_product_ids"), 2000), limit=40)
        if related:
            attributes["related_product_ids"] = related

        variants: list[CatalogVariantInput] = []
        seen_variants: set[str] = set()
        for ordinal, row in enumerate(rows, start=1):
            variant_id = _optional(row, mappings.get("variant_id"), 240) or (
                product_id if len(rows) == 1 else f"{product_id}-{ordinal}"
            )
            if variant_id in seen_variants:
                raise CatalogCSVError(
                    "Catalog contains duplicate variant_id "
                    f"'{variant_id}' for product '{product_id}'"
                )
            seen_variants.add(variant_id)
            inventory = _nonnegative_int(
                _optional(row, mappings.get("inventory_quantity"), 40), allow_empty=True
            )
            try:
                variant = CatalogVariantInput(
                    source_variant_id=variant_id,
                    sku=_optional(row, mappings.get("sku"), 160) or None,
                    title=title,
                    price_minor=_price_minor(
                        _optional(row, mappings.get("price"), 80), mappings.get("price")
                    ),
                    currency=(_optional(row, mappings.get("currency"), 3) or "USD").upper(),
                    available=inventory is None or inventory > 0,
                    inventory_quantity=inventory,
                    option_values=_attributes(row, mapped_headers, limit=12),
                )
            except ValidationError as exc:
                raise CatalogCSVError("Catalog contains an invalid variant value") from exc
            variants.append(variant)
        try:
            product = CatalogProductInput(
                source_product_id=product_id,
                title=title,
                description_text=description,
                brand=brand,
                category_path=[part for part in _CATEGORY_SPLIT.split(category) if part][:12],
                tags=tags,
                attributes=attributes,
                primary_image_url=_optional(first, mappings.get("image_url"), 2000) or None,
                source_updated_at=updated_at,
                variants=variants,
            )
        except ValidationError as exc:
            raise CatalogCSVError("Catalog contains an invalid product value") from exc
        products.append(product)
    return products


def _required(row: dict[str, str], header: str, field: str) -> str:
    value = row.get(header, "").strip()
    if not value:
        raise CatalogCSVError(f"Catalog contains an empty required {field}")
    return value


def _optional(row: dict[str, str], header: str | None, limit: int) -> str:
    if header is None:
        return ""
    return _bounded(row.get(header, "").strip(), limit, header)


def _bounded(value: str, limit: int, field: str) -> str:
    if len(value) > limit:
        raise CatalogCSVError(f"Catalog value for {field} exceeds {limit} characters")
    return value


def _split(value: str, *, limit: int) -> list[str]:
    return list(
        dict.fromkeys(item.strip()[:160] for item in _LIST_SPLIT.split(value) if item.strip())
    )[:limit]


def _timestamp(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogCSVError("Catalog updated_at values must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise CatalogCSVError("Catalog updated_at values must include a timezone")
    return parsed.astimezone(UTC)


def _price_minor(value: str, header: str | None) -> int:
    if not value:
        return 0
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise CatalogCSVError("Catalog prices must be numeric") from exc
    if not amount.is_finite():
        raise CatalogCSVError("Catalog prices must be finite")
    if amount < 0:
        raise CatalogCSVError("Catalog prices cannot be negative")
    if header and "minor" in header.lower():
        if amount != amount.to_integral_value():
            raise CatalogCSVError("Catalog minor-unit prices must be integers")
        return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _nonnegative_int(value: str, *, allow_empty: bool) -> int | None:
    if not value and allow_empty:
        return None
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise CatalogCSVError("Catalog inventory and counts must be integers") from exc
    if not amount.is_finite() or amount != amount.to_integral_value():
        raise CatalogCSVError("Catalog inventory and counts must be finite integers")
    parsed = int(amount)
    if parsed < 0:
        raise CatalogCSVError("Catalog inventory and counts cannot be negative")
    return parsed


def _score(value: str, *, scale: int) -> Decimal | None:
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise CatalogCSVError("Catalog ranking scores must be numeric") from exc
    if not parsed.is_finite():
        raise CatalogCSVError("Catalog ranking scores must be finite")
    if parsed > 1:
        parsed /= Decimal(scale)
    if parsed < 0 or parsed > 1:
        raise CatalogCSVError("Catalog ranking scores must resolve between 0 and 1")
    return parsed.quantize(Decimal("0.0001"))


def _attributes(
    row: dict[str, str], mapped_headers: set[str], *, limit: int = 24
) -> dict[str, str]:
    result: dict[str, str] = {}
    for header, value in row.items():
        if header in mapped_headers or not value.strip():
            continue
        key = _ATTRIBUTE_NAME.sub("_", header.strip().lower()).strip("_")[:80]
        if key and key not in _RESERVED:
            result[key] = value.strip()[:500]
        if len(result) >= limit:
            break
    return result
