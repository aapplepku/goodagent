"""Real auth and preview responses behind an HTTP API hop, on disposable PostgreSQL."""

import json
from datetime import timedelta
from http.cookies import SimpleCookie
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.store_setup import AuthTicketRecord, MerchantCredentialRecord
from open_commerce.shopper_agent.auth import hash_password, session_token_hash
from open_commerce.stores.auth import MerchantAuthService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("public_https", [False, True])
async def test_auth_and_preview_cookies_follow_deployment_origin(
    integration_settings: Settings, public_https: bool
) -> None:
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "public_origins": ["https://store.fixture.example"] if public_https else [],
        }
    )
    app = create_app(settings)
    db = app.state.database
    username, password, grant_token = uuid4().hex, "synthetic-owner-password", uuid4().hex
    try:
        owner, _ = await MerchantAuthService(db).oidc_identity(
            "https://fixture.example", uuid4().hex
        )
        async with db.transaction(owner.store.id, write=True) as session:
            session.add(
                MerchantCredentialRecord(
                    user_id=owner.user_id,
                    username=username,
                    password_hash=await hash_password(password),
                    recovery_hash=session_token_hash(uuid4().hex),
                )
            )
            session.add(
                AuthTicketRecord(
                    token_hash=session_token_hash(grant_token),
                    tenant_id=owner.store.id,
                    purpose="shopper_preview",
                    payload=json.dumps({"catalog_id": str(uuid4())}).encode(),
                    created_at=utc_now(),
                    expires_at=utc_now() + timedelta(minutes=5),
                )
            )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/v1/merchant/auth/login",
                json={
                    "username": username,
                    "password": password,
                },
            )
            assert login.status_code == 200
            merchant = SimpleCookie(login.headers["set-cookie"])["open_commerce_merchant_session"]
            assert bool(merchant["secure"]) is public_https
            preview = await client.post(
                f"/v1/stores/{owner.store.slug}/preview",
                json={
                    "token": grant_token,
                },
            )
            assert preview.status_code == 200
            name = f"open_commerce_preview_{owner.store.slug}"
            cookie = SimpleCookie(preview.headers["set-cookie"])[name]
            assert bool(cookie["secure"]) is public_https
            assert cookie["httponly"] and cookie["samesite"] == "lax"
            replay = await client.post(
                f"/v1/stores/{owner.store.slug}/preview",
                json={
                    "token": grant_token,
                },
            )
            assert replay.status_code == 401
            client.cookies.clear()
            for slug in ("", "missing-store", "bad; Path=/"):
                headers = {"x-store-slug": slug} if slug else {}
                denied = await client.post("/v1/shopper/auth/guest", headers=headers)
                assert denied.status_code == 404
                assert "set-cookie" not in denied.headers
                missing_preview = await client.post(
                    "/v1/stores/missing-store/preview",
                    json={"token": grant_token},
                    headers=headers,
                )
                assert missing_preview.status_code == 404
                assert "set-cookie" not in missing_preview.headers
    finally:
        # This suite shares a disposable database; do not leave an instance owner
        # behind for the separate first-owner bootstrap test.
        async with db.sessions() as session, session.begin():
            await session.execute(
                delete(MerchantCredentialRecord).where(
                    MerchantCredentialRecord.username == username
                )
            )
        await db.close()
