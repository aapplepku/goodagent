"""Local operator ranking builds and exact-version approval, never model-authorized activation."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from open_commerce.api.manager import IdempotencyHeader, ManagerContext
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.models import (
    RankingApproval,
    RankingModel,
    RankingOverview,
    RankingPreviewInput,
    TrainRankingInput,
)
from open_commerce.ranking.preview import RankingPreview, preview
from open_commerce.ranking.service import RankingService

router = APIRouter(prefix="/v1/manager/ranking", tags=["manager-ranking"])


def get_ranking_service(request: Request) -> RankingService:
    return RankingService(cast(RuntimeDatabase, request.app.state.database))


@router.get("", response_model=RankingOverview)
async def ranking_overview(
    context: ManagerContext, service: Annotated[RankingService, Depends(get_ranking_service)]
) -> RankingOverview:
    return await service.overview(context.tenant_id)


@router.post("/train", response_model=RankingModel, status_code=202)
async def train_ranking(
    payload: TrainRankingInput,
    context: ManagerContext,
    idempotency_key: IdempotencyHeader,
    service: Annotated[RankingService, Depends(get_ranking_service)],
) -> RankingModel:
    return await service.submit(context.tenant_id, payload, idempotency_key)


@router.post("/approve", response_model=RankingOverview)
async def approve_ranking(
    payload: RankingApproval,
    context: ManagerContext,
    idempotency_key: IdempotencyHeader,
    service: Annotated[RankingService, Depends(get_ranking_service)],
) -> RankingOverview:
    return await service.approve(context.tenant_id, payload, idempotency_key)


@router.post("/preview", response_model=RankingPreview)
async def preview_ranking(
    payload: RankingPreviewInput,
    context: ManagerContext,
    service: Annotated[RankingService, Depends(get_ranking_service)],
) -> RankingPreview:
    return await preview(service.database, context.tenant_id, payload)
