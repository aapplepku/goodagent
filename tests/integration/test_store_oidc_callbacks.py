"""Single-use hosted callbacks and browser binding, independent of provider crypto tests."""

import base64
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.providers.oidc import OIDCProvider, VerifiedIdentity

pytestmark = pytest.mark.integration


async def test_hosted_callback_binding_and_replay(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = "https://store.fixture.example"
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "hosted",
            "public_origins": [origin],
            "public_hosts": ["store.fixture.example"],
            "oidc_issuer": "https://identity.fixture.example",
            "oidc_client_id": "fixture-client",
            "oidc_client_secret": SecretStr("synthetic-secret"),
            "oidc_callback_url": origin + "/v1/merchant/auth/oidc/callback",
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"f" * 32).decode()),
            "hosted_daily_request_limit": 100,
            "hosted_daily_token_limit": 100000,
            "local_operations_enabled": False,
        }
    )
    state_values: dict[str, str] = {}
    calls = 0
    subject = uuid4().hex

    async def authorize(self: OIDCProvider, *, state: str, nonce: str, verifier: str) -> str:
        state_values.update(state=state, nonce=nonce, verifier=verifier)
        return "https://identity.fixture.example/authorize?" + urlencode({"state": state})

    async def exchange(
        self: OIDCProvider, *, code: str, nonce: str, verifier: str
    ) -> VerifiedIdentity:
        nonlocal calls
        calls += 1
        assert nonce == state_values["nonce"] and verifier == state_values["verifier"]
        return VerifiedIdentity("https://identity.fixture.example", subject)

    monkeypatch.setattr(OIDCProvider, "authorize", authorize)
    monkeypatch.setattr(OIDCProvider, "exchange", exchange)
    app = create_app(settings)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=origin) as client:
            start = await client.get("/v1/merchant/auth/oidc/start")
            assert start.status_code == 303
            assert "Secure" in start.headers["set-cookie"]
            assert "HttpOnly" in start.headers["set-cookie"]
            assert "SameSite=lax" in start.headers["set-cookie"]
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            path = "/v1/merchant/auth/oidc/callback"
            assert (
                await client.get(path, params={"code": "fixture", "state": "forged"})
            ).status_code == 401
            callback = await client.get(path, params={"code": "fixture", "state": state})
            assert callback.status_code == 303 and calls == 1
            assert (await client.get("/v1/merchant/store")).status_code == 200
            client.cookies.set("open_commerce_login_state", state)
            assert (
                await client.get(path, params={"code": "fixture", "state": state})
            ).status_code == 401
            assert calls == 1
    finally:
        await app.state.database.close()
