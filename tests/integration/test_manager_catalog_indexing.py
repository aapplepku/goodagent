"""End-to-end uploaded catalog persistence, worker indexing, and search serving."""

from typing import cast
from unittest.mock import create_autospec
from uuid import UUID, uuid4

import pytest

from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.browse_models import CatalogBrowseQuery
from open_commerce.catalog.persistence import active_catalog_integration, catalog_index_status
from open_commerce.config import Settings
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.manager_agent.models import (
    ManagerDatasetProfileRequest,
    ManagerThreadCreateRequest,
)
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import SearchRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.worker.jobs import JobRunner

pytestmark = pytest.mark.integration


class _CountMismatchSearch:
    async def prepare_uploaded_catalog_index(
        self, *, tenant_id: UUID, integration_id: UUID, source_version: str
    ) -> int:
        _ = tenant_id, integration_id, source_version
        return 1


async def test_uploaded_catalog_is_indexed_and_served_without_blocking_chat(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    collection = f"manager_catalog_{uuid4().hex}"
    search = DurableSearchService(database, collection_name=collection)
    tenant_id = uuid4()
    first_csv = (
        "product_id,variant_id,sku,title,description,category,brand,price,"
        "currency,inventory_quantity,popularity_score,image_url,updated_at\n"
        "lunar-lamp,lunar-lamp-1,LAMP-1,Lunar Reading Lamp,"
        "Focused warm light for a quiet desk,Lighting,Northstar,79,USD,12,98,"
        "https://example.test/lunar.jpg,"
        "2026-09-01T12:00:00Z\n"
        "paper-lamp,paper-lamp-1,LAMP-2,Paper Shade Lamp,"
        "Soft ambient bedroom light,Lighting,Northstar,49,USD,5,42,"
        "https://example.test/paper.jpg,"
        "2026-09-01T12:00:00Z\n"
    )
    try:
        await database.initialize_tenant(tenant_id)
        manager = DurableManagerAgentService(database)
        thread = await manager.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Catalog indexing"),
            idempotency_key="create-catalog-thread",
        )
        profiled = await manager.profile_dataset(
            tenant_id=tenant_id,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="catalog.csv",
                csv_text=first_csv,
            ),
            idempotency_key="upload-catalog",
        )

        assert profiled.catalog_index.status == "queued"
        assert profiled.catalog_index.product_count == 2
        assert "Lunar Reading Lamp" not in profiled.model_dump_json()

        runner = JobRunner(database, tenant_id, search_service=search)
        assert profiled.catalog_index.job_id is not None
        assert await runner.run_catalog_index(profiled.catalog_index.job_id)

        workspace = await manager.get_workspace(tenant_id=tenant_id)
        assert workspace.catalog_index.status == "ready"
        assert workspace.catalog_index.indexed_product_count == 2
        browser = CatalogBrowseService(database)
        published = await browser.browse(tenant_id=tenant_id, query=CatalogBrowseQuery())
        assert published.catalog is not None
        assert published.catalog.id == profiled.catalog_index.catalog_id
        assert published.catalog.source_version == profiled.catalog_index.source_version
        assert published.total == 2
        assert published.categories == ["Lighting"]
        assert published.items[0].title == "Lunar Reading Lamp"
        assert published.items[0].image_url == "https://example.test/lunar.jpg"
        assert published.items[0].price.amount_minor == 7900
        assert published.items[0].availability == "available"
        page = await browser.browse(
            tenant_id=tenant_id, query=CatalogBrowseQuery(limit=1, offset=1)
        )
        assert page.items[0].product_id == "paper-lamp"
        filtered = await browser.browse(
            tenant_id=tenant_id, query=CatalogBrowseQuery(q="lunar", category="Lighting")
        )
        assert filtered.total == 1
        literal = await browser.browse(tenant_id=tenant_id, query=CatalogBrowseQuery(q="%"))
        assert literal.total == 0
        discovery = await DurableShopperAgentService(database, search_service=search).discovery(
            tenant_id=tenant_id, account_id=uuid4()
        )
        assert discovery.catalog_status == "ready"
        assert discovery.conversation_mode == "basic"
        assert discovery.product_count == 2
        assert discovery.suggestions[0].category == "Lighting"
        assert discovery.suggestions[0].image_url == "https://example.test/lunar.jpg"

        provider = create_autospec(ManagerModelProvider, instance=True)
        configured_discovery = await DurableShopperAgentService(
            database, search_service=search, model_provider=provider
        ).discovery(tenant_id=tenant_id, account_id=uuid4())
        assert configured_discovery.conversation_mode == "model_configured"
        assert configured_discovery.suggestions == discovery.suggestions
        provider.begin.assert_not_called()

        replay = await manager.profile_dataset(
            tenant_id=tenant_id,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog", filename="catalog.csv", csv_text=first_csv
            ),
            idempotency_key="upload-identical-catalog-again",
        )
        assert replay.catalog_index.catalog_id == profiled.catalog_index.catalog_id
        assert replay.catalog_index.status == "ready"

        other_tenant = uuid4()
        await database.initialize_tenant(other_tenant)
        other_workspace = await manager.get_workspace(tenant_id=other_tenant)
        assert other_workspace.catalog_index.status == "not_configured"
        other_discovery = await DurableShopperAgentService(
            database, search_service=search
        ).discovery(tenant_id=other_tenant, account_id=uuid4())
        assert other_discovery.catalog_status == "not_configured"
        assert other_discovery.conversation_mode == "basic"
        assert other_discovery.suggestions == []
        other_browse = await browser.browse(tenant_id=other_tenant, query=CatalogBrowseQuery())
        assert other_browse.catalog is None
        assert other_browse.items == []

        result = await search.search(
            tenant_id=tenant_id,
            request=SearchRequest(query="focused warm desk light", debug=True),
        )
        assert result.results[0].product_id == "lunar-lamp"
        assert result.results[0].title == "Lunar Reading Lamp"
        assert result.trace is not None
        assert result.trace.retrieval["catalog_id"] == str(profiled.catalog_index.catalog_id)

        replacement = await manager.profile_dataset(
            tenant_id=tenant_id,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="replacement.csv",
                csv_text=(
                    "product_id,variant_id,title,description,price,currency,"
                    "inventory_quantity,updated_at\n"
                    "solar-lamp,solar-lamp-1,Solar Task Lamp,"
                    "Bright task lighting for studio work,99,USD,8,"
                    "2026-09-02T12:00:00Z\n"
                ),
            ),
            idempotency_key="upload-replacement-catalog",
        )
        assert replacement.catalog_index.status == "queued"
        assert replacement.catalog_index.catalog_id != profiled.catalog_index.catalog_id
        during = await browser.browse(tenant_id=tenant_id, query=CatalogBrowseQuery())
        assert during.catalog == published.catalog
        assert during.items == published.items
        assert during.indexing.status == "queued"
        assert during.indexing.filename == "replacement.csv"
        during_discovery = await DurableShopperAgentService(
            database, search_service=search
        ).discovery(tenant_id=tenant_id, account_id=uuid4())
        assert during_discovery.catalog_status == "ready"
        assert during_discovery.product_count == 2
        assert during_discovery.catalog_name == "catalog.csv"

        while_queued = await search.search(
            tenant_id=tenant_id,
            request=SearchRequest(query="desk lamp", debug=True),
        )
        assert while_queued.trace is not None
        assert while_queued.trace.retrieval["catalog_id"] == str(profiled.catalog_index.catalog_id)

        assert replacement.catalog_index.job_id is not None
        assert await runner.run_catalog_index(replacement.catalog_index.job_id)
        after_replacement = await search.search(
            tenant_id=tenant_id,
            request=SearchRequest(query="bright studio task lighting", debug=True),
        )
        assert after_replacement.results[0].product_id == "solar-lamp"
        replaced = await browser.browse(tenant_id=tenant_id, query=CatalogBrowseQuery(offset=24))
        assert replaced.catalog is not None
        assert replaced.catalog.id == replacement.catalog_index.catalog_id
        assert replaced.catalog.filename == "replacement.csv"
        assert replaced.total == 1
        assert replaced.offset == 0
        assert [product.product_id for product in replaced.items] == ["solar-lamp"]
        assert after_replacement.trace is not None
        assert after_replacement.trace.retrieval["catalog_id"] == str(
            replacement.catalog_index.catalog_id
        )
    finally:
        if await search.client.collection_exists(collection):
            await search.client.delete_collection(collection)
        await search.close()
        await database.close()


async def test_index_count_mismatch_retries_without_activating_catalog(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        manager = DurableManagerAgentService(database)
        thread = await manager.create_thread(
            tenant_id=tenant_id,
            request=ManagerThreadCreateRequest(title="Catalog count guard"),
            idempotency_key="create-count-guard-thread",
        )
        profiled = await manager.profile_dataset(
            tenant_id=tenant_id,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="catalog.csv",
                csv_text=(
                    "product_id,title,price,currency,updated_at\n"
                    "lamp,Reading Lamp,79,USD,2026-09-01T12:00:00Z\n"
                    "desk,Standing Desk,499,USD,2026-09-01T12:00:00Z\n"
                ),
            ),
            idempotency_key="upload-count-guard-catalog",
        )
        assert profiled.catalog_index.job_id is not None
        runner = JobRunner(
            database,
            tenant_id,
            search_service=cast(DurableSearchService, _CountMismatchSearch()),
        )

        with pytest.raises(ValueError, match="count does not match"):
            await runner.run_catalog_index(profiled.catalog_index.job_id)

        async with database.transaction(tenant_id) as session:
            status = await catalog_index_status(
                session,
                tenant_id=tenant_id,
                integration_id=profiled.catalog_index.catalog_id,
            )
            assert status.status == "queued"
            assert status.error_code == "ValueError"
            assert await active_catalog_integration(session, tenant_id=tenant_id) is None
        browse = await CatalogBrowseService(database).browse(
            tenant_id=tenant_id, query=CatalogBrowseQuery()
        )
        assert browse.catalog is None
        assert browse.items == []
        assert browse.indexing.error_code == "ValueError"
    finally:
        await database.close()
