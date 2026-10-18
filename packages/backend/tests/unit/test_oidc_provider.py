"""Controlled OIDC discovery, PKCE, signature, issuer, audience, and nonce verification."""

import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
from pydantic import SecretStr

from open_commerce.config import Settings
from open_commerce.providers.oidc import OIDCProvider


@pytest.mark.parametrize("fault", [None, "nonce", "aud", "iss", "signature"])
async def test_verified_oidc_identity(fault: str | None) -> None:
    issuer = "https://identity.fixture.example"
    key = RSAKey.generate_key(2048)
    key.ensure_kid()
    claims: dict[str, object] = {
        "iss": issuer,
        "sub": "fixture-user",
        "aud": "fixture-client",
        "iat": int(time.time()),
        "exp": int(time.time()) + 300,
        "nonce": "fixture-nonce",
    }
    if fault in {"nonce", "aud", "iss"}:
        claims[fault] = "incorrect"
    signed = jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        claims,
        RSAKey.generate_key(2048) if fault == "signature" else key,
    )

    def exchange(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": issuer + "/authorize",
                    "token_endpoint": issuer + "/token",
                    "jwks_uri": issuer + "/jwks",
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [key.as_dict(private=False)]})
        assert request.url.path == "/token"
        fields = parse_qs(request.content.decode())
        assert fields["code_verifier"] == ["v" * 64]
        assert fields["redirect_uri"] == ["https://store.fixture.example/callback"]
        return httpx.Response(
            200,
            json={"access_token": "synthetic-token", "token_type": "Bearer", "id_token": signed},
        )

    provider = OIDCProvider(
        Settings(
            _env_file=None,
            oidc_issuer=issuer,
            oidc_client_id="fixture-client",
            oidc_client_secret=SecretStr("synthetic-secret"),
            oidc_callback_url="https://store.fixture.example/callback",
        )
    )
    provider.client.client_kwargs["transport"] = httpx.MockTransport(exchange)
    url = await provider.authorize(state="fixture-state", nonce="fixture-nonce", verifier="v" * 64)
    query = parse_qs(urlsplit(url).query)
    assert query["state"] == ["fixture-state"] and query["code_challenge_method"] == ["S256"]
    if fault:
        with pytest.raises(JoseError):
            await provider.exchange(code="fixture-code", nonce="fixture-nonce", verifier="v" * 64)
    else:
        identity = await provider.exchange(
            code="fixture-code", nonce="fixture-nonce", verifier="v" * 64
        )
        assert identity.issuer == issuer and identity.subject == "fixture-user"
