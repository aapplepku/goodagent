"""Async Qdrant retrieval; PostgreSQL/catalog documents remain authoritative."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from open_commerce.search.embeddings import SPARSE_MODEL as SPARSE_MODEL
from open_commerce.search.embeddings import LocalHashEmbeddingProvider, sparse_vector
from open_commerce.search.index import _basic_ranked, _matches, _ranked_candidate
from open_commerce.search.models import (
    EmbeddingProvider,
    ProductFilters,
    ProductSearchDocument,
    RankedCandidate,
    RankingMode,
    SearchIntent,
    SearchRule,
)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PRODUCT_COLLECTION = "products_v2"
CANDIDATE_LIMIT = 100
PAYLOAD_INDEXES = (
    ("tenant_id", models.PayloadSchemaType.KEYWORD),
    ("instance_id", models.PayloadSchemaType.KEYWORD),
    ("source_version", models.PayloadSchemaType.KEYWORD),
    ("product_id", models.PayloadSchemaType.KEYWORD),
    ("category_path", models.PayloadSchemaType.KEYWORD),
    ("brand_normalized", models.PayloadSchemaType.KEYWORD),
    ("in_stock", models.PayloadSchemaType.BOOL),
    ("currency", models.PayloadSchemaType.KEYWORD),
    ("variants[].price_minor", models.PayloadSchemaType.INTEGER),
    ("variants[].in_stock", models.PayloadSchemaType.BOOL),
)


class QdrantProductSearchIndex:
    """Scope every operation to a tenant and one immutable catalog version.

    The two real Qdrant branches are fused by the shared deterministic RRF
    scorer (k=60). No process-local index is used when Qdrant is unavailable.
    """

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        instance_id: UUID,
        source_version: str | None = None,
        authoritative_documents: Mapping[str, ProductSearchDocument] | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        collection_name: str = PRODUCT_COLLECTION,
    ) -> None:
        self.client = client
        self.instance_id = instance_id
        self.source_version = source_version
        self.authoritative_documents = authoritative_documents
        self.embedding_provider = embedding_provider or LocalHashEmbeddingProvider()
        self.collection_name = collection_name
        if self.embedding_provider.model_id != LocalHashEmbeddingProvider.model_id:
            from hashlib import sha256

            self.collection_name += (
                "_" + sha256(self.embedding_provider.model_id.encode()).hexdigest()[:12]
            )

    async def ensure_collection(self) -> None:
        """Create a rebuildable, versioned collection; tolerate concurrent creation."""

        if await self.client.collection_exists(self.collection_name):
            return
        try:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=self.embedding_provider.dimensions,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF)
                },
            )
        except UnexpectedResponse as exc:
            if exc.status_code != 409:
                raise
        for field_name, field_schema in PAYLOAD_INDEXES:
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
            )

    def scope(self, tenant_id: UUID, filters: ProductFilters | None = None) -> models.Filter:
        return build_qdrant_filter(
            tenant_id, filters, instance_id=self.instance_id, source_version=self.source_version
        )

    async def document_count(self, *, tenant_id: UUID) -> int:
        await self.ensure_collection()
        return (
            await self.client.count(
                collection_name=self.collection_name, count_filter=self.scope(tenant_id), exact=True
            )
        ).count

    async def upsert_documents(
        self, *, tenant_id: UUID, documents: list[ProductSearchDocument]
    ) -> None:
        for document in documents:
            if (
                document.tenant_id != tenant_id
                or document.instance_id != self.instance_id
                or (self.source_version and document.source_version != self.source_version)
            ):
                raise ValueError("document scope does not match index scope")
        await self.ensure_collection()
        for offset in range(0, len(documents), 100):
            batch = documents[offset : offset + 100]
            vectors = await self.embedding_provider.embed_documents(
                [document.search_text for document in batch]
            )
            points = []
            for document, dense in zip(batch, vectors, strict=True):
                sparse = sparse_vector(document.search_text)
                points.append(
                    models.PointStruct(
                        id=document.point_id,
                        vector={
                            DENSE_VECTOR_NAME: dense,
                            SPARSE_VECTOR_NAME: models.SparseVector(
                                indices=sparse.indices, values=sparse.values
                            ),
                        },
                        payload=_payload(document),
                    )
                )
            await self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    async def delete_documents(self, *, tenant_id: UUID, product_ids: list[str]) -> None:
        if product_ids:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[self.scope(tenant_id), _any("product_id", product_ids)]
                    )
                ),
                wait=True,
            )

    async def delete_old_versions(self, *, tenant_id: UUID) -> None:
        if self.source_version is None:
            raise ValueError("source version is required for cleanup")
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        _equals("tenant_id", str(tenant_id)),
                        _equals("instance_id", str(self.instance_id)),
                    ],
                    must_not=[_equals("source_version", self.source_version)],
                )
            ),
            wait=True,
        )

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
        await self.ensure_collection()
        branches = ("sparse", "dense") if mode.startswith("hybrid") else (mode,)
        pool_size = (
            len(self.authoritative_documents)
            if self.authoritative_documents is not None
            else await self.document_count(tenant_id=tenant_id)
        )
        if pool_size > 10000:
            raise ValueError("The deterministic local index supports at most 10000 products")
        documents: dict[str, ProductSearchDocument] = {}
        ranks: dict[str, dict[str, Decimal | int | None]] = {}
        for branch in branches:
            query: list[float] | models.SparseVector
            if branch == "sparse":
                sparse = sparse_vector(intent.normalized_query)
                if not sparse.indices:
                    continue
                query = models.SparseVector(indices=sparse.indices, values=sparse.values)
            else:
                query = await self.embedding_provider.embed_query(intent.semantic_query)
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query,
                using=branch,
                query_filter=self.scope(tenant_id, filters),
                search_params=models.SearchParams(exact=True),
                with_payload=True,
                limit=max(1, pool_size),
                score_threshold=0.000001,
            )
            validated = []
            for point in response.points:
                document = self._document(tenant_id, point.payload, point.id)
                if document is not None and _matches(document, filters):
                    validated.append(
                        (document, Decimal(str(point.score)).quantize(Decimal("0.000001")))
                    )
            validated = _stable_branch_order(validated)
            for rank, (document, score) in enumerate(validated[: max(top_k, CANDIDATE_LIMIT)]):
                documents[document.product_id] = document
                values = ranks.setdefault(document.product_id, {})
                values[f"{branch}_rank"] = rank
                values[f"{branch}_score"] = score
        candidates = [
            _ranked_candidate(
                document=document,
                intent=intent,
                filters=filters,
                ranks=ranks[product_id],
                rules=rules,
                mode=mode,
                learned_semantics=self.embedding_provider.model_id
                != LocalHashEmbeddingProvider.model_id,
            )
            for product_id, document in documents.items()
        ]
        candidates = [candidate for candidate in candidates if candidate.score > 0]
        candidates.sort(key=lambda candidate: (-candidate.score, candidate.product_id))
        return candidates[:top_k]

    async def similar(
        self, *, tenant_id: UUID, anchor_product_ids: list[str], top_k: int
    ) -> list[RankedCandidate]:
        await self.ensure_collection()
        if not anchor_product_ids:
            documents = await self._scroll_documents(tenant_id)
            documents.sort(key=lambda document: (-document.popularity_score, document.product_id))
            return [
                _basic_ranked(document, document.popularity_score) for document in documents[:top_k]
            ]
        anchors = await self._scroll_documents(tenant_id, anchor_product_ids)
        if not anchors:
            return []
        vectors = await self.embedding_provider.embed_documents(
            [item.search_text for item in anchors]
        )
        vector = [sum(values) / len(vectors) for values in zip(*vectors, strict=True)]
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            using=DENSE_VECTOR_NAME,
            query_filter=models.Filter(
                must=[self.scope(tenant_id, ProductFilters())],
                must_not=[_any("product_id", anchor_product_ids)],
            ),
            search_params=models.SearchParams(exact=True),
            with_payload=True,
            limit=max(top_k, CANDIDATE_LIMIT),
            score_threshold=0.000001,
        )
        candidates = [
            _basic_ranked(document, Decimal(str(point.score)))
            for point in response.points
            if (document := self._document(tenant_id, point.payload, point.id)) is not None
            and _matches(document, ProductFilters())
            and document.product_id not in anchor_product_ids
        ]
        candidates.sort(key=lambda candidate: (-candidate.score, candidate.product_id))
        return candidates[:top_k]

    async def _scroll_documents(
        self, tenant_id: UUID, product_ids: list[str] | None = None
    ) -> list[ProductSearchDocument]:
        conditions: list[models.Condition] = [self.scope(tenant_id, ProductFilters())]
        if product_ids is not None:
            conditions.append(_any("product_id", product_ids))
        documents: list[ProductSearchDocument] = []
        offset: models.ExtendedPointId | None = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(must=conditions),
                offset=offset,
                limit=200,
                with_payload=True,
            )
            documents.extend(
                document
                for point in points
                if (document := self._document(tenant_id, point.payload, point.id)) is not None
                and _matches(document, ProductFilters())
            )
            if offset is None:
                return documents

    def _document(
        self, tenant_id: UUID, payload: dict[str, object] | None, point_id: object
    ) -> ProductSearchDocument | None:
        try:
            document = ProductSearchDocument.model_validate((payload or {}).get("document"))
        except ValidationError:
            return None
        if (
            document.tenant_id != tenant_id
            or document.instance_id != self.instance_id
            or document.point_id != str(point_id)
            or (self.source_version and document.source_version != self.source_version)
        ):
            return None
        if self.authoritative_documents is not None:
            current = self.authoritative_documents.get(document.product_id)
            if current is None or current.content_hash != document.content_hash:
                return None
            # Never use mutable index payloads as authoritative price/stock/ranking facts.
            return (
                current
                if current.tenant_id == tenant_id and current.instance_id == self.instance_id
                else None
            )
        return document


def build_qdrant_filter(
    tenant_id: UUID,
    filters: ProductFilters | None = None,
    *,
    instance_id: UUID,
    source_version: str | None = None,
) -> models.Filter:
    conditions: list[models.Condition] = [
        _equals("tenant_id", str(tenant_id)),
        _equals("instance_id", str(instance_id)),
    ]
    if source_version is not None:
        conditions.append(_equals("source_version", source_version))
    if filters is None:
        return models.Filter(must=conditions)
    conditions.append(_equals("in_stock", filters.in_stock is not False))
    if filters.category:
        conditions.append(_equals("category_path", filters.category))
    if filters.brand:
        conditions.append(_equals("brand_normalized", filters.brand.lower()))
    if filters.currency:
        conditions.append(_equals("currency", filters.currency))
    variant_conditions: list[models.Condition] = [_equals("in_stock", True)]
    if filters.min_price_minor is not None or filters.max_price_minor is not None:
        variant_conditions.append(
            models.FieldCondition(
                key="price_minor",
                range=models.Range(gte=filters.min_price_minor, lte=filters.max_price_minor),
            )
        )
    conditions.append(
        models.NestedCondition(
            nested=models.Nested(key="variants", filter=models.Filter(must=variant_conditions))
        )
    )
    for key, values in filters.attributes.items():
        conditions.append(_any(f"attributes_normalized.{key}", [value.lower() for value in values]))
    # Free-text/sub-string exclusions are enforced against the authoritative document
    # after retrieval. They are never translated into unsafe client-controlled field paths.
    return models.Filter(must=conditions)


def _stable_branch_order(
    points: list[tuple[ProductSearchDocument, Decimal]],
) -> list[tuple[ProductSearchDocument, Decimal]]:
    """Resolve float-reduction near ties before RRF ranks and pool truncation."""

    ordered = sorted(points, key=lambda item: (-item[1], item[0].product_id))
    stable: list[tuple[ProductSearchDocument, Decimal]] = []
    offset = 0
    while offset < len(ordered):
        end = offset + 1
        # Anchor each group at its highest score: pairwise chaining could merge
        # a long sequence whose endpoints are materially different.
        while end < len(ordered) and ordered[offset][1] - ordered[end][1] <= Decimal("0.00001"):
            end += 1
        stable.extend(sorted(ordered[offset:end], key=lambda item: item[0].product_id))
        offset = end
    return stable


def _equals(key: str, value: str | bool) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _any(key: str, values: list[str]) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchAny(any=values))


def _payload(document: ProductSearchDocument) -> dict[str, object]:
    variants: list[object] = [variant.model_dump(mode="json") for variant in document.variants]
    if not variants:
        variants = [{"price_minor": document.min_price_minor, "in_stock": document.in_stock}]
    return {
        "tenant_id": str(document.tenant_id),
        "instance_id": str(document.instance_id),
        "source_version": document.source_version,
        "product_id": document.product_id,
        "category_path": document.category_path,
        "brand_normalized": (document.brand or "").lower(),
        "in_stock": document.in_stock,
        "currency": document.currency,
        "variants": variants,
        "attributes_normalized": {
            key: [str(item).lower() for item in value]
            if isinstance(value, list)
            else [str(value).lower()]
            for key, value in document.attributes.items()
        },
        "document": document.model_dump(mode="json"),
    }
