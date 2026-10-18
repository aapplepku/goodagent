"""Committed recovery must fence previously verified local authentication."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from http.cookies import SimpleCookie
from types import ModuleType
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request, Response
from sqlalchemy import delete, func, select

import open_commerce.stores.auth as owner_module
import open_commerce.stores.console as console_module
import open_commerce.stores.shoppers as shopper_module
import tests.integration.test_checkout_account_continuity as checkout_fixtures
from open_commerce.api.context import RequestContext
from open_commerce.api.shopper import recover_shopper
from open_commerce.catalog.scope import CatalogScope, catalog_scope
from open_commerce.commerce.models import CartItemAddRequest
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.commerce import ShopperCartRecord
from open_commerce.persistence.models.shopper import ShopperAccountRecord, ShopperSessionRecord
from open_commerce.persistence.models.store_setup import AuthTicketRecord, MerchantCredentialRecord
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.shopper_agent.auth import hash_password, session_token_hash
from open_commerce.shopper_agent.models import ShopperLoginRequest, ShopperRegisterRequest
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import OwnerLoginRequest, OwnerRecoveryRequest, StoreError
from open_commerce.stores.shoppers import MergeSelection, ShopperAccounts, ShopperRecovery

pytestmark = pytest.mark.integration
checkout_store = checkout_fixtures.checkout_store
OLD_PASSWORD = "synthetic-original-recovery-password"
NEW_PASSWORD = "synthetic-replacement-recovery-password"


def recovery_request(database: RuntimeDatabase) -> Request:
    app = FastAPI()
    app.state.settings = database.settings
    app.state.database = database
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "server": ("fixture.invalid", 80),
            "path": "/v1/shopper/auth/recover",
            "headers": [(b"x-store-slug", b"synthetic-recovery")],
            "app": app,
        }
    )


@pytest.mark.parametrize("days", [1, 7, 30])
@pytest.mark.parametrize("operation", ["upgrade", "login", "recovery"])
async def test_new_registered_sessions_honor_configured_lifetime(
    checkout_store: tuple[RuntimeDatabase, UUID],
    monkeypatch: pytest.MonkeyPatch,
    days: int,
    operation: str,
) -> None:
    original, tenant = checkout_store
    database = RuntimeDatabase(
        original.settings.model_copy(
            update={"runtime_profile": "self_hosted", "shopper_session_days": days}
        ),
        sessions=original.sessions,
    )
    now = utc_now()
    monkeypatch.setattr(shopper_module, "utc_now", lambda: now)
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    registered, token = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="session-policy", display_name="Synthetic shopper", password=OLD_PASSWORD
        ),
    )
    if operation == "login":
        _, issued = await accounts.login(
            tenant, None, ShopperLoginRequest(username="session-policy", password=OLD_PASSWORD)
        )
        assert issued
        token = issued
    elif operation == "recovery":
        response = Response()
        result = await recover_shopper(
            ShopperRecovery(
                username="session-policy", code=registered.recovery_code, password=NEW_PASSWORD
            ),
            recovery_request(database),
            response,
            RequestContext(tenant_id=tenant, actor_id="fixture", roles={"shopper"}),
        )
        assert result.account.id == registered.account.id and result.recovery_code
        cookies: SimpleCookie = SimpleCookie()
        cookies.load(response.headers["set-cookie"])
        cookie = cookies["open_commerce_shopper_session_synthetic-recovery"]
        assert int(cookie["max-age"]) == days * 24 * 60 * 60
        assert cookie["httponly"] and cookie["samesite"] == "strict"
        token = cookie.value
    expires = now + timedelta(days=days)
    async with database.transaction(tenant) as session:
        row = await session.scalar(
            select(ShopperSessionRecord).where(
                ShopperSessionRecord.tenant_id == tenant,
                ShopperSessionRecord.token_hash == session_token_hash(token),
            )
        )
        assert row is not None and row.created_at == now and row.expires_at == expires
        repo = ShopperRepository(session, tenant)
        assert await repo.account_for_session(
            token_hash=session_token_hash(token), now=expires - timedelta(microseconds=1)
        )
        assert (
            await repo.account_for_session(token_hash=session_token_hash(token), now=expires)
            is None
        )
        assert (
            await repo.account_for_session(
                token_hash=session_token_hash(token), now=expires + timedelta(days=1)
            )
            is None
        )


@pytest.mark.parametrize("days", [1, 7, 30])
async def test_guest_session_keeps_its_own_expiry(
    checkout_store: tuple[RuntimeDatabase, UUID], monkeypatch: pytest.MonkeyPatch, days: int
) -> None:
    original, tenant = checkout_store
    database = RuntimeDatabase(
        original.settings.model_copy(update={"shopper_session_days": days}),
        sessions=original.sessions,
    )
    now = utc_now()
    monkeypatch.setattr(shopper_module, "utc_now", lambda: now)
    guest, token = await ShopperAccounts(database).guest(tenant, None)
    assert token and guest.account.is_guest
    async with database.transaction(tenant) as session:
        row = await session.scalar(
            select(ShopperSessionRecord).where(
                ShopperSessionRecord.tenant_id == tenant,
                ShopperSessionRecord.token_hash == session_token_hash(token),
            )
        )
        assert row is not None and row.expires_at == now + timedelta(hours=24)
        repo = ShopperRepository(session, tenant)
        assert await repo.account_for_session(
            token_hash=session_token_hash(token), now=now + timedelta(hours=23)
        )
        assert (
            await repo.account_for_session(
                token_hash=session_token_hash(token), now=now + timedelta(hours=24)
            )
            is None
        )


async def test_preview_recovery_rejects_before_consuming_public_credentials(
    checkout_store: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    registered, old_token = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="preview-recovery", display_name="Synthetic shopper", password=OLD_PASSWORD
        ),
    )
    payload = ShopperRecovery(
        username="preview-recovery", code=registered.recovery_code, password=NEW_PASSWORD
    )
    async with database.transaction(tenant) as session:
        credentials = await session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == tenant,
                ShopperAccountRecord.id == registered.account.id,
            )
        )
        assert credentials is not None
        before = (credentials.password_hash, credentials.recovery_hash)
    response = Response()
    with catalog_scope(CatalogScope(tenant, uuid4(), preview=True)):
        with pytest.raises(StoreError) as rejected:
            await recover_shopper(
                payload,
                recovery_request(database),
                response,
                RequestContext(tenant_id=tenant, actor_id="fixture-preview", roles={"shopper"}),
            )
        assert rejected.value.status_code == 409
    assert "set-cookie" not in response.headers
    async with database.transaction(tenant) as session:
        unchanged = await session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == tenant,
                ShopperAccountRecord.id == registered.account.id,
            )
        )
        assert unchanged is not None
        assert (unchanged.password_hash, unchanged.recovery_hash) == before
        assert await ShopperRepository(session, tenant).account_for_session(
            token_hash=session_token_hash(old_token), now=utc_now()
        )
    recovered, fresh = await accounts.recover(tenant, payload)
    assert fresh and recovered.account.id == registered.account.id and recovered.recovery_code
    with pytest.raises(StoreError) as replay:
        await accounts.recover(tenant, payload)
    assert replay.value.status_code == 401


async def test_overlapping_recovery_consumes_a_code_once(
    checkout_store: tuple[RuntimeDatabase, UUID],
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    registered, _ = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="concurrent-recovery", display_name="Synthetic shopper", password=OLD_PASSWORD
        ),
    )
    payload = ShopperRecovery(
        username="concurrent-recovery", code=registered.recovery_code, password=NEW_PASSWORD
    )
    outcomes = await asyncio.gather(
        accounts.recover(tenant, payload), accounts.recover(tenant, payload), return_exceptions=True
    )
    assert sum(isinstance(result, tuple) for result in outcomes) == 1
    assert (
        sum(isinstance(result, StoreError) and result.status_code == 401 for result in outcomes)
        == 1
    )
    async with database.transaction(tenant) as session:
        active = await session.scalar(
            select(func.count())
            .select_from(ShopperSessionRecord)
            .where(
                ShopperSessionRecord.tenant_id == tenant,
                ShopperSessionRecord.account_id == registered.account.id,
                ShopperSessionRecord.revoked_at.is_(None),
            )
        )
        assert active == 1


@dataclass
class OwnerFixture:
    database: RuntimeDatabase
    service: MerchantAuthService
    user_id: UUID
    username: str
    recovery: str
    session: str


@pytest.fixture
async def local_owner(integration_settings: Settings) -> AsyncIterator[OwnerFixture]:
    database = RuntimeDatabase(
        integration_settings.model_copy(update={"runtime_profile": "self_hosted"})
    )
    service = MerchantAuthService(database)
    identity, token = await service.oidc_identity("https://fixture.invalid", uuid4().hex)
    username, recovery = f"recovery-{uuid4().hex}", uuid4().hex
    try:
        async with database.sessions() as session, session.begin():
            session.add(
                MerchantCredentialRecord(
                    user_id=identity.user_id,
                    username=username,
                    password_hash=await hash_password(OLD_PASSWORD),
                    recovery_hash=session_token_hash(recovery),
                )
            )
        yield OwnerFixture(database, service, identity.user_id, username, recovery, token)
    finally:
        # Only this fixture's synthetic credential; keep other suite owners independent.
        async with database.sessions() as session, session.begin():
            await session.execute(
                delete(MerchantCredentialRecord).where(
                    MerchantCredentialRecord.user_id == identity.user_id,
                )
            )
        await database.close()


def hold_verification(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
) -> tuple[asyncio.Event, asyncio.Event]:
    entered, release = asyncio.Event(), asyncio.Event()
    verify = cast(Callable[[str, str], Awaitable[bool]], module.verify_password)

    async def held(password: str, hashed: str) -> bool:
        result = await verify(password, hashed)
        entered.set()
        await release.wait()
        return result

    monkeypatch.setattr(module, "verify_password", held)
    return entered, release


@pytest.mark.parametrize("replacement", [NEW_PASSWORD, OLD_PASSWORD])
async def test_owner_recovery_rejects_delayed_old_verification(
    local_owner: OwnerFixture,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    owner = local_owner
    entered, release = hold_verification(monkeypatch, owner_module)
    task = asyncio.create_task(
        owner.service.login(
            OwnerLoginRequest(
                username=owner.username,
                password=OLD_PASSWORD,
            )
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        _, current = await asyncio.wait_for(
            owner.service.recover(
                OwnerRecoveryRequest(
                    username=owner.username,
                    recovery_code=owner.recovery,
                    password=replacement,
                )
            ),
            5,
        )
        with pytest.raises(StoreError):
            await owner.service.authenticate(owner.session)
        assert (await owner.service.authenticate(current)).user_id == owner.user_id
        release.set()
        with pytest.raises(StoreError) as rejected:
            await asyncio.wait_for(task, 5)
        assert rejected.value.status_code == 401
        _, fresh = await owner.service.login(
            OwnerLoginRequest(
                username=owner.username,
                password=replacement,
            )
        )
        assert (await owner.service.authenticate(fresh)).user_id == owner.user_id
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("replacement", [NEW_PASSWORD, OLD_PASSWORD])
@pytest.mark.parametrize("guest_mode", ["none", "guest_cart", "conflicting_carts"])
async def test_shopper_recovery_rejects_delayed_old_verification(
    checkout_store: tuple[RuntimeDatabase, UUID],
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
    guest_mode: str,
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    guest, _ = await accounts.guest(tenant, None)
    account, old_session = await accounts.upgrade(
        tenant,
        guest.account.id,
        ShopperRegisterRequest(
            username="shopper-recovery-race",
            display_name="Synthetic shopper",
            password=OLD_PASSWORD,
        ),
    )
    browsing_guest, _ = await accounts.guest(tenant, None)
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    if guest_mode != "none":
        await commerce.add_item(
            tenant_id=tenant,
            account_id=browsing_guest.account.id,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
            idempotency_key="guest-cart",
            request_id="guest-cart",
        )
    if guest_mode == "conflicting_carts":
        await commerce.add_item(
            tenant_id=tenant,
            account_id=account.account.id,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
            idempotency_key="target-cart",
            request_id="target-cart",
        )
    entered, release = hold_verification(monkeypatch, shopper_module)
    task = asyncio.create_task(
        accounts.login(
            tenant,
            browsing_guest.account.id if guest_mode != "none" else None,
            ShopperLoginRequest(
                username="shopper-recovery-race",
                password=OLD_PASSWORD,
            ),
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        _, current = await asyncio.wait_for(
            accounts.recover(
                tenant,
                ShopperRecovery(
                    username="shopper-recovery-race",
                    code=account.recovery_code,
                    password=replacement,
                ),
            ),
            5,
        )
        before = await continuity_state(database, tenant)
        async with database.transaction(tenant) as session:
            repo = ShopperRepository(session, tenant)
            assert (
                await repo.account_for_session(
                    token_hash=session_token_hash(old_session), now=utc_now()
                )
                is None
            )
            assert (
                await repo.account_for_session(
                    token_hash=session_token_hash(current), now=utc_now()
                )
                is not None
            )
        release.set()
        with pytest.raises(StoreError) as rejected:
            await asyncio.wait_for(task, 5)
        assert rejected.value.status_code == 401
        assert await continuity_state(database, tenant) == before
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("replacement", [NEW_PASSWORD, OLD_PASSWORD])
@pytest.mark.parametrize("choice", ["keep_guest", "keep_account"])
async def test_recovery_rejects_previously_issued_cart_merge(
    checkout_store: tuple[RuntimeDatabase, UUID],
    choice: Literal["keep_guest", "keep_account"],
    replacement: str,
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    original, _ = await accounts.guest(tenant, None)
    target, _ = await accounts.upgrade(
        tenant,
        original.account.id,
        ShopperRegisterRequest(
            username="merge-recovery",
            display_name="Synthetic shopper",
            password=OLD_PASSWORD,
        ),
    )
    guest, _ = await accounts.guest(tenant, None)
    for account in (target.account.id, guest.account.id):
        await commerce.add_item(
            tenant_id=tenant,
            account_id=account,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
            idempotency_key="recovery-cart",
            request_id="recovery-cart",
        )
    grant, token = await accounts.login(
        tenant,
        guest.account.id,
        ShopperLoginRequest(
            username="merge-recovery",
            password=OLD_PASSWORD,
        ),
    )
    assert grant.merge_token and token is None
    await accounts.recover(
        tenant,
        ShopperRecovery(
            username="merge-recovery",
            code=target.recovery_code,
            password=replacement,
        ),
    )
    before = await continuity_state(database, tenant)
    with pytest.raises(StoreError) as rejected:
        await accounts.merge(
            tenant, guest.account.id, MergeSelection(token=grant.merge_token, cart_choice=choice)
        )
    assert rejected.value.status_code == 401
    assert await continuity_state(database, tenant) == before
    async with database.transaction(tenant) as session:
        carts = (
            await session.scalars(
                select(ShopperCartRecord).where(
                    ShopperCartRecord.tenant_id == tenant,
                    ShopperCartRecord.account_id.in_([guest.account.id, target.account.id]),
                )
            )
        ).all()
        assert len(carts) == 2 and all(cart.status == "open" for cart in carts)
        assert (await accounts.account(session, tenant, guest.account.id)).is_guest
    fresh, token = await accounts.login(
        tenant,
        guest.account.id,
        ShopperLoginRequest(username="merge-recovery", password=replacement),
    )
    assert fresh.merge_token and token is None
    merged, token = await accounts.merge(
        tenant, guest.account.id, MergeSelection(token=fresh.merge_token, cart_choice=choice)
    )
    assert merged.account.id == target.account.id and token
    with pytest.raises(StoreError) as consumed:
        await accounts.merge(
            tenant, guest.account.id, MergeSelection(token=fresh.merge_token, cart_choice=choice)
        )
    assert consumed.value.status_code == 401


async def continuity_state(database: RuntimeDatabase, tenant: UUID) -> tuple[object, ...]:
    async with database.transaction(tenant) as session:
        carts = (
            await session.execute(
                select(
                    ShopperCartRecord.id,
                    ShopperCartRecord.account_id,
                    ShopperCartRecord.version,
                    ShopperCartRecord.status,
                )
                .where(ShopperCartRecord.tenant_id == tenant)
                .order_by(ShopperCartRecord.id)
            )
        ).all()
        sessions = await session.scalar(
            select(func.count())
            .select_from(ShopperSessionRecord)
            .where(ShopperSessionRecord.tenant_id == tenant)
        )
        grants = (
            await session.execute(
                select(AuthTicketRecord.purpose, AuthTicketRecord.consumed_at)
                .where(AuthTicketRecord.tenant_id == tenant)
                .order_by(AuthTicketRecord.created_at, AuthTicketRecord.token_hash)
            )
        ).all()
        return tuple(carts), sessions, tuple(grants)


async def test_owner_login_admitted_before_recovery_is_revoked(local_owner: OwnerFixture) -> None:
    owner = local_owner
    _, admitted = await owner.service.login(
        OwnerLoginRequest(username=owner.username, password=OLD_PASSWORD)
    )
    assert (await owner.service.authenticate(admitted)).user_id == owner.user_id
    result, recovered = await owner.service.recover(
        OwnerRecoveryRequest(
            username=owner.username, recovery_code=owner.recovery, password=NEW_PASSWORD
        )
    )
    assert result.recovery_code and result.recovery_code != owner.recovery
    assert (await owner.service.authenticate(recovered)).user_id == owner.user_id
    with pytest.raises(StoreError) as revoked:
        await owner.service.authenticate(admitted)
    assert revoked.value.status_code == 401
    with pytest.raises(StoreError) as reused:
        await owner.service.recover(
            OwnerRecoveryRequest(
                username=owner.username, recovery_code=owner.recovery, password=NEW_PASSWORD
            )
        )
    assert reused.value.status_code == 401


async def test_console_rotation_fences_old_verification_only(
    local_owner: OwnerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = local_owner
    monkeypatch.setattr(console_module, "Settings", lambda: owner.database.settings)
    entered, release = hold_verification(monkeypatch, owner_module)
    task = asyncio.create_task(
        owner.service.login(OwnerLoginRequest(username=owner.username, password=OLD_PASSWORD))
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.wait_for(console_module.run("recover", owner.username), 5)
        # The only printed value is a disposable fixture code; never put it in the report.
        rotated = capsys.readouterr().out.strip()
        assert rotated and rotated != owner.recovery
        with pytest.raises(StoreError):
            await owner.service.authenticate(owner.session)
        release.set()
        with pytest.raises(StoreError) as stale:
            await asyncio.wait_for(task, 5)
        assert stale.value.status_code == 401
        # Console code issuance is not a password change or a permanent login lockout.
        _, fresh = await owner.service.login(
            OwnerLoginRequest(username=owner.username, password=OLD_PASSWORD)
        )
        assert (await owner.service.authenticate(fresh)).user_id == owner.user_id
        _, recovered = await owner.service.recover(
            OwnerRecoveryRequest(
                username=owner.username, recovery_code=rotated, password=NEW_PASSWORD
            )
        )
        assert (await owner.service.authenticate(recovered)).user_id == owner.user_id
        with pytest.raises(StoreError):
            await owner.service.authenticate(fresh)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize(
    ("damage", "expected"),
    [
        ("unbound", 401),
        ("invalid_binding", 401),
        ("foreign_guest", 403),
        ("foreign_store", 401),
        ("expired", 401),
        ("cart_changed", 409),
    ],
)
async def test_merge_grant_rejections_leave_account_and_carts_untouched(
    checkout_store: tuple[RuntimeDatabase, UUID], damage: str, expected: int
) -> None:
    database, tenant = checkout_store
    accounts = ShopperAccounts(database)
    commerce = DurableCommerceService(database, payment_provider=LocalTestPaymentProvider())
    original, _ = await accounts.guest(tenant, None)
    target, _ = await accounts.upgrade(
        tenant,
        original.account.id,
        ShopperRegisterRequest(
            username="grant-controls", display_name="Synthetic shopper", password=OLD_PASSWORD
        ),
    )
    guest, _ = await accounts.guest(tenant, None)
    for account in (target.account.id, guest.account.id):
        await commerce.add_item(
            tenant_id=tenant,
            account_id=account,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
            idempotency_key="grant-control-cart",
            request_id="grant-control-cart",
        )
    response, token = await accounts.login(
        tenant,
        guest.account.id,
        ShopperLoginRequest(username="grant-controls", password=OLD_PASSWORD),
    )
    assert response.merge_token and token is None
    requested_guest, requested_tenant = guest.account.id, tenant
    if damage in {"unbound", "invalid_binding", "expired"}:
        async with database.transaction(tenant, write=True) as session:
            grant = await session.scalar(
                select(AuthTicketRecord).where(
                    AuthTicketRecord.tenant_id == tenant,
                    AuthTicketRecord.token_hash == session_token_hash(response.merge_token),
                )
            )
            assert grant is not None
            if damage == "expired":
                grant.expires_at = utc_now() - timedelta(seconds=1)
            else:
                payload = json.loads(grant.payload)
                # Old releases persisted only these three fields; do not depend on new key names.
                legacy = {key: payload[key] for key in ("guest", "target", "carts")}
                extras = set(payload) - set(legacy)
                if damage == "invalid_binding":
                    assert len(extras) == 1
                    legacy[next(iter(extras))] = {"not": "a credential binding"}
                grant.payload = json.dumps(legacy).encode()
    elif damage == "foreign_guest":
        other, _ = await accounts.guest(tenant, None)
        requested_guest = other.account.id
    elif damage == "foreign_store":
        requested_tenant = uuid4()
        await database.initialize_tenant(requested_tenant)
    elif damage == "cart_changed":
        await commerce.add_item(
            tenant_id=tenant,
            account_id=guest.account.id,
            request=CartItemAddRequest(product_id="fixture-mug", quantity=1),
            idempotency_key="changed-cart",
            request_id="changed-cart",
        )
    before = await continuity_state(database, tenant)
    with pytest.raises(StoreError) as rejected:
        await accounts.merge(
            requested_tenant,
            requested_guest,
            MergeSelection(token=response.merge_token, cart_choice="keep_guest"),
        )
    assert rejected.value.status_code == expected
    assert await continuity_state(database, tenant) == before
    async with database.transaction(tenant) as session:
        assert (await accounts.account(session, tenant, guest.account.id)).is_guest
