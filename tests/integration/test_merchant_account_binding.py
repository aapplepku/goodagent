"""A mounted owner's intent never selects the replacement cookie's store."""

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.persistence.db import Base
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.models import OwnerAuthResponse, StoreProfileUpdate
from open_commerce.stores.setup import StoreSetupService
from open_commerce.worker.jobs import JobRunner

pytestmark = pytest.mark.integration

CATALOG = b"product_id,title,price,currency,inventory_quantity\nfixture-mug,Fixture mug,15,USD,20\n"


def binding(owner: OwnerAuthResponse) -> dict[str, str]:
    return {
        "X-Merchant-Owner-Id": str(owner.user_id),
        "X-Merchant-Store-Id": str(owner.store.id),
    }


async def snapshot(db: RuntimeDatabase, tenant: UUID) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    async with db.transaction(tenant) as session:
        for table in Base.metadata.sorted_tables:
            if "tenant_id" not in table.c:
                continue
            rows = await session.execute(
                select(table)
                .where(table.c.tenant_id == tenant)
                .order_by(*table.primary_key.columns)
            )
            result[table.name] = [dict(row) for row in rows.mappings()]
        rows = await session.execute(select(Tenant.__table__).where(Tenant.id == tenant))
        result["tenants"] = [dict(row) for row in rows.mappings()]
    return result


async def test_stale_owner_and_store_pair_cannot_retarget_protected_operations(
    integration_settings: Settings, tmp_path: Path
) -> None:
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "manager_model_provider": "deterministic",
            "asset_directory": tmp_path,
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
        }
    )
    db = RuntimeDatabase(settings)
    search = DurableSearchService(db, collection_name=f"test_merchant_binding_{uuid4().hex}")
    app = create_app(settings, search_service=search)
    auth = MerchantAuthService(db)
    a, token_a = await auth.oidc_identity("https://merchant-binding-fixture.example", uuid4().hex)
    b, token_b = await auth.oidc_identity("https://merchant-binding-fixture.example", uuid4().hex)
    imports, setup = CatalogImportService(db), StoreSetupService(db)
    try:
        await setup.profile(a.store.id, StoreProfileUpdate(name="Northstar Goods"))
        await setup.profile(b.store.id, StoreProfileUpdate(name="Southbank Goods"))
        staged_a = await imports.upload(a.store.id, "a.csv", CATALOG)
        staged_b = await imports.upload(b.store.id, "b.csv", CATALOG)
        assert staged_b.review_fingerprint
        catalog_b = await imports.confirm(
            b.store.id,
            staged_b.id,
            "fixture-confirm",
            expected_review_fingerprint=staged_b.review_fingerprint,
        )
        assert catalog_b.catalog_id and catalog_b.indexing and catalog_b.indexing.job_id
        await JobRunner(db, b.store.id, search_service=search).run_catalog_index(
            catalog_b.indexing.job_id
        )
        pending_b = await imports.upload(b.store.id, "b-pending.csv", CATALOG)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("open_commerce_merchant_session", token_a)
            assert (
                await client.post(
                    "/v1/manager/workspace/bootstrap",
                    headers={**binding(a), "Idempotency-Key": "bootstrap"},
                )
            ).status_code == 200
            thread_a = await client.post(
                "/v1/manager/threads",
                json={"title": "A retained channel"},
                headers={**binding(a), "Idempotency-Key": "thread"},
            )
            assert thread_a.status_code == 200, thread_a.text
            client.cookies.set("open_commerce_merchant_session", token_b)
            assert (
                await client.post(
                    "/v1/manager/workspace/bootstrap",
                    headers={**binding(b), "Idempotency-Key": "bootstrap"},
                )
            ).status_code == 200
            thread_b = await client.post(
                "/v1/manager/threads",
                json={"title": "B retained channel"},
                headers={**binding(b), "Idempotency-Key": "thread"},
            )
            assert thread_b.status_code == 200, thread_b.text
            thread_b_id = thread_b.json()["thread"]["id"]
            sessions = (await client.get("/v1/merchant/auth/sessions", headers=binding(b))).json()
            session_b_id = sessions["items"][0]["id"]
            preview = await client.post(
                "/v1/merchant/store/preview",
                json={"catalog_id": str(catalog_b.catalog_id)},
                headers=binding(b),
            )
            assert preview.status_code == 200, preview.text
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as shopper:
                shopper.headers["X-Store-Slug"] = b.store.slug
                assert (
                    await shopper.post(
                        f"/v1/stores/{b.store.slug}/preview",
                        json={"token": preview.json()["token"]},
                    )
                ).status_code == 200
                assert (await shopper.post("/v1/shopper/auth/guest")).status_code == 200
                found = await shopper.post(
                    "/v1/shopper/chat",
                    json={"content": "Find a fixture mug"},
                    headers={"Idempotency-Key": "preview-search"},
                )
                assert found.status_code == 200, found.text
            published = await client.post(
                "/v1/merchant/store/sharing",
                json={
                    "catalog_id": str(catalog_b.catalog_id),
                    "enabled": True,
                    "acknowledge_demo_checkout": True,
                    "acknowledge_image_issues": True,
                },
                headers={**binding(b), "Idempotency-Key": "publish-b"},
            )
            assert published.status_code == 200, published.text
            assert published.json()["sharing_enabled"] is True

            before_a, before_b = await snapshot(db, a.store.id), await snapshot(db, b.store.id)
            old = {**binding(a), "Idempotency-Key": "stale-owner"}
            operations: list[tuple[str, str, dict[str, object] | None]] = [
                ("PATCH", "/v1/merchant/store", {"name": "A edited title", "currency": "EUR"}),
                (
                    "POST",
                    "/v1/merchant/store/sharing",
                    {"catalog_id": str(uuid4()), "enabled": False},
                ),
                ("POST", "/v1/manager/workspace/reset", {"confirmation": "RESET"}),
                ("POST", "/v1/manager/workspace/bootstrap", None),
                ("GET", "/v1/manager/workspace", None),
                ("GET", "/v1/manager/commerce/overview", None),
                ("GET", "/v1/manager/catalog", None),
                ("POST", "/v1/manager/threads", {"title": "Must not be created"}),
                ("POST", f"/v1/manager/threads/{thread_b_id}/runs", {"content": "Hello"}),
                ("POST", "/v1/manager/activity/rules", {"name": "Must not be saved"}),
                ("POST", "/v1/merchant/imports/sample", None),
                ("GET", f"/v1/merchant/imports/{pending_b.id}", None),
                (
                    "POST",
                    f"/v1/merchant/imports/{pending_b.id}/confirm",
                    {"expected_review_fingerprint": pending_b.review_fingerprint},
                ),
                ("POST", f"/v1/merchant/imports/{pending_b.id}/cancel", None),
                ("POST", "/v1/merchant/store/check-ai", None),
                ("GET", "/v1/merchant/store", None),
                ("GET", "/v1/merchant/store/measurements", None),
                ("GET", "/v1/merchant/auth/me", None),
                ("GET", "/v1/merchant/auth/sessions", None),
                ("DELETE", f"/v1/merchant/auth/sessions/{session_b_id}", None),
                ("POST", "/v1/merchant/auth/logout", None),
            ]
            for method, path, body in operations:
                response = await client.request(method, path, json=body, headers=old)
                assert response.status_code == 401, (method, path, response.text)
                assert "set-cookie" not in response.headers
                assert str(b.store.id) not in response.text
                assert str(b.user_id) not in response.text
            uploaded = await client.post(
                "/v1/merchant/imports/upload?filename=stale.csv",
                content=CATALOG,
                headers={**old, "Content-Type": "text/csv"},
            )
            assert uploaded.status_code == 401, uploaded.text
            # A correctly keyed receipt in B cannot be read using stale A intent.
            replay = await client.post(
                "/v1/manager/workspace/bootstrap",
                headers={**binding(a), "Idempotency-Key": "bootstrap"},
            )
            assert replay.status_code == 401
            for headers in (
                {"X-Merchant-Owner-Id": str(a.user_id), "X-Merchant-Store-Id": str(b.store.id)},
                {"X-Merchant-Owner-Id": str(b.user_id), "X-Merchant-Store-Id": str(a.store.id)},
            ):
                assert (await client.get("/v1/merchant/store", headers=headers)).status_code == 401
                assert (
                    await client.get("/v1/manager/workspace", headers=headers)
                ).status_code == 401
            for headers in (
                {"X-Merchant-Owner-Id": str(b.user_id)},
                {"X-Merchant-Store-Id": str(b.store.id)},
                {**binding(b), "X-Merchant-Owner-Id": "malformed"},
            ):
                assert (await client.get("/v1/merchant/store", headers=headers)).status_code == 422
                assert (
                    await client.get("/v1/manager/workspace", headers=headers)
                ).status_code == 422
            assert await snapshot(db, a.store.id) == before_a
            assert await snapshot(db, b.store.id) == before_b

            # Current cookie identity may be discovered only by an explicit unbound read.
            me = await client.get("/v1/merchant/auth/me")
            assert me.status_code == 200 and me.json()["store"]["id"] == str(b.store.id)
            current = await client.get("/v1/merchant/store", headers=binding(b))
            assert current.status_code == 200 and current.json()["store"]["sharing_enabled"]
            assert (
                await client.get(f"/v1/merchant/imports/{staged_a.id}", headers=binding(b))
            ).status_code == 404
            assert (
                await client.get(
                    f"/v1/manager/threads/{thread_a.json()['thread']['id']}", headers=binding(b)
                )
            ).status_code == 404
            client.cookies.clear()
            assert (await client.get("/v1/merchant/store", headers=binding(b))).status_code == 401
            assert (
                await client.get("/v1/manager/workspace", headers=binding(b))
            ).status_code == 401
    finally:
        await search.client.delete_collection(search.collection_name)
        await search.close()
        await app.state.database.close()
        await db.close()
