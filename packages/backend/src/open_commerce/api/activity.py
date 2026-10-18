"""Scoped, privacy-preserving activity inspection and monitor configuration."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.manager import IdempotencyHeader, ManagerContext
from open_commerce.api.shopper import get_current_shopper
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.models import ShopperAccount
from open_commerce.telemetry.activity import ActivityRuleError, ActivityService
from open_commerce.telemetry.activity_models import (
    ActivityOverview,
    ActivityQuery,
    ActivityRule,
    ActivityRuleInput,
)

router = APIRouter(tags=["activity"])


def get_activity(request: Request) -> ActivityService:
    return ActivityService(cast(RuntimeDatabase, request.app.state.database))


@router.get("/v1/manager/activity", response_model=ActivityOverview)
async def manager_activity(
    context: ManagerContext,
    query: Annotated[ActivityQuery, Query()],
    service: Annotated[ActivityService, Depends(get_activity)],
) -> ActivityOverview:
    return await service.overview(tenant_id=context.tenant_id, account_id=None, query=query)


@router.post("/v1/manager/activity/rules", response_model=ActivityRule)
async def manager_activity_rule(
    payload: ActivityRuleInput,
    context: ManagerContext,
    idempotency_key: IdempotencyHeader,
    service: Annotated[ActivityService, Depends(get_activity)],
) -> ActivityRule:
    try:
        return await service.configure(
            tenant_id=context.tenant_id, account_id=None, definition=payload, key=idempotency_key
        )
    except ActivityRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/v1/shopper/activity", response_model=ActivityOverview)
async def shopper_activity(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    query: Annotated[ActivityQuery, Query()],
    service: Annotated[ActivityService, Depends(get_activity)],
) -> ActivityOverview:
    return await service.overview(tenant_id=context.tenant_id, account_id=account.id, query=query)


@router.post("/v1/shopper/activity/rules", response_model=ActivityRule)
async def shopper_activity_rule(
    payload: ActivityRuleInput,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    idempotency_key: IdempotencyHeader,
    service: Annotated[ActivityService, Depends(get_activity)],
) -> ActivityRule:
    try:
        return await service.configure(
            tenant_id=context.tenant_id,
            account_id=account.id,
            definition=payload,
            key=idempotency_key,
            account_version=account._data_version,
        )
    except ActivityRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
