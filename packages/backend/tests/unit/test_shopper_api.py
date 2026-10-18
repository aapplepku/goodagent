"""Shopper API session-cookie and authenticated chat contract tests."""

import json
from datetime import UTC, datetime
from unittest.mock import create_autospec, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.main import create_app
from open_commerce.api.shopper import SESSION_COOKIE, get_commerce_service
from open_commerce.catalog.browse_models import CatalogBrowseQuery, CatalogBrowseResponse
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.commerce.models import ShopperOrderList
from open_commerce.config import Settings
from open_commerce.controller.service import ControllerService
from open_commerce.core.types import canonical_hash
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.errors import ShopperAuthenticationError
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAuthResponse,
    ShopperChatRequest,
    ShopperChatResponse,
    ShopperConversation,
    ShopperConversationDetail,
    ShopperConversationList,
    ShopperDiscoveryResponse,
    ShopperDiscoverySuggestion,
    ShopperLoginRequest,
    ShopperMemoryDeleteResponse,
    ShopperMemoryList,
    ShopperMessage,
    ShopperRegisterRequest,
)
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.simulator.service import SimulatorService


class FakeShopperAgent:
    def __init__(self) -> None:
        self.account = ShopperAccount(
            id=uuid4(),
            username="alex",
            display_name="Alex",
            created_at=datetime.now(UTC),
        )
        self.token = "safe-local-session-token"

    async def register(
        self, *, tenant_id: UUID, request: ShopperRegisterRequest
    ) -> tuple[ShopperAuthResponse, str]:
        assert tenant_id and request.password.get_secret_value()
        return ShopperAuthResponse(account=self.account), self.token

    async def login(
        self, *, tenant_id: UUID, request: ShopperLoginRequest
    ) -> tuple[ShopperAuthResponse, str]:
        assert tenant_id and request.password.get_secret_value()
        return ShopperAuthResponse(account=self.account), self.token

    async def authenticate(self, *, tenant_id: UUID, raw_token: str) -> ShopperAccount:
        assert tenant_id
        if raw_token != self.token:
            raise ShopperAuthenticationError("Your session is invalid or expired")
        return self.account

    async def logout(self, *, tenant_id: UUID, raw_token: str) -> None:
        assert tenant_id and raw_token == self.token

    async def list_conversations(
        self, *, tenant_id: UUID, account_id: UUID
    ) -> ShopperConversationList:
        assert tenant_id and account_id == self.account.id
        return ShopperConversationList(items=[])

    async def get_conversation(
        self, *, tenant_id: UUID, account_id: UUID, conversation_id: UUID
    ) -> ShopperConversationDetail:
        raise AssertionError("not used")

    async def list_memories(self, *, tenant_id: UUID, account_id: UUID) -> ShopperMemoryList:
        assert tenant_id and account_id == self.account.id
        return ShopperMemoryList(items=[])

    async def discovery(self, *, tenant_id: UUID, account_id: UUID) -> ShopperDiscoveryResponse:
        assert tenant_id and account_id == self.account.id
        return ShopperDiscoveryResponse(
            conversation_mode="basic",
            catalog_status="ready",
            catalog_name="abo-catalog.csv",
            product_count=48,
            suggestions=[
                ShopperDiscoverySuggestion(
                    label="Explore Grocery",
                    query="Show me popular grocery products",
                    category="Grocery",
                    image_url="https://example.test/grocery.jpg",
                )
            ],
        )

    async def delete_memory(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        memory_id: UUID,
        idempotency_key: str,
    ) -> ShopperMemoryDeleteResponse:
        assert tenant_id and account_id == self.account.id and idempotency_key
        return ShopperMemoryDeleteResponse(memory_id=memory_id, deleted=True)

    async def chat(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: ShopperChatRequest,
        idempotency_key: str,
    ) -> ShopperChatResponse:
        assert tenant_id and account_id == self.account.id and idempotency_key
        now = datetime.now(UTC)
        conversation = ShopperConversation(
            id=uuid4(), title="Find boots", created_at=now, updated_at=now, version=1
        )
        return ShopperChatResponse(
            conversation=conversation,
            user_message=ShopperMessage(
                id=uuid4(),
                conversation_id=conversation.id,
                role="user",
                content=request.content,
                created_at=now,
            ),
            assistant_message=ShopperMessage(
                id=uuid4(),
                conversation_id=conversation.id,
                role="assistant",
                content="I found catalog matches.",
                created_at=now,
            ),
        )


async def test_shopper_account_cookie_authenticates_chat_and_logout() -> None:
    settings = Settings(environment="test", manager_model_provider="deterministic")
    simulator = SimulatorService()
    shopper = FakeShopperAgent()
    app = create_app(
        settings=settings,
        simulator_service=simulator,
        search_service=SearchService(),
        controller_service=ControllerService(simulator_service=simulator),
        shopper_agent_service=shopper,
    )
    calls: list[UUID] = []

    class Browser:
        async def browse(
            self, *, tenant_id: UUID, query: CatalogBrowseQuery
        ) -> CatalogBrowseResponse:
            calls.append(tenant_id)
            return CatalogBrowseResponse(
                catalog=None,
                indexing=CatalogIndexStatus(),
                categories=[],
                items=[],
                total=0,
                offset=query.offset,
                limit=query.limit,
            )

    app.dependency_overrides[get_catalog_browser] = Browser
    order_calls: list[tuple[UUID, UUID, int, int]] = []

    class Orders:
        async def orders(
            self, *, tenant_id: UUID, account_id: UUID, limit: int, offset: int
        ) -> ShopperOrderList:
            order_calls.append((tenant_id, account_id, limit, offset))
            return ShopperOrderList(items=[])

    app.dependency_overrides[get_commerce_service] = Orders
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/shopper/orders")).status_code == 401
        assert not order_calls
        assert (await client.get("/v1/shopper/catalog")).status_code == 401
        assert calls == []
        registered = await client.post(
            "/v1/shopper/auth/register",
            json={
                "username": "alex",
                "display_name": "Alex",
                "password": "local-demo-password",
            },
        )
        me = await client.get("/v1/shopper/me")
        assert (await client.get("/v1/shopper/orders?limit=5&offset=10")).status_code == 200
        assert order_calls == [(settings.local_tenant_id, shopper.account.id, 5, 10)]
        assert (await client.get("/v1/shopper/orders?limit=51")).status_code == 422
        assert (await client.get("/v1/shopper/orders?offset=-1")).status_code == 422
        assert (await client.get(f"/v1/shopper/orders?account_id={uuid4()}")).status_code == 422
        assert (await client.get(f"/v1/shopper/orders?tenant_id={uuid4()}")).status_code == 422
        discovery = await client.get("/v1/shopper/discovery")
        assert (await client.get("/v1/shopper/catalog?limit=12")).status_code == 200
        assert calls == [settings.local_tenant_id]
        assert (await client.get("/v1/shopper/catalog?limit=10000")).status_code == 422
        assert (await client.get(f"/v1/shopper/catalog?tenant_id={uuid4()}")).status_code == 422
        chat = await client.post(
            "/v1/shopper/chat",
            headers={"Idempotency-Key": "shopper-turn"},
            json={"content": "Find waterproof boots", "conversation_id": None},
        )
        memory_id = uuid4()
        forgotten = await client.delete(
            f"/v1/shopper/memories/{memory_id}",
            headers={"Idempotency-Key": "shopper-forget"},
        )
        logged_out = await client.post("/v1/shopper/auth/logout")
        signed_out = await client.get("/v1/shopper/me")
        assert (await client.get("/v1/shopper/catalog")).status_code == 401

    assert registered.status_code == 201
    cookie = registered.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert me.status_code == 200 and me.json()["account"]["username"] == "alex"
    assert discovery.status_code == 200
    assert discovery.json()["conversation_mode"] == "basic"
    assert discovery.json()["suggestions"][0]["label"] == "Explore Grocery"
    assert chat.status_code == 200
    assert chat.json()["assistant_message"]["content"] == "I found catalog matches."
    assert forgotten.status_code == 200
    assert forgotten.json() == {"memory_id": str(memory_id), "deleted": True}
    assert logged_out.status_code == 204
    assert signed_out.status_code == 401


@pytest.mark.parametrize(
    ("binding", "status_code"),
    [("matched", 200), ("mismatched", 401), ("invalid", 422), ("omitted", 200), ("null", 200)],
)
async def test_chat_account_precondition_precedes_service_invocation(
    binding: str, status_code: int
) -> None:
    settings = Settings(environment="test", manager_model_provider="deterministic")
    shopper = FakeShopperAgent()
    app = create_app(settings=settings, shopper_agent_service=shopper)
    other_account_id = uuid4()
    payload: dict[str, object] = {"content": "Find waterproof boots"}
    if binding != "omitted":
        payload["expected_account_id"] = {
            "matched": str(shopper.account.id),
            "mismatched": str(other_account_id),
            "invalid": "not-a-uuid",
            "null": None,
        }[binding]
    with patch.object(shopper, "chat", wraps=shopper.chat) as chat:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, shopper.token)
            response = await client.post(
                "/v1/shopper/chat", headers={"Idempotency-Key": "bound-chat"}, json=payload
            )
        assert response.status_code == status_code
        if status_code == 200:
            chat.assert_awaited_once()
            assert chat.call_args.kwargs["tenant_id"] == settings.local_tenant_id
            assert chat.call_args.kwargs["account_id"] == shopper.account.id
            assert chat.call_args.kwargs["request"].expected_account_id == (
                shopper.account.id if binding == "matched" else None
            )
        else:
            chat.assert_not_called()
        if status_code == 401:
            assert response.json()["error"]["code"] == "SHOPPER_AUTHENTICATION_REQUIRED"
            assert str(shopper.account.id) not in response.text
            assert str(other_account_id) not in response.text


@pytest.mark.parametrize("session_token", [None, "invalid-session"])
async def test_chat_account_precondition_cannot_replace_authentication(
    session_token: str | None,
) -> None:
    shopper = FakeShopperAgent()
    app = create_app(
        settings=Settings(environment="test", manager_model_provider="deterministic"),
        shopper_agent_service=shopper,
    )
    with patch.object(shopper, "chat", wraps=shopper.chat) as chat:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            if session_token is not None:
                client.cookies.set(SESSION_COOKIE, session_token)
            response = await client.post(
                "/v1/shopper/chat",
                headers={"Idempotency-Key": "unauthenticated-chat"},
                json={"content": "Find boots", "expected_account_id": str(shopper.account.id)},
            )
        assert response.status_code == 401
        chat.assert_not_called()


@pytest.mark.parametrize("binding", ["matched", "mismatched", "omitted"])
async def test_durable_chat_account_precondition_precedes_model_scope_and_receipts(
    binding: str,
) -> None:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = Settings(environment="test", manager_model_provider="deterministic")
    service = DurableShopperAgentService(database, search_service=SearchService())
    tenant_id, account_id, other_account_id = uuid4(), uuid4(), uuid4()
    request = ShopperChatRequest(content="Find boots")
    if binding != "omitted":
        request.expected_account_id = account_id if binding == "matched" else other_account_id
    with (
        patch("open_commerce.stores.usage.model_scope") as model_scope,
        patch.object(service, "_chat_scoped") as chat,
        patch.object(service.agent, "respond") as agent,
    ):
        if binding == "mismatched":
            with pytest.raises(ShopperAuthenticationError) as error:
                await service.chat(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    request=request,
                    idempotency_key="bound-chat",
                )
            assert str(account_id) not in str(error.value)
            assert str(other_account_id) not in str(error.value)
            model_scope.assert_not_called()
            chat.assert_not_called()
        else:
            response = await service.chat(
                tenant_id=tenant_id,
                account_id=account_id,
                request=request,
                idempotency_key="bound-chat",
            )
            assert response is chat.return_value
            model_scope.assert_called_once_with(database, tenant_id, account_id)
            chat.assert_awaited_once_with(
                tenant_id=tenant_id,
                account_id=account_id,
                request=request,
                idempotency_key="bound-chat",
            )
        database.transaction.assert_not_called()
        agent.assert_not_called()


@pytest.mark.parametrize("has_conversation", [False, True])
@pytest.mark.parametrize("binding", ["provided", "omitted", "null"])
def test_chat_account_precondition_preserves_legacy_serialization_and_receipt_hash(
    has_conversation: bool, binding: str
) -> None:
    legacy_payload: dict[str, object] = {
        "content": "Find waterproof boots",
        "conversation_id": str(uuid4()) if has_conversation else None,
    }
    payload = dict(legacy_payload)
    account_id = uuid4()
    if binding != "omitted":
        payload["expected_account_id"] = str(account_id) if binding == "provided" else None
    request = ShopperChatRequest.model_validate(payload)
    assert request.expected_account_id == (account_id if binding == "provided" else None)
    assert "expected_account_id" not in request.model_dump()
    assert request.model_dump(mode="json") == legacy_payload
    assert json.loads(request.model_dump_json()) == legacy_payload
    assert canonical_hash(request) == canonical_hash(legacy_payload)
    assert canonical_hash(request) != canonical_hash({**legacy_payload, "content": "Find sandals"})
