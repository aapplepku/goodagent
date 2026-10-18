"""A stale view's account expectation cannot retarget another valid session."""

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.db import Base
from open_commerce.persistence.models.shopper import ShopperMemoryRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.setup import StoreSetupService
from open_commerce.worker.jobs import JobRunner

pytestmark = pytest.mark.integration

# Include receipts, audit, reservations and login tickets, not just visible state.
SNAPSHOT_TABLES = (
    "shopper_accounts",
    "shopper_sessions",
    "shopper_conversations",
    "shopper_messages",
    "shopper_memories",
    "shopper_activity",
    "activity_rules",
    "activity_checks",
    "shopper_carts",
    "shopper_cart_lines",
    "inventory_reservations",
    "payment_attempts",
    "shopper_orders",
    "idempotency_records",
    "audit_events",
    "auth_tickets",
)


async def snapshot(db: RuntimeDatabase, tenant: UUID) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    async with db.transaction(tenant) as session:
        for name in SNAPSHOT_TABLES:
            table = Base.metadata.tables[name]
            rows = await session.execute(
                select(table)
                .where(table.c.tenant_id == tenant)
                .order_by(*table.primary_key.columns)
            )
            result[name] = [dict(row) for row in rows.mappings()]
    return result


async def test_stale_account_requests_leave_other_account_unchanged(
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "manager_model_provider": "deterministic",
            "asset_directory": tmp_path,
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"b" * 32).decode()),
        }
    )
    db = RuntimeDatabase(settings)
    search = DurableSearchService(db, collection_name=f"test_account_binding_{uuid4().hex}")
    app = create_app(settings, search_service=search)
    owner, _ = await MerchantAuthService(db).oidc_identity(
        "https://account-binding-fixture.example",
        uuid4().hex,
    )
    tenant = owner.store.id
    imports, setup = CatalogImportService(db), StoreSetupService(db)
    try:
        upload = await imports.upload(
            tenant,
            "catalog.csv",
            b"product_id,title,price,currency,inventory_quantity\nmug,Travel mug,15,USD,50\n",
        )
        assert upload.review_fingerprint
        catalog = await imports.confirm(
            tenant, upload.id, "confirm", expected_review_fingerprint=upload.review_fingerprint
        )
        assert catalog.indexing and catalog.indexing.job_id and catalog.catalog_id
        await JobRunner(db, tenant, search_service=search).run_catalog_index(
            catalog.indexing.job_id
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.headers["x-store-slug"] = owner.store.slug
            grant = await setup.preview(tenant, catalog.catalog_id)
            assert (
                await client.post(
                    f"/v1/stores/{owner.store.slug}/preview",
                    json={"token": grant.token},
                )
            ).status_code == 200
            created_a = await client.post("/v1/shopper/auth/guest")
            assert created_a.json()["created"] is True
            a = created_a.json()["account"]["id"]
            cookies_a = dict(client.cookies)
            await client.post("/v1/shopper/auth/logout")
            created_b = await client.post("/v1/shopper/auth/guest")
            assert created_b.json()["created"] is True
            b = created_b.json()["account"]["id"]
            assert a != b
            matching = {"X-Shopper-Account-Id": b, "Idempotency-Key": "original-add"}
            added = await client.post(
                "/v1/shopper/cart/items",
                json={"product_id": "mug", "quantity": 2},
                headers=matching,
            )
            assert added.status_code == 200, added.text
            cart = (await client.get("/v1/shopper/cart", headers=matching)).json()
            chat = await client.post(
                "/v1/shopper/chat",
                json={"content": "Find a travel mug"},
                headers={**matching, "Idempotency-Key": "original-chat"},
            )
            assert chat.status_code == 200, chat.text
            conversation = chat.json()["conversation"]["id"]
            memory = uuid4()
            async with db.transaction(tenant, write=True) as session:
                session.add(
                    ShopperMemoryRecord(
                        id=memory,
                        tenant_id=tenant,
                        account_id=UUID(b),
                        source_message_id=UUID(chat.json()["user_message"]["id"]),
                        content="Synthetic preference for travel mugs",
                        created_at=utc_now(),
                    )
                )
            rule: dict[str, object] = {
                "name": "Fixture cart activity",
                "query": {"kind": "cart_add"},
            }
            assert (
                await client.post(
                    "/v1/shopper/activity/rules",
                    json=rule,
                    headers={**matching, "Idempotency-Key": "original-rule"},
                )
            ).status_code == 200
            assert (
                await client.patch(
                    "/v1/shopper/preferences",
                    json={"enabled": False},
                    headers={**matching, "Idempotency-Key": "original-preference"},
                )
            ).status_code == 200
            preview = await client.post(
                "/v1/shopper/checkout/preview",
                json={"cart_version": cart["version"]},
                headers={**matching, "Idempotency-Key": "original-checkout"},
            )
            assert preview.status_code == 200, preview.text
            checkout_id = preview.json()["checkout_id"]
            cart = (await client.get("/v1/shopper/cart", headers=matching)).json()
            before = await snapshot(db, tenant)
            cookies_b = dict(client.cookies)
            reused = await client.post("/v1/shopper/auth/guest")
            assert reused.status_code == 200
            assert reused.json()["created"] is False
            assert reused.json()["account"]["id"] == b
            assert "set-cookie" not in reused.headers
            assert dict(client.cookies) == cookies_b
            line = cart["lines"][0]["id"]
            # Include B-owned IDs and its exact cart version: ownership checks alone
            # would permit these operations, but the stale A intent must not.
            operations: list[tuple[str, str, dict[str, object] | None]] = [
                ("DELETE", "/shopping-data", None),
                ("DELETE", "/auth/sessions", None),
                ("POST", "/auth/logout", None),
                ("PATCH", "/preferences", {"enabled": True}),
                ("POST", "/cart/items", {"product_id": "mug", "quantity": 1}),
                ("PATCH", f"/cart/items/{line}", {"quantity": 3}),
                ("DELETE", f"/cart/items/{line}", None),
                ("POST", "/checkout/preview", {"cart_version": cart["version"]}),
                (
                    "POST",
                    "/checkout/confirm",
                    {
                        "checkout_id": checkout_id,
                        "payment_method": "test_success",
                    },
                ),
                ("DELETE", f"/memories/{memory}", None),
                ("POST", "/activity/rules", rule),
                ("POST", "/product-selections", {"product_id": "mug", "quantity": 1}),
                ("POST", "/chat", {"content": "This must not be saved for B"}),
                (
                    "POST",
                    "/auth/register",
                    {
                        "username": "wrong-guest",
                        "display_name": "Not B",
                        "password": "synthetic-test-password",
                    },
                ),
                (
                    "POST",
                    "/auth/login",
                    {
                        "username": "not-an-account",
                        "password": "synthetic-test-password",
                    },
                ),
                ("GET", "/me", None),
                ("GET", "/cart", None),
                ("GET", "/memories", None),
                ("GET", "/activity", None),
                ("GET", "/auth/sessions", None),
                ("GET", "/conversations", None),
                ("GET", f"/conversations/{conversation}", None),
                ("GET", "/checkout/current", None),
                ("GET", f"/checkout/{checkout_id}", None),
                ("GET", "/orders", None),
                ("GET", "/catalog", None),
            ]
            for index, (method, path, body) in enumerate(operations):
                response = await client.request(
                    method,
                    f"/v1/shopper{path}",
                    json=body,
                    headers={"X-Shopper-Account-Id": a, "Idempotency-Key": f"stale-{index}"},
                )
                assert response.status_code == 401, (method, path, response.text)
                assert b not in response.text
                assert "set-cookie" not in response.headers
                assert dict(client.cookies) == cookies_b
            # Even an existing B receipt cannot be replayed into an A-labelled UI.
            for path, method, replay_body, key in (
                ("/cart/items", "POST", {"product_id": "mug", "quantity": 2}, "original-add"),
                ("/preferences", "PATCH", {"enabled": False}, "original-preference"),
            ):
                replay = await client.request(
                    method,
                    f"/v1/shopper{path}",
                    json=replay_body,
                    headers={
                        "X-Shopper-Account-Id": a,
                        "Idempotency-Key": key,
                    },
                )
                assert replay.status_code == 401
            assert await snapshot(db, tenant) == before
            assert (await client.get("/v1/shopper/cart", headers=matching)).json() == cart
            # Explicit discovery is deliberately unbound; it reveals the new
            # authenticated identity for recovery without replaying the old action.
            assert (await client.get("/v1/shopper/me")).json()["account"]["id"] == b
            denied = await client.get(
                "/v1/shopper/cart",
                headers={
                    "x-store-slug": f"unknown-{uuid4().hex}",
                    "X-Shopper-Account-Id": b,
                },
            )
            assert denied.status_code == 404
            client.cookies.clear()
            assert (await client.get("/v1/shopper/cart", headers=matching)).status_code == 404
            # Restoring an old, now revoked A cookie cannot turn its expected ID
            # into authorization. Re-establish only the private preview grant.
            client.cookies.update(cookies_a)
            assert (
                await client.get(
                    "/v1/shopper/cart",
                    headers={
                        "X-Shopper-Account-Id": a,
                    },
                )
            ).status_code == 401
    finally:
        await search.client.delete_collection(search.collection_name)
        await search.close()
        await app.state.database.close()
        await db.close()
