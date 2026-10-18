from datetime import timedelta
from uuid import UUID

import pytest

from open_commerce.core.enums import EventType
from open_commerce.search.index import InMemoryProductSearchIndex
from open_commerce.search.models import (
    EventBatchRequest,
    ProductFilters,
    RankedCandidate,
    RankingMode,
    SearchEventInput,
    SearchIntent,
    SearchRequest,
    SearchRule,
    SearchRuleRequest,
)
from open_commerce.search.service import SearchService
from open_commerce.simulator.engine import create_initial_state
from open_commerce.simulator.scenarios import get_scenario

from .helpers import BASE_TIME, TENANT_ID, make_ranked_candidate


class AlwaysViolatingIndex(InMemoryProductSearchIndex):
    def __init__(self) -> None:
        super().__init__()
        self.search_calls = 0

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
        self.search_calls += 1
        _ = (tenant_id, intent, filters, top_k, mode, rules)
        return [
            make_ranked_candidate(
                product_id="violating",
                constraint_matches={"in_stock": False},
            )
        ]


@pytest.mark.asyncio
async def test_search_retry_loop_is_capped_and_preserves_hard_constraints() -> None:
    index = AlwaysViolatingIndex()
    service = SearchService(index=index)

    response = await service.search(
        tenant_id=TENANT_ID,
        request=SearchRequest(
            query="trail",
            filters=ProductFilters(in_stock=True),
            debug=True,
        ),
    )

    assert index.search_calls == 3
    assert response.evaluation.decision == "retry"
    assert response.results == []
    assert response.relaxed_preferences == []
    assert response.interpretation.required_filters.in_stock is True
    assert response.trace is not None
    assert len(response.trace.retries) == 2


@pytest.mark.asyncio
async def test_event_ingestion_deduplicates_per_tenant() -> None:
    service = SearchService()
    request = EventBatchRequest(
        events=[
            SearchEventInput(
                event_id="evt-1",
                occurred_at=BASE_TIME,
                session_id="session-1",
                type=EventType.PRODUCT_IMPRESSION,
                product_id="prod_1",
                position=1,
                surface="search",
            ),
            SearchEventInput(
                event_id="evt-1",
                occurred_at=BASE_TIME,
                session_id="session-1",
                type=EventType.PRODUCT_IMPRESSION,
                product_id="prod_1",
                position=1,
                surface="search",
            ),
        ]
    )

    first = await service.ingest_events(tenant_id=TENANT_ID, request=request)
    second = await service.ingest_events(tenant_id=TENANT_ID, request=request)

    assert first.accepted == 1
    assert first.deduplicated == 1
    assert second.accepted == 0
    assert second.deduplicated == 2


def test_rule_creation_is_idempotent_and_delete_is_repeatable() -> None:
    service = SearchService()
    request = SearchRuleRequest(
        query_text="trail",
        product_ids=["prod_1"],
        multiplier="1.5",
        starts_at=BASE_TIME - timedelta(days=1),
        ends_at=BASE_TIME + timedelta(days=1),
        reason="test",
    )

    first = service.create_rule(
        tenant_id=TENANT_ID,
        request=request,
        idempotency_key="rule-key",
    )
    second = service.create_rule(
        tenant_id=TENANT_ID,
        request=request,
        idempotency_key="rule-key",
    )

    assert first.id == second.id
    assert len(service.list_rules(tenant_id=TENANT_ID).items) == 1

    service.delete_rule(tenant_id=TENANT_ID, rule_id=first.id)
    service.delete_rule(tenant_id=TENANT_ID, rule_id=first.id)

    assert service.list_rules(tenant_id=TENANT_ID).items[0].status == "deleted"


@pytest.mark.asyncio
async def test_search_service_can_rank_simulator_exposures() -> None:
    definition = get_scenario("acquisition_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    service = SearchService()

    exposures = await service.rank_simulator_exposures(
        state=state,
        query_text="hiking camp gear",
        category="outdoor",
        limit=5,
    )

    assert len(exposures) == 5
    assert [exposure.position for exposure in exposures] == [1, 2, 3, 4, 5]
    assert all(exposure.product_id.startswith("prod_outdoor_") for exposure in exposures)
