"""Real PostgreSQL + HTTP Qdrant reconstruction, safety and executor-rule tests."""

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import EventType
from open_commerce.persistence.models.events import BehavioralEventRecord
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.errors import SearchContextNotFoundError
from open_commerce.search.models import (
    EvaluateSearchRequest,
    EventBatchRequest,
    ProductFilters,
    RankingMode,
    RecommendationRequest,
    SearchEventInput,
    SearchRequest,
)
from open_commerce.search.service import documents_from_simulator_state
from open_commerce.simulator.durable import load_state

from .test_durable_controller import approve, prepared_goal

pytestmark = pytest.mark.integration


async def test_live_search_rebuilds_from_postgres_and_survives_pool_restart(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_sqlite(*args: object, **kwargs: object) -> None:
        raise AssertionError("deployed search must never open a SQLite database")

    monkeypatch.setattr(sqlite3, "connect", reject_sqlite)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", reject_sqlite)
    database = RuntimeDatabase(integration_settings)
    collection = f"qualification_{uuid4().hex}"
    search = DurableSearchService(database, collection_name=collection)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        controller = DurableControllerService(database)
        goal = await controller.create_goal(
            tenant_id=tenant, request=GoalCreateRequest(), idempotency_key="create"
        )
        request = SearchRequest(query="SIM-FOO-0003-1", goal_context_id=goal.spec.id, debug=True)
        first = await search.search(tenant_id=tenant, request=request)
        assert first.results[0].product_id == "prod_footwear_0003"
        assert first.trace is not None and first.trace.retrieval["provider"] == "qdrant"
        price = first.results[0].price.amount_minor
        modes: list[RankingMode] = [
            "sparse",
            "dense",
            "hybrid",
            "hybrid_reranked",
            "hybrid_boosted",
        ]
        for mode in modes:
            response = await search.search(
                tenant_id=tenant,
                request=SearchRequest(
                    query="outdoor shell under $150",
                    goal_context_id=goal.spec.id,
                    mode=mode,
                    filters=ProductFilters(attributes={"material": ["recycled nylon"]}),
                ),
            )
            assert response.results
            assert all(item.price.amount_minor <= 15000 for item in response.results)
            assert all(all(item.constraint_matches.values()) for item in response.results)
        with pytest.raises(SearchContextNotFoundError):
            await search.search(tenant_id=uuid4(), request=request)
        async with database.transaction(tenant, write=True) as session:
            state = await load_state(session, tenant, goal.simulator_instance_id)
            product = next(item for item in state.products if item.id == "prod_footwear_0003")
            for variant in product.variants:
                variant.price_minor += 111
            await SqlSimulatorRepository(session).save_state(state)
        updated = await search.search(tenant_id=tenant, request=request)
        assert updated.results[0].price.amount_minor == price + 111
        assert updated.trace is not None
        assert (
            updated.trace.retrieval["catalog_version"] != first.trace.retrieval["catalog_version"]
        )
        await search.client.delete_collection(collection)
        rebuilt = await search.search(tenant_id=tenant, request=request)
        assert rebuilt.results == updated.results
        await search.close()
        await database.close()
        database = RuntimeDatabase(integration_settings)
        search = DurableSearchService(database, collection_name=collection)
        restored = await search.search(tenant_id=tenant, request=request)
        assert restored.results == updated.results
        recommendations = await search.recommendations(
            tenant_id=tenant,
            request=RecommendationRequest(
                goal_context_id=goal.spec.id,
                anchor_product_ids=["prod_footwear_0003"],
            ),
        )
        assert recommendations.results
        assert all(item.product_id != "prod_footwear_0003" for item in recommendations.results)
    finally:
        if await search.client.collection_exists(collection):
            await search.client.delete_collection(collection)
        await search.close()
        await database.close()


async def test_live_search_uses_authoritative_facts_not_forged_qdrant_payloads(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    collection = f"qualification_{uuid4().hex}"
    search = DurableSearchService(database, collection_name=collection)
    tenant = uuid4()
    try:
        await database.initialize_tenant(tenant)
        controller = DurableControllerService(database)
        goal = await controller.create_goal(
            tenant_id=tenant, request=GoalCreateRequest(), idempotency_key="create"
        )
        request = SearchRequest(query="SIM-FOO-0003-1", goal_context_id=goal.spec.id)
        original = await search.search(tenant_id=tenant, request=request)
        async with database.transaction(tenant) as session:
            state = await load_state(session, tenant, goal.simulator_instance_id)
        document = next(
            item
            for item in documents_from_simulator_state(state)
            if item.product_id == original.results[0].product_id
        )
        forged = document.model_dump(mode="json")
        forged["title"] = "Forged index title"
        forged["min_price_minor"] = 1
        forged["max_price_minor"] = 1
        await search.client.set_payload(
            collection_name=collection,
            points=[document.point_id],
            payload={"document": forged},
            wait=True,
        )
        guarded = await search.search(tenant_id=tenant, request=request)
        assert guarded.results == original.results
        fake_result = original.results[0].model_copy(deep=True)
        fake_result.price.amount_minor = 1
        fake_result.constraint_matches = {"price": True, "in_stock": True}
        evaluated = await search.evaluate(
            tenant_id=tenant,
            request=EvaluateSearchRequest(
                query=request.query,
                goal_context_id=goal.spec.id,
                results=[fake_result],
            ),
        )
        assert "displayed_price" in evaluated.hard_constraint_violations
    finally:
        if await search.client.collection_exists(collection):
            await search.client.delete_collection(collection)
        await search.close()
        await database.close()


async def test_executed_search_rule_is_durable_and_uses_simulated_clock(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    collection = f"qualification_{uuid4().hex}"
    search = DurableSearchService(database, collection_name=collection)
    try:
        tenant, _, action_id = await prepared_goal(database, "set_search_boost")
        await approve(database, tenant, action_id)
        controller = DurableControllerService(database)
        executed = await controller.execute_action(
            tenant_id=tenant, action_id=action_id, idempotency_key="execute"
        )
        rules = await search.list_rules(tenant_id=tenant, goal_context_id=executed.action.goal_id)
        assert len(rules.items) == 1 and rules.items[0].reason_action_id == action_id
        rule = rules.items[0]
        assert (
            rule.evaluation_time is not None
            and rule.starts_at <= rule.evaluation_time < rule.ends_at
        )
        response = await search.search(
            tenant_id=tenant,
            request=SearchRequest(
                query=rule.query_text,
                goal_context_id=executed.action.goal_id,
                mode="hybrid_boosted",
                top_k=50,
            ),
        )
        assert any(item.score_components.goal_boost > 0 for item in response.results)
        assert all(item.score_components.goal_boost <= Decimal("0.15") for item in response.results)
    finally:
        if await search.client.collection_exists(collection):
            await search.client.delete_collection(collection)
        await search.close()
        await database.close()


async def test_event_receipts_and_deduplication_survive_database_pool_restart(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    search = DurableSearchService(database)
    tenant = uuid4()
    request = EventBatchRequest(
        events=[
            SearchEventInput(
                event_id="event-synthetic-1",
                occurred_at=datetime.now(UTC),
                session_id="synthetic-session",
                type=EventType.PRODUCT_IMPRESSION,
                surface="search",
                metadata={"dwell_ms": 10},
            )
        ]
    )
    try:
        await database.initialize_tenant(tenant)
        first = await search.ingest_events(
            tenant_id=tenant, request=request, idempotency_key="batch"
        )
        assert first.accepted == 1
        await search.close()
        await database.close()
        database = RuntimeDatabase(integration_settings)
        search = DurableSearchService(database)
        replay = await search.ingest_events(
            tenant_id=tenant, request=request, idempotency_key="batch"
        )
        assert replay == first
        repeated = await search.ingest_events(
            tenant_id=tenant, request=request, idempotency_key="batch-2"
        )
        assert repeated.accepted == 0 and repeated.deduplicated == 1
        async with database.transaction(tenant) as session:
            records = list(
                await session.scalars(
                    select(BehavioralEventRecord).where(BehavioralEventRecord.tenant_id == tenant)
                )
            )
            assert len(records) == 1
            assert records[0].session_id_hash != "synthetic-session"
            assert records[0].source_event_id != "event-synthetic-1"
    finally:
        await search.close()
        await database.close()


async def test_unavailable_search_returns_safe_503_without_local_index_fallback(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(update={"local_tenant_id": uuid4()})
    database = RuntimeDatabase(settings)
    search = DurableSearchService(
        database, AsyncQdrantClient(url="http://127.0.0.1:1", timeout=1, check_compatibility=False)
    )
    app = create_app(settings, search_service=search)
    try:
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            response = await client.post("/v1/search", json={"query": "trail"})
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "SEARCH_UNAVAILABLE"
            assert "127.0.0.1:1" not in response.text
            assert "Traceback" not in response.text
    finally:
        await database.close()
