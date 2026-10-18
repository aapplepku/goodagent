"""Owner setup, identity isolation, recovery, and shared budgets on PostgreSQL."""

import asyncio
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import (
    OwnerLoginRequest,
    OwnerRecoveryRequest,
    OwnerSetupRequest,
    StoreError,
)
from open_commerce.stores.usage import ModelQuotaExceeded, admit_model_call, model_scope
from open_commerce.worker.jobs import JobRunner, runner_for_store

pytestmark = pytest.mark.integration


async def test_bootstrap_does_not_claim_existing_store_and_recovery_revokes_sessions(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(update={"runtime_profile": "self_hosted"})
    db = RuntimeDatabase(settings)
    service = MerchantAuthService(db)
    old_tenant = uuid4()
    await db.initialize_tenant(old_tenant)
    token = await service.issue_bootstrap()
    request = OwnerSetupRequest(
        name="First store",
        username="first-owner",
        password="synthetic-owner-password",
        bootstrap_token=token,
    )
    try:
        created, cookie = await service.setup(request)
        assert created.store.id != old_tenant and not created.store.sharing_enabled
        assert created.store.description == "Find your next favorite at First store."
        assert (await service.authenticate(cookie)).tenant_id == created.store.id
        with pytest.raises(StoreError):
            await service.setup(request)
        with pytest.raises(StoreError):
            await service.issue_bootstrap()
        with pytest.raises(StoreError):
            await service.authenticate(token)
        login, login_cookie = await service.login(
            OwnerLoginRequest(username="first-owner", password="synthetic-owner-password")
        )
        assert login.store.id == created.store.id
        recovered, recovery_cookie = await service.recover(
            OwnerRecoveryRequest(
                username="first-owner",
                recovery_code=SecretStr(created.recovery_code or ""),
                password="replacement-password",
            )
        )
        assert recovered.store.id == created.store.id
        with pytest.raises(StoreError):
            await service.authenticate(login_cookie)
        with pytest.raises(StoreError):
            await service.authenticate(cookie)
        with pytest.raises(StoreError):
            await service.recover(
                OwnerRecoveryRequest(
                    username="first-owner",
                    recovery_code=SecretStr(created.recovery_code or ""),
                    password="replacement-password",
                )
            )
        assert (await service.authenticate(recovery_cookie)).tenant_id == created.store.id
        async with AsyncClient(
            transport=ASGITransport(app=create_app(settings)), base_url="http://test"
        ) as client:
            assert (await client.get("/v1/manager/workspace")).status_code == 401
            client.cookies.set("open_commerce_merchant_session", recovery_cookie)
            assert (await client.get("/v1/merchant/auth/me")).status_code == 200
            assert (await client.post("/v1/simulator/instances", json={})).status_code == 403
            response = await client.get(
                "/v1/shopper/discovery", headers={"x-store-slug": created.store.slug}
            )
            assert response.status_code == 404
    finally:
        await db.close()


async def test_oidc_identity_bound_to_issuer_and_worker_store_validation(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(update={"runtime_profile": "self_hosted"})
    db = RuntimeDatabase(settings)
    auth = MerchantAuthService(db)
    try:
        first, _ = await auth.oidc_identity("https://issuer-one.example", "same-subject")
        again, _ = await auth.oidc_identity("https://issuer-one.example", "same-subject")
        other, _ = await auth.oidc_identity("https://issuer-two.example", "same-subject")
        assert first.user_id == again.user_id and first.store.id == again.store.id
        assert first.user_id != other.user_id and first.store.id != other.store.id
        ctx: dict[str, object] = {"runner": JobRunner(db, settings.local_tenant_id)}
        assert (await runner_for_store(ctx, str(other.store.id))).tenant_id == other.store.id
        with pytest.raises(ValueError, match="unavailable"):
            await runner_for_store(ctx, str(uuid4()))
    finally:
        await db.close()


async def test_model_admission_serializes_concurrent_store_calls(
    integration_settings: Settings,
) -> None:
    settings = integration_settings.model_copy(
        update={"runtime_profile": "self_hosted", "model_daily_request_limit": 1}
    )
    db = RuntimeDatabase(settings)
    store, _ = await MerchantAuthService(db).oidc_identity("https://budget.example", "test-subject")

    async def attempt() -> bool:
        with model_scope(db, store.store.id):
            try:
                await admit_model_call(100, 100)
                return True
            except ModelQuotaExceeded:
                return False

    try:
        assert sorted(await asyncio.gather(attempt(), attempt())) == [False, True]
    finally:
        await db.close()
