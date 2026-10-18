"""Deterministic product-query parsing."""

from __future__ import annotations

import re
from decimal import Decimal

from open_commerce.search.embeddings import tokenize
from open_commerce.search.errors import SearchConstraintsError
from open_commerce.search.models import PriceRange, ProductFilters, SearchIntent

CATEGORIES = {"apparel", "footwear", "outdoor", "electronics", "home"}
COLOR_WORDS = {"black", "green", "blue", "white", "gray"}
MATERIAL_WORDS = {"cotton", "nylon", "aluminum", "ceramic", "mesh"}
PRICE_RE = re.compile(r"(?:under|below|less than|<=?)\s*\$?(\d{1,5}(?:\.\d{1,2})?)", re.I)
NEGATION_RE = re.compile(r"\b(?:no|not|without)\s+([a-z0-9 -]{2,40})", re.I)
QUOTED_RE = re.compile(r'"([^"]+)"')


def parse_search_intent(query: str, request_filters: ProductFilters | None = None) -> SearchIntent:
    """Parse shopper text into safe structured intent."""

    normalized = _normalize_query(query)
    terms = tokenize(normalized)
    category_hints = sorted({term for term in terms if term in CATEGORIES})
    required_filters = ProductFilters(
        category=category_hints[0] if len(category_hints) == 1 else None,
    )
    price_range = _price_range(normalized)
    if price_range is not None:
        required_filters.max_price_minor = price_range.max_price_minor
        required_filters.currency = price_range.currency
    if "in stock" in normalized or "available" in terms:
        required_filters.in_stock = True

    preferred_attributes: dict[str, list[str]] = {}
    colors = sorted({term for term in terms if term in COLOR_WORDS})
    materials = sorted({term for term in terms if term in MATERIAL_WORDS})
    if colors:
        preferred_attributes["color_family"] = colors
    if materials:
        preferred_attributes["material"] = materials

    excluded = _excluded_terms(normalized)
    excluded_attributes = {"text": excluded} if excluded else {}
    required_filters.excluded_attributes = excluded_attributes
    try:
        merged_filters = required_filters.merged(request_filters)
    except ValueError as exc:
        raise SearchConstraintsError("Shopper constraints conflict; none were relaxed.") from exc
    ambiguity = ["multiple_categories"] if len(category_hints) > 1 else []
    quoted = [item.lower() for item in QUOTED_RE.findall(query)]
    lexical_terms = sorted(set(terms + quoted))
    semantic_query = " ".join(term for term in terms if term not in {"under", "below"})
    return SearchIntent(
        normalized_query=normalized,
        lexical_terms=lexical_terms,
        semantic_query=semantic_query or normalized,
        category_hints=category_hints,
        required_filters=merged_filters,
        preferred_attributes=preferred_attributes,
        excluded_attributes=excluded_attributes,
        budget=price_range,
        ambiguity=ambiguity,
        confidence=Decimal("0.82") if not ambiguity else Decimal("0.62"),
    )


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def _price_range(query: str) -> PriceRange | None:
    match = PRICE_RE.search(query)
    if match is None:
        return None
    minor = int(Decimal(match.group(1)) * 100)
    return PriceRange(max_price_minor=minor, currency="USD")


def _excluded_terms(query: str) -> list[str]:
    excluded: list[str] = []
    for match in NEGATION_RE.finditer(query):
        phrase = match.group(1).strip()
        if not phrase:
            continue
        excluded.extend(tokenize(phrase))
    return sorted(set(excluded))
