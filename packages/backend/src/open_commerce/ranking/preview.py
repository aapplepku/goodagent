"""Operator-only baseline/candidate search comparison without serving changes."""

from uuid import UUID

from open_commerce.core.types import StrictDomainModel
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.models import RankingPreviewInput
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import SearchRequest, SearchResponse


class RankingPreview(StrictDomainModel):
    baseline: SearchResponse
    candidate: SearchResponse


async def preview(
    database: RuntimeDatabase, tenant_id: UUID, request: RankingPreviewInput
) -> RankingPreview:
    search = DurableSearchService(database)
    try:
        query = SearchRequest(query=request.query, top_k=10, debug=True)
        baseline = await search.search(tenant_id=tenant_id, request=query, baseline=True)
        candidate = await search.search(
            tenant_id=tenant_id, request=query, preview_model_id=request.model_id
        )
        if (
            baseline.trace
            and candidate.trace
            and baseline.trace.retrieval.get("catalog_version")
            != candidate.trace.retrieval.get("catalog_version")
        ):
            from open_commerce.ranking.models import RankingDataError

            raise RankingDataError("Catalog changed during preview; retry the comparison.")
        return RankingPreview(baseline=baseline, candidate=candidate)
    finally:
        await search.close()
