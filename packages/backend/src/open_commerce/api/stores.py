"""Owner-controlled setup plus a minimal public store discovery boundary."""

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import Field, SecretStr
from sqlalchemy import select

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.store_auth import current_owner
from open_commerce.api.store_cookies import secure_cookie, store_cookie
from open_commerce.core.types import StrictDomainModel, utc_now
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord, CatalogImportRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.store_setup import AuthTicketRecord
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.stores.import_models import ImportConfirmRequest, ImportMapping, ImportReview
from open_commerce.stores.import_validation import MAX_UPLOAD
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.measurement import (
    MonitoringPreset,
    StoreMeasurements,
    check_monitors,
    configure_monitor,
    measurements,
)
from open_commerce.stores.models import (
    OwnerIdentity,
    PreviewResponse,
    PublicationRequest,
    StoreError,
    StoreProfile,
    StoreProfileUpdate,
)
from open_commerce.stores.setup import StoreReadiness, StoreSetupService

router = APIRouter(tags=["store-setup"])
Owner = Annotated[OwnerIdentity, Depends(current_owner)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=150)]


@router.get("/v1/merchant/store/measurements", response_model=StoreMeasurements)
async def get_measurements(request: Request, owner: Owner) -> StoreMeasurements:
    return await measurements(request.app.state.database, owner.tenant_id)


@router.put("/v1/merchant/store/monitors", response_model=StoreReadiness)
async def setup_monitor(
    payload: MonitoringPreset, request: Request, owner: Owner
) -> StoreReadiness:
    db = request.app.state.database
    await configure_monitor(db, owner.tenant_id, payload)
    await check_monitors(db, owner.tenant_id)
    return await StoreSetupService(db).readiness(owner.tenant_id)


class CatalogSelection(StrictDomainModel):
    catalog_id: UUID


class AIConnection(StrictDomainModel):
    configured: bool
    connected: bool
    detail: str


@router.post("/v1/merchant/store/check-ai", response_model=AIConnection)
async def check_ai(request: Request, owner: Owner) -> AIConnection:
    from open_commerce.manager_agent.model_provider import ManagerModelMessage
    from open_commerce.runtime_services import manager_model_provider
    from open_commerce.stores.setup import store_records
    from open_commerce.stores.usage import model_scope

    db = request.app.state.database
    provider = manager_model_provider(db.settings)
    connected = False
    detail = "Configure the server-side AI credential, then retry this check."
    if provider:
        try:
            with model_scope(db, owner.tenant_id):
                turn = await provider.begin(
                    instructions="Reply with a short greeting. No tools or private data.",
                    messages=[ManagerModelMessage(role="user", content="Hello")],
                    tools=[],
                    max_output_tokens=128,
                ).next([])
                connected = bool(turn.content and not turn.tool_calls)
                detail = (
                    "Connection verified."
                    if connected
                    else "Provider returned no usable answer. Retry the check."
                )
        except Exception:
            detail = (
                "AI connection could not be verified. "
                "Check server configuration and usage limits, then retry."
            )
    async with db.transaction(owner.tenant_id, write=True) as session:
        _, setup = await store_records(session, owner.tenant_id)
        setup.readiness = {
            **setup.readiness,
            "ai_verified": connected,
            "ai_checked_at": utc_now().isoformat(),
            "ai_detail": detail,
        }
    return AIConnection(configured=provider is not None, connected=connected, detail=detail)


class PreviewExchange(StrictDomainModel):
    token: SecretStr = Field(min_length=1, max_length=200)


class Storefront(StrictDomainModel):
    slug: str
    name: str
    description: str
    currency: str
    preview: bool = False
    sample_data: bool = False
    checkout_mode: str = "demo"


@router.get("/v1/merchant/store", response_model=StoreReadiness)
async def get_store(request: Request, owner: Owner) -> StoreReadiness:
    return await StoreSetupService(request.app.state.database).readiness(owner.tenant_id)


@router.patch("/v1/merchant/store", response_model=StoreProfile)
async def update_store(payload: StoreProfileUpdate, request: Request, owner: Owner) -> StoreProfile:
    return await StoreSetupService(request.app.state.database).profile(owner.tenant_id, payload)


@router.post("/v1/merchant/store/preview", response_model=PreviewResponse)
async def preview_store(
    payload: CatalogSelection, request: Request, owner: Owner
) -> PreviewResponse:
    return await StoreSetupService(request.app.state.database).preview(
        owner.tenant_id, payload.catalog_id
    )


@router.post("/v1/merchant/store/sharing", response_model=StoreProfile)
async def share_store(
    payload: PublicationRequest, request: Request, owner: Owner, idempotency_key: Key
) -> StoreProfile:
    return await StoreSetupService(request.app.state.database).share(
        owner.tenant_id, payload, idempotency_key
    )


@router.post("/v1/merchant/imports/upload", response_model=ImportReview, status_code=201)
async def upload_catalog(
    request: Request,
    owner: Owner,
    filename: Annotated[str, Query(min_length=1, max_length=255)] = "catalog.csv",
) -> ImportReview:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD:
            raise StoreError("Catalog exceeds 20 MiB.", 413)
        data.extend(chunk)
    return await CatalogImportService(request.app.state.database).upload(
        owner.tenant_id, filename, bytes(data)
    )


@router.post("/v1/merchant/imports/sample", response_model=ImportReview, status_code=201)
async def sample_catalog(request: Request, owner: Owner) -> ImportReview:
    from open_commerce.stores.sample import sample_catalog_bytes

    service = CatalogImportService(request.app.state.database)
    uploaded = await service.upload(
        owner.tenant_id, "explicit-abo-sample.csv", sample_catalog_bytes()
    )
    async with request.app.state.database.transaction(owner.tenant_id, write=True) as session:
        record = await service.get(session, owner.tenant_id, uploaded.id)
        record.report = {"sample_data": True}
    return uploaded.model_copy(update={"sample_data": True})


@router.get("/v1/merchant/imports/{import_id}", response_model=ImportReview)
async def get_import(import_id: UUID, request: Request, owner: Owner) -> ImportReview:
    return await CatalogImportService(request.app.state.database).review(owner.tenant_id, import_id)


@router.put("/v1/merchant/imports/{import_id}/mapping", response_model=ImportReview)
async def map_import(
    import_id: UUID, payload: ImportMapping, request: Request, owner: Owner
) -> ImportReview:
    return await CatalogImportService(request.app.state.database).review(
        owner.tenant_id, import_id, payload
    )


@router.post("/v1/merchant/imports/{import_id}/confirm", response_model=ImportReview)
async def confirm_import(
    import_id: UUID,
    payload: ImportConfirmRequest,
    request: Request,
    owner: Owner,
    idempotency_key: Key,
) -> ImportReview:
    return await CatalogImportService(request.app.state.database).confirm(
        owner.tenant_id,
        import_id,
        idempotency_key,
        expected_review_fingerprint=payload.expected_review_fingerprint,
    )


@router.post("/v1/merchant/imports/{import_id}/retry", response_model=ImportReview)
async def retry_import(import_id: UUID, request: Request, owner: Owner) -> ImportReview:
    return await CatalogImportService(request.app.state.database).retry(owner.tenant_id, import_id)


@router.post("/v1/merchant/imports/{import_id}/cancel", response_model=ImportReview)
async def cancel_import(import_id: UUID, request: Request, owner: Owner) -> ImportReview:
    return await CatalogImportService(request.app.state.database).cancel(owner.tenant_id, import_id)


@router.post("/v1/stores/{slug}/preview", response_model=Storefront)
async def exchange_preview(
    slug: str, payload: PreviewExchange, request: Request, response: Response
) -> Storefront:
    db = request.app.state.database
    async with db.sessions() as session:
        tenant = await session.scalar(
            select(Tenant.id).where(Tenant.slug == slug, Tenant.status == "active")
        )
    if tenant is None:
        raise StoreError("Preview unavailable.", 404)
    async with db.transaction(tenant, write=True) as session:
        grant = await session.scalar(
            select(AuthTicketRecord).where(
                AuthTicketRecord.tenant_id == tenant,
                AuthTicketRecord.purpose == "shopper_preview",
                AuthTicketRecord.token_hash == session_token_hash(payload.token.get_secret_value()),
                AuthTicketRecord.expires_at > utc_now(),
                AuthTicketRecord.consumed_at.is_(None),
            )
        )
        if grant is None:
            raise StoreError(
                "Preview expired or already used. Open a new preview from store setup.", 401
            )
        grant.consumed_at = utc_now()
        token = secrets.token_urlsafe(32)
        session.add(
            AuthTicketRecord(
                token_hash=session_token_hash(token),
                tenant_id=tenant,
                purpose="preview_session",
                payload=grant.payload,
                expires_at=grant.expires_at,
                created_at=utc_now(),
            )
        )
        response.set_cookie(
            store_cookie(request, "open_commerce_preview", slug=slug),
            token,
            httponly=True,
            samesite="lax",
            secure=secure_cookie(db.settings, request),
            max_age=1800,
        )
        return await storefront(session, tenant, preview=True)


async def storefront(session: object, tenant: UUID, *, preview: bool = False) -> Storefront:
    from sqlalchemy.ext.asyncio import AsyncSession

    from open_commerce.stores.setup import store_records

    assert isinstance(session, AsyncSession)
    owner, setup = await store_records(session, tenant)
    return Storefront(
        slug=owner.slug,
        name=owner.display_name,
        description=setup.description,
        currency=owner.default_currency,
        preview=preview,
        sample_data=setup.sample_data,
    )


@router.get("/v1/shopper/store", response_model=Storefront)
async def get_storefront(
    request: Request, context: Annotated[RequestContext, Depends(get_request_context)]
) -> Storefront:
    async with request.app.state.database.transaction(context.tenant_id) as session:
        scope = getattr(request.state, "catalog_scope", None)
        result = await storefront(session, context.tenant_id, preview=bool(scope and scope.preview))
        result.sample_data = bool(scope and scope.sample)
        return result


@router.get("/v1/merchant/assets/{asset_id}")
async def get_owner_asset(asset_id: UUID, request: Request, owner: Owner) -> FileResponse:
    async with request.app.state.database.transaction(owner.tenant_id) as session:
        asset = await session.scalar(
            select(CatalogAssetRecord).where(
                CatalogAssetRecord.tenant_id == owner.tenant_id, CatalogAssetRecord.id == asset_id
            )
        )
        if asset is None:
            raise StoreError("Image not found.", 404)
    path = request.app.state.settings.asset_directory / str(owner.tenant_id) / f"{asset.id}.png"
    if not path.is_file():
        raise StoreError("Image unavailable.", 404)
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "private, no-store"}
    )


@router.get("/v1/shopper/assets/{asset_id}")
async def get_asset(
    asset_id: UUID,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> FileResponse:
    scope = getattr(request.state, "catalog_scope", None)
    if scope is None:
        raise StoreError("Open a store to view its images.", 404)
    async with request.app.state.database.transaction(context.tenant_id) as session:
        asset = await session.scalar(
            select(CatalogAssetRecord)
            .join(
                CatalogImportRecord,
                (CatalogImportRecord.id == CatalogAssetRecord.import_id)
                & (CatalogImportRecord.tenant_id == CatalogAssetRecord.tenant_id),
            )
            .where(
                CatalogAssetRecord.tenant_id == context.tenant_id,
                CatalogAssetRecord.id == asset_id,
                CatalogImportRecord.catalog_id == scope.catalog_id,
            )
        )
        if asset is None:
            raise StoreError("Image not found.", 404)
    path = request.app.state.settings.asset_directory / str(context.tenant_id) / f"{asset.id}.png"
    if not path.is_file():
        raise StoreError("Image unavailable.", 404)
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "private, no-store"}
    )
