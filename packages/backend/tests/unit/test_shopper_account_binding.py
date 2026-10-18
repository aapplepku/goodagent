"""Account intent never substitutes for cookie, tenant, or private-preview authorization."""

from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, call, create_autospec
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient, Response
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from open_commerce.api import activity, shopper
from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.errors import register_exception_handlers
from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.scope import CatalogScope, catalog_scope
from open_commerce.commerce.models import Cart, CommerceRuntime
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.repositories.audit import SqlAuditRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.errors import ShopperAuthenticationError
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAgentRuntime,
    ShopperAuthResponse,
)
from open_commerce.stores.shoppers import ContinuityResponse, ShopperAccounts
from open_commerce.telemetry.activity import ActivityService

TENANT = UUID("10000000-0000-0000-0000-000000000001")
CURRENT = UUID("80000000-0000-0000-0000-000000000002")
EXPECTED = UUID("80000000-0000-0000-0000-000000000001")
RESOURCE = "84000000-0000-0000-0000-000000000001"
HEADER = "X-Shopper-Account-Id"
TOKEN = "synthetic-current-session"
COOKIE = f"{shopper.SESSION_COOKIE}_fixture"

PROTECTED = [
    ("GET", "/me", None),
    ("GET", "/conversations", None),
    ("GET", f"/conversations/{RESOURCE}", None),
    ("GET", "/memories", None),
    ("GET", "/discovery", None),
    ("GET", "/catalog", None),
    ("GET", "/cart", None),
    ("GET", "/checkout/current", None),
    ("GET", f"/checkout/{RESOURCE}", None),
    ("GET", "/orders", None),
    ("GET", "/auth/sessions", None),
    ("GET", "/activity", None),
    ("PATCH", "/preferences", {"enabled": True}),
    ("DELETE", "/shopping-data", None),
    ("DELETE", "/auth/sessions", None),
    ("POST", "/cart/items", {"product_id": "fixture-mug", "quantity": 1}),
    ("PATCH", f"/cart/items/{RESOURCE}", {"quantity": 2}),
    ("DELETE", f"/cart/items/{RESOURCE}", None),
    ("POST", "/checkout/preview", {"cart_version": 2}),
    (
        "POST",
        "/checkout/confirm",
        {"checkout_id": RESOURCE, "payment_method": "test_success"},
    ),
    ("DELETE", f"/memories/{RESOURCE}", None),
    ("POST", "/activity/rules", {"name": "Synthetic rule"}),
    ("POST", "/product-selections", {"product_id": "fixture-mug", "quantity": 1}),
    ("POST", "/auth/merge", {"token": "synthetic-merge", "cart_choice": "keep_account"}),
    ("POST", "/chat", {"content": "Find blue mugs"}),
]

AUTH = [
    (
        "/auth/register",
        {"username": "fixture", "display_name": "Fixture", "password": "synthetic-password"},
        201,
    ),
    ("/auth/login", {"username": "fixture", "password": "synthetic-password"}, 200),
    ("/auth/guest", None, 200),
    ("/auth/logout", None, 204),
]


@dataclass
class BindingApp:
    app: FastAPI
    database: MagicMock
    service: MagicMock
    commerce: MagicMock
    accounts: MagicMock
    catalog: MagicMock
    activity: MagicMock
    telemetry: AsyncMock
    replay: AsyncMock
    remember: MagicMock
    audit: AsyncMock
    identities: list[object]

    def assert_no_effects(self) -> None:
        assert all(
            entry[0] == "authenticate" or entry[0].startswith("database.")
            for entry in self.service.mock_calls
        )
        assert all(entry[0] == "account" for entry in self.accounts.mock_calls)
        self.commerce.assert_not_called()
        assert not self.commerce.mock_calls
        assert not self.catalog.mock_calls
        assert not self.activity.mock_calls
        assert all(entry == call(TENANT) for entry in self.database.transaction.call_args_list)
        session = self.database.transaction.return_value.__aenter__.return_value
        session.execute.assert_not_called()
        session.add.assert_not_called()
        session.flush.assert_not_called()
        self.telemetry.assert_not_called()
        self.replay.assert_not_called()
        self.remember.assert_not_called()
        self.audit.assert_not_called()
        assert self.identities and all(identity is None for identity in self.identities)


@pytest.fixture
def binding_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[BindingApp]:
    settings = Settings(_env_file=None, runtime_profile="self_hosted")
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = settings
    service = create_autospec(ShopperAgentRuntime, instance=True)
    service.database = database
    commerce = create_autospec(CommerceRuntime, instance=True)
    accounts = create_autospec(ShopperAccounts, instance=True)
    catalog = create_autospec(CatalogBrowseService, instance=True)
    activity_service = create_autospec(ActivityService, instance=True)
    account = ShopperAccount(
        id=CURRENT, username="fixture", display_name="Fixture", created_at=utc_now(), is_guest=True
    )

    async def authenticate(*, tenant_id: UUID, raw_token: str) -> ShopperAccount:
        assert tenant_id == TENANT
        if raw_token != TOKEN:
            raise ShopperAuthenticationError("Sign in to continue")
        return account

    service.authenticate.side_effect = authenticate
    service.register.return_value = (ShopperAuthResponse(account=account), "synthetic-new-session")
    service.login.return_value = service.register.return_value
    accounts.upgrade.return_value = service.register.return_value
    accounts.guest.return_value = service.register.return_value
    accounts.recover.return_value = service.register.return_value
    accounts.login.return_value = (ContinuityResponse(account=account), "synthetic-new-session")
    accounts.preferences.return_value = account
    commerce.add_item.return_value = Cart()
    monkeypatch.setattr(shopper, "ShopperAccounts", lambda database: accounts)
    telemetry = AsyncMock()
    replay = AsyncMock()
    remember = MagicMock()
    audit = AsyncMock()
    monkeypatch.setattr(ActivityService, "record_best_effort", telemetry)
    monkeypatch.setattr(RequestRepository, "replay", replay)
    monkeypatch.setattr(RequestRepository, "remember", remember)
    monkeypatch.setattr(SqlAuditRepository, "append", audit)
    app = FastAPI()
    app.state.settings = settings
    app.state.database = database
    app.state.shopper_agent_service = service
    app.state.commerce_service = commerce

    async def context() -> RequestContext:
        return RequestContext(
            tenant_id=TENANT,
            actor_id="shopper",
            roles=set(),
            auth_mode="session",
            tenant_source="store",
        )

    app.dependency_overrides[get_request_context] = context
    app.dependency_overrides[get_catalog_browser] = lambda: catalog
    app.dependency_overrides[activity.get_activity] = lambda: activity_service
    identities: list[object] = []

    @app.middleware("http")
    async def observe(request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        request.state.request_id = "account-binding-test"
        response = await call_next(request)
        identities.append(getattr(request.state, "shopper_activity_identity", None))
        return response

    app.include_router(shopper.router)
    app.include_router(activity.router)
    register_exception_handlers(app)
    yield BindingApp(
        app,
        database,
        service,
        commerce,
        accounts,
        catalog,
        activity_service,
        telemetry,
        replay,
        remember,
        audit,
        identities,
    )


def assert_denied(response: Response, expected_status: int) -> None:
    assert response.status_code == expected_status, response.text
    assert "set-cookie" not in response.headers
    assert str(EXPECTED) not in response.text
    assert str(CURRENT) not in response.text
    assert "not-a-uuid" not in response.text
    if expected_status == 401:
        assert response.json()["error"]["code"] == "SHOPPER_AUTHENTICATION_REQUIRED"


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
@pytest.mark.parametrize(("binding", "status"), [(str(EXPECTED), 401), ("not-a-uuid", 422)])
async def test_protected_routes_reject_before_effects(
    binding_app: BindingApp,
    method: str,
    path: str,
    body: dict[str, object] | None,
    binding: str,
    status: int,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.request(
            method,
            "/v1/shopper" + path,
            json=body,
            headers={"x-store-slug": "fixture", HEADER: binding, "Idempotency-Key": "original"},
        )
    assert_denied(response, status)
    binding_app.assert_no_effects()


@pytest.mark.parametrize("profile", ["self_hosted", "legacy_demo", "hosted"])
@pytest.mark.parametrize("binding", [None, str(CURRENT), str(EXPECTED), "not-a-uuid"])
async def test_shared_dependency_profiles_and_unbound_discovery(
    binding_app: BindingApp,
    profile: Literal["self_hosted", "legacy_demo", "hosted"],
    binding: str | None,
) -> None:
    binding_app.app.state.settings = binding_app.app.state.settings.model_copy(
        update={"runtime_profile": profile}
    )
    headers = {"x-store-slug": "fixture"}
    if binding is not None:
        headers[HEADER] = binding
    cookie = shopper.SESSION_COOKIE if profile == "legacy_demo" else COOKIE
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={cookie: TOKEN},
    ) as client:
        response = await client.get("/v1/shopper/me", headers=headers)
    if binding in {None, str(CURRENT)}:
        assert response.status_code == 200
        assert response.json()["account"]["id"] == str(CURRENT)
        assert binding_app.identities == [(TENANT, CURRENT)]
        binding_app.service.authenticate.assert_awaited_once_with(tenant_id=TENANT, raw_token=TOKEN)
        if profile != "legacy_demo":
            assert binding_app.accounts.account.await_args.args[1:] == (TENANT, CURRENT)
    else:
        assert_denied(response, 401 if binding == str(EXPECTED) else 422)
        binding_app.assert_no_effects()


@pytest.mark.parametrize(("path", "body", "success"), AUTH)
@pytest.mark.parametrize("profile", ["self_hosted", "legacy_demo"])
@pytest.mark.parametrize("binding", [None, str(CURRENT), str(EXPECTED), "not-a-uuid"])
async def test_auth_transitions_bind_only_when_requested(
    binding_app: BindingApp,
    path: str,
    body: dict[str, object] | None,
    success: int,
    profile: str,
    binding: str | None,
) -> None:
    binding_app.app.state.settings = binding_app.app.state.settings.model_copy(
        update={"runtime_profile": profile}
    )
    headers = {"x-store-slug": "fixture"}
    if binding is not None:
        headers[HEADER] = binding
    cookie = shopper.SESSION_COOKIE if profile == "legacy_demo" else COOKIE
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={cookie: TOKEN},
    ) as client:
        response = await client.post("/v1/shopper" + path, json=body, headers=headers)
    if binding in {str(EXPECTED), "not-a-uuid"}:
        assert_denied(response, 401 if binding == str(EXPECTED) else 422)
        binding_app.assert_no_effects()
        return
    assert response.status_code == success, response.text
    assert "set-cookie" in response.headers
    if path == "/auth/login" and profile != "legacy_demo":
        assert binding_app.accounts.login.await_args.args[:2] == (TENANT, CURRENT)
    if path == "/auth/register" and profile != "legacy_demo":
        assert binding_app.accounts.upgrade.await_args.args[:2] == (TENANT, CURRENT)
    if binding is not None:
        binding_app.service.authenticate.assert_awaited_once_with(tenant_id=TENANT, raw_token=TOKEN)


@pytest.mark.parametrize("token", ["synthetic-created-session", None])
@pytest.mark.parametrize("binding", [None, str(CURRENT)])
async def test_guest_response_distinguishes_creation_from_reused_guest(
    binding_app: BindingApp,
    token: str | None,
    binding: str | None,
) -> None:
    result = binding_app.accounts.guest.return_value[0]
    assert result.account.is_guest
    binding_app.accounts.guest.return_value = (result, token)
    headers = {"x-store-slug": "fixture"}
    if binding is not None:
        headers[HEADER] = binding
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.post("/v1/shopper/auth/guest", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {**result.model_dump(mode="json"), "created": token is not None}
    assert TOKEN not in response.text
    if token is None:
        assert "set-cookie" not in response.headers
    else:
        assert token not in response.text
        assert f"{COOKIE}={token}" in response.headers["set-cookie"]
    binding_app.accounts.guest.assert_awaited_once_with(TENANT, TOKEN)
    if binding is None:
        binding_app.service.authenticate.assert_not_called()
        binding_app.database.transaction.assert_not_called()
    else:
        binding_app.service.authenticate.assert_awaited_once_with(tenant_id=TENANT, raw_token=TOKEN)


@pytest.mark.parametrize(
    "path", ["/me", "/auth/login", "/auth/register", "/auth/logout", "/auth/guest"]
)
@pytest.mark.parametrize("cookie", [None, "invalid-session", "wrong-store"])
async def test_binding_does_not_replace_cookie_authentication(
    binding_app: BindingApp,
    path: str,
    cookie: str | None,
) -> None:
    cookies = {} if cookie is None else {COOKIE: cookie}
    if cookie == "wrong-store":
        cookies = {f"{shopper.SESSION_COOKIE}_other-store": TOKEN}
    body = next((body for auth_path, body, _ in AUTH if auth_path == path), None)
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies=cookies,
    ) as client:
        response = await client.request(
            "GET" if path == "/me" else "POST",
            "/v1/shopper" + path,
            json=body,
            headers={"x-store-slug": "fixture", HEADER: str(CURRENT)},
        )
    assert_denied(response, 401)
    binding_app.assert_no_effects()


@pytest.mark.parametrize("cookie", [None, "invalid-session"])
async def test_unbound_login_and_logout_preserve_expired_cookie_behavior(
    binding_app: BindingApp,
    cookie: str | None,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={} if cookie is None else {COOKIE: cookie},
        headers={"x-store-slug": "fixture"},
    ) as client:
        response = await client.post("/v1/shopper/auth/logout")
        assert response.status_code == 204
        assert "set-cookie" in response.headers
        response = await client.post(
            "/v1/shopper/auth/login", json={"username": "fixture", "password": "synthetic-password"}
        )
    assert response.status_code == 200
    assert binding_app.accounts.login.await_args.args[:2] == (TENANT, None)


async def test_explicit_unbound_recovery_needs_no_current_cookie(binding_app: BindingApp) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/shopper/auth/recover",
            headers={"x-store-slug": "fixture"},
            json={
                "username": "fixture",
                "code": "synthetic-code",
                "password": "synthetic-password",
            },
        )
    assert response.status_code == 200
    binding_app.service.authenticate.assert_not_called()
    binding_app.accounts.recover.assert_awaited_once()


@pytest.mark.parametrize("binding", [None, str(CURRENT)])
async def test_valid_binding_preserves_mutation_target_and_key(
    binding_app: BindingApp,
    binding: str | None,
) -> None:
    headers = {"x-store-slug": "fixture", "Idempotency-Key": "original-receipt"}
    if binding:
        headers[HEADER] = binding
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
        headers=headers,
    ) as client:
        response = await client.patch("/v1/shopper/preferences", json={"enabled": True})
        assert response.status_code == 200
        response = await client.post("/v1/shopper/cart/items", json={"product_id": "fixture-mug"})
        assert response.status_code == 200
        response = await client.delete("/v1/shopper/shopping-data")
        assert response.status_code == 204
    binding_app.accounts.preferences.assert_awaited_once_with(
        TENANT, CURRENT, True, idempotency_key="original-receipt"
    )
    assert binding_app.commerce.add_item.await_args.kwargs["account_id"] == CURRENT
    assert binding_app.commerce.add_item.await_args.kwargs["tenant_id"] == TENANT
    assert binding_app.commerce.add_item.await_args.kwargs["idempotency_key"] == "original-receipt"
    binding_app.accounts.delete_data.assert_awaited_once_with(TENANT, CURRENT)


async def test_matching_header_preserves_private_preview_check(
    binding_app: BindingApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shopper, "ShopperAccounts", ShopperAccounts)
    session = binding_app.database.transaction.return_value.__aenter__.return_value
    session.scalar = AsyncMock(
        return_value=SimpleNamespace(expires_at=None, preview_catalog_id=None)
    )
    with catalog_scope(CatalogScope(TENANT, uuid4(), preview=True)):
        async with AsyncClient(
            transport=ASGITransport(app=binding_app.app),
            base_url="http://test",
            cookies={COOKIE: TOKEN},
        ) as client:
            response = await client.delete(
                "/v1/shopper/shopping-data",
                headers={"x-store-slug": "fixture", HEADER: str(CURRENT)},
            )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "STORE_REQUEST_BLOCKED"
    session.execute.assert_not_called()
    binding_app.assert_no_effects()


async def test_chat_body_precondition_remains_independent(binding_app: BindingApp) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.post(
            "/v1/shopper/chat",
            headers={"x-store-slug": "fixture", HEADER: str(CURRENT), "Idempotency-Key": "chat"},
            json={"content": "Find blue mugs", "expected_account_id": str(EXPECTED)},
        )
    assert_denied(response, 401)
    binding_app.service.chat.assert_not_called()


def test_optional_uuid_header_is_documented(binding_app: BindingApp) -> None:
    paths = binding_app.app.openapi()["paths"]
    for path, operations in paths.items():
        if not path.startswith("/v1/shopper/") or path == "/v1/shopper/auth/recover":
            continue
        for operation in operations.values():
            parameter = next(item for item in operation["parameters"] if item["name"] == HEADER)
            assert parameter["in"] == "header" and not parameter["required"]
            assert {"type": "string", "format": "uuid"} in parameter["schema"]["anyOf"]


def test_guest_creation_result_is_required_in_response_contract(binding_app: BindingApp) -> None:
    schema = binding_app.app.openapi()
    response = schema["paths"]["/v1/shopper/auth/guest"]["post"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ShopperGuestResponse"
    }
    guest = schema["components"]["schemas"]["ShopperGuestResponse"]
    assert "created" in guest["required"]
    assert guest["properties"]["created"]["type"] == "boolean"
    assert "created" not in schema["components"]["schemas"]["ShopperAuthResponse"]["properties"]
