"""Search, recommendation, event, and search-rule API routes."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.pagination import paginate_items
from open_commerce.api.services import SearchRuntime as SearchService
from open_commerce.api.services import resolve
from open_commerce.search.models import (
    EvaluateSearchRequest,
    EventBatchRequest,
    EventBatchResponse,
    ParseSearchResponse,
    RecommendationRequest,
    RecommendationResponse,
    ResultSetEvaluation,
    SearchRequest,
    SearchResponse,
    SearchRuleListResponse,
)

router = APIRouter(tags=["search"])
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]


def get_search_service(request: Request) -> SearchService:
    """Return the app-level search service."""

    return cast(SearchService, request.app.state.search_service)


@router.post("/v1/search", response_model=SearchResponse)
async def search_products(
    payload: SearchRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    """Search tenant-scoped products."""

    return await service.search(tenant_id=context.tenant_id, request=payload)


@router.post("/v1/search/parse", response_model=ParseSearchResponse)
async def parse_search(
    payload: SearchRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
) -> ParseSearchResponse:
    """Parse a search query without touching indexed documents."""

    return await service.parse(tenant_id=context.tenant_id, request=payload)


@router.post("/v1/search/evaluate", response_model=ResultSetEvaluation)
async def evaluate_search(
    payload: EvaluateSearchRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
) -> ResultSetEvaluation:
    """Evaluate a search result set."""

    return await service.evaluate(tenant_id=context.tenant_id, request=payload)


@router.post("/v1/recommendations", response_model=RecommendationResponse)
async def recommend_products(
    payload: RecommendationRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
) -> RecommendationResponse:
    """Return tenant-scoped product recommendations."""

    return await service.recommendations(tenant_id=context.tenant_id, request=payload)


@router.post("/v1/events/batch", response_model=EventBatchResponse)
async def ingest_event_batch(
    payload: EventBatchRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
) -> EventBatchResponse:
    """Ingest pseudonymous search/product events."""

    return await service.ingest_events(
        tenant_id=context.tenant_id, request=payload, idempotency_key=idempotency_key
    )


@router.get("/v1/search/rules", response_model=SearchRuleListResponse)
async def list_search_rules(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SearchService, Depends(get_search_service)],
    cursor: str | None = None,
    goal_context_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> SearchRuleListResponse:
    """List tenant-scoped search rules."""

    response = await resolve(
        service.list_rules(tenant_id=context.tenant_id, goal_context_id=goal_context_id)
    )
    items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
    return SearchRuleListResponse(items=items, next_cursor=next_cursor)
