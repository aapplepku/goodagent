"""Shopper account, memory, and conversational search routes."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response, status

from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.shopper_activity import ShopperActivityRoute
from open_commerce.api.store_cookies import secure_cookie, store_cookie
from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.browse_models import CatalogBrowseQuery, CatalogBrowseResponse
from open_commerce.commerce.models import (
    Cart,
    CartItemAddRequest,
    CartItemUpdateRequest,
    CheckoutConfirmation,
    CheckoutConfirmRequest,
    CheckoutPreview,
    CheckoutPreviewRequest,
    CheckoutRecovery,
    CommerceRuntime,
    ShopperOrderList,
    ShopperOrderQuery,
)
from open_commerce.config import Settings
from open_commerce.shopper_agent.errors import ShopperAuthenticationError
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAgentRuntime,
    ShopperAuthResponse,
    ShopperChatRequest,
    ShopperChatResponse,
    ShopperConversationDetail,
    ShopperConversationList,
    ShopperDiscoveryResponse,
    ShopperGuestResponse,
    ShopperLoginRequest,
    ShopperMemoryDeleteResponse,
    ShopperMemoryList,
    ShopperRegisterRequest,
)
from open_commerce.stores.models import SessionList
from open_commerce.stores.shoppers import (
    ContinuityResponse,
    MergeSelection,
    PreferenceSettings,
    ShopperAccounts,
    ShopperRecovery,
)

router = APIRouter(prefix="/v1/shopper", tags=["shopper-agent"], route_class=ShopperActivityRoute)
SESSION_COOKIE = "open_commerce_shopper_session"
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]
ExpectedAccountHeader = Annotated[
    UUID | None,
    Header(
        alias="X-Shopper-Account-Id",
        description="Expected current shopper; a precondition, not authentication.",
    ),
]


def get_shopper_agent_service(request: Request) -> ShopperAgentRuntime:
    return cast(ShopperAgentRuntime, request.app.state.shopper_agent_service)


def get_commerce_service(request: Request) -> CommerceRuntime:
    return cast(CommerceRuntime, request.app.state.commerce_service)


async def get_current_shopper(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    expected_account_id: ExpectedAccountHeader = None,
) -> ShopperAccount:
    if request.app.state.settings.runtime_profile != "legacy_demo":
        session_token = request.cookies.get(store_cookie(request, SESSION_COOKIE))
    if session_token is None:
        raise ShopperAuthenticationError("Sign in to continue")
    account = await service.authenticate(tenant_id=context.tenant_id, raw_token=session_token)
    if request.app.state.settings.runtime_profile != "legacy_demo":
        async with request.app.state.database.transaction(context.tenant_id) as session:
            await ShopperAccounts(request.app.state.database).account(
                session, context.tenant_id, account.id, account_version=account._data_version
            )
    if expected_account_id is not None and expected_account_id != account.id:
        raise ShopperAuthenticationError("Your shopping session changed. Check your session again.")
    request.state.shopper_activity_identity = (context.tenant_id, account.id)
    request.state.shopper_activity_version = account._data_version
    return account


async def get_bound_shopper(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    expected_account_id: ExpectedAccountHeader = None,
) -> ShopperAccount | None:
    """Check a supplied binding before auth transitions; allow explicit unbound auth."""
    if expected_account_id is None:
        return None
    return await get_current_shopper(request, context, service, session_token, expected_account_id)


@router.get("/orders", response_model=ShopperOrderList)
async def shopper_orders(
    query: Annotated[ShopperOrderQuery, Query()],
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> ShopperOrderList:
    return await service.orders(
        tenant_id=context.tenant_id, account_id=account.id, limit=query.limit, offset=query.offset
    )


@router.post("/product-selections", status_code=204)
async def record_product_selection(
    payload: CartItemAddRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> None:
    from open_commerce.stores.models import StoreError
    from open_commerce.telemetry.activity import ActivityRuleError, ActivityService
    from open_commerce.telemetry.activity_models import ActivityEventInput, ActivityKind

    products = await CatalogBrowseService(request.app.state.database).browse(
        tenant_id=context.tenant_id,
        query=CatalogBrowseQuery(product_id=payload.product_id, limit=1),
    )
    if not products.items:
        raise StoreError("Product not found.", 404)
    try:
        await ActivityService(request.app.state.database).record(
            tenant_id=context.tenant_id,
            account_id=account.id,
            event=ActivityEventInput(kind=ActivityKind.PRODUCT_SELECT, status="ok", duration_ms=0),
            key=f"selection:{idempotency_key}",
            account_version=account._data_version,
        )
    except ActivityRuleError as exc:
        raise StoreError(str(exc), 401) from exc


@router.post("/auth/register", response_model=ShopperAuthResponse, status_code=201)
async def register_shopper(
    payload: ShopperRegisterRequest,
    response: Response,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
    bound_account: Annotated[ShopperAccount | None, Depends(get_bound_shopper)],
) -> ShopperAuthResponse:
    if request.app.state.settings.runtime_profile != "legacy_demo":
        account = bound_account or await service.authenticate(
            tenant_id=context.tenant_id,
            raw_token=request.cookies.get(store_cookie(request, SESSION_COOKIE), ""),
        )
        result, raw_token = await ShopperAccounts(request.app.state.database).upgrade(
            context.tenant_id, account.id, payload
        )
        _set_session_cookie(response, request.app.state.settings, raw_token, request)
        return result
    result, raw_token = await service.register(tenant_id=context.tenant_id, request=payload)
    _set_session_cookie(response, request.app.state.settings, raw_token, request)
    return result


@router.post("/auth/login", response_model=ContinuityResponse)
async def login_shopper(
    payload: ShopperLoginRequest,
    response: Response,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
    bound_account: Annotated[ShopperAccount | None, Depends(get_bound_shopper)],
) -> ContinuityResponse:
    if request.app.state.settings.runtime_profile != "legacy_demo":
        guest = bound_account
        if guest is None:
            try:
                guest = await service.authenticate(
                    tenant_id=context.tenant_id,
                    raw_token=request.cookies.get(store_cookie(request, SESSION_COOKIE), ""),
                )
            except ShopperAuthenticationError:
                pass
        result, token = await ShopperAccounts(request.app.state.database).login(
            context.tenant_id, guest.id if guest else None, payload
        )
        if token:
            _set_session_cookie(response, request.app.state.settings, token, request)
        return result
    legacy_result, raw_token = await service.login(tenant_id=context.tenant_id, request=payload)
    _set_session_cookie(response, request.app.state.settings, raw_token, request)
    return ContinuityResponse.model_validate(legacy_result.model_dump())


@router.post(
    "/auth/guest",
    response_model=ShopperGuestResponse,
    dependencies=[Depends(get_bound_shopper)],
)
async def guest_shopper(
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> ShopperGuestResponse:
    result, token = await ShopperAccounts(request.app.state.database).guest(
        context.tenant_id, request.cookies.get(store_cookie(request, SESSION_COOKIE))
    )
    if token:
        _set_session_cookie(response, request.app.state.settings, token, request)
    return ShopperGuestResponse(
        account=result.account, recovery_code=result.recovery_code, created=token is not None
    )


@router.post("/auth/merge", response_model=ContinuityResponse)
async def merge_shopper(
    payload: MergeSelection,
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> ContinuityResponse:
    result, token = await ShopperAccounts(request.app.state.database).merge(
        context.tenant_id, account.id, payload
    )
    _set_session_cookie(response, request.app.state.settings, token, request)
    return result


@router.patch("/preferences", response_model=ShopperAuthResponse)
async def set_preferences(
    payload: PreferenceSettings,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> ShopperAuthResponse:
    result = await ShopperAccounts(request.app.state.database).preferences(
        context.tenant_id, account.id, payload.enabled, idempotency_key=idempotency_key
    )
    return ShopperAuthResponse(account=result)


@router.delete("/shopping-data", status_code=204)
async def delete_shopping_data(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> None:
    await ShopperAccounts(request.app.state.database).delete_data(context.tenant_id, account.id)


@router.get("/auth/sessions", response_model=SessionList)
async def shopper_sessions(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> SessionList:
    return await ShopperAccounts(request.app.state.database).sessions(
        context.tenant_id,
        account.id,
        request.cookies.get(store_cookie(request, SESSION_COOKIE), ""),
    )


@router.delete("/auth/sessions", status_code=204)
async def revoke_shopper_sessions(
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> None:
    async with request.app.state.database.transaction(context.tenant_id, write=True) as session:
        await ShopperAccounts(request.app.state.database).revoke(
            session, context.tenant_id, account.id
        )


@router.post("/auth/recover", response_model=ShopperAuthResponse)
async def recover_shopper(
    payload: ShopperRecovery,
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> ShopperAuthResponse:
    result, token = await ShopperAccounts(request.app.state.database).recover(
        context.tenant_id, payload
    )
    _set_session_cookie(response, request.app.state.settings, token, request)
    return result


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_bound_shopper)],
)
async def logout_shopper(
    request: Request,
    response: Response,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    if request.app.state.settings.runtime_profile != "legacy_demo":
        session_token = request.cookies.get(store_cookie(request, SESSION_COOKIE))
    if session_token is not None:
        await service.logout(tenant_id=context.tenant_id, raw_token=session_token)
    response.delete_cookie(store_cookie(request, SESSION_COOKIE), path="/", samesite="strict")


@router.get("/me", response_model=ShopperAuthResponse)
async def get_shopper_account(
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
) -> ShopperAuthResponse:
    return ShopperAuthResponse(account=account)


@router.get("/conversations", response_model=ShopperConversationList)
async def list_shopper_conversations(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperConversationList:
    return await service.list_conversations(tenant_id=context.tenant_id, account_id=account.id)


@router.get("/conversations/{conversation_id}", response_model=ShopperConversationDetail)
async def get_shopper_conversation(
    conversation_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperConversationDetail:
    return await service.get_conversation(
        tenant_id=context.tenant_id,
        account_id=account.id,
        conversation_id=conversation_id,
    )


@router.get("/memories", response_model=ShopperMemoryList)
async def list_shopper_memories(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperMemoryList:
    return await service.list_memories(tenant_id=context.tenant_id, account_id=account.id)


@router.get("/discovery", response_model=ShopperDiscoveryResponse)
async def get_shopper_discovery(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperDiscoveryResponse:
    """Return starter prompts grounded in the manager's active catalog."""

    return await service.discovery(tenant_id=context.tenant_id, account_id=account.id)


@router.get("/catalog", response_model=CatalogBrowseResponse)
async def browse_shopper_catalog(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    query: Annotated[CatalogBrowseQuery, Query()],
    service: Annotated[CatalogBrowseService, Depends(get_catalog_browser)],
) -> CatalogBrowseResponse:
    """The store's published products, available only to signed-in shoppers."""
    del account  # Authentication is required; product reads are shared within the tenant.
    return await service.browse(tenant_id=context.tenant_id, query=query)


@router.get("/cart", response_model=Cart)
async def get_shopper_cart(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> Cart:
    """Return the authenticated shopper's open cart."""

    return await service.get_cart(tenant_id=context.tenant_id, account_id=account.id)


@router.post("/cart/items", response_model=Cart)
async def add_shopper_cart_item(
    payload: CartItemAddRequest,
    idempotency_key: IdempotencyHeader,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> Cart:
    """Add a server-priced active-catalog product to the open cart."""

    return await service.add_item(
        tenant_id=context.tenant_id,
        account_id=account.id,
        request=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.patch("/cart/items/{line_id}", response_model=Cart)
async def update_shopper_cart_item(
    line_id: UUID,
    payload: CartItemUpdateRequest,
    idempotency_key: IdempotencyHeader,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> Cart:
    """Change a cart quantity after re-reading price and observed stock."""

    return await service.update_item(
        tenant_id=context.tenant_id,
        account_id=account.id,
        line_id=line_id,
        request=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.delete("/cart/items/{line_id}", response_model=Cart)
async def delete_shopper_cart_item(
    line_id: UUID,
    idempotency_key: IdempotencyHeader,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> Cart:
    """Remove one account-scoped cart line."""

    return await service.delete_item(
        tenant_id=context.tenant_id,
        account_id=account.id,
        line_id=line_id,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.post("/checkout/preview", response_model=CheckoutPreview)
async def preview_shopper_checkout(
    payload: CheckoutPreviewRequest,
    idempotency_key: IdempotencyHeader,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> CheckoutPreview:
    """Validate price/stock and create a short-lived local reservation."""

    return await service.preview_checkout(
        tenant_id=context.tenant_id,
        account_id=account.id,
        request=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.get("/checkout/current", response_model=CheckoutRecovery | None)
async def current_shopper_checkout(
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> CheckoutRecovery | None:
    return await service.checkout_status(tenant_id=context.tenant_id, account_id=account.id)


@router.get("/checkout/{checkout_id}", response_model=CheckoutRecovery)
async def get_shopper_checkout(
    checkout_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> CheckoutRecovery:
    result = await service.checkout_status(
        tenant_id=context.tenant_id, account_id=account.id, checkout_id=checkout_id
    )
    assert result is not None
    return result


@router.post("/checkout/confirm", response_model=CheckoutConfirmation)
async def confirm_shopper_checkout(
    payload: CheckoutConfirmRequest,
    idempotency_key: IdempotencyHeader,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> CheckoutConfirmation:
    """Run the local test provider and create at most one order."""

    return await service.confirm_checkout(
        tenant_id=context.tenant_id,
        account_id=account.id,
        request=payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.delete("/memories/{memory_id}", response_model=ShopperMemoryDeleteResponse)
async def delete_shopper_memory(
    memory_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperMemoryDeleteResponse:
    return await service.delete_memory(
        tenant_id=context.tenant_id,
        account_id=account.id,
        memory_id=memory_id,
        idempotency_key=idempotency_key,
    )


@router.post("/chat", response_model=ShopperChatResponse)
async def chat_with_shopper_agent(
    payload: ShopperChatRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    account: Annotated[ShopperAccount, Depends(get_current_shopper)],
    service: Annotated[ShopperAgentRuntime, Depends(get_shopper_agent_service)],
) -> ShopperChatResponse:
    if payload.expected_account_id is not None and payload.expected_account_id != account.id:
        raise ShopperAuthenticationError(
            "Your shopping account changed. Check your session before retrying."
        )
    payload._account_version = account._data_version
    return await service.chat(
        tenant_id=context.tenant_id,
        account_id=account.id,
        request=payload,
        idempotency_key=idempotency_key,
    )


def _set_session_cookie(
    response: Response, settings: Settings, raw_token: str, request: Request
) -> None:
    response.set_cookie(
        store_cookie(request, SESSION_COOKIE),
        raw_token,
        max_age=settings.shopper_session_days * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie(settings, request),
        samesite="strict",
        path="/",
    )
