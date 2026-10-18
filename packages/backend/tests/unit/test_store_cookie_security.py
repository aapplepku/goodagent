"""Configured HTTPS survives the HTTP hop between Next.js and the API."""

from http.cookies import SimpleCookie

import pytest
from fastapi import FastAPI, Request, Response

from open_commerce.api.shopper import SESSION_COOKIE, _set_session_cookie
from open_commerce.api.store_auth import MERCHANT_COOKIE, owner_cookie
from open_commerce.api.store_cookies import store_cookie
from open_commerce.config import Settings


def request_for(settings: Settings, scheme: str = "http", **headers: str) -> Request:
    app = FastAPI()
    app.state.settings = settings
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": scheme,
            "path": "/",
            "server": ("api", 8000),
            "app": app,
            "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
        }
    )


@pytest.mark.parametrize("shopper", [False, True])
@pytest.mark.parametrize(
    ("profile", "origins", "scheme", "expected"),
    [
        ("self_hosted", ["https://store.fixture.example"], "http", True),
        ("self_hosted", [], "https", True),
        ("self_hosted", [], "http", False),
        ("self_hosted", ["http://localhost:3000"], "http", False),
        ("hosted", [], "http", True),
        ("legacy_demo", [], "http", False),
    ],
)
def test_session_cookie_transport_security(
    shopper: bool, profile: str, origins: list[str], scheme: str, expected: bool
) -> None:
    settings = Settings(_env_file=None).model_copy(
        update={"runtime_profile": profile, "public_origins": origins}
    )
    request = request_for(settings, scheme, **{"x-store-slug": "fixture-store"})
    response = Response()
    if shopper:
        _set_session_cookie(response, settings, "synthetic-cookie", request)
        name = store_cookie(request, SESSION_COOKIE)
    else:
        owner_cookie(response, request, "synthetic-cookie")
        name = MERCHANT_COOKIE
    cookie = SimpleCookie(response.headers["set-cookie"])[name]
    assert bool(cookie["secure"]) is expected
    assert cookie["httponly"]
    assert cookie["samesite"] == ("strict" if shopper else "lax")


def test_untrusted_headers_cannot_choose_cookie_transport_policy() -> None:
    settings = Settings(_env_file=None, runtime_profile="self_hosted")
    request = request_for(
        settings,
        **{
            "origin": "https://attacker.invalid",
            "x-forwarded-proto": "https",
        },
    )
    response = Response()
    owner_cookie(response, request, "synthetic-cookie")
    assert not SimpleCookie(response.headers["set-cookie"])[MERCHANT_COOKIE]["secure"]


def test_store_cookie_names_are_isolated_and_reject_unsafe_slugs() -> None:
    settings = Settings(_env_file=None, runtime_profile="self_hosted")
    first = request_for(settings, **{"x-store-slug": "first-store"})
    second = request_for(settings, **{"x-store-slug": "second-store"})
    for prefix in (SESSION_COOKIE, "open_commerce_preview"):
        assert store_cookie(first, prefix) != store_cookie(second, prefix)
        assert store_cookie(first, prefix, slug="bad; Path=/") == prefix + "_invalid_store"
