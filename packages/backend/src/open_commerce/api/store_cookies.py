"""Distinct browser cookies keep concurrent stores and preview visits isolated."""

import re
from urllib.parse import urlsplit

from fastapi import Request

from open_commerce.config import Settings


def secure_cookie(settings: Settings, request: Request) -> bool:
    # Next.js calls the API over HTTP even when the public storefront uses TLS.
    return (
        settings.runtime_profile == "hosted"
        or request.url.scheme == "https"
        or any(urlsplit(origin).scheme == "https" for origin in settings.public_origins)
    )


def store_cookie(request: Request, name: str, *, slug: str | None = None) -> str:
    if request.app.state.settings.runtime_profile == "legacy_demo":
        return name
    store = slug or request.headers.get("x-store-slug") or ""
    if not re.fullmatch(r"[a-z0-9-]{1,120}", store):
        return f"{name}_invalid_store"
    return f"{name}_{store}"
