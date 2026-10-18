"""Search, recommendation, rules, and event service."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from open_commerce.core.types import canonical_hash
from open_commerce.search.embeddings import SPARSE_MODEL, LocalHashEmbeddingProvider
from open_commerce.search.index import RANKING_VERSION, InMemoryProductSearchIndex
from open_commerce.search.models import (
    EvaluateSearchRequest,
    EventBatchRequest,
    EventBatchResponse,
    ParseSearchResponse,
    ProductFilters,
    ProductSearchDocument,
    RankedCandidate,
    RecommendationRequest,
    RecommendationResponse,
    ResultSetEvaluation,
    SearchIntent,
    SearchRequest,
    SearchResponse,
    SearchRetryPlan,
    SearchRule,
    SearchRuleListResponse,
    SearchRuleRequest,
    SearchTrace,
)
from open_commerce.search.normalization import TEMPLATE_VERSION, product_document_from_simulator
from open_commerce.search.parser import parse_search_intent
from open_commerce.simulator.engine import create_initial_state
from open_commerce.simulator.models import Exposure, ProductState, SimulatorState
from open_commerce.simulator.scenarios import get_scenario


class SearchService:
    """Tenant-scoped deterministic search service."""

    def __init__(self, index: InMemoryProductSearchIndex | None = None) -> None:
        self.index = index or InMemoryProductSearchIndex()
        self._rules: dict[UUID, list[SearchRule]] = {}
        self._rule_idempotency: dict[UUID, dict[str, SearchRule]] = {}
        self._seen_events: dict[UUID, set[str]] = {}
        self._demo_indexed_tenants: set[UUID] = set()

    async def parse(self, *, tenant_id: UUID, request: SearchRequest) -> ParseSearchResponse:
        """Parse a search query."""

        _ = tenant_id
        return ParseSearchResponse(
            interpretation=parse_search_intent(request.query, request.filters),
        )

    async def search(self, *, tenant_id: UUID, request: SearchRequest) -> SearchResponse:
        """Run search with deterministic evaluation and bounded retries."""

        await self.ensure_demo_catalog(tenant_id)
        query_id = uuid4()
        intent = parse_search_intent(request.query, request.filters)
        rules = self.active_rules(tenant_id)
        results = await self.index.search(
            tenant_id=tenant_id,
            intent=intent,
            filters=intent.required_filters,
            top_k=request.top_k,
            mode=request.mode,
            rules=rules,
        )
        evaluation = evaluate_results(intent=intent, results=results)
        retries: list[dict[str, object]] = []
        relaxed_preferences: list[str] = []
        retry_count = 0
        while evaluation.decision == "retry" and retry_count < 2:
            retry_count += 1
            if evaluation.retry_plan is None:
                break
            relaxed_preferences.extend(evaluation.retry_plan.relaxed_preferences)
            retries.append(
                {
                    "attempt": retry_count,
                    "reason": evaluation.retry_plan.reason,
                    "relaxed_preferences": evaluation.retry_plan.relaxed_preferences,
                }
            )
            results = await self.index.search(
                tenant_id=tenant_id,
                intent=intent,
                filters=intent.required_filters,
                top_k=request.top_k,
                mode="hybrid_reranked",
                rules=rules,
            )
            evaluation = evaluate_results(intent=intent, results=results)

        if evaluation.hard_constraint_violations:
            results = []

        trace = (
            SearchTrace(
                query_id=query_id,
                ranking_version=RANKING_VERSION,
                retrieval={
                    "mode": request.mode,
                    "fusion": "rrf",
                    "result_count": len(results),
                    "max_retries": 2,
                },
                retries=retries,
                results=[
                    {
                        "product_id": result.product_id,
                        "score_components": result.score_components.model_dump(mode="json"),
                        "constraint_matches": result.constraint_matches,
                    }
                    for result in results
                ],
            )
            if request.debug
            else None
        )
        return SearchResponse(
            query_id=query_id,
            interpretation=intent,
            results=results,
            clarification=(
                "Try a narrower category or price range."
                if evaluation.decision == "clarify"
                else None
            ),
            relaxed_preferences=relaxed_preferences,
            ranking_version=RANKING_VERSION,
            evaluation=evaluation,
            trace=trace,
        )

    async def evaluate(
        self,
        *,
        tenant_id: UUID,
        request: EvaluateSearchRequest,
    ) -> ResultSetEvaluation:
        """Evaluate a result set."""

        _ = tenant_id
        intent = parse_search_intent(request.query)
        return evaluate_results(intent=intent, results=request.results)

    async def recommendations(
        self,
        *,
        tenant_id: UUID,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        """Return deterministic similar/complementary/popular recommendations."""

        await self.ensure_demo_catalog(tenant_id)
        query_id = uuid4()
        results = await self.index.similar(
            tenant_id=tenant_id,
            anchor_product_ids=request.anchor_product_ids,
            top_k=request.top_k,
        )
        strategy = "similar" if request.anchor_product_ids else "popular"
        trace = (
            SearchTrace(
                query_id=query_id,
                ranking_version=RANKING_VERSION,
                retrieval={"strategy": strategy, "result_count": len(results)},
                results=[
                    {"product_id": result.product_id, "score": str(result.score)}
                    for result in results
                ],
            )
            if request.debug
            else None
        )
        return RecommendationResponse(
            query_id=query_id,
            strategy=strategy,
            results=results,
            trace=trace,
        )

    async def rank_simulator_exposures(
        self,
        *,
        state: SimulatorState,
        query_text: str,
        category: str,
        limit: int,
    ) -> list[Exposure]:
        """Rank simulator product exposures through the search service."""

        await self.index_simulator_state(state=state)
        response = await self.search(
            tenant_id=state.tenant_id,
            request=SearchRequest(
                query=query_text,
                filters=ProductFilters(category=category, in_stock=True),
                top_k=limit,
            ),
        )
        return [
            Exposure(
                product_id=result.product_id,
                score=result.score,
                relevance=result.score_components.relevance,
                position=index + 1,
            )
            for index, result in enumerate(response.results)
        ]

    async def ingest_events(
        self,
        *,
        tenant_id: UUID,
        request: EventBatchRequest,
        idempotency_key: str | None = None,
    ) -> EventBatchResponse:
        """Deduplicate and accept search/product behavioral events."""

        _ = idempotency_key
        seen = self._seen_events.setdefault(tenant_id, set())
        accepted = 0
        deduplicated = 0
        for event in request.events:
            if event.event_id in seen:
                deduplicated += 1
                continue
            seen.add(event.event_id)
            accepted += 1
        return EventBatchResponse(accepted=accepted, deduplicated=deduplicated)

    def list_rules(
        self, *, tenant_id: UUID, goal_context_id: UUID | None = None
    ) -> SearchRuleListResponse:
        """List active and deleted search rules for a tenant."""

        if goal_context_id is not None:
            raise ValueError("Offline search has no durable goal binding")
        return SearchRuleListResponse(items=list(self._rules.get(tenant_id, [])))

    def create_rule(
        self,
        *,
        tenant_id: UUID,
        request: SearchRuleRequest,
        idempotency_key: str,
    ) -> SearchRule:
        """Create a bounded search rule."""

        tenant_keys = self._rule_idempotency.setdefault(tenant_id, {})
        existing = tenant_keys.get(idempotency_key)
        if existing is not None:
            return existing
        rule = SearchRule(id=uuid4(), tenant_id=tenant_id, **request.model_dump())
        self._rules.setdefault(tenant_id, []).append(rule)
        tenant_keys[idempotency_key] = rule
        return rule

    def delete_rule(self, *, tenant_id: UUID, rule_id: UUID) -> None:
        """Mark a search rule deleted."""

        for rule in self._rules.get(tenant_id, []):
            if rule.id == rule_id:
                rule.status = "deleted"
                return
        raise KeyError(str(rule_id))

    async def index_simulator_state(self, *, state: SimulatorState) -> int:
        """Index a simulator state's product catalog."""

        documents = documents_from_simulator_state(state)
        await self.index.upsert_documents(tenant_id=state.tenant_id, documents=documents)
        self._demo_indexed_tenants.add(state.tenant_id)
        return len(documents)

    async def ensure_demo_catalog(self, tenant_id: UUID) -> None:
        """Index the default simulator catalog once for local search demos."""

        if tenant_id in self._demo_indexed_tenants:
            return
        definition = get_scenario("acquisition_v1")
        state = create_initial_state(
            definition=definition,
            tenant_id=tenant_id,
            seed=definition.seed,
        )
        await self.index_simulator_state(state=state)

    def active_rules(self, tenant_id: UUID) -> list[SearchRule]:
        """Return currently active search rules."""

        now = datetime.now(UTC)
        return [
            rule
            for rule in self._rules.get(tenant_id, [])
            if rule.status == "active" and rule.starts_at <= now < rule.ends_at
        ]


def documents_from_simulator_state(
    state: SimulatorState, *, embedding_model: str = LocalHashEmbeddingProvider.model_id
) -> list[ProductSearchDocument]:
    """Normalize simulator products into search documents."""

    return documents_from_simulator_products(
        tenant_id=state.tenant_id,
        products=state.products,
        updated_at=state.current_time,
        source_version=canonical_hash(
            {
                "engine": state.engine_version,
                "template": TEMPLATE_VERSION,
                "embedding": embedding_model,
                "sparse": SPARSE_MODEL,
                "generation": state.generation,
                "products": [product.model_dump(mode="json") for product in state.products],
            }
        ),
        instance_id=state.id,
    )


def documents_from_simulator_products(
    *,
    tenant_id: UUID,
    products: list[ProductState],
    updated_at: datetime,
    source_version: str,
    instance_id: UUID | None = None,
) -> list[ProductSearchDocument]:
    """Normalize simulator products into search documents."""

    return [
        product_document_from_simulator(
            tenant_id=tenant_id,
            product=product,
            updated_at=updated_at,
            source_version=source_version,
            instance_id=instance_id,
        )
        for product in products
    ]


def evaluate_results(
    *,
    intent: SearchIntent,
    results: Sequence[RankedCandidate],
) -> ResultSetEvaluation:
    """Evaluate hard-constraint coverage and decide whether to answer."""

    hard_violations: list[str] = []
    for result in results:
        for key, passed in result.constraint_matches.items():
            if not passed:
                hard_violations.append(key)
    categories = {tuple(result.category_path) for result in results if result.category_path}
    diversity = (
        Decimal(len(categories)) / Decimal(max(1, len(results))) if results else Decimal("0")
    )
    if hard_violations:
        decision = "retry"
        retry_plan = SearchRetryPlan(reason="hard_constraint_violation")
    elif not results:
        decision = "no_result"
        retry_plan = None
    elif len(results) < 3:
        decision = "clarify"
        retry_plan = None
    else:
        decision = "answer"
        retry_plan = None
    _ = intent
    return ResultSetEvaluation(
        coverage_by_constraint={
            "hard_constraints": Decimal("0") if hard_violations else Decimal("1")
        },
        hard_constraint_violations=sorted(set(hard_violations)),
        result_diversity=min(Decimal("1"), diversity),
        confidence=Decimal("0.85") if decision == "answer" else Decimal("0.55"),
        decision=decision,
        retry_plan=retry_plan,
    )


def default_rule_window() -> tuple[datetime, datetime]:
    """Return a deterministic-looking active default window around current time."""

    now = datetime.now(UTC)
    return now - timedelta(days=1), now + timedelta(days=30)
