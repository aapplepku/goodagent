"""Durable engagement upload, CPU training, exact approval and shared search serving."""

import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.models import (
    ManagerDatasetProfileRequest,
    ManagerMessageRequest,
    ManagerThreadCreateRequest,
)
from open_commerce.manager_agent.runs import ManagerRunService, run_row
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.models import RankingApproval, RankingDataError, TrainRankingInput
from open_commerce.ranking.service import RankingService
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import SearchRequest
from open_commerce.worker.jobs import JobRunner

from .test_manager_runs import call, message, provider

pytestmark = pytest.mark.integration


def engagement_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["event_id", "event_type", "occurred_at", "product_id", "session_id"])
    for index in range(600):
        product = "high" if index % 2 else "low"
        at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
        kinds = ["product_view"]
        if (product == "high" and index % 10 != 1) or (product == "low" and index % 20 == 0):
            kinds.extend(["add_to_cart", "purchase"])
        for offset, kind in enumerate(kinds):
            writer.writerow(
                [
                    f"event-{index}-{offset}",
                    kind,
                    (at + timedelta(minutes=offset)).isoformat(),
                    product,
                    f"session-{index}",
                ]
            )
    return output.getvalue()


async def test_build_preview_approval_replay_and_tenant_catalog_isolation(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    collection = f"ranking_{uuid4().hex}"
    search = DurableSearchService(database, collection_name=collection)
    manager = DurableManagerAgentService(database)
    ranking = RankingService(database)
    try:
        await database.initialize_tenant(tenant)
        thread = await manager.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title="Search models"),
            idempotency_key="thread",
        )
        catalog = await manager.profile_dataset(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="catalog",
                filename="coffee.csv",
                csv_text=(
                    "product_id,title,price,currency,inventory_quantity\n"
                    "high,High Coffee,12,USD,10\nlow,Low Coffee,12,USD,10\n"
                ),
            ),
            idempotency_key="catalog",
        )
        assert catalog.catalog_index.job_id
        await JobRunner(database, tenant, search_service=search).run_catalog_index(
            catalog.catalog_index.job_id
        )
        await manager.profile_dataset(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerDatasetProfileRequest(
                dataset_kind="engagement", filename="engagement.csv", csv_text=engagement_csv()
            ),
            idempotency_key="engagement",
        )
        overview = await ranking.overview(tenant)
        assert overview.dataset and overview.dataset.event_count > 600
        assert "session-" not in overview.model_dump_json()
        request = TrainRankingInput(
            goal="Increase purchases from search", target="purchase", method="logistic_regression"
        )
        job = await ranking.submit(tenant, request, "train")
        assert (await ranking.submit(tenant, request, "train")).id == job.id
        assert await ranking.run(tenant, job.id)
        assert not await RankingService(database).run(tenant, job.id)
        trained = (await ranking.overview(tenant)).models[0]
        assert trained.status == "ready" and trained.metrics["eligible_for_activation"]
        assert not trained.active
        baseline = await search.search(
            tenant_id=tenant, request=SearchRequest(query="coffee", debug=True)
        )
        preview = await search.search(
            tenant_id=tenant,
            request=SearchRequest(query="coffee", debug=True),
            preview_model_id=trained.id,
        )
        assert str(trained.id) not in baseline.ranking_version
        assert str(trained.id) in preview.ranking_version
        assert any(item.score_components.engagement_boost > 0 for item in preview.results)
        approval = RankingApproval(
            model_id=trained.id,
            expected_active_id=None,
            artifact_hash=trained.artifact_hash,
            confirm="APPLY_LOCAL_RANKING",
        )
        with pytest.raises(RankingDataError, match="Exact artifact"):
            await ranking.approve(
                tenant,
                approval.model_copy(update={"artifact_hash": "sha256:" + "0" * 64}),
                "bad-hash",
            )
        await ranking.approve(tenant, approval, "apply")
        await ranking.approve(tenant, approval, "apply")
        served = await search.search(
            tenant_id=tenant, request=SearchRequest(query="coffee", debug=True)
        )
        assert served.ranking_version == preview.ranking_version
        blocked = await search.search(
            tenant_id=tenant, request=SearchRequest(query="coffee under $1", debug=True)
        )
        assert not blocked.results
        other = uuid4()
        await database.initialize_tenant(other)
        assert (await ranking.overview(other)).models == []
        with pytest.raises(RankingDataError):
            await ranking.approve(other, approval, "cross-tenant")
        # A failed candidate never replaces the explicitly selected usable ranker.
        bad = await ranking.submit(
            tenant,
            TrainRankingInput(goal="Increase clicks", target="click", method="logistic_regression"),
            "bad-fit",
        )
        assert not await ranking.run(tenant, bad.id)
        assert any(model.active for model in (await ranking.overview(tenant)).models)
        await ranking.approve(
            tenant,
            RankingApproval(
                model_id=None, expected_active_id=trained.id, confirm="DISABLE_LOCAL_RANKING"
            ),
            "disable",
        )
        restored = await search.search(tenant_id=tenant, request=SearchRequest(query="coffee"))
        assert restored.ranking_version == baseline.ranking_version

        model_provider = provider(
            [
                call("inspect_ranking_signals", {}, "signals"),
                call("train_search_ranker", request.model_dump(mode="json"), "train"),
                message("The evaluated candidate is ready for review, not activated."),
            ]
        )
        agent_service = DurableManagerAgentService(
            database, model_provider=model_provider, search_service=search
        )
        runs = ManagerRunService(database)
        agent_run = await runs.submit(
            tenant_id=tenant,
            thread_id=thread.thread.id,
            request=ManagerMessageRequest(content=f"{request.goal}. Build a ranking model."),
            idempotency_key="agent-fit",
        )
        assert not await runs.process(tenant_id=tenant, run_id=agent_run.id, service=agent_service)
        assert (await runs.get(tenant_id=tenant, run_id=agent_run.id)).status == "waiting"
        queued = (await ranking.overview(tenant)).models[0]
        assert queued.status == "queued"
        assert await ranking.run(tenant, queued.id)
        async with database.transaction(tenant, write=True) as session:
            checkpoint = await run_row(session, tenant, agent_run.id)
            checkpoint.available_at = utc_now()
        restarted = DurableManagerAgentService(
            database, model_provider=model_provider, search_service=search
        )
        assert await runs.process(tenant_id=tenant, run_id=agent_run.id, service=restarted)
        assert (await runs.get(tenant_id=tenant, run_id=agent_run.id)).status == "completed"
        assert not any(item.active for item in (await ranking.overview(tenant)).models)
        events = await runs.events(tenant_id=tenant, run_id=agent_run.id)
        assert (
            sum(
                item.tool == "train_search_ranker" and item.kind == "tool_started"
                for item in events.items
            )
            == 1
        )
        assert "session-" not in events.model_dump_json()
        assert "synthetic-test-only" not in events.model_dump_json()
    finally:
        await search.client.delete_collection(collection_name=collection)
        await search.close()
        await database.close()
