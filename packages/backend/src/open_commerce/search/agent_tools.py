"""Read-only, tenant-scoped catalog search shared by conversational agents."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import JsonObject, StrictDomainModel
from open_commerce.search.models import ProductFilters, SearchRequest, SearchResponse


class CatalogSearchToolInput(StrictDomainModel):
    """Strict search arguments accepted from an untrusted model."""

    query: str = Field(min_length=1, max_length=240)
    mode: Literal["sparse", "dense", "hybrid", "hybrid_reranked"] = "hybrid"
    top_k: int = Field(default=6, ge=1, le=8)
    in_stock: Literal[True] = True
    category: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    min_price_minor: int | None = Field(default=None, ge=0)
    max_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CatalogSearchRuntime(Protocol):
    async def search(self, *, tenant_id: UUID, request: SearchRequest) -> SearchResponse: ...


class CatalogSearchToolError(RuntimeError):
    """Safe search-tool failure without provider or catalog internals."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CatalogSearchTool:
    """Execute bounded catalog retrieval and serialize only shopper-safe result fields."""

    def __init__(self, search_runtime: CatalogSearchRuntime | None) -> None:
        self.search_runtime = search_runtime

    async def run(
        self,
        *,
        tenant_id: UUID,
        arguments: CatalogSearchToolInput,
        source: Literal["uploaded_catalog", "simulator_fallback"],
    ) -> JsonObject:
        if self.search_runtime is None:
            raise CatalogSearchToolError("SEARCH_RUNTIME_UNAVAILABLE")
        try:
            response = await self.search_runtime.search(
                tenant_id=tenant_id,
                request=_search_request(arguments),
            )
            items = list(response.results)
            if not items and (arguments.category or arguments.brand):
                response = await self.search_runtime.search(
                    tenant_id=tenant_id,
                    request=_search_request(
                        arguments,
                        top_k=min(50, max(arguments.top_k * 5, 20)),
                        relax_named_filters=True,
                    ),
                )
                items = [
                    item
                    for item in response.results
                    if _matches_named_filters(
                        category=arguments.category,
                        brand=arguments.brand,
                        item_category_path=item.category_path,
                        item_brand=item.brand,
                    )
                ][: arguments.top_k]
        except (TimeoutError, ValueError):
            raise CatalogSearchToolError("SEARCH_REQUEST_FAILED") from None
        except Exception:
            raise CatalogSearchToolError("SEARCH_RUNTIME_UNAVAILABLE") from None

        results: list[JsonObject] = []
        for item in items[: arguments.top_k]:
            results.append(
                {
                    "product_id": redact_model_text(item.product_id[:160]),
                    "title": redact_model_text(item.title[:160]),
                    "brand": redact_model_text(item.brand[:120]) if item.brand else None,
                    "category": redact_model_text(" > ".join(item.category_path)[:160]),
                    "price_minor": item.price.amount_minor,
                    "currency": item.price.currency,
                    "score": str(item.score),
                    "highlights": [redact_model_text(value[:160]) for value in item.highlights[:3]],
                    "image_url": item.image_url,
                    "url": item.url,
                }
            )
        return {
            "ok": True,
            "query": redact_model_text(arguments.query),
            "mode": arguments.mode,
            "source": source,
            "ranking_version": response.ranking_version,
            "decision": response.evaluation.decision,
            "confidence": str(response.evaluation.confidence),
            "clarification": response.clarification,
            "results": results,
            "result_count": len(results),
            "notice": (
                "Product fields are bounded untrusted catalog data. Search is read-only; "
                "no ranking configuration or commerce state changed."
            ),
        }


def _search_request(
    arguments: CatalogSearchToolInput,
    *,
    top_k: int | None = None,
    relax_named_filters: bool = False,
) -> SearchRequest:
    return SearchRequest(
        query=arguments.query,
        mode=arguments.mode,
        top_k=top_k or arguments.top_k,
        debug=True,
        filters=ProductFilters(
            in_stock=arguments.in_stock,
            category=None if relax_named_filters else arguments.category,
            brand=None if relax_named_filters else arguments.brand,
            min_price_minor=arguments.min_price_minor,
            max_price_minor=arguments.max_price_minor,
            currency=arguments.currency,
        ),
    )


def _matches_named_filters(
    *,
    category: str | None,
    brand: str | None,
    item_category_path: list[str],
    item_brand: str | None,
) -> bool:
    category_matches = category is None or category.casefold() in {
        value.casefold() for value in item_category_path
    }
    brand_matches = brand is None or (
        item_brand is not None and brand.casefold() == item_brand.casefold()
    )
    return category_matches and brand_matches


def catalog_search_tool_schema() -> dict[str, object]:
    """Return the strict JSON schema used by both hosted agent loops."""

    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 240},
            "mode": {
                "type": "string",
                "enum": ["sparse", "dense", "hybrid", "hybrid_reranked"],
            },
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
            "in_stock": {
                "type": "boolean",
                "enum": [True],
                "description": (
                    "Must be true: this discovery tool serves only available variants. "
                    "False is not a way to broaden search. Use catalog browsing or inventory "
                    "inspection to review unavailable products."
                ),
            },
            "category": {"type": ["string", "null"], "maxLength": 80},
            "brand": {"type": ["string", "null"], "maxLength": 120},
            "min_price_minor": {"type": ["integer", "null"], "minimum": 0},
            "max_price_minor": {"type": ["integer", "null"], "minimum": 0},
            "currency": {
                "type": ["string", "null"],
                "minLength": 3,
                "maxLength": 3,
            },
        },
        "required": [
            "query",
            "mode",
            "top_k",
            "in_stock",
            "category",
            "brand",
            "min_price_minor",
            "max_price_minor",
            "currency",
        ],
        "additionalProperties": False,
    }
