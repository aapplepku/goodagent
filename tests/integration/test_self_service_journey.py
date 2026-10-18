"""Publication and guest journeys against isolated PostgreSQL and Qdrant."""

import base64
import hashlib
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import select, update

from open_commerce.api.main import create_app
from open_commerce.catalog.scope import CatalogScope, catalog_scope
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogAssetRecord, CatalogImportRecord
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.shopper_activity import ShopperActivityRecord
from open_commerce.persistence.models.store_setup import AuthTicketRecord, SetupEventRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.imports import CatalogImportService
from open_commerce.stores.measurement import measurements
from open_commerce.stores.models import PublicationRequest, StoreError
from open_commerce.stores.setup import StoreSetupService
from open_commerce.stores.shoppers import ShopperAccounts
from open_commerce.worker.jobs import JobRunner

pytestmark = pytest.mark.integration
CSV = (
    b"product_id,title,price,currency,inventory_quantity\n"
    b"a,Travel mug,15,USD,50\nb,Soft throw,35,USD,30\n"
)


async def test_import_preview_publication_and_guest_continuity(
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "manager_model_provider": "deterministic",
            "asset_directory": tmp_path,
            "encryption_key": SecretStr(base64.urlsafe_b64encode(b"x" * 32).decode()),
        }
    )
    db = RuntimeDatabase(settings)
    search = DurableSearchService(db, collection_name=f"test_setup_{uuid4().hex}")
    owner, owner_cookie = await MerchantAuthService(db).oidc_identity(
        "https://fixture.example", uuid4().hex
    )
    tenant = owner.store.id
    imports = CatalogImportService(db)
    setup = StoreSetupService(db)
    app = create_app(settings, search_service=search)
    try:
        upload = await imports.upload(tenant, "catalog.csv", CSV)
        async with db.transaction(tenant) as session:
            record = await session.scalar(
                select(CatalogImportRecord).where(
                    CatalogImportRecord.tenant_id == tenant, CatalogImportRecord.id == upload.id
                )
            )
            assert record and b"Travel mug" not in record.encrypted_data
        assert upload.review_fingerprint
        confirmed = await imports.confirm(
            tenant, upload.id, "confirm", expected_review_fingerprint=upload.review_fingerprint
        )
        assert confirmed == await imports.confirm(
            tenant, upload.id, "confirm", expected_review_fingerprint=upload.review_fingerprint
        )
        assert confirmed.indexing and confirmed.indexing.job_id and confirmed.catalog_id
        asset_id = uuid4()
        image_path = tmp_path / str(tenant) / f"{asset_id}.png"
        image_path.parent.mkdir()
        Image.new("RGB", (2, 2), "green").save(image_path)
        image_bytes = image_path.read_bytes()
        asset_url = f"/v1/shopper/assets/{asset_id}"
        async with db.transaction(tenant, write=True) as session:
            session.add(
                CatalogAssetRecord(
                    id=asset_id,
                    tenant_id=tenant,
                    import_id=upload.id,
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                    created_at=utc_now(),
                )
            )
            product = await session.scalar(
                select(Product).where(
                    Product.tenant_id == tenant,
                    Product.integration_id == confirmed.catalog_id,
                    Product.source_product_id == "a",
                )
            )
            assert product
            product.attributes = {**product.attributes, "image_failed": True}
            milestones = list(
                await session.scalars(
                    select(SetupEventRecord.kind).where(
                        SetupEventRecord.tenant_id == tenant,
                        SetupEventRecord.kind.in_(["products_uploaded", "products_confirmed"]),
                    )
                )
            )
            assert sorted(milestones) == ["products_confirmed", "products_uploaded"]
        await JobRunner(db, tenant, search_service=search).run_catalog_index(
            confirmed.indexing.job_id
        )
        readiness = await setup.readiness(tenant)
        assert readiness.indexing.status == "ready"
        assert readiness.image_failures == 1
        assert [issue.product_id for issue in readiness.image_issues] == ["a"]
        assert not readiness.image_issues_truncated
        grant = await setup.preview(tenant, confirmed.catalog_id)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            missing_store = await client.get("/v1/shopper/store")
            assert missing_store.status_code == 404
            assert missing_store.json()["error"]["code"] == "STORE_UNAVAILABLE"
            client.headers["x-store-slug"] = owner.store.slug
            unavailable = await client.post("/v1/shopper/auth/guest")
            assert unavailable.status_code == 404
            assert unavailable.json()["error"]["code"] == "STORE_UNAVAILABLE"
            unknown_store = await client.get(
                "/v1/shopper/store", headers={"x-store-slug": f"unknown-{uuid4().hex}"}
            )
            assert unknown_store.status_code == 404
            assert unknown_store.json()["error"]["code"] == "STORE_UNAVAILABLE"
            assert (
                unknown_store.json()["error"]["message"] == unavailable.json()["error"]["message"]
            )
            assert (await client.get(asset_url)).status_code == 404
            exchanged = await client.post(
                f"/v1/stores/{owner.store.slug}/preview", json={"token": grant.token}
            )
            assert exchanged.status_code == 200, exchanged.text
            preview_image = await client.get(asset_url)
            assert preview_image.status_code == 200 and preview_image.content == image_bytes
            assert preview_image.headers["cache-control"] == "no-store"
            assert (
                await client.post(
                    f"/v1/stores/{owner.store.slug}/preview", json={"token": grant.token}
                )
            ).status_code == 401
            guest = await client.post("/v1/shopper/auth/guest")
            assert guest.status_code == 200, guest.text
            assert (await client.get("/v1/merchant/store")).status_code == 401
            browse = await client.get("/v1/shopper/catalog")
            assert browse.status_code == 200 and browse.json()["total"] == 2
            missing_product = await client.post(
                "/v1/shopper/product-selections",
                json={"product_id": "not-a-fixture-product", "quantity": 1},
                headers={"Idempotency-Key": "missing-product"},
            )
            assert missing_product.status_code == 404
            assert missing_product.json()["error"]["code"] == "STORE_REQUEST_BLOCKED"
            async with db.transaction(tenant, write=True) as session:
                await session.execute(
                    update(AuthTicketRecord)
                    .where(
                        AuthTicketRecord.tenant_id == tenant,
                        AuthTicketRecord.purpose == "preview_session",
                    )
                    .values(expires_at=utc_now() - timedelta(seconds=1))
                )
            expired_preview = await client.get("/v1/shopper/catalog")
            assert expired_preview.status_code == 404
            assert expired_preview.json()["error"]["code"] == "STORE_UNAVAILABLE"
            fresh_grant = await setup.preview(tenant, confirmed.catalog_id)
            assert (
                await client.post(
                    f"/v1/stores/{owner.store.slug}/preview", json={"token": fresh_grant.token}
                )
            ).status_code == 200
            assert (await client.get("/v1/shopper/me")).json()["account"]["id"] == guest.json()[
                "account"
            ]["id"]
            assert (await client.get("/v1/shopper/catalog")).json()["total"] == 2
            chat = await client.post(
                "/v1/shopper/chat",
                json={"content": "Find a travel mug"},
                headers={"Idempotency-Key": "search-once"},
            )
            assert chat.status_code == 200, chat.text
            assert chat.json()["assistant_message"]["products"]
            publication = PublicationRequest(
                catalog_id=confirmed.catalog_id,
                enabled=True,
                acknowledge_demo_checkout=True,
                acknowledge_image_issues=True,
            )
            await setup.share(tenant, publication, "share")
            client.cookies.clear()
            public_image = await client.get(asset_url)
            assert public_image.status_code == 200 and public_image.content == image_bytes
            assert public_image.headers["cache-control"] == "no-store"
            guest = await client.post("/v1/shopper/auth/guest")
            guest_id = guest.json()["account"]["id"]
            added = await client.post(
                "/v1/shopper/cart/items",
                json={"product_id": "a", "quantity": 1},
                headers={"Idempotency-Key": "add"},
            )
            assert added.status_code == 200, added.text
            upgraded = await client.post(
                "/v1/shopper/auth/register",
                json={
                    "username": "new-shopper",
                    "display_name": "Tester",
                    "password": "synthetic-test-password",
                },
            )
            assert upgraded.status_code == 201, upgraded.text
            assert upgraded.json()["account"]["id"] == guest_id
            assert upgraded.json()["recovery_code"]
            assert (await client.get("/v1/shopper/cart")).json()["item_count"] == 1
            assert (await client.patch("/v1/shopper/preferences", json={"enabled": False})).json()[
                "account"
            ]["memory_enabled"] is False
            assert (await client.get("/v1/shopper/memories")).json()["items"] == []
            # Signing into an existing account never silently combines carts.
            await client.post("/v1/shopper/auth/logout")
            await client.post("/v1/shopper/auth/guest")
            added = await client.post(
                "/v1/shopper/cart/items",
                json={"product_id": "a", "quantity": 2},
                headers={"Idempotency-Key": "guest-two"},
            )
            assert added.status_code == 200, added.text
            login = await client.post(
                "/v1/shopper/auth/login",
                json={"username": "new-shopper", "password": "synthetic-test-password"},
            )
            assert login.status_code == 200 and login.json()["merge_token"]
            assert login.json()["guest_cart_lines"][0]["quantity"] == 2
            assert login.json()["account_cart_lines"][0]["quantity"] == 1
            # The choice must still describe both carts when it is committed.
            cart = (await client.get("/v1/shopper/cart")).json()
            changed = await client.patch(
                f"/v1/shopper/cart/items/{cart['lines'][0]['id']}",
                json={"quantity": 3},
                headers={"Idempotency-Key": "change-before-merge"},
            )
            assert changed.status_code == 200
            stale = await client.post(
                "/v1/shopper/auth/merge",
                json={"token": login.json()["merge_token"], "cart_choice": "keep_guest"},
            )
            assert stale.status_code == 409 and "cart changed" in stale.text
            login = await client.post(
                "/v1/shopper/auth/login",
                json={"username": "new-shopper", "password": "synthetic-test-password"},
            )
            assert login.json()["guest_cart_lines"][0]["quantity"] == 3
            merged = await client.post(
                "/v1/shopper/auth/merge",
                json={"token": login.json()["merge_token"], "cart_choice": "keep_guest"},
            )
            assert merged.status_code == 200, merged.text
            assert merged.json()["account"]["id"] == guest_id
            assert (await client.get("/v1/shopper/cart")).json()["item_count"] == 3
            # A stale visit cookie cannot block valid account credentials or
            # import the expired guest's private data into that account.
            await client.post("/v1/shopper/auth/logout")
            stale_guest = (await client.post("/v1/shopper/auth/guest")).json()["account"]["id"]
            async with db.transaction(tenant, write=True) as session:
                await session.execute(
                    update(ShopperAccountRecord)
                    .where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.id == stale_guest,
                    )
                    .values(expires_at=utc_now() - timedelta(seconds=1))
                )
            login = await client.post(
                "/v1/shopper/auth/login",
                json={"username": "new-shopper", "password": "synthetic-test-password"},
            )
            assert login.status_code == 200, login.text
            assert login.json()["account"]["id"] == guest_id
            assert not login.json()["merge_token"]
            assert (await client.get("/v1/shopper/cart")).json()["item_count"] == 3
            # A verified replacement stays private until separately tested and approved.
            replacement = await imports.upload(
                tenant, "new.csv", CSV.replace(b"a,Travel", b"c,Travel")
            )
            assert replacement.review_fingerprint
            new_catalog = await imports.confirm(
                tenant,
                replacement.id,
                "confirm-new",
                expected_review_fingerprint=replacement.review_fingerprint,
            )
            assert new_catalog.indexing and new_catalog.indexing.job_id
            await JobRunner(db, tenant, search_service=search).run_catalog_index(
                new_catalog.indexing.job_id
            )
            assert not (await setup.readiness(tenant)).checklist["search_tested"]
            with pytest.raises(StoreError, match="this version's private preview"):
                await setup.share(
                    tenant,
                    publication.model_copy(update={"catalog_id": new_catalog.catalog_id}),
                    "reject-untested-replacement",
                )
            assert (await client.get("/v1/shopper/catalog")).json()["catalog"]["id"] == str(
                confirmed.catalog_id
            )
            saved_cart = (await client.get("/v1/shopper/cart")).json()
            await setup.share(tenant, publication.model_copy(update={"enabled": False}), "disable")
            denied = await client.get("/v1/shopper/catalog")
            assert denied.status_code == 404
            assert denied.json()["error"]["code"] == "STORE_UNAVAILABLE"
            assert (await client.get(asset_url)).status_code == 404
            client.cookies.set("open_commerce_merchant_session", owner_cookie)
            assert (await client.get("/v1/merchant/store")).status_code == 200
            owner_image = await client.get(f"/v1/merchant/assets/{asset_id}")
            assert owner_image.status_code == 200 and owner_image.content == image_bytes
            assert owner_image.headers["cache-control"] == "no-store"
            await setup.share(tenant, publication, "restore-sharing")
            assert (await client.get("/v1/shopper/me")).json()["account"]["id"] == guest_id
            assert (await client.get("/v1/shopper/cart")).json() == saved_cart
    finally:
        await search.client.delete_collection(search.collection_name)
        await search.close()
        await app.state.database.close()
        await db.close()


async def test_guest_quota_and_cross_store_denial(integration_settings: Settings) -> None:
    settings = integration_settings.model_copy(update={"runtime_profile": "self_hosted"})
    db = RuntimeDatabase(settings)
    owner, _ = await MerchantAuthService(db).oidc_identity(
        "https://guest-fixture.example", uuid4().hex
    )
    accounts = ShopperAccounts(db)
    try:
        guest, _ = await accounts.guest(owner.store.id, None)
        for index in range(10):
            assert await accounts.admit_turn(owner.store.id, guest.account.id, str(index))
        assert await accounts.admit_turn(owner.store.id, guest.account.id, "0")
        assert not await accounts.admit_turn(owner.store.id, guest.account.id, "11")
        await accounts.delete_data(owner.store.id, guest.account.id)
        assert not await accounts.admit_turn(owner.store.id, guest.account.id, "12")
        with pytest.raises(StoreError):
            await accounts.upgrade(
                uuid4(),
                guest.account.id,
                ShopperRegisterRequest(
                    username="wrong", display_name="No", password="synthetic-test-password"
                ),
            )
        with catalog_scope(CatalogScope(owner.store.id, uuid4(), preview=True)):
            with pytest.raises(StoreError):
                async with db.transaction(owner.store.id) as session:
                    await accounts.account(session, owner.store.id, guest.account.id)
    finally:
        await db.close()


async def test_search_selection_cohort_excludes_test_and_other_store_activity(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    try:
        owner, _ = await MerchantAuthService(db).oidc_identity(
            "https://fixture.example", uuid4().hex
        )
        other, _ = await MerchantAuthService(db).oidc_identity(
            "https://fixture.example", uuid4().hex
        )
        accounts = ShopperAccounts(db)
        tenant = owner.store.id
        guests = [(await accounts.guest(tenant, None))[0].account.id for _ in range(4)]
        other_guest = (await accounts.guest(other.store.id, None))[0].account.id
        now = utc_now()
        async with db.transaction(tenant, write=True) as session:
            for store, account, kind, seconds, preview, sample in (
                (tenant, guests[0], "search", -30, False, False),
                (tenant, guests[0], "search", -20, False, False),
                (tenant, guests[0], "product_select", -10, False, False),
                (tenant, guests[1], "product_select", -30, False, False),
                (tenant, guests[1], "search", -10, False, False),
                (tenant, guests[2], "search", -30, True, False),
                (tenant, guests[2], "product_select", -10, True, False),
                (tenant, guests[3], "search", -30, False, True),
                (tenant, guests[3], "product_select", -10, False, True),
                (other.store.id, other_guest, "search", -30, False, False),
                (other.store.id, other_guest, "product_select", -10, False, False),
            ):
                session.add(
                    ShopperActivityRecord(
                        id=uuid4(),
                        tenant_id=store,
                        account_id=account,
                        event_key=str(uuid4()),
                        kind=kind,
                        status="ok",
                        duration_ms=0,
                        is_preview=preview,
                        is_sample=sample,
                        occurred_at=now + timedelta(seconds=seconds),
                    )
                )
        result = await measurements(db, tenant)
        assert result.successful_searches == 3
        assert result.product_selections == 2
        assert result.searching_accounts == 2
        assert result.searchers_with_selection == 1
    finally:
        await db.close()
