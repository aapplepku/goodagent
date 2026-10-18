"""PostgreSQL catalog/rules/events with reconstructable live Qdrant retrieval."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import (
    active_catalog_integration,
    catalog_records,
)
from open_commerce.persistence.models.actions import CompiledActionRecord
from open_commerce.persistence.models.events import BehavioralEventRecord
from open_commerce.persistence.models.goals import Goal
from open_commerce.persistence.models.search import SearchIndexVersion
from open_commerce.persistence.models.simulator import SimulatorInstanceRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.service import serving_artifact
from open_commerce.ranking.serving import rerank
from open_commerce.search.catalog_documents import document_from_catalog_records
from open_commerce.search.embeddings import (
    LocalHashEmbeddingProvider,
    cosine,
    sparse_dot,
    sparse_vector,
)
from open_commerce.search.errors import SearchContextNotFoundError, SearchUnavailableError
from open_commerce.search.index import (
    RANKING_VERSION,
    _constraint_matches,
    _eligible_price,
    _ranked_candidate,
)
from open_commerce.search.models import (
    EmbeddingProvider,
    EvaluateSearchRequest,
    EventBatchRequest,
    EventBatchResponse,
    ParseSearchResponse,
    ProductSearchDocument,
    RecommendationRequest,
    RecommendationResponse,
    ResultSetEvaluation,
    SearchRequest,
    SearchResponse,
    SearchRule,
    SearchRuleListResponse,
    SearchTrace,
)
from open_commerce.search.normalization import TEMPLATE_VERSION
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.qdrant_index import (
    PRODUCT_COLLECTION,
    SPARSE_MODEL,
    QdrantProductSearchIndex,
)
from open_commerce.search.service import documents_from_simulator_state, evaluate_results
from open_commerce.simulator.durable import DurableSimulatorService, load_state
from open_commerce.simulator.models import SimulatorState


class DurableSearchService:
    """No authoritative process-local state or unavailable-service fallback."""

    def __init__(
        self,
        database: RuntimeDatabase,
        client: AsyncQdrantClient | None = None,
        *,
        collection_name: str = PRODUCT_COLLECTION,
    ) -> None:
        self.database = database
        self.collection_name = collection_name
        self.embedding_provider: EmbeddingProvider = LocalHashEmbeddingProvider()
        if database.settings.search_embedding_backend == "minilm":
            from open_commerce.search.learned_embeddings import get_minilm_provider

            if database.settings.search_model_directory is None:
                raise ValueError("explicit checksum-pinned search model directory required")
            self.embedding_provider = get_minilm_provider(database.settings.search_model_directory)
        self.client = client or AsyncQdrantClient(
            url=database.settings.qdrant_url, timeout=10, check_compatibility=False
        )

    async def close(self) -> None:
        await self.client.close()

    async def parse(self, *, tenant_id: UUID, request: SearchRequest) -> ParseSearchResponse:
        return ParseSearchResponse(
            interpretation=parse_search_intent(request.query, request.filters)
        )

    async def search(
        self,
        *,
        tenant_id: UUID,
        request: SearchRequest,
        preview_model_id: UUID | None = None,
        baseline: bool = False,
    ) -> SearchResponse:
        intent = parse_search_intent(request.query, request.filters)
        async with self._catalog(tenant_id, request.goal_context_id) as (state, index, _, rules):
            if state is not None and state.merchandising is not None:
                from open_commerce.search.merchandising import serve_search

                return await serve_search(
                    state,
                    tenant_id=tenant_id,
                    request=request,
                    index=index,
                    embedding_model=self.embedding_provider.model_id,
                )
            results = await index.search(
                tenant_id=tenant_id,
                intent=intent,
                filters=intent.required_filters,
                top_k=100 if state is None else request.top_k,
                mode=request.mode,
                rules=rules,
            )
            ranking_version = RANKING_VERSION
            if state is None and not baseline:
                async with self.database.transaction(tenant_id) as ranking_session:
                    selected = None
                    if preview_model_id is not None:
                        from open_commerce.ranking.models import RankingDataError
                        from open_commerce.ranking.service import checked_artifact, get_model

                        candidate = await get_model(ranking_session, tenant_id, preview_model_id)
                        if candidate.catalog_id != index.instance_id or candidate.status != "ready":
                            raise RankingDataError(
                                "Preview needs a ready model for the active catalog."
                            )
                        selected = candidate.id, checked_artifact(candidate)
                    else:
                        selected = await serving_artifact(
                            ranking_session, tenant_id, index.instance_id
                        )
                    if selected:
                        model_id, artifact = selected
                        results = rerank(results, artifact, intent)
                        ranking_version = f"{RANKING_VERSION}:engagement:{model_id}"
            results = results[: request.top_k]
            evaluation = evaluate_results(intent=intent, results=results)
            if evaluation.hard_constraint_violations:
                results = []
            query_id = uuid4()
            return SearchResponse(
                query_id=query_id,
                interpretation=intent,
                results=results,
                clarification="No matching products in this catalog." if not results else None,
                ranking_version=ranking_version,
                evaluation=evaluation,
                trace=SearchTrace(
                    query_id=query_id,
                    ranking_version=ranking_version,
                    retrieval={
                        "provider": "qdrant",
                        "mode": request.mode,
                        "fusion": "rrf-k60" if request.mode.startswith("hybrid") else None,
                        "catalog_id": str(index.instance_id),
                        "catalog_version": index.source_version,
                        "collection": index.collection_name,
                        "embedding_model": index.embedding_provider.model_id,
                        "sparse_model": SPARSE_MODEL,
                        "result_count": len(results),
                    },
                    results=[
                        {
                            "product_id": item.product_id,
                            "score_components": item.score_components.model_dump(mode="json"),
                            "constraint_matches": item.constraint_matches,
                            "branch_ranks": item.branch_ranks,
                        }
                        for item in results
                    ],
                )
                if request.debug
                else None,
            )

    async def recommendations(
        self, *, tenant_id: UUID, request: RecommendationRequest
    ) -> RecommendationResponse:
        # Merchandising PDP relationships are authoritative PostgreSQL policy and do not
        # depend on vector search. Resolve that path before considering an index rebuild.
        async with self._catalog(tenant_id, request.goal_context_id, require_index=False) as (
            state,
            _,
            _,
            _,
        ):
            if state is not None and state.merchandising is not None:
                from open_commerce.search.merchandising import serve_pdp

                return serve_pdp(state, tenant_id=tenant_id, request=request)
        async with self._catalog(tenant_id, request.goal_context_id) as (
            _,
            index,
            _,
            _,
        ):
            results = await index.similar(
                tenant_id=tenant_id,
                anchor_product_ids=request.anchor_product_ids,
                top_k=request.top_k,
            )
            query_id = uuid4()
            return RecommendationResponse(
                query_id=query_id,
                strategy="similar" if request.anchor_product_ids else "popular",
                results=results,
                trace=SearchTrace(
                    query_id=query_id,
                    ranking_version=RANKING_VERSION,
                    retrieval={
                        "provider": "qdrant",
                        "catalog_id": str(index.instance_id),
                        "catalog_version": index.source_version,
                    },
                )
                if request.debug
                else None,
            )

    async def evaluate(
        self, *, tenant_id: UUID, request: EvaluateSearchRequest
    ) -> ResultSetEvaluation:
        intent = parse_search_intent(request.query, request.filters)
        async with self._catalog(tenant_id, request.goal_context_id, require_index=False) as (
            state,
            _,
            catalog_documents,
            _,
        ):
            documents = {item.product_id: item for item in catalog_documents}
            scoped = [
                documents[key]
                for key in dict.fromkeys(r.product_id for r in request.results)
                if key in documents
            ]
            vectors = await self.embedding_provider.embed_documents([d.search_text for d in scoped])
            query_vector = await self.embedding_provider.embed_query(intent.semantic_query)
            dense = {
                d.product_id: Decimal(str(cosine(vector, query_vector)))
                for d, vector in zip(scoped, vectors, strict=True)
            }
            lexical = sparse_vector(intent.normalized_query)
            checked = []
            seen = set()
            for result in request.results:
                document = documents.get(result.product_id)
                constraints = {"catalog": False}
                if document is not None:
                    constraints = _constraint_matches(document, intent.required_filters)
                    authoritative = _ranked_candidate(
                        document=document,
                        intent=intent,
                        filters=intent.required_filters,
                        ranks={
                            "dense_score": dense[document.product_id],
                            "sparse_score": Decimal(
                                str(sparse_dot(lexical, sparse_vector(document.search_text)))
                            ),
                        },
                        rules=[],
                        mode="hybrid",
                        learned_semantics=self.embedding_provider.model_id
                        != LocalHashEmbeddingProvider.model_id,
                    )
                    constraints["relevance"] = authoritative.score_components.relevance >= (
                        state.merchandising.constraints.minimum_relevance
                        if state is not None and state.merchandising
                        else Decimal("0.0001")
                    )
                    constraints["displayed_price"] = (
                        result.price.amount_minor
                        == _eligible_price(document, intent.required_filters)
                        and result.price.currency == document.currency
                    )
                    authoritative.price = result.price
                    result = authoritative
                constraints["unique_product"] = result.product_id not in seen
                seen.add(result.product_id)
                checked.append(result.model_copy(update={"constraint_matches": constraints}))
            return evaluate_results(intent=intent, results=checked)

    async def list_rules(
        self, *, tenant_id: UUID, goal_context_id: UUID | None = None
    ) -> SearchRuleListResponse:
        async with self.database.transaction(tenant_id, write=True) as session:
            if goal_context_id is None and await active_catalog_integration(
                session, tenant_id=tenant_id
            ):
                return SearchRuleListResponse(items=[])
            state = await self._state(session, tenant_id, goal_context_id)
            return SearchRuleListResponse(items=await self._rules(session, state))

    async def reindex(self, *, tenant_id: UUID, goal_context_id: UUID | None = None) -> int:
        async with self._catalog(tenant_id, goal_context_id, force=True) as (_, _, documents, _):
            return len(documents)

    @asynccontextmanager
    async def _catalog(
        self,
        tenant_id: UUID,
        goal_id: UUID | None,
        *,
        force: bool = False,
        require_index: bool = True,
    ) -> AsyncIterator[
        tuple[
            SimulatorState | None,
            QdrantProductSearchIndex,
            list[ProductSearchDocument],
            list[SearchRule],
        ]
    ]:
        # Serialize with simulator changes, so one response uses a committed, consistent
        # catalog snapshot. The client timeout bounds network waits while holding this lock.
        async with self.database.transaction(tenant_id, write=True) as session:
            try:
                if goal_id is None:
                    integration = await active_catalog_integration(session, tenant_id=tenant_id)
                    if integration is not None:
                        source_version = str(integration.non_secret_config["source_version"])
                        index, documents = (
                            await self.prepare_uploaded_index(
                                session,
                                tenant_id=tenant_id,
                                integration_id=integration.id,
                                source_version=source_version,
                                force=force,
                            )
                            if require_index
                            else await self._uploaded_index(
                                session,
                                tenant_id=tenant_id,
                                integration_id=integration.id,
                                source_version=source_version,
                            )
                        )
                        yield None, index, documents, []
                        return
                state = await self._state(session, tenant_id, goal_id)
                index, documents = (
                    await self.prepare_state_index(session, state, force=force)
                    if require_index
                    else self._state_index(state)
                )
                yield state, index, documents, await self._rules(session, state)
            except (
                httpx.HTTPError,
                ResponseHandlingException,
                UnexpectedResponse,
                TimeoutError,
            ) as exc:
                raise SearchUnavailableError(
                    "Search is temporarily unavailable; retry after recovery."
                ) from exc

    async def prepare_uploaded_catalog_index(
        self, *, tenant_id: UUID, integration_id: UUID, source_version: str
    ) -> int:
        """Build one staged CSV index before atomically activating its integration."""

        async with self.database.transaction(tenant_id, write=True) as session:
            _, documents = await self.prepare_uploaded_index(
                session,
                tenant_id=tenant_id,
                integration_id=integration_id,
                source_version=source_version,
                force=True,
            )
            return len(documents)

    async def prepare_uploaded_index(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        integration_id: UUID,
        source_version: str,
        force: bool,
    ) -> tuple[QdrantProductSearchIndex, list[ProductSearchDocument]]:
        index, documents = await self._uploaded_index(
            session,
            tenant_id=tenant_id,
            integration_id=integration_id,
            source_version=source_version,
        )
        if force or await index.document_count(tenant_id=tenant_id) != len(documents):
            await index.upsert_documents(tenant_id=tenant_id, documents=documents)
            # Keep prior uploaded projections usable until the replacement is activated.
            if await index.document_count(tenant_id=tenant_id) != len(documents):
                raise SearchUnavailableError("Uploaded catalog index rebuild is incomplete")
        await self._record_index_version(
            session,
            tenant_id=tenant_id,
            catalog_id=integration_id,
            source_version=source_version,
            indexed_count=len(documents),
        )
        return index, documents

    async def _uploaded_index(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        integration_id: UUID,
        source_version: str,
    ) -> tuple[QdrantProductSearchIndex, list[ProductSearchDocument]]:
        records = await catalog_records(session, tenant_id=tenant_id, integration_id=integration_id)
        documents = [
            document_from_catalog_records(
                tenant_id=tenant_id,
                integration_id=integration_id,
                source_version=source_version,
                product=product,
                variants=variants,
                inventory=inventory,
            )
            for product, variants, inventory in records
        ]
        if not documents:
            raise SearchContextNotFoundError("Uploaded catalog is empty")
        index = QdrantProductSearchIndex(
            client=self.client,
            collection_name=self.collection_name,
            instance_id=integration_id,
            source_version=source_version,
            authoritative_documents={item.product_id: item for item in documents},
            embedding_provider=self.embedding_provider,
        )
        return index, documents

    async def prepare_state_index(
        self, session: AsyncSession, state: SimulatorState, *, force: bool = False
    ) -> tuple[QdrantProductSearchIndex, list[ProductSearchDocument]]:
        """Reconstruct inside the caller's tenant lock; API and simulation share this path."""
        tenant_id = state.tenant_id
        index, documents = self._state_index(state)
        if force or await index.document_count(tenant_id=tenant_id) != len(documents):
            await index.upsert_documents(tenant_id=tenant_id, documents=documents)
            await index.delete_old_versions(tenant_id=tenant_id)
            if await index.document_count(tenant_id=tenant_id) != len(documents):
                raise SearchUnavailableError("Index rebuild is incomplete")
        await self._record_index_version(
            session,
            tenant_id=tenant_id,
            catalog_id=state.id,
            source_version=str(index.source_version),
            indexed_count=len(documents),
        )
        return index, documents

    def _state_index(
        self, state: SimulatorState
    ) -> tuple[QdrantProductSearchIndex, list[ProductSearchDocument]]:
        documents = documents_from_simulator_state(
            state, embedding_model=self.embedding_provider.model_id
        )
        if not documents:
            raise SearchContextNotFoundError("Catalog is empty")
        index = QdrantProductSearchIndex(
            client=self.client,
            collection_name=self.collection_name,
            instance_id=state.id,
            source_version=documents[0].source_version,
            authoritative_documents={item.product_id: item for item in documents},
            embedding_provider=self.embedding_provider,
        )
        return index, documents

    async def _record_index_version(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        catalog_id: UUID,
        source_version: str,
        indexed_count: int,
    ) -> None:
        now = datetime.now(UTC)
        await session.execute(
            insert(SearchIndexVersion)
            .values(
                id=uuid5(NAMESPACE_URL, f"{tenant_id}:{catalog_id}:{source_version}"),
                tenant_id=tenant_id,
                name=str(catalog_id),
                embedding_model=self.embedding_provider.model_id,
                sparse_model=SPARSE_MODEL,
                document_template_version=TEMPLATE_VERSION,
                ranking_version=RANKING_VERSION,
                status="ready",
                indexed_product_count=indexed_count,
                created_at=now,
                activated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[SearchIndexVersion.id])
        )

    async def _rules(self, session: AsyncSession, state: SimulatorState) -> list[SearchRule]:
        if not state.search_boosts:
            return []
        rows = await session.execute(
            select(CompiledActionRecord.idempotency_key, CompiledActionRecord.id).where(
                CompiledActionRecord.tenant_id == state.tenant_id,
                CompiledActionRecord.type == "set_search_boost",
                CompiledActionRecord.target_provider["resource_id"].as_string() == str(state.id),
                CompiledActionRecord.idempotency_key.in_(
                    [boost.created_by_command for boost in state.search_boosts]
                ),
            )
        )
        return rules_from_state(state, {key: action_id for key, action_id in rows})

    async def _state(
        self, session: AsyncSession, tenant_id: UUID, goal_id: UUID | None
    ) -> SimulatorState:
        if self.database.settings.runtime_profile != "legacy_demo":
            raise SearchContextNotFoundError("Upload and verify a catalog before searching.")
        if goal_id is not None:
            instance_id = await session.scalar(
                select(Goal.simulator_instance_id).where(
                    Goal.tenant_id == tenant_id,
                    Goal.id == goal_id,
                )
            )
            if instance_id is None:
                raise SearchContextNotFoundError("Goal catalog not found")
        else:
            instance_id = await session.scalar(
                select(SimulatorInstanceRecord.id)
                .where(
                    SimulatorInstanceRecord.tenant_id == tenant_id,
                )
                .order_by(SimulatorInstanceRecord.created_at.desc(), SimulatorInstanceRecord.id)
                .limit(1)
            )
            if instance_id is None:
                created = await DurableSimulatorService(self.database).create_in_transaction(
                    session,
                    tenant_id=tenant_id,
                    scenario_id="acquisition_v1",
                    seed=42,
                    idempotency_key="search:default-catalog-v2",
                )
                instance_id = created.id
        return await load_state(session, tenant_id, instance_id)

    async def ingest_events(
        self, *, tenant_id: UUID, request: EventBatchRequest, idempotency_key: str
    ) -> EventBatchResponse:
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(
                scope="search:events", key=idempotency_key, request=request
            )
            if cached is not None:
                return EventBatchResponse.model_validate(cached)
            accepted = 0
            for event in request.events:
                event_id = _pseudonym(tenant_id, event.event_id)
                inserted = await session.scalar(
                    insert(BehavioralEventRecord)
                    .values(
                        tenant_id=tenant_id,
                        source="local_demo_search",
                        source_event_id=event_id,
                        schema_version="search-events-v2",
                        event_type=event.type.value,
                        occurred_at=event.occurred_at,
                        received_at=datetime.now(UTC),
                        session_id_hash=_pseudonym(tenant_id, event.session_id),
                        anonymous_user_id_hash=(
                            _pseudonym(tenant_id, event.anonymous_user_id)
                            if event.anonymous_user_id
                            else None
                        ),
                        query_id=event.query_id,
                        result_position=event.position,
                        surface=event.surface,
                        consent={"synthetic_local_demo": True},
                        safe_properties={
                            "product_ref_hash": _pseudonym(tenant_id, event.product_id)
                            if event.product_id
                            else None,
                            "variant_ref_hash": _pseudonym(tenant_id, event.variant_id)
                            if event.variant_id
                            else None,
                            **event.metadata,
                        },
                    )
                    .on_conflict_do_nothing(constraint="uq_events_tenant_source_event")
                    .returning(BehavioralEventRecord.id)
                )
                accepted += inserted is not None
            response = EventBatchResponse(
                accepted=accepted, deduplicated=len(request.events) - accepted
            )
            receipts.remember(
                scope="search:events", key=idempotency_key, request=request, response=response
            )
            return response


def _pseudonym(tenant_id: UUID, value: str) -> str:
    return sha256(f"{tenant_id}:{value}".encode()).hexdigest()


def rules_from_state(state: SimulatorState, action_ids: dict[str, UUID]) -> list[SearchRule]:
    return [
        SearchRule(
            id=uuid5(NAMESPACE_URL, f"{state.tenant_id}:{state.id}:{boost.id}"),
            tenant_id=state.tenant_id,
            query_text=boost.query_text,
            product_ids=boost.product_ids,
            category=boost.category,
            multiplier=boost.multiplier,
            starts_at=boost.starts_at,
            ends_at=boost.ends_at,
            status="active" if boost.active else "deleted",
            evaluation_time=state.current_time,
            reason="Simulator executor action",
            reason_action_id=action_ids[boost.created_by_command],
        )
        for boost in state.search_boosts
        if boost.created_by_command in action_ids
    ]
