"""Shared simulator storefront serving, independent of the planning fast path."""

from collections import Counter
from decimal import Decimal
from uuid import UUID, uuid4

from open_commerce.core.merchandising import RecommendationControls
from open_commerce.search.index import (
    RANKING_VERSION,
    _basic_ranked,
    _constraint_matches,
    _eligible_price,
)
from open_commerce.search.models import (
    ProductSearchDocument,
    ProductSearchIndex,
    RecommendationRequest,
    RecommendationResponse,
    SearchRequest,
    SearchResponse,
    SearchTrace,
)
from open_commerce.search.normalization import product_document_from_simulator
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.service import documents_from_simulator_state, evaluate_results
from open_commerce.simulator.models import SimulatorState

MERCHANDISING_RANKING_VERSION = "merchandising-serving-v1"


def serve_pdp(
    state: SimulatorState,
    *,
    tenant_id: UUID,
    request: RecommendationRequest,
    documents: list[ProductSearchDocument] | None = None,
) -> RecommendationResponse:
    """Explicit catalog eligibility precedes bounded business priority and diversity."""
    if state.tenant_id != tenant_id or state.merchandising is None:
        raise ValueError("tenant-owned merchandising profile required")
    if request.surface != "product_detail" or len(request.anchor_product_ids) != 1:
        raise ValueError("merchandising supports one anchored PDP panel only")
    products = {p.id: p for p in state.products}
    anchor = products.get(request.anchor_product_ids[0])
    if anchor is None:
        raise ValueError("unknown scoped PDP anchor")
    policy = state.merchandising.recommendation_policy
    active = policy.starts_at is None or (
        policy.starts_at <= state.current_time
        and policy.ends_at is not None
        and state.current_time < policy.ends_at
    )
    controls = (
        policy.controls
        if active
        else RecommendationControls(
            minimum_relevance=state.merchandising.constraints.minimum_relevance
        )
    )
    compatible = {
        c.complement_product_id: c.evidence_id
        for c in state.merchandising.compatibility
        if c.anchor_product_id == anchor.id
    }
    indexed = {d.product_id: d for d in documents or documents_from_simulator_state(state)}
    eligible = []
    evidence = {}
    for product in state.products:
        if (
            product.id == anchor.id
            or product.id in controls.excluded_product_ids
            or product.low_stock
        ):
            continue
        if not any(v.available and v.inventory > 0 for v in product.variants):
            continue
        if controls.strategy == "complements":
            if product.id not in compatible:
                continue
            reason = compatible[product.id]
        else:
            family = anchor.attributes.get("product_type")
            if (
                not family
                or product.category != anchor.category
                or product.attributes.get("product_type") != family
            ):
                continue
            reason = f"catalog:product_type:{family}:category:{anchor.category}"
        relevance = Decimal(1)
        if relevance < max(
            controls.minimum_relevance, state.merchandising.constraints.minimum_relevance
        ):
            continue
        priority = controls.inventory_priority if product.excess_inventory else Decimal(0)
        eligible.append((relevance + priority, product))
        evidence[product.id] = reason
    eligible.sort(key=lambda item: (-item[0], item[1].id))
    brands: Counter[str] = Counter()
    results = []
    for score, product in eligible:
        if brands[product.brand] >= controls.max_per_brand:
            continue
        document = product_document_from_simulator(
            tenant_id=tenant_id,
            product=product,
            updated_at=state.current_time,
            source_version=indexed[product.id].source_version,
            instance_id=state.id,
        )
        candidate = _basic_ranked(document, Decimal(1))
        candidate.score = score
        candidate.score_components.dense = Decimal(0)
        candidate.score_components.goal_boost = score - 1
        candidate.score_components.final = score
        candidate.constraint_matches["explicit_relationship"] = True
        candidate.highlights = [evidence[product.id]]
        results.append(candidate)
        brands[product.brand] += 1
        if len(results) >= min(request.top_k, controls.limit):
            break
    query_id = uuid4()
    return RecommendationResponse(
        query_id=query_id,
        strategy=controls.strategy,
        results=results,
        policy_version=policy.version,
        policy_active=active,
        trace=SearchTrace(
            query_id=query_id,
            ranking_version=MERCHANDISING_RANKING_VERSION,
            retrieval={
                "surface": "product_detail",
                "anchor_product_id": anchor.id,
                "policy_version": policy.version,
                "policy_active": active,
                "exposed_product_ids": [r.product_id for r in results],
                "eligibility_method": "explicit_catalog_relationship_not_similarity",
                "eligible_count": len(eligible),
            },
            results=[
                {"product_id": r.product_id, "evidence_id": evidence[r.product_id]} for r in results
            ],
        ),
    )


async def serve_search(
    state: SimulatorState,
    *,
    tenant_id: UUID,
    request: SearchRequest,
    index: ProductSearchIndex,
    embedding_model: str,
) -> SearchResponse:
    """Same retrieval and boost eligibility used by API requests and simulator sessions."""
    if state.tenant_id != tenant_id or state.merchandising is None:
        raise ValueError("tenant-owned merchandising profile required")
    intent = parse_search_intent(request.query, request.filters)
    mode = "hybrid" if request.mode == "hybrid_boosted" else request.mode
    results = await index.search(
        tenant_id=tenant_id,
        intent=intent,
        filters=intent.required_filters,
        top_k=100,
        mode=mode,
        rules=[],
    )
    products = {p.id: p for p in state.products}
    # The index may be a daily snapshot. Recheck the live qualifying variant before
    # exposing a price; another variant's stock cannot satisfy this shopper's budget.
    live_documents = {
        r.product_id: product_document_from_simulator(
            tenant_id=tenant_id,
            product=products[r.product_id],
            updated_at=state.current_time,
            source_version="live-serving",
            instance_id=state.id,
        )
        for r in results
        if r.product_id in products
    }
    results = [
        r
        for r in results
        if r.score_components.relevance >= state.merchandising.constraints.minimum_relevance
        and all(r.constraint_matches.values())
        and r.product_id in products
        and any(v.available and v.inventory > 0 for v in products[r.product_id].variants)
        and all(_constraint_matches(live_documents[r.product_id], intent.required_filters).values())
    ]
    for result in results:
        live_price = _eligible_price(live_documents[result.product_id], intent.required_filters)
        if live_price is None:
            raise ValueError("eligible live search result lacks a qualifying variant")
        result.price.amount_minor = live_price
        product = products[result.product_id]
        boost = Decimal(0)
        if not product.low_stock:
            for rule in state.search_boosts:
                if (
                    rule.active
                    and rule.starts_at <= state.current_time < rule.ends_at
                    and result.product_id in rule.product_ids
                    and rule.query_text.casefold() in intent.normalized_query
                ):
                    boost = max(
                        boost,
                        min(Decimal("0.15"), rule.multiplier - 1)
                        * result.score_components.relevance,
                    )
        result.score_components.goal_boost = boost
        result.score_components.final += boost
        result.score += boost
    results.sort(key=lambda r: (-r.score, r.product_id))
    results = results[: request.top_k]
    evaluation = evaluate_results(intent=intent, results=results)
    query_id = uuid4()
    return SearchResponse(
        query_id=query_id,
        interpretation=intent,
        results=results,
        ranking_version=MERCHANDISING_RANKING_VERSION,
        evaluation=evaluation,
        clarification=None if results else "No eligible products.",
        trace=SearchTrace(
            query_id=query_id,
            ranking_version=MERCHANDISING_RANKING_VERSION,
            retrieval={
                "retrieval_ranking": RANKING_VERSION,
                "embedding_model": embedding_model,
                "mode": mode,
                "exposed_product_ids": [r.product_id for r in results],
                "active_boost_ids": [
                    r.id
                    for r in state.search_boosts
                    if r.active and r.starts_at <= state.current_time < r.ends_at
                ],
            },
            results=[
                {
                    "product_id": r.product_id,
                    "score_components": r.score_components.model_dump(mode="json"),
                }
                for r in results
            ],
        ),
    )
