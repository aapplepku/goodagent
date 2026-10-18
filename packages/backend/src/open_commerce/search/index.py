"""In-memory product search index."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from open_commerce.core.money import Money
from open_commerce.search.embeddings import (
    LocalHashEmbeddingProvider,
    cosine,
    semantic_tokens,
    sparse_dot,
    sparse_vector,
    tokenize,
)
from open_commerce.search.models import (
    EmbeddingProvider,
    IndexedDocument,
    ProductFilters,
    ProductSearchDocument,
    RankedCandidate,
    RankingMode,
    ScoreComponents,
    SearchIntent,
    SearchRule,
    SparseVectorData,
)

RANKING_VERSION = "rank-v4"
RRF_K = Decimal("60")
MINIMUM_RELEVANCE_FOR_BOOST = Decimal("0.20")
MAX_GOAL_BOOST = Decimal("0.15")


class InMemoryProductSearchIndex:
    """Tenant-partitioned deterministic search index for tests and local fallback."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.embedding_provider = embedding_provider or LocalHashEmbeddingProvider()
        self._documents: dict[UUID, dict[str, IndexedDocument]] = defaultdict(dict)

    async def upsert_documents(
        self,
        *,
        tenant_id: UUID,
        documents: list[ProductSearchDocument],
    ) -> None:
        """Upsert product documents for a tenant."""

        texts = [document.search_text for document in documents]
        vectors = await self.embedding_provider.embed_documents(texts)
        tenant_docs = self._documents[tenant_id]
        for document, dense_vector in zip(documents, vectors, strict=True):
            if document.tenant_id != tenant_id:
                raise ValueError("document tenant does not match index tenant")
            tenant_docs[document.product_id] = IndexedDocument(
                document=document,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector(document.search_text),
            )

    async def delete_documents(self, *, tenant_id: UUID, product_ids: list[str]) -> None:
        """Delete product documents for a tenant."""

        for product_id in product_ids:
            self._documents[tenant_id].pop(product_id, None)

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
        """Run sparse, dense, or hybrid search."""

        query_dense = await self.embedding_provider.embed_query(intent.semantic_query)
        query_sparse = sparse_vector(intent.normalized_query)
        records = [
            record
            for record in self._documents[tenant_id].values()
            if _matches(record.document, filters)
        ]
        sparse_ranked = sorted(
            records,
            key=lambda record: (
                -sparse_dot(query_sparse, record.sparse_vector),
                record.document.product_id,
            ),
        )
        dense_ranked = sorted(
            records,
            key=lambda record: (
                -cosine(query_dense, record.dense_vector),
                record.document.product_id,
            ),
        )
        ranks = _branch_ranks(
            sparse_ranked=sparse_ranked,
            dense_ranked=dense_ranked,
            query_sparse=query_sparse,
            query_dense=query_dense,
        )
        if mode == "sparse":
            ordered_ids = [record.document.product_id for record in sparse_ranked]
        elif mode == "dense":
            ordered_ids = [record.document.product_id for record in dense_ranked]
        else:
            ordered_ids = _rrf_order(ranks)

        candidates = [
            _ranked_candidate(
                document=self._documents[tenant_id][product_id].document,
                intent=intent,
                filters=filters,
                ranks=ranks[product_id],
                rules=rules,
                mode=mode,
                learned_semantics=self.embedding_provider.model_id
                != LocalHashEmbeddingProvider.model_id,
            )
            for product_id in ordered_ids
        ]
        candidates = [candidate for candidate in candidates if candidate.score > Decimal("0")]
        candidates.sort(key=lambda candidate: (-candidate.score, candidate.product_id))
        return candidates[:top_k]

    async def similar(
        self,
        *,
        tenant_id: UUID,
        anchor_product_ids: list[str],
        top_k: int,
    ) -> list[RankedCandidate]:
        """Return dense-similar products with complementary/popular fallback."""

        tenant_docs = self._documents[tenant_id]
        anchors = [
            tenant_docs[product_id]
            for product_id in anchor_product_ids
            if product_id in tenant_docs
        ]
        if not anchors:
            return _popular_fallback(list(tenant_docs.values()), top_k)
        anchor_vector = [
            sum(record.dense_vector[index] for record in anchors) / len(anchors)
            for index in range(self.embedding_provider.dimensions)
        ]
        ranked = sorted(
            [
                record
                for record in tenant_docs.values()
                if record.document.product_id not in anchor_product_ids and record.document.in_stock
            ],
            key=lambda record: (
                -cosine(anchor_vector, record.dense_vector),
                record.document.product_id,
            ),
        )
        intent = SearchIntent(
            normalized_query="similar products",
            lexical_terms=[],
            semantic_query="similar products",
            category_hints=[],
            required_filters=ProductFilters(in_stock=True),
            confidence=Decimal("1"),
        )
        return [
            _basic_ranked(
                record.document,
                Decimal(str(round(cosine(anchor_vector, record.dense_vector), 6))),
            )
            for record in ranked[:top_k]
        ] or _popular_fallback(list(tenant_docs.values()), top_k, intent=intent)

    def document_count(self, tenant_id: UUID) -> int:
        """Return indexed product count for tests and CLI."""

        return len(self._documents[tenant_id])


def _branch_ranks(
    *,
    sparse_ranked: list[IndexedDocument],
    dense_ranked: list[IndexedDocument],
    query_sparse: SparseVectorData,
    query_dense: list[float],
) -> dict[str, dict[str, Decimal | int | None]]:
    ranks: dict[str, dict[str, Decimal | int | None]] = {}
    for index, record in enumerate(sparse_ranked):
        score = Decimal(str(round(sparse_dot(query_sparse, record.sparse_vector), 6)))
        ranks.setdefault(record.document.product_id, {})["sparse_rank"] = index
        ranks[record.document.product_id]["sparse_score"] = score
    for index, record in enumerate(dense_ranked):
        score = Decimal(str(round(cosine(query_dense, record.dense_vector), 6)))
        ranks.setdefault(record.document.product_id, {})["dense_rank"] = index
        ranks[record.document.product_id]["dense_score"] = score
    return ranks


def _rrf_order(ranks: dict[str, dict[str, Decimal | int | None]]) -> list[str]:
    scored: list[tuple[Decimal, str]] = []
    for product_id, branch in ranks.items():
        score = Decimal("0")
        sparse_rank = branch.get("sparse_rank")
        dense_rank = branch.get("dense_rank")
        if isinstance(sparse_rank, int):
            score += Decimal("1") / (RRF_K + Decimal(sparse_rank))
        if isinstance(dense_rank, int):
            score += Decimal("1") / (RRF_K + Decimal(dense_rank))
        scored.append((score, product_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [product_id for _, product_id in scored]


def _ranked_candidate(
    *,
    document: ProductSearchDocument,
    intent: SearchIntent,
    filters: ProductFilters,
    ranks: dict[str, Decimal | int | None],
    rules: list[SearchRule],
    mode: RankingMode,
    learned_semantics: bool = False,
) -> RankedCandidate:
    sparse_score = _as_decimal(ranks.get("sparse_score"))
    dense_score = _as_decimal(ranks.get("dense_score"))
    sparse_relevance = _bounded(
        sparse_score / (sparse_score + Decimal("3")) if sparse_score > 0 else Decimal("0")
    )
    dense_relevance = _bounded(dense_score)
    relevance = max(sparse_relevance, dense_relevance, _lexical_coverage(document, intent))
    if not _has_relevance_evidence(document, intent) and not (
        learned_semantics and dense_relevance >= Decimal("0.45")
    ):
        relevance = Decimal("0")
    if mode == "sparse":
        base_score = sparse_relevance
        rrf = Decimal("0")
    elif mode == "dense":
        base_score = dense_relevance
        rrf = Decimal("0")
    else:
        rrf = _candidate_rrf(ranks)
        base_score = _bounded(rrf * Decimal("20"))

    exact_identifier = bool(
        re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+){2,}", intent.normalized_query)
        and re.search(r"\d", intent.normalized_query)
        and re.search(
            rf"(?<![a-z0-9-]){re.escape(intent.normalized_query)}(?![a-z0-9-])",
            document.search_text.lower(),
        )
    )
    if exact_identifier and mode != "dense":
        base_score = Decimal("1")
        relevance = Decimal("1")
    goal_boost = (
        _search_rule_boost(document, intent, rules, relevance)
        if mode == "hybrid_boosted"
        else Decimal("0")
    )
    stock_penalty = (
        Decimal("0.04")
        if document.inventory_bucket == "low" and mode in {"hybrid_reranked", "hybrid_boosted"}
        else Decimal("0")
    )
    rerank_boost = (
        document.popularity_score * Decimal("0.04")
        + (document.quality_score or Decimal("0")) * Decimal("0.03")
        + _lexical_coverage(document, intent) * Decimal("0.10")
        if mode == "hybrid_reranked"
        else Decimal("0")
    )
    constraints = _constraint_matches(document, filters)
    eligible = all(constraints.values()) and relevance > 0
    final = (
        _bounded(base_score + goal_boost + rerank_boost - stock_penalty)
        if eligible
        else Decimal("0")
    )
    if not eligible:
        goal_boost = Decimal("0")
    components = ScoreComponents(
        relevance=_quantize(relevance),
        sparse=_quantize(sparse_relevance),
        dense=_quantize(dense_relevance),
        rrf=_quantize(rrf),
        exact_identifier=exact_identifier,
        goal_boost=_quantize(goal_boost),
        stock_penalty=_quantize(stock_penalty),
        final=_quantize(final),
    )
    return RankedCandidate(
        product_id=document.product_id,
        title=document.title,
        price=Money(
            amount_minor=(
                price
                if (price := _eligible_price(document, filters)) is not None
                else document.min_price_minor
            ),
            currency=document.currency,
        ),
        brand=document.brand,
        image_url=document.image_url,
        category_path=document.category_path,
        highlights=_highlights(document, intent),
        score=components.final,
        score_components=components,
        constraint_matches=constraints,
        branch_ranks={
            "sparse": _rank_or_none(ranks.get("sparse_rank")),
            "dense": _rank_or_none(ranks.get("dense_rank")),
        },
    )


def _candidate_rrf(ranks: dict[str, Decimal | int | None]) -> Decimal:
    score = Decimal("0")
    for key in ("sparse_rank", "dense_rank"):
        rank = ranks.get(key)
        if isinstance(rank, int):
            score += Decimal("1") / (RRF_K + Decimal(rank))
    return score


def _search_rule_boost(
    document: ProductSearchDocument,
    intent: SearchIntent,
    rules: list[SearchRule],
    relevance: Decimal,
) -> Decimal:
    if (
        relevance < MINIMUM_RELEVANCE_FOR_BOOST
        or document.inventory_bucket in {"low", "out"}
        or not _has_relevance_evidence(document, intent)
    ):
        return Decimal("0")
    boost = Decimal("0")
    for rule in rules:
        if rule.tenant_id != document.tenant_id:
            continue
        now = rule.evaluation_time or datetime.now(UTC)
        if rule.status != "active" or not rule.starts_at <= now < rule.ends_at:
            continue
        if rule.query_text.lower() not in intent.normalized_query:
            continue
        product_match = not rule.product_ids or document.product_id in rule.product_ids
        category_match = rule.category is None or rule.category in document.category_path
        if product_match and category_match:
            boost = max(boost, min(relevance * (rule.multiplier - Decimal("1")), MAX_GOAL_BOOST))
    return boost


def _lexical_coverage(document: ProductSearchDocument, intent: SearchIntent) -> Decimal:
    if not intent.lexical_terms:
        return Decimal("0")
    document_terms = set(tokenize(document.search_text))
    matches = sum(1 for term in intent.lexical_terms if term in document_terms)
    return Decimal(matches) / Decimal(len(intent.lexical_terms))


def _matches(document: ProductSearchDocument, filters: ProductFilters) -> bool:
    return all(_constraint_matches(document, filters).values())


def _eligible_price(document: ProductSearchDocument, filters: ProductFilters) -> int | None:
    prices = [variant.price_minor for variant in document.variants if variant.in_stock]
    if not document.variants and document.in_stock:
        prices = [document.min_price_minor]
    return min(
        (
            price
            for price in prices
            if (filters.min_price_minor is None or price >= filters.min_price_minor)
            and (filters.max_price_minor is None or price <= filters.max_price_minor)
        ),
        default=None,
    )


def _attribute_values(document: ProductSearchDocument, key: str) -> set[str]:
    value = document.attributes.get(key)
    return (
        {str(item).lower() for item in value}
        if isinstance(value, list)
        else ({str(value).lower()} if value is not None else set())
    )


def _has_relevance_evidence(document: ProductSearchDocument, intent: SearchIntent) -> bool:
    ignored = {"the", "for", "and", "with", "under", "below", "without", "not", "in", "stock"}
    query = {term for term in semantic_tokens(intent.semantic_query) if term not in ignored}
    return bool(query & set(semantic_tokens(document.search_text)))


def _constraint_matches(
    document: ProductSearchDocument,
    filters: ProductFilters,
) -> dict[str, bool]:
    return {
        "in_stock": document.in_stock and filters.in_stock is not False,
        "category": filters.category is None or filters.category in document.category_path,
        "brand": filters.brand is None or (document.brand or "").lower() == filters.brand.lower(),
        "currency": filters.currency is None or document.currency == filters.currency,
        "price": _eligible_price(document, filters) is not None,
        "attributes": all(
            bool(_attribute_values(document, key) & {item.lower() for item in values})
            for key, values in filters.attributes.items()
        ),
        "exclusions": all(
            not any(
                value.lower()
                in (
                    document.search_text.lower()
                    if key == "text"
                    else " ".join(sorted(_attribute_values(document, key)))
                )
                for value in values
            )
            for key, values in filters.excluded_attributes.items()
        ),
    }


def _highlights(document: ProductSearchDocument, intent: SearchIntent) -> list[str]:
    text = document.search_text.lower()
    highlights = [term for term in intent.lexical_terms if term in text]
    return highlights[:5]


def _as_decimal(value: Decimal | int | None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return Decimal("0")


def _rank_or_none(value: Decimal | int | None) -> int | None:
    return value if isinstance(value, int) else None


def _bounded(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _basic_ranked(document: ProductSearchDocument, score: Decimal) -> RankedCandidate:
    components = ScoreComponents(
        relevance=_quantize(_bounded(score)),
        sparse=Decimal("0"),
        dense=_quantize(_bounded(score)),
        rrf=Decimal("0"),
        final=_quantize(_bounded(score)),
    )
    return RankedCandidate(
        product_id=document.product_id,
        title=document.title,
        price=Money(
            amount_minor=(
                price
                if (price := _eligible_price(document, ProductFilters())) is not None
                else document.min_price_minor
            ),
            currency=document.currency,
        ),
        brand=document.brand,
        image_url=document.image_url,
        category_path=document.category_path,
        highlights=[],
        score=components.final,
        score_components=components,
        constraint_matches=_constraint_matches(document, ProductFilters()),
        branch_ranks={"sparse": None, "dense": None},
    )


def _popular_fallback(
    records: list[IndexedDocument],
    top_k: int,
    intent: SearchIntent | None = None,
) -> list[RankedCandidate]:
    _ = intent
    ranked = sorted(
        [record for record in records if record.document.in_stock],
        key=lambda record: (-record.document.popularity_score, record.document.product_id),
    )
    return [
        _basic_ranked(
            record.document, Decimal("0.35") + record.document.popularity_score * Decimal("0.20")
        )
        for record in ranked[:top_k]
    ]


def query_terms(query: str) -> set[str]:
    """Expose tokenizer for tests and benchmark utilities."""

    return set(tokenize(query))
