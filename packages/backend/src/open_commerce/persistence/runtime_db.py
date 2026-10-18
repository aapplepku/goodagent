"""Short, tenant-scoped PostgreSQL transactions for the deployed runtime."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, DisconnectionError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from open_commerce.config import Settings
from open_commerce.persistence.db import create_session_factory
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.workflow import TenantRuntime


class DatabaseUnavailableError(RuntimeError):
    """A connection or pool outage, without exposing connection details."""


class RuntimeDatabase:
    """One pool per process; correctness lives in committed rows and database locks."""

    def __init__(
        self, settings: Settings, *, sessions: async_sessionmaker[AsyncSession] | None = None
    ) -> None:
        self.settings = settings
        self.sessions = sessions or create_session_factory(settings)

    @asynccontextmanager
    async def transaction(
        self, tenant_id: UUID, *, write: bool = False
    ) -> AsyncIterator[AsyncSession]:
        try:
            async with self.sessions() as session, session.begin():
                if write:
                    # State changes share an ordering lock released on commit or disconnect.
                    lock_id = int.from_bytes(sha256(tenant_id.bytes).digest()[:8], signed=True)
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(:tenant_lock)"),
                        {"tenant_lock": lock_id},
                    )
                yield session
        except (OSError, TimeoutError, PoolTimeoutError, DisconnectionError) as exc:
            raise DatabaseUnavailableError("Database connection unavailable") from exc
        except DBAPIError as exc:
            if isinstance(exc, OperationalError) or exc.connection_invalidated:
                raise DatabaseUnavailableError("Database connection unavailable") from exc
            raise

    async def initialize_tenant(self, tenant_id: UUID) -> None:
        async with self.transaction(tenant_id, write=True) as session:
            await session.execute(
                insert(Tenant)
                .values(
                    id=tenant_id,
                    slug=f"demo-{tenant_id}",
                    display_name="Local simulator",
                    default_currency="USD",
                    timezone="UTC",
                    status="active",
                )
                .on_conflict_do_nothing(index_elements=[Tenant.id])
            )
            await session.execute(
                insert(TenantRuntime)
                .values(tenant_id=tenant_id)
                .on_conflict_do_nothing(index_elements=[TenantRuntime.tenant_id])
            )

    async def close(self) -> None:
        engine = self.sessions.kw.get("bind")
        if engine is not None:
            await engine.dispose()
