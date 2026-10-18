"""Local operator-only read-only catalog connectors."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from open_commerce.api.manager import IdempotencyHeader, ManagerContext
from open_commerce.catalog.intake import CatalogIntake
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.catalog.sources import CatalogConnection
from open_commerce.persistence.runtime_db import RuntimeDatabase

router = APIRouter(prefix="/v1/manager/connectors", tags=["manager-connectors"])


def get_intake(request: Request) -> CatalogIntake:
    return CatalogIntake(cast(RuntimeDatabase, request.app.state.database))


@router.post("/shopify/check", response_model=CatalogConnection)
async def check_shopify(
    context: ManagerContext, service: Annotated[CatalogIntake, Depends(get_intake)]
) -> CatalogConnection:
    return await service.check(context.tenant_id)


@router.post("/shopify/import", response_model=CatalogIndexStatus, status_code=202)
async def import_shopify(
    context: ManagerContext,
    idempotency_key: IdempotencyHeader,
    service: Annotated[CatalogIntake, Depends(get_intake)],
) -> CatalogIndexStatus:
    return await service.load(context.tenant_id, idempotency_key)
