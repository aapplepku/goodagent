"""Guest continuity and account privacy controls on the existing shopper identity."""

import json
import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, SecretStr
from sqlalchemy import String, cast, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.scope import current_catalog
from open_commerce.core.types import StrictDomainModel, utc_now
from open_commerce.persistence.models.commerce import ShopperCartLineRecord, ShopperCartRecord
from open_commerce.persistence.models.shopper import (
    ShopperAccountRecord,
    ShopperConversationRecord,
    ShopperMemoryRecord,
    ShopperMessageRecord,
    ShopperSessionRecord,
)
from open_commerce.persistence.models.shopper_activity import (
    ActivityCheckRecord,
    ActivityRuleRecord,
    ShopperActivityRecord,
)
from open_commerce.persistence.models.store_setup import AuthTicketRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.commerce import CommerceRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import (
    hash_password,
    new_session_token,
    session_token_hash,
    verify_password,
)
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperAuthResponse,
    ShopperLoginRequest,
    ShopperRegisterRequest,
)
from open_commerce.stores.models import SessionInfo, SessionList, StoreError

_CONTENT_RECEIPT_PREFIXES = (
    "shopper:chat:",
    "shopper:chat:start:",
    "shopper:memory:save:",
    "shopper:memory:delete:",
)


class PreferenceSettings(StrictDomainModel):
    enabled: bool


class ShopperRecovery(StrictDomainModel):
    username: str
    code: SecretStr
    password: SecretStr


class MergeSelection(StrictDomainModel):
    token: SecretStr
    cart_choice: Literal["keep_guest", "keep_account"]


class CartChoiceLine(StrictDomainModel):
    title: str
    variant_title: str
    quantity: int = Field(ge=1, le=20)


class ContinuityResponse(ShopperAuthResponse):
    merge_token: str | None = None
    guest_cart_items: int = 0
    account_cart_items: int = 0
    guest_cart_lines: list[CartChoiceLine] = Field(default_factory=list, max_length=100)
    account_cart_lines: list[CartChoiceLine] = Field(default_factory=list, max_length=100)


class TurnAllowance(StrictDomainModel):
    allowed: bool


class ShopperAccounts:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def account(
        self,
        session: AsyncSession,
        tenant: UUID,
        account: UUID,
        *,
        account_version: int | None = None,
    ) -> ShopperAccountRecord:
        row = await session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == tenant,
                ShopperAccountRecord.id == account,
                ShopperAccountRecord.status == "active",
            )
        )
        if row is None or (row.expires_at is not None and row.expires_at <= utc_now()):
            raise StoreError("This shopping session has expired.", 401)
        scope = current_catalog.get()
        expected_preview = scope.catalog_id if scope and scope.preview else None
        if row.preview_catalog_id != expected_preview:
            raise StoreError("Open a new shopping session for this store preview.", 401)
        if account_version is not None and row.version != account_version:
            raise StoreError("Your shopping data changed. Start a new request.", 401)
        return row

    async def session(self, session: AsyncSession, tenant: UUID, row: ShopperAccountRecord) -> str:
        token = new_session_token()
        now = utc_now()
        await ShopperRepository(session, tenant).create_session(
            session_id=uuid4(),
            account_id=row.id,
            token_hash=session_token_hash(token),
            expires_at=row.expires_at
            or now + timedelta(days=self.database.settings.shopper_session_days),
            now=now,
        )
        return token

    async def guest(
        self, tenant: UUID, previous: str | None
    ) -> tuple[ShopperAuthResponse, str | None]:
        async with self.database.transaction(tenant, write=True) as session:
            repo = ShopperRepository(session, tenant)
            existing = await repo.account_for_session(
                token_hash=session_token_hash(previous or ""), now=utc_now()
            )
            if existing:
                try:
                    await self.account(session, tenant, existing.id)
                    return ShopperAuthResponse(account=existing), None
                except StoreError:
                    pass
            scope = current_catalog.get()
            row = ShopperAccountRecord(
                id=uuid4(),
                tenant_id=tenant,
                username=f"g-{uuid4().hex}",
                display_name="Guest",
                password_hash="disabled",
                status="active",
                is_guest=True,
                memory_enabled=True,
                expires_at=utc_now() + timedelta(hours=24),
                preview_catalog_id=scope.catalog_id if scope and scope.preview else None,
                created_at=utc_now(),
                updated_at=utc_now(),
                version=1,
            )
            session.add(row)
            await session.flush()
            token = await self.session(session, tenant, row)
            return ShopperAuthResponse(account=repo._account(row)), token

    async def upgrade(
        self, tenant: UUID, account: UUID, payload: ShopperRegisterRequest
    ) -> tuple[ShopperAuthResponse, str]:
        password = await hash_password(payload.password.get_secret_value())
        async with self.database.transaction(tenant, write=True) as session:
            row = await self.account(session, tenant, account)
            if row.preview_catalog_id:
                raise StoreError(
                    "Private previews use temporary guests. Accounts are available after sharing.",
                    409,
                )
            if not row.is_guest:
                raise StoreError("Already signed in.", 409)
            if await ShopperRepository(session, tenant).get_account_credentials(
                payload.username.lower()
            ):
                raise StoreError(
                    "Username is already in use. Sign in to preserve your guest progress.", 409
                )
            row.username = payload.username.lower()
            row.display_name = payload.display_name.strip()
            row.password_hash = password
            row.is_guest = False
            row.expires_at = None
            code = secrets.token_urlsafe(32)
            row.recovery_hash = session_token_hash(code)
            await self.revoke(session, tenant, account)
            token = await self.session(session, tenant, row)
            return ShopperAuthResponse(
                account=ShopperRepository._account(row), recovery_code=code
            ), token

    async def login(
        self, tenant: UUID, guest_id: UUID | None, payload: ShopperLoginRequest
    ) -> tuple[ContinuityResponse, str | None]:
        async with self.database.transaction(tenant) as session:
            credentials = await ShopperRepository(session, tenant).get_account_credentials(
                payload.username.lower()
            )
        if credentials is None or not await verify_password(
            payload.password.get_secret_value(), credentials[1]
        ):
            raise StoreError("Username or password is incorrect.", 401)
        async with self.database.transaction(tenant, write=True) as session:
            target = await self.account(session, tenant, credentials[0].id)
            if (
                target.is_guest
                or target.username != payload.username.lower()
                or target.password_hash != credentials[1]
            ):
                raise StoreError("Username or password is incorrect.", 401)
            guest = await self.account(session, tenant, guest_id) if guest_id else None
            if guest and guest.is_guest:
                repo = CommerceRepository(session, tenant)
                guest_cart = await repo.open_cart(account_id=guest.id)
                target_cart = await repo.open_cart(account_id=target.id)
                guest_lines = (
                    await repo.cart_lines(account_id=guest.id, cart_id=guest_cart.id)
                    if guest_cart
                    else []
                )
                target_lines = (
                    await repo.cart_lines(account_id=target.id, cart_id=target_cart.id)
                    if target_cart
                    else []
                )
                if guest_lines and target_lines:
                    token = secrets.token_urlsafe(32)
                    session.add(
                        AuthTicketRecord(
                            token_hash=session_token_hash(token),
                            tenant_id=tenant,
                            purpose="guest_merge",
                            payload=json.dumps(
                                {
                                    "guest": str(guest.id),
                                    "target": str(target.id),
                                    "credential_fingerprint": self._credential_fingerprint(
                                        tenant, target
                                    ),
                                    "carts": [
                                        [str(cart.id), cart.version] if cart else None
                                        for cart in (guest_cart, target_cart)
                                    ],
                                }
                            ).encode(),
                            expires_at=utc_now() + timedelta(minutes=10),
                            created_at=utc_now(),
                        )
                    )
                    return ContinuityResponse(
                        account=ShopperRepository._account(guest),
                        merge_token=token,
                        guest_cart_items=len(guest_lines),
                        account_cart_items=len(target_lines),
                        guest_cart_lines=[self._choice_line(line) for line in guest_lines],
                        account_cart_lines=[self._choice_line(line) for line in target_lines],
                    ), None
                await self.merge_records(
                    session, tenant, guest, target, "keep_guest" if guest_lines else "keep_account"
                )
            token = await self.session(session, tenant, target)
            return ContinuityResponse(account=ShopperRepository._account(target)), token

    async def merge(
        self, tenant: UUID, guest_id: UUID, payload: MergeSelection
    ) -> tuple[ContinuityResponse, str]:
        async with self.database.transaction(tenant, write=True) as session:
            grant = await session.scalar(
                select(AuthTicketRecord).where(
                    AuthTicketRecord.tenant_id == tenant,
                    AuthTicketRecord.purpose == "guest_merge",
                    AuthTicketRecord.token_hash
                    == session_token_hash(payload.token.get_secret_value()),
                    AuthTicketRecord.consumed_at.is_(None),
                    AuthTicketRecord.expires_at > utc_now(),
                )
            )
            if grant is None:
                raise StoreError("Sign in again to review cart changes.", 401)
            ids = json.loads(grant.payload)
            if ids["guest"] != str(guest_id):
                raise StoreError("Merge belongs to a different guest session.", 403)
            guest = await self.account(session, tenant, guest_id)
            target = await self.account(session, tenant, UUID(ids["target"]))
            fingerprint = ids.get("credential_fingerprint")
            if (
                target.is_guest
                or not isinstance(fingerprint, str)
                or len(fingerprint) != 64
                or not fingerprint.isascii()
                or not secrets.compare_digest(
                    fingerprint, self._credential_fingerprint(tenant, target)
                )
            ):
                raise StoreError("Sign in again to review cart changes.", 401)
            repo = CommerceRepository(session, tenant)
            carts = [
                await repo.open_cart(account_id=account.id, for_update=True)
                for account in (guest, target)
            ]
            if ids.get("carts") != [
                [str(cart.id), cart.version] if cart else None for cart in carts
            ]:
                raise StoreError("A cart changed. Sign in again to review both carts.", 409)
            await self.merge_records(session, tenant, guest, target, payload.cart_choice)
            grant.consumed_at = utc_now()
            token = await self.session(session, tenant, target)
            return ContinuityResponse(account=ShopperRepository._account(target)), token

    @staticmethod
    def _credential_fingerprint(tenant: UUID, target: ShopperAccountRecord) -> str:
        # This change detector stays in the persisted grant, never the browser response.
        return session_token_hash(
            json.dumps(
                [
                    "guest_merge:v1",
                    str(tenant),
                    str(target.id),
                    target.password_hash,
                    target.recovery_hash,
                ],
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _choice_line(line: ShopperCartLineRecord) -> CartChoiceLine:
        return CartChoiceLine(
            title=line.title, variant_title=line.variant_title, quantity=line.quantity
        )

    async def merge_records(
        self,
        session: AsyncSession,
        tenant: UUID,
        guest: ShopperAccountRecord,
        target: ShopperAccountRecord,
        choice: str,
    ) -> None:
        if not guest.is_guest or guest.id == target.id:
            raise StoreError("Only a guest can be merged into an account.", 409)
        repo = CommerceRepository(session, tenant)
        for account in (guest.id, target.id):
            cart = await repo.open_cart(account_id=account, for_update=True)
            if cart:
                await repo.invalidate_checkout(cart=cart, now=utc_now())
                if (choice == "keep_guest" and account == target.id) or (
                    choice == "keep_account" and account == guest.id
                ):
                    cart.status = "abandoned"
                elif account == guest.id and choice == "keep_guest":
                    # Retained checkout audits still belong to the guest's old cart version.
                    cart.version += 1
                    cart.updated_at = utc_now()
        await session.flush()
        for model in (
            ShopperConversationRecord,
            ShopperMessageRecord,
            ShopperMemoryRecord,
            ShopperCartRecord,
            ShopperCartLineRecord,
        ):
            await session.execute(
                update(model)
                .where(model.tenant_id == tenant, model.account_id == guest.id)
                .values(account_id=target.id)
            )
        await self.erase_activity(session, tenant, guest.id)
        await self._erase_content_receipts(session, tenant, guest.id)
        await self.revoke(session, tenant, guest.id)
        guest.version += 1
        guest.status = "disabled"

    async def _erase_content_receipts(
        self, session: AsyncSession, tenant: UUID, account: UUID
    ) -> None:
        # Response copies belong to the retired identity, not the transferred history.
        await session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant,
                IdempotencyRecord.scope.in_(
                    [f"{prefix}{account}" for prefix in _CONTENT_RECEIPT_PREFIXES]
                ),
            )
        )

    async def preferences(
        self, tenant: UUID, account: UUID, enabled: bool, *, idempotency_key: str | None = None
    ) -> ShopperAccount:
        async with self.database.transaction(tenant, write=True) as session:
            row = await self.account(session, tenant, account)
            receipts = RequestRepository(session, tenant)
            scope = f"shopper:preferences:{account}"
            request = PreferenceSettings(enabled=enabled)
            if idempotency_key is not None:
                cached = await receipts.replay(scope=scope, key=idempotency_key, request=request)
                if cached is not None:
                    return ShopperRepository._account(row)
            row.memory_enabled = enabled
            if idempotency_key is not None:
                receipts.remember(
                    scope=scope, key=idempotency_key, request=request, response=request
                )
            return ShopperRepository._account(row)

    async def revoke(self, session: AsyncSession, tenant: UUID, account: UUID) -> None:
        await session.execute(
            update(ShopperSessionRecord)
            .where(
                ShopperSessionRecord.tenant_id == tenant, ShopperSessionRecord.account_id == account
            )
            .values(revoked_at=utc_now())
        )

    async def erase_activity(self, session: AsyncSession, tenant: UUID, account: UUID) -> None:
        rules = select(ActivityRuleRecord.id).where(
            ActivityRuleRecord.tenant_id == tenant, ActivityRuleRecord.account_id == account
        )
        await session.execute(
            delete(ActivityCheckRecord).where(
                ActivityCheckRecord.tenant_id == tenant, ActivityCheckRecord.rule_id.in_(rules)
            )
        )
        for model in (ShopperActivityRecord, ActivityRuleRecord):
            await session.execute(
                delete(model).where(model.tenant_id == tenant, model.account_id == account)
            )
        await session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant,
                IdempotencyRecord.scope == f"activity:configure:{account}",
            )
        )

    async def delete_data(self, tenant: UUID, account: UUID, *, expired: bool = False) -> None:
        async with self.database.transaction(tenant, write=True) as session:
            if expired:
                # Cleanup's earlier selection can predate registration or another retirement.
                eligible = await session.scalar(
                    select(ShopperAccountRecord.id).where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.id == account,
                        ShopperAccountRecord.is_guest.is_(True),
                        ShopperAccountRecord.status == "active",
                        ShopperAccountRecord.expires_at.is_not(None),
                        ShopperAccountRecord.expires_at <= utc_now(),
                    )
                )
                if eligible is None:
                    return
            # Delayed personal writes must keep the version captured before this transaction.
            await session.execute(
                update(ShopperAccountRecord)
                .where(ShopperAccountRecord.tenant_id == tenant, ShopperAccountRecord.id == account)
                .values(version=ShopperAccountRecord.version + 1)
            )
            await self.erase_activity(session, tenant, account)
            for model in (ShopperMemoryRecord, ShopperMessageRecord, ShopperConversationRecord):
                await session.execute(
                    delete(model).where(model.tenant_id == tenant, model.account_id == account)
                )
            await session.execute(
                delete(IdempotencyRecord).where(
                    IdempotencyRecord.tenant_id == tenant,
                    IdempotencyRecord.scope.startswith("shopper:"),
                    IdempotencyRecord.scope.endswith(str(account)),
                    # Keep content-free setting receipts so late retries cannot undo opt-out.
                    IdempotencyRecord.scope != f"shopper:preferences:{account}",
                )
            )
            repo = CommerceRepository(session, tenant)
            cart = await repo.open_cart(account_id=account)
            if cart:
                await repo.invalidate_checkout(cart=cart, now=utc_now())
                cart.status = "abandoned"
            # Keep identity and auditable checkout records; erase conversation/operational data.
            if expired:
                await self.revoke(session, tenant, account)
                await session.execute(
                    update(ShopperAccountRecord)
                    .where(
                        ShopperAccountRecord.tenant_id == tenant, ShopperAccountRecord.id == account
                    )
                    .values(status="disabled")
                )

    async def cleanup(self, tenant: UUID) -> None:
        async with self.database.transaction(tenant) as session:
            ids = list(
                await session.scalars(
                    select(ShopperAccountRecord.id)
                    .where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.is_guest.is_(True),
                        ShopperAccountRecord.status == "active",
                        ShopperAccountRecord.expires_at <= utc_now(),
                    )
                    .limit(100)
                )
            )
        for account in ids:
            await self.delete_data(tenant, account, expired=True)

        async with self.database.transaction(tenant) as session:
            outstanding = (
                select(IdempotencyRecord.key)
                .where(
                    IdempotencyRecord.tenant_id == tenant,
                    IdempotencyRecord.scope.in_(
                        [
                            prefix + cast(ShopperAccountRecord.id, String)
                            for prefix in _CONTENT_RECEIPT_PREFIXES
                        ]
                    ),
                )
                .exists()
            )
            retired = list(
                await session.scalars(
                    select(ShopperAccountRecord.id)
                    .where(
                        ShopperAccountRecord.tenant_id == tenant,
                        ShopperAccountRecord.is_guest.is_(True),
                        ShopperAccountRecord.status == "disabled",
                        outstanding,
                    )
                    .order_by(ShopperAccountRecord.id)
                    # Bound accounts per pass; receipt count and lock time can vary.
                    .limit(100)
                )
            )
        for account in retired:
            await self._erase_retired_guest_receipts(tenant, account)

    async def _erase_retired_guest_receipts(self, tenant: UUID, account: UUID) -> None:
        async with self.database.transaction(tenant, write=True) as session:
            # Selection may predate an identity change or another cleanup worker.
            eligible = await session.scalar(
                select(ShopperAccountRecord.id).where(
                    ShopperAccountRecord.tenant_id == tenant,
                    ShopperAccountRecord.id == account,
                    ShopperAccountRecord.is_guest.is_(True),
                    ShopperAccountRecord.status == "disabled",
                    select(IdempotencyRecord.key)
                    .where(
                        IdempotencyRecord.tenant_id == tenant,
                        IdempotencyRecord.scope.in_(
                            [f"{prefix}{account}" for prefix in _CONTENT_RECEIPT_PREFIXES]
                        ),
                    )
                    .exists(),
                )
            )
            if eligible is not None:
                await self._erase_content_receipts(session, tenant, account)

    async def admit_turn(self, tenant: UUID, account: UUID, key: str) -> bool:
        async with self.database.transaction(tenant, write=True) as session:
            row = await self.account(session, tenant, account)
            if not row.is_guest:
                return True
            scope = f"guest:turn:{account}"
            repo = RequestRepository(session, tenant)
            cached = await repo.replay(scope=scope, key=key, request={})
            if cached:
                return bool(cached["allowed"])
            used = (
                await session.scalar(
                    select(func.count())
                    .select_from(IdempotencyRecord)
                    .where(IdempotencyRecord.tenant_id == tenant, IdempotencyRecord.scope == scope)
                )
                or 0
            )
            if used >= 10:
                return False
            repo.remember(scope=scope, key=key, request={}, response=TurnAllowance(allowed=True))
            return True

    async def sessions(self, tenant: UUID, account: UUID, token: str) -> SessionList:
        async with self.database.transaction(tenant) as session:
            rows = await session.scalars(
                select(ShopperSessionRecord)
                .where(
                    ShopperSessionRecord.tenant_id == tenant,
                    ShopperSessionRecord.account_id == account,
                    ShopperSessionRecord.revoked_at.is_(None),
                    ShopperSessionRecord.expires_at > utc_now(),
                )
                .order_by(ShopperSessionRecord.created_at.desc())
                .limit(50)
            )
            return SessionList(
                items=[
                    SessionInfo(
                        id=r.id,
                        created_at=r.created_at,
                        expires_at=r.expires_at,
                        current=r.token_hash == session_token_hash(token),
                    )
                    for r in rows
                ]
            )

    async def recover(
        self, tenant: UUID, payload: ShopperRecovery
    ) -> tuple[ShopperAuthResponse, str]:
        scope = current_catalog.get()
        if scope and scope.preview:
            raise StoreError(
                "Private previews use temporary guests. "
                "Recover your account from the shared store.",
                409,
            )
        if not 10 <= len(payload.password.get_secret_value()) <= 128:
            raise StoreError("Password must contain 10 to 128 characters.")
        password = await hash_password(payload.password.get_secret_value())
        async with self.database.transaction(tenant, write=True) as session:
            row = await session.scalar(
                select(ShopperAccountRecord).where(
                    ShopperAccountRecord.tenant_id == tenant,
                    ShopperAccountRecord.username == payload.username.lower(),
                    ShopperAccountRecord.is_guest.is_(False),
                    ShopperAccountRecord.recovery_hash
                    == session_token_hash(payload.code.get_secret_value()),
                )
            )
            if row is None:
                raise StoreError("Recovery code is invalid or already used.", 401)
            code = secrets.token_urlsafe(32)
            row.recovery_hash = session_token_hash(code)
            row.password_hash = password
            await self.revoke(session, tenant, row.id)
            token = await self.session(session, tenant, row)
            return ShopperAuthResponse(
                account=ShopperRepository._account(row), recovery_code=code
            ), token
