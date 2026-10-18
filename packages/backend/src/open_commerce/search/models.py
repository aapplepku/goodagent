"""Typed models for product search, recommendations, events, and traces."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, field_validator, model_validator

from open_commerce.core.enums import EventType
from open_commerce.core.money import Money
from open_commerce.core.types import JsonObject, StrictDomainModel, ensure_utc

RankingMode = Literal["sparse", "dense", "hybrid", "hybrid_reranked", "hybrid_boosted"]
SearchDecision = Literal["answer", "clarify", "retry", "no_result"]


class PriceRange(StrictDomainModel):
    """Integer-minor-unit price range."""

    min_price_minor: int | None = Field(default=None, ge=0)
    max_price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_bounds(self) -> PriceRange:
        if (
            self.min_price_minor is not None
            and self.max_price_minor is not None
            and self.max_price_minor < self.min_price_minor
        ):
            raise ValueError("max_price_minor must be greater than or equal to min_price_minor")
        return self


class ProductFilters(StrictDomainModel):
    """Structured product filters accepted by public APIs."""

    in_stock: bool | None = True
    category: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    min_price_minor: int | None = Field(default=None, ge=0)
    max_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    attributes: dict[
        Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")],
        Annotated[
            list[Annotated[str, Field(min_length=1, max_length=80)]],
            Field(min_length=1, max_length=20),
        ],
    ] = Field(default_factory=dict, max_length=20)
    excluded_attributes: dict[
        Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")],
        Annotated[
            list[Annotated[str, Field(min_length=1, max_length=80)]],
            Field(min_length=1, max_length=20),
        ],
    ] = Field(default_factory=dict, max_length=20)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    def merged(self, other: ProductFilters | None) -> ProductFilters:
        """Intersect hard constraints; request filters cannot relax parsed exclusions or budgets."""

        if other is None:
            return self
        for key in ("category", "brand", "currency"):
            left, right = getattr(self, key), getattr(other, key)
            if left and right and left.lower() != right.lower():
                raise ValueError(f"conflicting {key} constraints")
        attributes = dict(self.attributes)
        for key, values in other.attributes.items():
            if key in attributes:
                overlap = {item.lower() for item in attributes[key]} & {
                    item.lower() for item in values
                }
                if not overlap:
                    raise ValueError("conflicting required attributes")
                attributes[key] = sorted(overlap)
            else:
                attributes[key] = values
        excluded = {
            key: sorted(
                set(self.excluded_attributes.get(key, []))
                | set(other.excluded_attributes.get(key, []))
            )
            for key in self.excluded_attributes.keys() | other.excluded_attributes.keys()
        }
        minima = [
            value for value in (self.min_price_minor, other.min_price_minor) if value is not None
        ]
        maxima = [
            value for value in (self.max_price_minor, other.max_price_minor) if value is not None
        ]
        return ProductFilters(
            in_stock=False if self.in_stock is False or other.in_stock is False else True,
            category=other.category or self.category,
            brand=other.brand or self.brand,
            min_price_minor=max(minima) if minima else None,
            max_price_minor=min(maxima) if maxima else None,
            currency=other.currency or self.currency,
            attributes=attributes,
            excluded_attributes=excluded,
        )

    @model_validator(mode="after")
    def validate_price_range(self) -> ProductFilters:
        if (
            self.min_price_minor is not None
            and self.max_price_minor is not None
            and self.min_price_minor > self.max_price_minor
        ):
            raise ValueError("conflicting price constraints")
        return self


class SearchVariant(StrictDomainModel):
    id: str
    price_minor: int = Field(ge=0)
    in_stock: bool


class ProductSearchDocument(StrictDomainModel):
    """Tenant-owned product document for retrieval."""

    tenant_id: UUID
    instance_id: UUID | None = None
    variants: list[SearchVariant] = Field(default_factory=list)
    product_id: str
    variant_ids: list[str]
    title: str
    description_text: str
    brand: str | None
    image_url: str | None = Field(default=None, max_length=2000)
    variant_skus: list[str]
    category_path: list[str]
    tags: list[str]
    attributes: dict[str, str | int | bool | list[str]]
    min_price_minor: int = Field(ge=0)
    max_price_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    in_stock: bool
    available_variant_count: int = Field(ge=0)
    inventory_bucket: Literal["out", "low", "normal", "excess"]
    unit_margin_rate: Decimal | None = None
    popularity_score: Decimal = Field(ge=0, le=1)
    quality_score: Decimal | None = Field(default=None, ge=0, le=1)
    updated_at: datetime
    source_version: str
    search_text: str
    content_hash: str

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def point_id(self) -> str:
        """Return deterministic Qdrant/local point ID."""

        return str(
            uuid5(
                NAMESPACE_URL,
                f"open-commerce:{self.tenant_id}:{self.instance_id}:{self.product_id}",
            )
        )


class SparseVectorData(StrictDomainModel):
    """Hashed sparse vector payload."""

    indices: list[int]
    values: list[float]

    @model_validator(mode="after")
    def validate_lengths(self) -> SparseVectorData:
        if len(self.indices) != len(self.values):
            raise ValueError("sparse indices and values must have the same length")
        return self


class SearchUserContext(StrictDomainModel):
    """Pseudonymous search context."""

    recent_product_ids: list[str] = Field(default_factory=list)


class SearchRequest(StrictDomainModel):
    """Public search request body. Tenant comes from request context."""

    query: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=200)
    user_context: SearchUserContext | None = None
    filters: ProductFilters | None = None
    goal_context_id: UUID | None = None
    mode: RankingMode = "hybrid"
    top_k: int = Field(default=20, ge=1, le=50)
    debug: bool = False


class SearchIntent(StrictDomainModel):
    """Deterministic query interpretation."""

    normalized_query: str
    lexical_terms: list[str]
    semantic_query: str
    category_hints: list[str]
    required_filters: ProductFilters
    preferred_attributes: dict[str, list[str]] = Field(default_factory=dict)
    excluded_attributes: dict[str, list[str]] = Field(default_factory=dict)
    budget: PriceRange | None = None
    sort_preference: Literal["relevance", "price_asc", "price_desc"] = "relevance"
    ambiguity: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(ge=0, le=1)


class ScoreComponents(StrictDomainModel):
    """Inspectable score components."""

    relevance: Decimal
    sparse: Decimal
    dense: Decimal
    rrf: Decimal
    exact_identifier: bool = False
    goal_boost: Decimal = Decimal("0")
    engagement_boost: Decimal = Decimal("0")
    stock_penalty: Decimal = Decimal("0")
    final: Decimal


class SearchCandidate(StrictDomainModel):
    """Internal candidate with branch ranks."""

    document: ProductSearchDocument
    sparse_score: Decimal
    dense_score: Decimal
    sparse_rank: int | None = None
    dense_rank: int | None = None


class RankedCandidate(StrictDomainModel):
    """Search result card with debug-safe trace components."""

    product_id: str
    title: str
    price: Money
    brand: str | None
    category_path: list[str]
    highlights: list[str]
    score: Decimal
    image_url: str | None = None
    url: str | None = None
    score_components: ScoreComponents
    constraint_matches: dict[str, bool]
    branch_ranks: dict[str, int | None]


class SearchRetryPlan(StrictDomainModel):
    """Deterministic retry plan."""

    reason: str
    relaxed_preferences: list[str] = Field(default_factory=list)


class ResultSetEvaluation(StrictDomainModel):
    """Evaluation of one result set."""

    coverage_by_constraint: dict[str, Decimal]
    hard_constraint_violations: list[str]
    result_diversity: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)
    decision: SearchDecision
    retry_plan: SearchRetryPlan | None = None


class SearchTrace(StrictDomainModel):
    """Debug trace for search retrieval and ranking."""

    query_id: UUID
    ranking_version: str
    retrieval: JsonObject
    retries: list[JsonObject] = Field(default_factory=list)
    results: list[JsonObject] = Field(default_factory=list)


class SearchResponse(StrictDomainModel):
    """Public search response."""

    query_id: UUID
    interpretation: SearchIntent
    results: list[RankedCandidate]
    clarification: str | None = None
    relaxed_preferences: list[str] = Field(default_factory=list)
    ranking_version: str
    evaluation: ResultSetEvaluation
    trace: SearchTrace | None = None


class ParseSearchResponse(StrictDomainModel):
    """Search parser response."""

    interpretation: SearchIntent


class EvaluateSearchRequest(StrictDomainModel):
    """Request to evaluate an existing result set."""

    query: str = Field(min_length=1, max_length=500)
    filters: ProductFilters | None = None
    goal_context_id: UUID | None = None
    results: list[RankedCandidate] = Field(max_length=50)


class RecommendationRequest(StrictDomainModel):
    """Recommendation request body."""

    surface: Literal["product_detail", "cart", "home", "search"] = "product_detail"
    goal_context_id: UUID | None = None
    anchor_product_ids: list[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, max_length=20
    )
    session_id: str | None = Field(default=None, max_length=200)
    user_context: SearchUserContext | None = None
    top_k: int = Field(default=10, ge=1, le=30)
    debug: bool = False


class RecommendationResponse(StrictDomainModel):
    """Recommendation response."""

    query_id: UUID
    strategy: str
    results: list[RankedCandidate]
    trace: SearchTrace | None = None
    policy_version: int | None = Field(default=None, ge=0, exclude_if=lambda v: v is None)
    policy_active: bool | None = Field(default=None, exclude_if=lambda v: v is None)


class SearchRuleRequest(StrictDomainModel):
    """Create a bounded search boost rule."""

    query_text: str = Field(min_length=1, max_length=200)
    product_ids: list[str] = Field(default_factory=list)
    category: str | None = None
    multiplier: Decimal = Field(gt=Decimal("0"), le=Decimal("3"))
    starts_at: datetime
    ends_at: datetime
    reason: str

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_window(self) -> SearchRuleRequest:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class SearchRule(SearchRuleRequest):
    """Tenant-owned search boost rule."""

    id: UUID
    tenant_id: UUID
    status: Literal["active", "deleted"] = "active"
    evaluation_time: datetime | None = None
    reason_action_id: UUID | None = None


class SearchRuleListResponse(StrictDomainModel):
    """Search rule collection response."""

    items: list[SearchRule]
    next_cursor: str | None = None


class SearchEventInput(StrictDomainModel):
    """Public event batch item. Tenant comes from request context."""

    event_id: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    session_id: str = Field(min_length=1, max_length=200)
    anonymous_user_id: str | None = Field(default=None, max_length=200)
    type: EventType
    query_id: UUID | None = None
    product_id: str | None = None
    variant_id: str | None = None
    position: int | None = Field(default=None, ge=1)
    surface: Literal["search", "product_detail", "cart", "home"]
    ranking_version: str | None = None
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_safe_metadata(cls, value: JsonObject) -> JsonObject:
        for key, item in value.items():
            if key not in {"dwell_ms", "quantity"} or type(item) is not int:
                raise ValueError("Only numeric dwell_ms and quantity metadata are accepted")
            if item < 0 or item > 1_000_000:
                raise ValueError("Event metadata is out of range")
        return value

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class EventBatchRequest(StrictDomainModel):
    """Batch event ingestion request."""

    events: list[SearchEventInput] = Field(min_length=1, max_length=200)


class EventBatchResponse(StrictDomainModel):
    """Batch event ingestion result."""

    accepted: int
    deduplicated: int


class IndexedDocument(StrictDomainModel):
    """Search index record with vectors."""

    document: ProductSearchDocument
    dense_vector: list[float]
    sparse_vector: SparseVectorData


class EmbeddingProvider(Protocol):
    """Local or hosted embedding provider interface."""

    model_id: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a query."""
        ...


class ProductSearchIndex(Protocol):
    """Tenant-scoped product search index interface."""

    async def upsert_documents(
        self,
        *,
        tenant_id: UUID,
        documents: list[ProductSearchDocument],
    ) -> None:
        """Upsert product documents."""
        ...

    async def delete_documents(self, *, tenant_id: UUID, product_ids: list[str]) -> None:
        """Delete product documents for a tenant."""
        ...

    async def search(
        self,
        *,
        tenant_id: UUID,
        intent: SearchIntent,
        filters: ProductFilters,
        top_k: int,
        mode: RankingMode,
        rules: list[SearchRule],
    ) -> list[RankedCandidate]:
        """Search product documents."""
        ...

    async def similar(
        self,
        *,
        tenant_id: UUID,
        anchor_product_ids: list[str],
        top_k: int,
    ) -> list[RankedCandidate]:
        """Return similar products."""
        ...


class Reranker(Protocol):
    """Optional reranker interface."""

    async def rerank(
        self,
        query: SearchIntent,
        candidates: list[RankedCandidate],
    ) -> list[RankedCandidate]:
        """Rerank candidates."""
        ...
