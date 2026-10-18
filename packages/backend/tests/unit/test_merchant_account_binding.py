"""Merchant intent binds a view to cookie authority without selecting that authority."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response

from open_commerce.api import activity, context, manager, store_auth, stores
from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context, require_roles
from open_commerce.api.errors import register_exception_handlers
from open_commerce.api.merchant_intent import OWNER_HEADER, STORE_HEADER
from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.commerce.models import CommerceRuntime
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerThreadNotFoundError
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerAgentRuntime,
    ManagerDataOnboarding,
    ManagerWorkspaceResetResponse,
    ManagerWorkspaceResponse,
)
from open_commerce.manager_agent.runs import ManagerRunService
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.models import (
    OwnerAuthResponse,
    OwnerIdentity,
    SessionInfo,
    SessionList,
    SetupStatus,
    StoreError,
    StoreProfile,
)
from open_commerce.stores.setup import StoreSetupService
from open_commerce.telemetry.activity import ActivityService

OWNER_A, OWNER_B, STORE_A, STORE_B, RESOURCE = [UUID(int=value) for value in range(1, 6)]
TOKEN = "synthetic-merchant-B"
COOKIE = store_auth.MERCHANT_COOKIE
BOUND_A = {OWNER_HEADER: str(OWNER_A), STORE_HEADER: str(STORE_A)}
BOUND_B = {OWNER_HEADER: str(OWNER_B), STORE_HEADER: str(STORE_B)}

PROTECTED = [
    ("GET", "/v1/merchant/auth/me", None),
    ("GET", "/v1/merchant/auth/sessions", None),
    ("DELETE", f"/v1/merchant/auth/sessions/{RESOURCE}", None),
    ("POST", "/v1/merchant/auth/logout", None),
    ("GET", "/v1/merchant/store", None),
    ("PATCH", "/v1/merchant/store", {"name": "A edited title"}),
    ("POST", "/v1/merchant/store/preview", {"catalog_id": str(RESOURCE)}),
    ("POST", "/v1/merchant/store/sharing", {"catalog_id": str(RESOURCE), "enabled": False}),
    (
        "POST",
        "/v1/merchant/store/sharing",
        {
            "catalog_id": str(RESOURCE),
            "enabled": True,
            "acknowledge_demo_checkout": True,
            "acknowledge_image_issues": True,
        },
    ),
    ("GET", "/v1/merchant/store/measurements", None),
    ("PUT", "/v1/merchant/store/monitors", {"name": "failed_imports", "enabled": True}),
    ("POST", "/v1/merchant/imports/upload", None),
    ("POST", "/v1/merchant/imports/sample", None),
    ("GET", f"/v1/merchant/imports/{RESOURCE}", None),
    (
        "POST",
        f"/v1/merchant/imports/{RESOURCE}/confirm",
        {"expected_review_fingerprint": "sha256:" + "1" * 64},
    ),
    ("POST", f"/v1/merchant/imports/{RESOURCE}/retry", None),
    ("POST", f"/v1/merchant/imports/{RESOURCE}/cancel", None),
    ("GET", f"/v1/merchant/assets/{RESOURCE}", None),
    ("GET", "/v1/manager/catalog", None),
    ("GET", "/v1/manager/workspace", None),
    ("POST", "/v1/manager/workspace/bootstrap", None),
    ("POST", "/v1/manager/workspace/reset", {"confirmation": "RESET"}),
    ("GET", "/v1/manager/status", None),
    ("GET", "/v1/manager/commerce/overview", None),
    ("GET", "/v1/manager/threads", None),
    ("GET", f"/v1/manager/threads/{RESOURCE}", None),
    ("DELETE", f"/v1/manager/threads/{RESOURCE}/messages", None),
    ("POST", f"/v1/manager/threads/{RESOURCE}/messages", {"content": "A message"}),
    ("POST", f"/v1/manager/threads/{RESOURCE}/runs", {"content": "A command"}),
    ("GET", f"/v1/manager/runs/{RESOURCE}", None),
    ("GET", f"/v1/manager/runs/{RESOURCE}/events", None),
    ("POST", f"/v1/manager/runs/{RESOURCE}/cancel", None),
    ("GET", "/v1/manager/memories", None),
    ("DELETE", f"/v1/manager/memories/{RESOURCE}", None),
    ("GET", "/v1/manager/activity", None),
    ("POST", "/v1/manager/activity/rules", {"name": "A rule"}),
]


@dataclass
class BindingApp:
    app: FastAPI
    auth: MagicMock
    database: MagicMock
    setup: MagicMock
    agent: MagicMock
    effects: list[MagicMock | AsyncMock]

    def assert_no_effects(self) -> None:
        assert all(entry[0] == "authenticate" for entry in self.auth.mock_calls)
        assert not self.database.mock_calls
        assert all(not effect.mock_calls for effect in self.effects)


@pytest.fixture
def binding_app(monkeypatch: pytest.MonkeyPatch) -> BindingApp:
    settings = Settings(_env_file=None, runtime_profile="self_hosted")
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = settings
    auth = create_autospec(MerchantAuthService, instance=True)
    identity = OwnerIdentity(user_id=OWNER_B, tenant_id=STORE_B)
    profile = StoreProfile(id=STORE_B, slug="store-b", name="Store B")

    async def authenticate(token: str | None) -> OwnerIdentity:
        if token != TOKEN:
            raise StoreError("Sign in to your store workspace.", 401)
        return identity

    auth.authenticate.side_effect = authenticate
    auth.profile.return_value = OwnerAuthResponse(user_id=OWNER_B, store=profile)
    auth.login.return_value = (auth.profile.return_value, "synthetic-new-session")
    auth.recover.return_value = auth.login.return_value
    auth.status.return_value = SetupStatus(
        profile="self_hosted", setup_required=False, login_method="local"
    )
    auth.sessions.return_value = SessionList(
        items=[SessionInfo(id=RESOURCE, current=True, created_at=utc_now(), expires_at=utc_now())]
    )
    monkeypatch.setattr(store_auth, "MerchantAuthService", lambda database: auth)
    monkeypatch.setattr(context, "MerchantAuthService", lambda database: auth)
    setup = create_autospec(StoreSetupService, instance=True)
    setup.profile.return_value = profile
    imports = create_autospec(CatalogImportService, instance=True)
    agent = create_autospec(ManagerAgentRuntime, instance=True)
    workspace = ManagerWorkspaceResponse(
        channels=[],
        onboarding=ManagerDataOnboarding(tenant_id=STORE_B),
        capabilities=ManagerAgentCapabilities(semantic_backend="offline", learned_semantics=False),
    )
    agent.reset_workspace.return_value = ManagerWorkspaceResetResponse(
        workspace=workspace,
        deleted_channel_count=0,
        deleted_message_count=0,
        deleted_memory_count=0,
    )
    commerce = create_autospec(CommerceRuntime, instance=True)
    runs = create_autospec(ManagerRunService, instance=True)
    catalog = create_autospec(CatalogBrowseService, instance=True)
    monitor = create_autospec(ActivityService, instance=True)
    monkeypatch.setattr(stores, "StoreSetupService", lambda database: setup)
    monkeypatch.setattr(stores, "CatalogImportService", lambda database: imports)
    effects: list[MagicMock | AsyncMock] = [setup, imports, agent, commerce, runs, catalog, monitor]
    for name in ("configure_monitor", "check_monitors", "measurements"):
        effect = AsyncMock()
        monkeypatch.setattr(stores, name, effect)
        effects.append(effect)
    replay, remember = AsyncMock(), MagicMock()
    monkeypatch.setattr(RequestRepository, "replay", replay)
    monkeypatch.setattr(RequestRepository, "remember", remember)
    effects.extend([replay, remember])
    app = FastAPI()
    app.state.settings, app.state.database = settings, database
    app.state.manager_agent_service, app.state.commerce_service = agent, commerce
    app.dependency_overrides[manager.get_manager_runs] = lambda: runs
    app.dependency_overrides[get_catalog_browser] = lambda: catalog
    app.dependency_overrides[activity.get_activity] = lambda: monitor
    for router in (store_auth.router, stores.router, manager.router, activity.router):
        app.include_router(router)
    register_exception_handlers(app)

    @app.get("/context")
    async def inspect_context(
        value: Annotated[RequestContext, Depends(get_request_context)],
    ) -> RequestContext:
        return value

    @app.get("/role")
    async def inspect_role(
        value: Annotated[RequestContext, Depends(require_roles("viewer"))],
    ) -> RequestContext:
        return value

    return BindingApp(app, auth, database, setup, agent, effects)


def assert_denied(response: Response, status: int) -> None:
    assert response.status_code == status, response.text
    assert "set-cookie" not in response.headers
    for private in (OWNER_A, OWNER_B, STORE_A, STORE_B, TOKEN, "not-a-uuid"):
        assert str(private) not in response.text
    if status == 401:
        assert response.json()["error"]["code"] == "STORE_REQUEST_BLOCKED"
        assert response.json()["error"]["details"] == {}


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
@pytest.mark.parametrize("malformed", [False, True])
async def test_protected_routes_stop_before_services_receipts_or_writes(
    binding_app: BindingApp, method: str, path: str, body: dict[str, object] | None, malformed: bool
) -> None:
    binding = {**BOUND_A, OWNER_HEADER: "not-a-uuid"} if malformed else BOUND_A
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.request(
            method, path, json=body, headers={**binding, "Idempotency-Key": "original-A"}
        )
    assert_denied(response, 422 if malformed else 401)
    binding_app.assert_no_effects()
    if malformed:
        binding_app.auth.authenticate.assert_not_awaited()
    else:
        binding_app.auth.authenticate.assert_awaited_once_with(TOKEN)


@pytest.mark.parametrize("path", ["/v1/merchant/auth/me", "/context"])
@pytest.mark.parametrize(
    "binding",
    [
        {**BOUND_B, OWNER_HEADER: str(OWNER_A)},
        {**BOUND_B, STORE_HEADER: str(STORE_A)},
    ],
)
async def test_each_component_must_match_cookie_authority(
    binding_app: BindingApp, path: str, binding: dict[str, str]
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.get(path, headers=binding)
    assert_denied(response, 401)
    binding_app.auth.authenticate.assert_awaited_once_with(TOKEN)
    binding_app.assert_no_effects()


@pytest.mark.parametrize("path", ["/v1/merchant/auth/logout", "/v1/manager/workspace/reset"])
@pytest.mark.parametrize(
    "binding",
    [
        [(OWNER_HEADER, str(OWNER_B))],
        [(STORE_HEADER, str(STORE_B))],
        [(OWNER_HEADER, ""), (STORE_HEADER, str(STORE_B))],
        [(OWNER_HEADER, str(OWNER_B)), (STORE_HEADER, "not-a-uuid")],
        [
            (OWNER_HEADER, str(OWNER_B)),
            (OWNER_HEADER.lower(), str(OWNER_A)),
            (STORE_HEADER, str(STORE_B)),
        ],
        [(OWNER_HEADER, str(OWNER_B)), (STORE_HEADER, str(STORE_B)), (STORE_HEADER, str(STORE_B))],
        [(OWNER_HEADER, f"{OWNER_A},{OWNER_B}"), (STORE_HEADER, str(STORE_B))],
    ],
)
async def test_incomplete_malformed_and_duplicate_headers_are_side_effect_free(
    binding_app: BindingApp, path: str, binding: list[tuple[str, str]]
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.post(
            path,
            json={"confirmation": "RESET"},
            headers=[*binding, ("Idempotency-Key", "original-A")],
        )
    assert_denied(response, 422)
    binding_app.auth.authenticate.assert_not_awaited()
    binding_app.assert_no_effects()


@pytest.mark.parametrize("path", ["/v1/merchant/auth/me", "/context"])
@pytest.mark.parametrize("binding", [{}, BOUND_B])
@pytest.mark.parametrize("profile", ["self_hosted", "hosted"])
async def test_missing_or_matching_pair_preserves_authenticated_identity(
    binding_app: BindingApp, path: str, binding: dict[str, str], profile: str
) -> None:
    binding_app.app.state.settings = binding_app.app.state.settings.model_copy(
        update={"runtime_profile": profile}
    )
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.get(path, headers=binding)
    assert response.status_code == 200, response.text
    assert str(STORE_B) in response.text and str(OWNER_B) in response.text
    binding_app.auth.authenticate.assert_awaited_once_with(TOKEN)


@pytest.mark.parametrize("path", ["/v1/merchant/auth/me", "/context"])
@pytest.mark.parametrize("status", [401, 403])
async def test_authentication_and_membership_failure_precede_comparison(
    binding_app: BindingApp, path: str, status: int
) -> None:
    binding_app.auth.authenticate.side_effect = StoreError("Original auth denial.", status)
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app), base_url="http://test"
    ) as client:
        response = await client.get(path, headers=BOUND_A)
    assert_denied(response, status)
    assert response.json()["error"]["message"] == "Original auth denial."
    binding_app.auth.authenticate.assert_awaited_once_with(None)
    binding_app.assert_no_effects()


@pytest.mark.parametrize("path", ["/v1/merchant/auth/me", "/context"])
async def test_real_cookie_and_membership_queries_never_use_expected_ids(
    binding_app: BindingApp, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(store_auth, "MerchantAuthService", MerchantAuthService)
    monkeypatch.setattr(context, "MerchantAuthService", MerchantAuthService)
    binding_app.database.sessions = MagicMock()
    session = binding_app.database.sessions.return_value.__aenter__.return_value
    session.scalar = AsyncMock(
        side_effect=[SimpleNamespace(user_id=OWNER_B, tenant_id=STORE_B), object()]
    )
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
    ) as client:
        response = await client.get(path, headers=BOUND_A)
    assert_denied(response, 401)
    assert session.scalar.await_count == 2
    membership = session.scalar.call_args_list[1].args[0].compile().params.values()
    assert STORE_B in membership and OWNER_B in membership
    assert STORE_A not in membership and OWNER_A not in membership
    binding_app.database.transaction.assert_not_called()
    session.add.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.parametrize("binding", [{}, BOUND_B])
async def test_matching_writes_keep_tenant_payload_key_and_logout_behavior(
    binding_app: BindingApp, binding: dict[str, str]
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
        headers=binding,
    ) as client:
        profile = await client.patch("/v1/merchant/store", json={"name": "B edited"})
        reset = await client.post(
            "/v1/manager/workspace/reset",
            json={"confirmation": "RESET"},
            headers={"Idempotency-Key": "retained-key"},
        )
        logout = await client.post("/v1/merchant/auth/logout")
    assert profile.status_code == reset.status_code == 200
    assert binding_app.setup.profile.call_args.args[0] == STORE_B
    assert binding_app.setup.profile.call_args.args[1].name == "B edited"
    reset_args = binding_app.agent.reset_workspace.call_args.kwargs
    assert reset_args["tenant_id"] == STORE_B and reset_args["idempotency_key"] == "retained-key"
    assert reset_args["request"].model_dump() == {"confirmation": "RESET"}
    assert logout.status_code == 204 and "Max-Age=0" in logout.headers["set-cookie"]
    binding_app.auth.revoke.assert_awaited_once_with(
        OwnerIdentity(user_id=OWNER_B, tenant_id=STORE_B), RESOURCE
    )


@pytest.mark.parametrize("action", ["login", "recover"])
async def test_explicit_unbound_auth_can_replace_session(
    binding_app: BindingApp, action: str
) -> None:
    body = {"username": "fixture", "password": "synthetic-password"}
    if action == "recover":
        body["recovery_code"] = "synthetic-recovery"
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app), base_url="http://test"
    ) as client:
        response = await client.post(f"/v1/merchant/auth/{action}", json=body)
        status = await client.get("/v1/merchant/auth/status")
    assert response.status_code == status.status_code == 200
    assert COOKIE in response.headers["set-cookie"]
    binding_app.auth.authenticate.assert_not_awaited()
    getattr(binding_app.auth, action).assert_awaited_once()


@pytest.mark.parametrize("binding", [{}, BOUND_A])
async def test_legacy_context_ignores_well_formed_intent_without_cookie_auth(
    binding_app: BindingApp, binding: dict[str, str]
) -> None:
    settings = Settings(_env_file=None, runtime_profile="legacy_demo")
    binding_app.app.state.settings = settings
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app), base_url="http://test"
    ) as client:
        response = await client.get("/context", headers=binding)
    assert response.status_code == 200
    result = response.json()
    assert result["tenant_id"] == str(settings.local_tenant_id)
    assert result["auth_mode"] == "local_demo" and result["tenant_source"] == "settings"
    assert set(result["roles"]) == {"owner", "operator", "viewer"}
    binding_app.auth.authenticate.assert_not_awaited()
    binding_app.assert_no_effects()


async def test_shopper_context_does_not_authenticate_merchant_intent(
    binding_app: BindingApp,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/shopper/store", headers=BOUND_A)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"
    binding_app.auth.authenticate.assert_not_awaited()
    binding_app.assert_no_effects()


async def test_existing_role_and_resource_denials_are_not_replaced(binding_app: BindingApp) -> None:
    binding_app.agent.get_thread.side_effect = ManagerThreadNotFoundError("Not found")
    async with AsyncClient(
        transport=ASGITransport(app=binding_app.app),
        base_url="http://test",
        cookies={COOKIE: TOKEN},
        headers=BOUND_B,
    ) as client:
        role = await client.get("/role")
        resource = await client.get(f"/v1/manager/threads/{RESOURCE}")
    assert role.status_code == 403
    assert resource.status_code == 404
    binding_app.agent.get_thread.assert_awaited_once_with(tenant_id=STORE_B, thread_id=RESOURCE)


def test_openapi_exposes_optional_uuid_headers_at_both_boundaries(binding_app: BindingApp) -> None:
    paths = binding_app.app.openapi()["paths"]
    for path, method in [
        ("/v1/merchant/store", "patch"),
        ("/v1/merchant/auth/logout", "post"),
        ("/v1/manager/workspace/reset", "post"),
        ("/v1/manager/activity", "get"),
    ]:
        parameters = {item["name"]: item for item in paths[path][method]["parameters"]}
        for name in (OWNER_HEADER, STORE_HEADER):
            parameter = parameters[name]
            assert parameter["in"] == "header" and parameter["required"] is False
            assert {"type": "string", "format": "uuid"} in parameter["schema"]["anyOf"]
    for action in ("login", "recover", "status"):
        auth_method = "get" if action == "status" else "post"
        assert not paths[f"/v1/merchant/auth/{action}"][auth_method].get("parameters")
