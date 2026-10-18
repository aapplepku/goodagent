"""Actual committed-row visibility around guest expiry and successful registration."""

import asyncio
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.shopper import (
    ShopperAccountRecord,
    ShopperConversationRecord,
    ShopperMemoryRecord,
    ShopperMessageRecord,
    ShopperSessionRecord,
)
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.stores.models import StoreError
from open_commerce.stores.shoppers import ShopperAccounts

pytestmark = pytest.mark.integration


async def test_registration_crossing_expiry_survives_a_stale_cleanup_selection(
    integration_settings: Settings,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    upgrade_admitted, cleanup_selected, release_upgrade = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    tasks: list[asyncio.Task[object]] = []
    try:
        await database.initialize_tenant(tenant)
        accounts = ShopperAccounts(database)
        guest, _ = await accounts.guest(tenant, None)
        account = guest.account.id
        deadline = utc_now() + timedelta(minutes=1)
        clock = [deadline - timedelta(microseconds=1)]
        conversation, message, memory = uuid4(), uuid4(), uuid4()
        async with database.transaction(tenant, write=True) as session:
            row = await accounts.account(session, tenant, account)
            row.expires_at = deadline
            session.add(
                ShopperConversationRecord(
                    id=conversation,
                    tenant_id=tenant,
                    account_id=account,
                    title="Keep my progress",
                    created_at=utc_now(),
                    updated_at=utc_now(),
                    version=1,
                )
            )
            await session.flush()
            session.add(
                ShopperMessageRecord(
                    id=message,
                    tenant_id=tenant,
                    account_id=account,
                    conversation_id=conversation,
                    role="user",
                    content="I prefer organic products",
                    created_at=utc_now(),
                )
            )
            await session.flush()
            session.add(
                ShopperMemoryRecord(
                    id=memory,
                    tenant_id=tenant,
                    account_id=account,
                    source_message_id=message,
                    content="Prefers organic products",
                    created_at=utc_now(),
                )
            )
        original_credentials, original_delete = (
            ShopperRepository.get_account_credentials,
            accounts.delete_data,
        )

        async def delayed_credentials(
            repo: ShopperRepository,
            username: str,
        ) -> tuple[object, str] | None:
            # Registration already passed liveness while holding the write lock.
            clock[0] = deadline + timedelta(microseconds=1)
            upgrade_admitted.set()
            await asyncio.wait_for(release_upgrade.wait(), timeout=10)
            return await original_credentials(repo, username)

        async def observed_delete(*args: object, **kwargs: object) -> None:
            assert args == (tenant, account) and kwargs == {"expired": True}
            cleanup_selected.set()
            await original_delete(tenant, account, expired=True)

        with (
            patch("open_commerce.stores.shoppers.utc_now", side_effect=lambda: clock[0]),
            patch.object(ShopperRepository, "get_account_credentials", delayed_credentials),
            patch.object(accounts, "delete_data", side_effect=observed_delete),
        ):
            upgrade = asyncio.create_task(
                accounts.upgrade(
                    tenant,
                    account,
                    ShopperRegisterRequest(
                        username="registered-at-deadline",
                        display_name="Fixture shopper",
                        password="synthetic-expiry-password",
                    ),
                )
            )
            tasks.append(upgrade)
            await asyncio.wait_for(upgrade_admitted.wait(), timeout=10)
            cleanup = asyncio.create_task(accounts.cleanup(tenant))
            tasks.append(cleanup)
            await asyncio.wait_for(cleanup_selected.wait(), timeout=10)
            release_upgrade.set()
            registered, token = await asyncio.wait_for(upgrade, timeout=10)
            assert registered.account.id == account and not registered.account.is_guest
            await asyncio.wait_for(cleanup, timeout=10)

        async with database.transaction(tenant) as session:
            stored = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant,
                    ShopperAccountRecord.id == account,
                )
            )
            assert stored is not None
            retained = {}
            for model in (ShopperConversationRecord, ShopperMessageRecord, ShopperMemoryRecord):
                retained[model.__tablename__] = await session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(
                        model.tenant_id == tenant,
                        model.account_id == account,
                    )
                )
            fresh_session = await session.scalar(
                select(ShopperSessionRecord).where(
                    ShopperSessionRecord.tenant_id == tenant,
                    ShopperSessionRecord.account_id == account,
                    ShopperSessionRecord.token_hash == session_token_hash(token),
                )
            )
            assert fresh_session is not None
            assert {
                "status": stored.status,
                "guest": stored.is_guest,
                "expiry": stored.expires_at,
                "version": stored.version,
                "revoked": fresh_session.revoked_at,
                **retained,
            } == {
                "status": "active",
                "guest": False,
                "expiry": None,
                "version": 1,
                "revoked": None,
                "shopper_conversations": 1,
                "shopper_messages": 1,
                "shopper_memories": 1,
            }
            authenticated = await ShopperRepository(session, tenant).account_for_session(
                token_hash=session_token_hash(token),
                now=utc_now(),
            )
            assert authenticated is not None and authenticated.id == account
        await accounts.cleanup(tenant)
    finally:
        release_upgrade.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await database.close()


async def test_duplicate_cleanup_selections_retire_a_guest_once(
    integration_settings: Settings,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    selected = 0
    both_selected = asyncio.Event()
    try:
        await database.initialize_tenant(tenant)
        accounts = ShopperAccounts(database)
        guest, _ = await accounts.guest(tenant, None)
        async with database.transaction(tenant, write=True) as session:
            row = await accounts.account(session, tenant, guest.account.id)
            row.expires_at = utc_now() - timedelta(seconds=1)
        original_delete = accounts.delete_data

        async def delayed_delete(*args: object, **kwargs: object) -> None:
            nonlocal selected
            assert args == (tenant, guest.account.id) and kwargs == {"expired": True}
            selected += 1
            if selected == 2:
                both_selected.set()
            await asyncio.wait_for(both_selected.wait(), timeout=10)
            await original_delete(tenant, guest.account.id, expired=True)

        with patch.object(accounts, "delete_data", side_effect=delayed_delete):
            await asyncio.wait_for(
                asyncio.gather(
                    accounts.cleanup(tenant),
                    accounts.cleanup(tenant),
                ),
                timeout=15,
            )
        assert selected == 2
        await accounts.cleanup(tenant)
        async with database.transaction(tenant) as session:
            retired = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant,
                    ShopperAccountRecord.id == guest.account.id,
                )
            )
            assert retired is not None and retired.status == "disabled"
            assert retired.version == 2
    finally:
        await database.close()


async def test_late_registration_stays_denied_and_committed_registration_survives_cleanup(
    integration_settings: Settings,
) -> None:
    database, tenant = RuntimeDatabase(integration_settings), uuid4()
    try:
        await database.initialize_tenant(tenant)
        accounts = ShopperAccounts(database)
        expired, _ = await accounts.guest(tenant, None)
        async with database.transaction(tenant, write=True) as session:
            row = await accounts.account(session, tenant, expired.account.id)
            row.expires_at = utc_now() - timedelta(seconds=1)
        payload = ShopperRegisterRequest(
            username="on-time-shopper",
            display_name="On-time fixture",
            password="synthetic-expiry-password",
        )
        with pytest.raises(StoreError) as denied:
            await accounts.upgrade(tenant, expired.account.id, payload)
        assert denied.value.status_code == 401
        fresh, _ = await accounts.guest(tenant, None)
        registered, token = await accounts.upgrade(tenant, fresh.account.id, payload)
        await accounts.cleanup(tenant)
        await accounts.cleanup(tenant)
        async with database.transaction(tenant) as session:
            current = await accounts.account(session, tenant, registered.account.id)
            assert current.status == "active" and not current.is_guest
            assert current.version == 1 and current.expires_at is None
            assert (
                await ShopperRepository(session, tenant).account_for_session(
                    token_hash=session_token_hash(token),
                    now=utc_now(),
                )
                is not None
            )
        # Explicit user deletion remains separate from background eligibility.
        await accounts.delete_data(tenant, registered.account.id)
        async with database.transaction(tenant) as session:
            current = await accounts.account(session, tenant, registered.account.id)
            assert current.status == "active" and current.version == 2
    finally:
        await database.close()


@pytest.mark.parametrize("reason", ["registered", "unexpired", "disabled", "foreign", "missing"])
async def test_ineligible_expiry_retirement_does_not_touch_account_or_sessions(
    integration_settings: Settings,
    reason: str,
) -> None:
    database, tenant, other_tenant = RuntimeDatabase(integration_settings), uuid4(), uuid4()
    try:
        await database.initialize_tenant(tenant)
        await database.initialize_tenant(other_tenant)
        accounts = ShopperAccounts(database)
        guest, _ = await accounts.guest(tenant, None)
        async with database.transaction(tenant, write=True) as session:
            row = await accounts.account(session, tenant, guest.account.id)
            if reason != "unexpired":
                row.expires_at = utc_now() - timedelta(seconds=1)
            if reason == "registered":
                row.is_guest = False
                row.expires_at = None
            if reason == "disabled":
                row.status = "disabled"

        async def snapshot() -> dict[str, list[dict[str, object]]]:
            values = {}
            async with database.transaction(tenant) as session:
                for model in (ShopperAccountRecord, ShopperSessionRecord):
                    result = await session.execute(
                        select(model.__table__)
                        .where(
                            model.tenant_id == tenant,
                        )
                        .order_by(model.id)
                    )
                    values[model.__tablename__] = [dict(row) for row in result.mappings()]
            return values

        before = await snapshot()
        await accounts.delete_data(
            other_tenant if reason == "foreign" else tenant,
            uuid4() if reason == "missing" else guest.account.id,
            expired=True,
        )
        assert await snapshot() == before
    finally:
        await database.close()
