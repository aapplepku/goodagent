"""Pre-authentication control plane and tenant-scoped merchant authorization."""

import re
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.types import utc_now
from open_commerce.persistence.models.identity import Tenant, TenantMembership, User
from open_commerce.persistence.models.store_setup import (
    AuthTicketRecord,
    MerchantCredentialRecord,
    MerchantSessionRecord,
    SetupEventRecord,
    StoreSetupRecord,
)
from open_commerce.persistence.models.workflow import TenantRuntime
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import (
    hash_password,
    new_session_token,
    session_token_hash,
    verify_password,
)
from open_commerce.stores.models import (
    OwnerAuthResponse,
    OwnerIdentity,
    OwnerLoginRequest,
    OwnerRecoveryRequest,
    OwnerSetupRequest,
    SessionInfo,
    SessionList,
    SetupStatus,
    StoreError,
    StoreProfile,
    StoreProfileUpdate,
)


def store_profile(tenant: Tenant, setup: StoreSetupRecord) -> StoreProfile:
    return StoreProfile(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.display_name,
        currency=tenant.default_currency,
        description=setup.description,
        goal=setup.goal,
        sharing_enabled=setup.sharing_enabled,
        published_catalog_id=setup.published_catalog_id,
        sample_data=setup.sample_data,
        readiness={
            k: v for k, v in setup.readiness.items() if v is None or isinstance(v, bool | str | int)
        },
    )


async def create_owned_store(
    session: AsyncSession, *, user_id: UUID, profile: StoreProfileUpdate
) -> StoreProfile:
    now = utc_now()
    tenant_id = uuid4()
    stem = re.sub(r"[^a-z0-9]+", "-", profile.name.lower()).strip("-")[:65] or "store"
    tenant = Tenant(
        id=tenant_id,
        slug=f"{stem}-{tenant_id.hex[:8]}",
        display_name=profile.name,
        default_currency=profile.currency,
        timezone="UTC",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(tenant)
    await session.flush()
    setup = StoreSetupRecord(
        tenant_id=tenant_id,
        description=profile.description or f"Find your next favorite at {profile.name}.",
        goal=profile.goal,
        sharing_enabled=False,
        readiness={},
        sample_data=False,
        created_at=now,
    )
    session.add_all(
        [
            setup,
            TenantRuntime(tenant_id=tenant_id),
            TenantMembership(tenant_id=tenant_id, user_id=user_id, role="owner", created_at=now),
            SetupEventRecord(
                tenant_id=tenant_id,
                kind="store_created",
                event_key="store_created",
                details={},
                occurred_at=now,
            ),
        ]
    )
    await session.flush()
    return store_profile(tenant, setup)


class MerchantAuthService:
    """Global queries here resolve identity only; store data requires a tenant scope."""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def status(self) -> SetupStatus:
        profile = self.database.settings.runtime_profile
        async with self.database.sessions() as session:
            owners = await session.scalar(
                select(func.count()).select_from(MerchantCredentialRecord)
            )
        return SetupStatus(
            profile=profile,
            setup_required=profile == "self_hosted" and not owners,
            login_method="oidc"
            if profile == "hosted"
            else "legacy"
            if profile == "legacy_demo"
            else "local",
        )

    async def issue_bootstrap(self) -> str:
        if self.database.settings.runtime_profile != "self_hosted":
            raise StoreError("Bootstrap is only available for self-hosted instances.", 403)
        token = new_session_token()
        async with self.database.sessions() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(1130001)"))
            if await session.scalar(select(MerchantCredentialRecord.user_id).limit(1)):
                raise StoreError("This instance already has an owner; use console recovery.", 409)
            session.add(
                AuthTicketRecord(
                    token_hash=session_token_hash(token),
                    purpose="bootstrap",
                    payload=b"",
                    expires_at=utc_now() + timedelta(minutes=30),
                    created_at=utc_now(),
                )
            )
        return token

    async def setup(self, payload: OwnerSetupRequest) -> tuple[OwnerAuthResponse, str]:
        if self.database.settings.runtime_profile != "self_hosted":
            raise StoreError("Local owner setup is unavailable in this profile.", 403)
        password_hash = await hash_password(payload.password.get_secret_value())
        recovery = new_session_token()
        async with self.database.sessions() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(1130001)"))
            ticket = await session.scalar(
                select(AuthTicketRecord)
                .where(
                    AuthTicketRecord.token_hash
                    == session_token_hash(payload.bootstrap_token.get_secret_value()),
                    AuthTicketRecord.purpose == "bootstrap",
                    AuthTicketRecord.tenant_id.is_(None),
                    AuthTicketRecord.consumed_at.is_(None),
                    AuthTicketRecord.expires_at > utc_now(),
                )
                .with_for_update()
            )
            if ticket is None:
                raise StoreError(
                    "The setup token is invalid or expired. Generate another in the console.", 401
                )
            if await session.scalar(select(MerchantCredentialRecord.user_id).limit(1)):
                raise StoreError("This instance already has an owner.", 409)
            ticket.consumed_at = utc_now()
            user_id = uuid4()
            session.add(User(id=user_id, external_subject=f"local:{user_id}", created_at=utc_now()))
            await session.flush()
            session.add(
                MerchantCredentialRecord(
                    user_id=user_id,
                    username=payload.username.lower(),
                    password_hash=password_hash,
                    recovery_hash=session_token_hash(recovery),
                )
            )
            profile = await create_owned_store(session, user_id=user_id, profile=payload)
            token = await self._session(session, user_id=user_id, tenant_id=profile.id)
            result = OwnerAuthResponse(user_id=user_id, store=profile, recovery_code=recovery)
        return result, token

    async def login(self, payload: OwnerLoginRequest) -> tuple[OwnerAuthResponse, str]:
        if self.database.settings.runtime_profile == "hosted":
            raise StoreError("Use the configured sign-in provider.", 403)
        username = payload.username.lower()
        async with self.database.sessions() as session:
            credential = await session.scalar(
                select(MerchantCredentialRecord).where(
                    MerchantCredentialRecord.username == username
                )
            )
            verified = (
                (credential.user_id, credential.password_hash, credential.recovery_hash)
                if credential is not None
                else None
            )
        if verified is None or not await verify_password(
            payload.password.get_secret_value(), verified[1]
        ):
            raise StoreError("The username or password is incorrect.", 401)
        # Recovery and console rotation lock this row; keep password work outside that lock.
        async with self.database.sessions() as session, session.begin():
            credential = await session.scalar(
                select(MerchantCredentialRecord)
                .where(
                    MerchantCredentialRecord.user_id == verified[0],
                    MerchantCredentialRecord.username == username,
                )
                .with_for_update()
            )
            if (
                credential is None
                or credential.password_hash != verified[1]
                or credential.recovery_hash != verified[2]
            ):
                raise StoreError("The username or password is incorrect.", 401)
            profile = await self._owned_profile(session, credential.user_id)
            token = await self._session(session, user_id=credential.user_id, tenant_id=profile.id)
            result = OwnerAuthResponse(user_id=credential.user_id, store=profile)
        return result, token

    async def recover(self, payload: OwnerRecoveryRequest) -> tuple[OwnerAuthResponse, str]:
        if self.database.settings.runtime_profile == "hosted":
            raise StoreError("Recover your account with the sign-in provider.", 403)
        hashed = await hash_password(payload.password.get_secret_value())
        recovery = new_session_token()
        async with self.database.sessions() as session, session.begin():
            credential = await session.scalar(
                select(MerchantCredentialRecord)
                .where(
                    MerchantCredentialRecord.username == payload.username.lower(),
                    MerchantCredentialRecord.recovery_hash
                    == session_token_hash(payload.recovery_code.get_secret_value()),
                )
                .with_for_update()
            )
            if credential is None:
                raise StoreError("The recovery code is invalid or has already been used.", 401)
            profile = await self._owned_profile(session, credential.user_id)
            credential.password_hash = hashed
            credential.recovery_hash = session_token_hash(recovery)
            await session.execute(
                update(MerchantSessionRecord)
                .where(
                    MerchantSessionRecord.tenant_id == profile.id,
                    MerchantSessionRecord.user_id == credential.user_id,
                )
                .values(revoked_at=utc_now())
            )
            token = await self._session(session, user_id=credential.user_id, tenant_id=profile.id)
            result = OwnerAuthResponse(
                user_id=credential.user_id, store=profile, recovery_code=recovery
            )
        return result, token

    async def authenticate(self, token: str | None) -> OwnerIdentity:
        if not token or len(token) > 200:
            raise StoreError("Sign in to your store workspace.", 401)
        async with self.database.sessions() as session:
            row = await session.scalar(
                select(MerchantSessionRecord).where(
                    MerchantSessionRecord.token_hash == session_token_hash(token),
                    MerchantSessionRecord.expires_at > utc_now(),
                    MerchantSessionRecord.revoked_at.is_(None),
                )
            )
            if row is None:
                raise StoreError("Your workspace session expired. Sign in again.", 401)
            member = await session.scalar(
                select(TenantMembership)
                .join(Tenant)
                .where(
                    TenantMembership.tenant_id == row.tenant_id,
                    TenantMembership.user_id == row.user_id,
                    TenantMembership.role == "owner",
                    Tenant.status == "active",
                )
            )
            if member is None:
                raise StoreError("You do not have access to this store.", 403)
            return OwnerIdentity(user_id=row.user_id, tenant_id=row.tenant_id)

    async def profile(self, owner: OwnerIdentity) -> OwnerAuthResponse:
        async with self.database.transaction(owner.tenant_id) as session:
            row = (
                await session.execute(
                    select(Tenant, StoreSetupRecord)
                    .join(StoreSetupRecord)
                    .where(
                        Tenant.id == owner.tenant_id,
                        StoreSetupRecord.tenant_id == owner.tenant_id,
                    )
                )
            ).one()
            return OwnerAuthResponse(user_id=owner.user_id, store=store_profile(*row))

    async def sessions(self, owner: OwnerIdentity, token: str) -> SessionList:
        async with self.database.transaction(owner.tenant_id) as session:
            rows = await session.scalars(
                select(MerchantSessionRecord)
                .where(
                    MerchantSessionRecord.tenant_id == owner.tenant_id,
                    MerchantSessionRecord.user_id == owner.user_id,
                    MerchantSessionRecord.revoked_at.is_(None),
                    MerchantSessionRecord.expires_at > utc_now(),
                )
                .order_by(MerchantSessionRecord.created_at.desc())
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

    async def revoke(self, owner: OwnerIdentity, session_id: UUID | None = None) -> None:
        async with self.database.transaction(owner.tenant_id, write=True) as session:
            query = update(MerchantSessionRecord).where(
                MerchantSessionRecord.tenant_id == owner.tenant_id,
                MerchantSessionRecord.user_id == owner.user_id,
            )
            if session_id is not None:
                query = query.where(MerchantSessionRecord.id == session_id)
            await session.execute(query.values(revoked_at=utc_now()))

    async def oidc_identity(self, issuer: str, subject: str) -> tuple[OwnerAuthResponse, str]:
        # OIDC issuer and subject are verified by the provider, never accepted from an API payload.
        identity = "oidc:" + session_token_hash(issuer + "\x00" + subject)
        async with self.database.sessions() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(1130002)"))
            user = await session.scalar(select(User).where(User.external_subject == identity))
            if user is None:
                user = User(id=uuid4(), external_subject=identity, created_at=utc_now())
                session.add(user)
                await session.flush()
                profile = await create_owned_store(
                    session, user_id=user.id, profile=StoreProfileUpdate(name="My store")
                )
            else:
                profile = await self._owned_profile(session, user.id)
            token = await self._session(session, user_id=user.id, tenant_id=profile.id)
            result = OwnerAuthResponse(user_id=user.id, store=profile)
        return result, token

    @staticmethod
    async def _owned_profile(session: AsyncSession, user_id: UUID) -> StoreProfile:
        # Membership discovery is identity control-plane; subsequent access uses its tenant.
        tenant_id = await session.scalar(
            select(TenantMembership.tenant_id).where(
                TenantMembership.user_id == user_id, TenantMembership.role == "owner"
            )
        )
        if tenant_id is None:
            raise StoreError("This account does not own a store.", 403)
        row = (
            await session.execute(
                select(Tenant, StoreSetupRecord)
                .join(StoreSetupRecord)
                .where(
                    Tenant.id == tenant_id,
                    Tenant.status == "active",
                    StoreSetupRecord.tenant_id == tenant_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise StoreError("This store is unavailable.", 403)
        return store_profile(*row)

    @staticmethod
    async def _session(session: AsyncSession, *, user_id: UUID, tenant_id: UUID) -> str:
        token = new_session_token()
        session.add(
            MerchantSessionRecord(
                user_id=user_id,
                tenant_id=tenant_id,
                token_hash=session_token_hash(token),
                expires_at=utc_now() + timedelta(days=7),
                created_at=utc_now(),
            )
        )
        await session.flush()
        return token
