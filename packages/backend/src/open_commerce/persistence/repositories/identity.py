"""Tenant/user seed helpers for local tests."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.persistence.models.identity import Tenant, TenantMembership, User


async def seed_local_identity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> None:
    """Create a minimal local tenant/user/membership for tests."""

    session.add(
        Tenant(
            id=tenant_id,
            slug="local-demo",
            display_name="Local Demo",
            default_currency="USD",
            timezone="UTC",
            status="active",
        ),
    )
    session.add(User(id=user_id, external_subject="local-user", email_hash=None))
    session.add(
        TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            role="owner",
            created_at=datetime.now(UTC),
        ),
    )
