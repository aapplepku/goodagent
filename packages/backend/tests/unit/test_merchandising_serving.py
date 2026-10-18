"""Shared storefront configuration is consumed by actual seeded shopper simulation."""

from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from open_commerce.controller.models import GoalCreateRequest
from open_commerce.controller.service import ControllerService
from open_commerce.core.enums import ExecutionStatus
from open_commerce.core.merchandising import MerchandisingConstraints, RecommendationControls
from open_commerce.core.providers import SetRecommendationPolicyCommand
from open_commerce.core.types import TimeWindow
from open_commerce.search.embeddings import LocalHashEmbeddingProvider
from open_commerce.search.index import InMemoryProductSearchIndex
from open_commerce.search.merchandising import serve_pdp, serve_search
from open_commerce.search.models import (
    ProductFilters,
    RankingMode,
    RecommendationRequest,
    SearchRequest,
)
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.qdrant_index import QdrantProductSearchIndex
from open_commerce.search.service import documents_from_simulator_state
from open_commerce.simulator.merchandising_engine import simulate_merchandising_day
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.provider import SimulatorProvider


def fixture() -> SimulatorState:
    service = ControllerService()
    tenant = uuid4()
    goal = service.create_goal(
        tenant_id=tenant,
        request=GoalCreateRequest(seed=42, merchandising=MerchandisingConstraints()),
        idempotency_key="merch",
    )
    return service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )


async def test_pdp_complements_exclude_unrelated_high_margin_products() -> None:
    state = fixture()
    anchor = "merch_wall_chargers_1"
    request = RecommendationRequest(anchor_product_ids=[anchor])
    before = serve_pdp(state, tenant_id=state.tenant_id, request=request)
    assert before.strategy == "alternatives"
    assert all("wall_chargers" in r.product_id for r in before.results)
    excluded = "merch_charging_cables_1"
    result = await SimulatorProvider(state).set_recommendation_policy(
        SetRecommendationPolicyCommand(
            tenant_id=state.tenant_id,
            idempotency_key="reviewed-control-test",
            expected_version=0,
            controls=RecommendationControls(
                strategy="complements", excluded_product_ids=[excluded]
            ),
            window=TimeWindow(
                start_at=state.current_time, end_at=state.current_time + timedelta(days=2)
            ),
        )
    )
    assert result.status == ExecutionStatus.SUCCEEDED
    after = serve_pdp(state, tenant_id=state.tenant_id, request=request)
    assert after.policy_version == 1
    assert after.results and all("charging_cables" in r.product_id for r in after.results)
    assert excluded not in {r.product_id for r in after.results}
    for product in state.products:
        if "headphones" in product.id:
            for variant in product.variants:
                variant.cost_minor = 0
            product.excess_inventory = True
    assert {
        r.product_id for r in serve_pdp(state, tenant_id=state.tenant_id, request=request).results
    } == {r.product_id for r in after.results}
    with pytest.raises(ValueError, match="tenant"):
        serve_pdp(state, tenant_id=uuid4(), request=request)


async def test_shared_serving_simulation_records_matched_traffic_exact_economics_and_addons() -> (
    None
):
    baseline = fixture()
    intervention = baseline.model_copy(deep=True)
    assert intervention.merchandising is not None and baseline.merchandising is not None
    intervention.merchandising.recommendation_policy.version = 1
    intervention.merchandising.recommendation_policy.controls = RecommendationControls(
        strategy="complements"
    )
    for state in [baseline, intervention]:
        index = InMemoryProductSearchIndex()
        await index.upsert_documents(
            tenant_id=state.tenant_id, documents=documents_from_simulator_state(state)
        )
        await simulate_merchandising_day(
            state,
            tenant_id=state.tenant_id,
            index=index,
            embedding_model=LocalHashEmbeddingProvider.model_id,
        )
        metric = state.metrics[-1]
        merch = state.merchandising
        assert merch is not None
        assert metric.sessions > 0 and metric.orders > 0
        assert metric.ad_spend_minor == 0
        assert metric.orders == len(merch.checkout_lines)
        assert metric.units_sold == sum(len(lines) for lines in merch.checkout_lines.values())
        assert metric.contribution_profit_minor == sum(
            r.economics.contribution_profit_minor
            for r in merch.redemptions.values()
            if r.status == "redeemed"
        )
        assert metric.impressions == sum(
            o.search_exposures + o.recommendation_exposures for o in merch.product_outcomes.values()
        )
        assert all(
            merch.redemptions[key].product_id in batch.product_ids
            for batch in merch.serving_log.values()
            for key in batch.order_keys
        )
        restored = SimulatorState.model_validate_json(state.model_dump_json())
        assert restored.state_hash == state.state_hash
    assert baseline.metrics[-1].sessions == intervention.metrics[-1].sessions
    assert all(len(lines) == 1 for lines in baseline.merchandising.checkout_lines.values())
    assert any(len(lines) == 2 for lines in intervention.merchandising.checkout_lines.values())
    assert {
        b.policy_version
        for b in intervention.merchandising.serving_log.values()
        if b.surface == "product_detail"
    } == {1}


async def test_search_hard_budget_and_stock_precede_any_business_priority() -> None:
    state = fixture()
    index = InMemoryProductSearchIndex()
    await index.upsert_documents(
        tenant_id=state.tenant_id, documents=documents_from_simulator_state(state)
    )
    response = await serve_search(
        state,
        tenant_id=state.tenant_id,
        index=index,
        embedding_model=LocalHashEmbeddingProvider.model_id,
        request=SearchRequest(query="hiking boots", filters=ProductFilters(max_price_minor=100)),
    )
    assert response.results == []
    assert response.evaluation.hard_constraint_violations == []
    assert state.merchandising is not None
    state.merchandising.constraints.minimum_relevance = Decimal(1)


async def test_live_variant_availability_is_rechecked_after_indexing() -> None:
    state = fixture()
    product = state.products[0]
    state.products = [product]
    index = InMemoryProductSearchIndex()
    documents = documents_from_simulator_state(state)
    await index.upsert_documents(tenant_id=state.tenant_id, documents=documents)
    product.variants[0].available = False
    response = await serve_search(
        state,
        tenant_id=state.tenant_id,
        index=index,
        embedding_model=LocalHashEmbeddingProvider.model_id,
        request=SearchRequest(
            query=product.title,
            filters=ProductFilters(max_price_minor=product.variants[0].price_minor),
        ),
    )
    assert response.results == []
    unbounded = await serve_search(
        state,
        tenant_id=state.tenant_id,
        index=index,
        embedding_model=LocalHashEmbeddingProvider.model_id,
        request=SearchRequest(query=product.title),
    )
    assert unbounded.results[0].price.amount_minor == product.variants[1].price_minor


@pytest.mark.parametrize("backend", ["memory", "qdrant"])
@pytest.mark.parametrize("mode", ["sparse", "dense", "hybrid"])
async def test_unavailable_cheap_variant_cannot_satisfy_price_filter(
    backend: Literal["memory", "qdrant"],
    mode: RankingMode,
) -> None:
    state = fixture()
    product = state.products[0]
    product.variants[0].available = False
    assert product.variants[0].inventory > 0
    state.products = [product]
    documents = documents_from_simulator_state(state)
    assert documents[0].available_variant_count == 1
    assert documents[0].variants[0].in_stock is False
    client = AsyncQdrantClient(location=":memory:")
    try:
        index = (
            InMemoryProductSearchIndex()
            if backend == "memory"
            else QdrantProductSearchIndex(
                client=client,
                instance_id=state.id,
                authoritative_documents={d.product_id: d for d in documents},
            )
        )
        await index.upsert_documents(tenant_id=state.tenant_id, documents=documents)
        budget = product.variants[0].price_minor
        intent = parse_search_intent(product.title, ProductFilters(max_price_minor=budget))
        assert (
            await index.search(
                tenant_id=state.tenant_id,
                intent=intent,
                filters=intent.required_filters,
                mode=mode,
                top_k=5,
                rules=[],
            )
            == []
        )
        intent = parse_search_intent(product.title)
        results = await index.search(
            tenant_id=state.tenant_id,
            intent=intent,
            filters=intent.required_filters,
            mode=mode,
            top_k=5,
            rules=[],
        )
        assert len(results) == 1
        assert results[0].price.amount_minor == product.variants[1].price_minor
    finally:
        await client.close()
