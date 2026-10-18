"""Merchant login and setup. Shopper authentication uses a separate session audience."""

import hmac
import json
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from open_commerce.api.merchant_intent import MerchantIntentDependency, verify_merchant_intent
from open_commerce.api.store_cookies import secure_cookie
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.store_setup import AuthTicketRecord
from open_commerce.providers.oidc import OIDCProvider
from open_commerce.shopper_agent.auth import new_session_token, session_token_hash
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.crypto import decrypt, encrypt
from open_commerce.stores.models import (
    OwnerAuthResponse,
    OwnerIdentity,
    OwnerLoginRequest,
    OwnerRecoveryRequest,
    OwnerSetupRequest,
    SessionList,
    SetupStatus,
    StoreError,
)

router = APIRouter(prefix="/v1/merchant/auth", tags=["merchant-auth"])
MERCHANT_COOKIE = "open_commerce_merchant_session"
OIDC_COOKIE = "open_commerce_login_state"


def auth_service(request: Request) -> MerchantAuthService:
    return MerchantAuthService(request.app.state.database)


async def current_owner(request: Request, intent: MerchantIntentDependency = None) -> OwnerIdentity:
    owner = await auth_service(request).authenticate(request.cookies.get(MERCHANT_COOKIE))
    verify_merchant_intent(owner, intent)
    return owner


def owner_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        MERCHANT_COOKIE,
        token,
        httponly=True,
        secure=secure_cookie(request.app.state.settings, request),
        samesite="lax",
        max_age=7 * 86400,
        path="/",
    )


@router.get("/status", response_model=SetupStatus)
async def setup_status(request: Request) -> SetupStatus:
    return await auth_service(request).status()


@router.post("/setup", response_model=OwnerAuthResponse)
async def setup_owner(
    payload: OwnerSetupRequest, request: Request, response: Response
) -> OwnerAuthResponse:
    result, token = await auth_service(request).setup(payload)
    owner_cookie(response, request, token)
    return result


@router.post("/login", response_model=OwnerAuthResponse)
async def login_owner(
    payload: OwnerLoginRequest, request: Request, response: Response
) -> OwnerAuthResponse:
    result, token = await auth_service(request).login(payload)
    owner_cookie(response, request, token)
    return result


@router.post("/recover", response_model=OwnerAuthResponse)
async def recover_owner(
    payload: OwnerRecoveryRequest, request: Request, response: Response
) -> OwnerAuthResponse:
    result, token = await auth_service(request).recover(payload)
    owner_cookie(response, request, token)
    return result


@router.get("/me", response_model=OwnerAuthResponse)
async def owner_me(
    request: Request, owner: Annotated[OwnerIdentity, Depends(current_owner)]
) -> OwnerAuthResponse:
    return await auth_service(request).profile(owner)


@router.get("/sessions", response_model=SessionList)
async def owner_sessions(
    request: Request, owner: Annotated[OwnerIdentity, Depends(current_owner)]
) -> SessionList:
    return await auth_service(request).sessions(owner, request.cookies[MERCHANT_COOKIE])


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_owner_session(
    session_id: UUID, request: Request, owner: Annotated[OwnerIdentity, Depends(current_owner)]
) -> None:
    await auth_service(request).revoke(owner, session_id)


@router.post("/logout", status_code=204)
async def logout_owner(
    request: Request, response: Response, owner: Annotated[OwnerIdentity, Depends(current_owner)]
) -> None:
    service = auth_service(request)
    sessions = await service.sessions(owner, request.cookies[MERCHANT_COOKIE])
    for item in sessions.items:
        if item.current:
            await service.revoke(owner, item.id)
    response.delete_cookie(MERCHANT_COOKIE, path="/", samesite="lax")


@router.get("/oidc/start")
async def oidc_start(request: Request) -> RedirectResponse:
    settings = request.app.state.settings
    if settings.runtime_profile != "hosted":
        raise StoreError("Provider sign-in is unavailable in this profile.", 404)
    provider = OIDCProvider(settings)
    state, nonce, verifier = new_session_token(), new_session_token(), new_session_token()
    state_hash = session_token_hash(state)
    payload = encrypt(
        settings,
        json.dumps({"nonce": nonce, "verifier": verifier}).encode(),
        context=f"oidc:{state_hash}",
    )
    url = await provider.authorize(state=state, nonce=nonce, verifier=verifier)
    async with request.app.state.database.sessions() as session, session.begin():
        session.add(
            AuthTicketRecord(
                token_hash=state_hash,
                purpose="merchant_oidc",
                payload=payload,
                expires_at=utc_now() + timedelta(minutes=10),
                created_at=utc_now(),
            )
        )
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(OIDC_COOKIE, state, httponly=True, secure=True, samesite="lax", max_age=600)
    return response


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    code: Annotated[str, Query(max_length=4096)],
    state: Annotated[str, Query(max_length=200)],
) -> RedirectResponse:
    settings = request.app.state.settings
    if settings.runtime_profile != "hosted":
        raise StoreError("Provider sign-in is unavailable in this profile.", 404)
    cookie = request.cookies.get(OIDC_COOKIE, "")
    if not cookie or not hmac.compare_digest(cookie, state):
        raise StoreError("The sign-in request expired. Start again.", 401)
    state_hash = session_token_hash(state)
    async with request.app.state.database.sessions() as session, session.begin():
        ticket = await session.scalar(
            select(AuthTicketRecord)
            .where(
                AuthTicketRecord.token_hash == state_hash,
                AuthTicketRecord.purpose == "merchant_oidc",
                AuthTicketRecord.tenant_id.is_(None),
                AuthTicketRecord.expires_at > utc_now(),
                AuthTicketRecord.consumed_at.is_(None),
            )
            .with_for_update()
        )
        if ticket is None:
            raise StoreError("The sign-in request expired or was already used.", 401)
        ticket.consumed_at = utc_now()
        payload = json.loads(decrypt(settings, ticket.payload, context=f"oidc:{state_hash}"))
        ticket.payload = b""
    try:
        identity = await OIDCProvider(settings).exchange(
            code=code, nonce=payload["nonce"], verifier=payload["verifier"]
        )
        _, token = await auth_service(request).oidc_identity(identity.issuer, identity.subject)
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError("Sign-in could not be verified. Please try again.", 401) from exc
    response = RedirectResponse("/manager", status_code=303)
    owner_cookie(response, request, token)
    response.delete_cookie(OIDC_COOKIE)
    return response
