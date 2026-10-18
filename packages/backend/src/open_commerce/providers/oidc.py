"""OpenID Connect authorization-code client with server-owned transient state."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth

from open_commerce.config import Settings
from open_commerce.stores.models import StoreError


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str


class OIDCProvider:
    def __init__(self, settings: Settings) -> None:
        if (
            not settings.oidc_issuer
            or not settings.oidc_client_id
            or not settings.oidc_callback_url
        ):
            raise StoreError("The hosted sign-in provider is not configured.", 503)
        issuer = settings.oidc_issuer.rstrip("/")
        for value in (issuer, settings.oidc_callback_url):
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.fragment
            ):
                raise StoreError("Sign-in configuration requires exact HTTPS URLs.", 503)
        self.issuer = issuer
        self.redirect_uri = settings.oidc_callback_url
        # The configured issuer is deployment-owned, never a shopper or merchant URL.
        self.client = OAuth().register(
            "identity",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret.get_secret_value()
            if settings.oidc_client_secret
            else None,
            server_metadata_url=f"{issuer}/.well-known/openid-configuration",
            client_kwargs={"scope": "openid", "code_challenge_method": "S256", "timeout": 15},
        )

    async def authorize(self, *, state: str, nonce: str, verifier: str) -> str:
        result: dict[str, Any] = await self.client.create_authorization_url(
            self.redirect_uri,
            state=state,
            nonce=nonce,
            code_verifier=verifier,
        )
        return str(result["url"])

    async def exchange(self, *, code: str, nonce: str, verifier: str) -> VerifiedIdentity:
        token = await self.client.fetch_access_token(
            self.redirect_uri,
            code=code,
            code_verifier=verifier,
        )
        claims = await self.client.parse_id_token(
            token,
            nonce=nonce,
            claims_options={"iss": {"essential": True, "value": self.issuer}},
        )
        if (
            not claims
            or claims.get("iss") != self.issuer
            or claims.get("nonce") != nonce
            or not isinstance(claims.get("sub"), str)
            or not claims.get("sub")
        ):
            raise StoreError("The sign-in provider returned an invalid identity.", 401)
        return VerifiedIdentity(issuer=self.issuer, subject=claims["sub"])
