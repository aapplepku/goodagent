"""Credential admission and private merge grants with offline persistence doubles."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.config import Settings
from open_commerce.persistence.models.commerce import ShopperCartLineRecord, ShopperCartRecord
from open_commerce.persistence.models.shopper import ShopperAccountRecord, ShopperSessionRecord
from open_commerce.persistence.models.store_setup import AuthTicketRecord, MerchantCredentialRecord
from open_commerce.persistence.repositories.commerce import CommerceRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import hash_password
from open_commerce.shopper_agent.models import ShopperLoginRequest
from open_commerce.stores import auth, shoppers
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import OwnerLoginRequest, StoreError, StoreProfile
from open_commerce.stores.shoppers import MergeSelection, ShopperAccounts

TENANT, OWNER, ACCOUNT, GUEST = [UUID(int=i) for i in range(13301, 13305)]
NOW = datetime(2026, 10, 18, tzinfo=UTC)
PASSWORD = "synthetic-password-only"


def session_double() -> MagicMock:
    session = MagicMock()
    session.__aenter__.return_value = session
    session.scalar = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.parametrize("change", ["none", "password", "recovery", "missing"])
async def test_owner_admission_reloads_and_locks_after_verification(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = MagicMock(runtime_profile="self_hosted")
    read, write = session_double(), session_double()
    database.sessions = MagicMock(side_effect=[read, write])
    record = MerchantCredentialRecord(
        user_id=OWNER,
        username="synthetic-owner",
        password_hash="old-hash",
        recovery_hash="old-code",
    )
    read.scalar.return_value = record
    write.scalar.return_value = record if change != "missing" else None

    async def verify(password: str, encoded: str) -> bool:
        assert password == PASSWORD and encoded == "old-hash"
        read.__aexit__.assert_awaited_once()
        assert database.sessions.call_count == 1
        # Deliberately mutate the original object: the verified snapshot must be immutable.
        if change == "password":
            record.password_hash = "replacement-hash"
        elif change == "recovery":
            record.recovery_hash = "console-replacement-code"
        return True

    monkeypatch.setattr(auth, "verify_password", verify)
    service = MerchantAuthService(database)
    profile = AsyncMock(
        return_value=StoreProfile(id=TENANT, name="Synthetic store", slug="synthetic")
    )
    monkeypatch.setattr(service, "_owned_profile", profile)
    payload = OwnerLoginRequest(username="Synthetic-Owner", password=PASSWORD)
    if change == "none":
        result, token = await service.login(payload)
        assert result.user_id == OWNER and token
        profile.assert_awaited_once_with(write, OWNER)
        write.add.assert_called_once()
        write.flush.assert_awaited_once()
    else:
        with pytest.raises(StoreError) as error:
            await service.login(payload)
        assert error.value.status_code == 401
        assert str(error.value) == "The username or password is incorrect."
        profile.assert_not_awaited()
        write.add.assert_not_called()
        write.flush.assert_not_awaited()
    first = read.scalar.call_args.args[0]
    locked = write.scalar.call_args.args[0]
    assert first._for_update_arg is None
    assert locked._for_update_arg is not None
    assert locked.compile().params == {"user_id_1": OWNER, "username_1": "synthetic-owner"}
    write.begin.assert_called_once()


@pytest.mark.parametrize("reason", ["absent", "incorrect", "hosted"])
async def test_owner_failure_does_not_start_admission(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = MagicMock(runtime_profile="hosted" if reason == "hosted" else "self_hosted")
    read = session_double()
    read.scalar.return_value = (
        None
        if reason == "absent"
        else MerchantCredentialRecord(
            user_id=OWNER, username="synthetic-owner", password_hash="old-hash", recovery_hash=None
        )
    )
    database.sessions = MagicMock(return_value=read)
    verify = AsyncMock(return_value=False)
    monkeypatch.setattr(auth, "verify_password", verify)
    with pytest.raises(StoreError) as error:
        await MerchantAuthService(database).login(
            OwnerLoginRequest(username="synthetic-owner", password=PASSWORD)
        )
    assert error.value.status_code == (403 if reason == "hosted" else 401)
    assert database.sessions.call_count == (0 if reason == "hosted" else 1)
    assert verify.await_count == (1 if reason == "incorrect" else 0)
    read.add.assert_not_called()


def account(account_id: UUID, *, guest: bool = False) -> ShopperAccountRecord:
    return ShopperAccountRecord(
        id=account_id,
        tenant_id=TENANT,
        username="synthetic-guest" if guest else "synthetic-account",
        display_name="Synthetic shopper",
        password_hash="disabled" if guest else "old-hash",
        recovery_hash=None if guest else "old-code",
        is_guest=guest,
        memory_enabled=True,
        status="active",
        expires_at=None,
        preview_catalog_id=None,
        version=4,
        created_at=NOW,
        updated_at=NOW,
    )


@dataclass
class ShopperHarness:
    database: MagicMock
    read: MagicMock
    write: MagicMock
    commerce: MagicMock
    service: ShopperAccounts
    target: ShopperAccountRecord
    guest: ShopperAccountRecord
    carts: dict[UUID, ShopperCartRecord]
    grant: AuthTicketRecord | None = None
    in_write: bool = False
    merge: AsyncMock = field(default_factory=AsyncMock)

    @asynccontextmanager
    async def transaction(
        self, tenant: UUID, *, write: bool = False
    ) -> AsyncIterator[AsyncSession]:
        assert tenant == TENANT
        self.in_write = write
        try:
            yield cast(AsyncSession, self.write if write else self.read)
        finally:
            self.in_write = False

    async def scalar(self, statement: Select[Any]) -> object:
        assert self.in_write
        params = statement.compile().params
        assert params["tenant_id_1"] == TENANT
        if statement.column_descriptions[0]["entity"] is AuthTicketRecord:
            assert params["purpose_1"] == "guest_merge"
            row = self.grant
            if row and row.consumed_at is None and row.expires_at > NOW:
                assert params["token_hash_1"] == row.token_hash
                return row
            return None
        assert statement.column_descriptions[0]["entity"] is ShopperAccountRecord
        result = self.guest if params["id_1"] == GUEST else self.target
        return result if result.status == "active" else None

    def add(self, row: object) -> None:
        assert self.in_write
        if isinstance(row, AuthTicketRecord):
            self.grant = row

    async def issue_grant(self) -> str:
        response, token = await self.service.login(
            TENANT, GUEST, ShopperLoginRequest(username="synthetic-account", password=PASSWORD)
        )
        assert token is None and response.merge_token
        assert response.account.id == GUEST
        assert self.grant is not None
        private = json.loads(self.grant.payload)["credential_fingerprint"]
        assert private not in response.model_dump_json()
        assert "credential_fingerprint" not in response.model_dump_json()
        assert self.target.password_hash not in self.grant.payload.decode()
        assert self.target.recovery_hash is not None
        assert self.target.recovery_hash not in self.grant.payload.decode()
        self.write.add.reset_mock()
        self.write.flush.reset_mock()
        self.commerce.reset_mock()
        return response.merge_token


@pytest.fixture
def shopper(monkeypatch: pytest.MonkeyPatch) -> ShopperHarness:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = Settings(_env_file=None, shopper_session_days=3)
    read, write = session_double(), session_double()
    target, guest = account(ACCOUNT), account(GUEST, guest=True)
    read.scalar.return_value = target
    carts = {
        identity: ShopperCartRecord(
            id=UUID(int=13310 + number),
            tenant_id=TENANT,
            account_id=identity,
            status="open",
            version=number + 1,
            currency="USD",
            created_at=NOW,
            updated_at=NOW,
        )
        for number, identity in enumerate((GUEST, ACCOUNT))
    }
    commerce = create_autospec(CommerceRepository, instance=True)
    commerce.open_cart.side_effect = lambda *, account_id, **_: carts[account_id]
    commerce.cart_lines.return_value = [
        ShopperCartLineRecord(title="Synthetic item", variant_title="Default", quantity=1)
    ]
    h = ShopperHarness(
        database, read, write, commerce, ShopperAccounts(database), target, guest, carts
    )
    database.transaction.side_effect = h.transaction
    write.scalar.side_effect = h.scalar
    write.add.side_effect = h.add
    monkeypatch.setattr(shoppers, "utc_now", lambda: NOW)
    monkeypatch.setattr(shoppers, "CommerceRepository", lambda *_: commerce)
    monkeypatch.setattr(h.service, "merge_records", h.merge)

    async def verify(password: str, encoded: str) -> bool:
        assert not h.in_write
        return password == PASSWORD and encoded == "old-hash"

    monkeypatch.setattr(shoppers, "verify_password", verify)
    return h


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize(
    "change", ["password", "username", "guest", "disabled", "expired", "preview"]
)
async def test_shopper_revalidates_before_any_continuity_effect(
    monkeypatch: pytest.MonkeyPatch, shopper: ShopperHarness, change: str, guest: bool
) -> None:
    async def verify(password: str, encoded: str) -> bool:
        assert not shopper.in_write and encoded == "old-hash"
        if change == "password":
            shopper.target.password_hash = "replacement-hash"
        elif change == "username":
            shopper.target.username = "changed-name"
        elif change == "guest":
            shopper.target.is_guest = True
        elif change == "disabled":
            shopper.target.status = "disabled"
        elif change == "expired":
            shopper.target.expires_at = NOW
        else:
            shopper.target.preview_catalog_id = UUID(int=13399)
        return True

    monkeypatch.setattr(shoppers, "verify_password", verify)
    with pytest.raises(StoreError) as error:
        await shopper.service.login(
            TENANT,
            GUEST if guest else None,
            ShopperLoginRequest(username="synthetic-account", password=PASSWORD),
        )
    assert error.value.status_code == 401
    shopper.write.add.assert_not_called()
    shopper.write.flush.assert_not_awaited()
    shopper.write.execute.assert_not_awaited()
    shopper.commerce.open_cart.assert_not_awaited()
    shopper.merge.assert_not_awaited()
    assert shopper.target.version == 4


async def test_matching_shopper_without_guest_receives_session(shopper: ShopperHarness) -> None:
    response, token = await shopper.service.login(
        TENANT, None, ShopperLoginRequest(username="Synthetic-Account", password=PASSWORD)
    )
    assert token and response.account.id == ACCOUNT
    row = shopper.write.add.call_args.args[0]
    assert isinstance(row, ShopperSessionRecord) and row.account_id == ACCOUNT
    assert row.tenant_id == TENANT and row.revoked_at is None
    assert row.created_at == NOW and row.expires_at == NOW + timedelta(days=3)
    shopper.commerce.open_cart.assert_not_awaited()


@pytest.mark.parametrize("choice", ["keep_guest", "keep_account"])
async def test_current_grant_preserves_choice_and_one_time_use(
    shopper: ShopperHarness, choice: str
) -> None:
    token = await shopper.issue_grant()
    request = MergeSelection(token=token, cart_choice=choice)
    response, session = await shopper.service.merge(TENANT, GUEST, request)
    assert response.account.id == ACCOUNT and session
    shopper.merge.assert_awaited_once_with(
        shopper.write, TENANT, shopper.guest, shopper.target, choice
    )
    assert shopper.grant is not None and shopper.grant.consumed_at == NOW
    assert shopper.write.add.call_count == 1
    issued = shopper.write.add.call_args.args[0]
    assert isinstance(issued, ShopperSessionRecord)
    assert issued.created_at == NOW and issued.expires_at == NOW + timedelta(days=3)
    with pytest.raises(StoreError) as error:
        await shopper.service.merge(TENANT, GUEST, request)
    assert error.value.status_code == 401
    assert shopper.write.add.call_count == 1 and shopper.merge.await_count == 1


@pytest.mark.parametrize(
    "change", ["password", "recovery", "unbound", "null", "number", "unicode", "short", "wrong"]
)
async def test_obsolete_or_unbound_grant_has_no_effects(
    shopper: ShopperHarness, change: str
) -> None:
    token = await shopper.issue_grant()
    assert shopper.grant is not None
    data = json.loads(shopper.grant.payload)
    if change == "password":
        shopper.target.password_hash = "replacement-hash"
    elif change == "recovery":
        shopper.target.recovery_hash = "replacement-code"
    elif change == "unbound":
        del data["credential_fingerprint"]
    else:
        data["credential_fingerprint"] = {
            "null": None,
            "number": 17,
            "unicode": "\u00e9" * 64,
            "short": "a",
            "wrong": "0" * 64,
        }[change]
    shopper.grant.payload = json.dumps(data).encode()
    with pytest.raises(StoreError) as error:
        await shopper.service.merge(
            TENANT, GUEST, MergeSelection(token=token, cart_choice="keep_guest")
        )
    assert error.value.status_code == 401
    assert str(error.value) == "Sign in again to review cart changes."
    assert shopper.grant.consumed_at is None
    shopper.commerce.open_cart.assert_not_awaited()
    shopper.merge.assert_not_awaited()
    shopper.write.add.assert_not_called()
    shopper.write.execute.assert_not_awaited()
    shopper.write.flush.assert_not_awaited()
    assert shopper.guest.status == "active" and shopper.guest.version == 4
    assert all(cart.status == "open" for cart in shopper.carts.values())


@pytest.mark.parametrize("obstacle", ["guest", "cart", "expired", "disabled"])
async def test_existing_merge_guards_remain(shopper: ShopperHarness, obstacle: str) -> None:
    token = await shopper.issue_grant()
    assert shopper.grant is not None
    if obstacle == "cart":
        shopper.carts[ACCOUNT].version += 1
    elif obstacle == "expired":
        shopper.grant.expires_at = NOW
    elif obstacle == "disabled":
        shopper.target.status = "disabled"
    with pytest.raises(StoreError) as error:
        await shopper.service.merge(
            TENANT,
            UUID(int=13399) if obstacle == "guest" else GUEST,
            MergeSelection(token=token, cart_choice="keep_account"),
        )
    assert (
        error.value.status_code
        == {"guest": 403, "cart": 409, "expired": 401, "disabled": 401}[obstacle]
    )
    shopper.merge.assert_not_awaited()
    shopper.write.add.assert_not_called()
    assert shopper.grant.consumed_at is None


async def test_same_password_rehash_changes_private_binding() -> None:
    target = account(ACCOUNT)
    first_hash = await hash_password(PASSWORD)
    target.password_hash = first_hash
    first = ShopperAccounts._credential_fingerprint(TENANT, target)
    target.password_hash = await hash_password(PASSWORD)
    assert target.password_hash != first_hash
    assert ShopperAccounts._credential_fingerprint(TENANT, target) != first


def test_private_binding_scopes_target_and_tenant_but_not_data_version() -> None:
    target = account(ACCOUNT)
    baseline = ShopperAccounts._credential_fingerprint(TENANT, target)
    assert ShopperAccounts._credential_fingerprint(UUID(int=13399), target) != baseline
    target.id = UUID(int=13398)
    assert ShopperAccounts._credential_fingerprint(TENANT, target) != baseline
    target.id = ACCOUNT
    target.version += 1
    target.memory_enabled = False
    assert ShopperAccounts._credential_fingerprint(TENANT, target) == baseline
    other = account(UUID(int=13397))
    other.password_hash = "unrelated-account-change"
    assert ShopperAccounts._credential_fingerprint(TENANT, target) == baseline
