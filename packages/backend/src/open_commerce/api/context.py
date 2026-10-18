"""Request context resolution for local-demo tenancy."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from open_commerce.api.merchant_intent import MerchantIntentDependency, verify_merchant_intent
from open_commerce.api.store_cookies import store_cookie
from open_commerce.catalog.scope import CatalogScope, catalog_scope
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.integrations import Integration
from open_commerce.persistence.models.store_setup import AuthTicketRecord, StoreSetupRecord
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import StoreUnavailableError


class RequestContext(BaseModel):
    """Resolved tenant and role context for one request."""

    tenant_id: UUID
    actor_id: str
    roles: set[str]
    auth_mode: Literal["local_demo", "session"] = "local_demo"
    tenant_source: Literal["settings", "membership", "store"] = "settings"


async def get_request_context(
    request: Request, intent: MerchantIntentDependency = None
) -> AsyncIterator[RequestContext]:
    """Resolve local demo request context from trusted process settings."""

    settings: Settings = request.app.state.settings
    if settings.runtime_profile != "legacy_demo":
        if request.url.path.startswith("/v1/shopper"):
            slug = request.headers.get("x-store-slug", "")
            if not slug or len(slug) > 120:
                raise StoreUnavailableError("Open a store link to start shopping.")
            # Slug discovery reveals only an enabled storefront, never merchant data.
            async with request.app.state.database.sessions() as session:
                row = (
                    await session.execute(
                        select(
                            Tenant.id,
                            StoreSetupRecord.sharing_enabled,
                            StoreSetupRecord.published_catalog_id,
                            StoreSetupRecord.sample_data,
                        )
                        .join(StoreSetupRecord)
                        .where(Tenant.slug == slug, Tenant.status == "active")
                    )
                ).one_or_none()
            if row is None:
                raise StoreUnavailableError()
            catalog = row.published_catalog_id if row.sharing_enabled else None
            preview = False
            raw_preview = request.cookies.get(store_cookie(request, "open_commerce_preview"), "")
            if raw_preview and len(raw_preview) <= 200:
                async with request.app.state.database.transaction(row.id) as session:
                    grant = await session.scalar(
                        select(AuthTicketRecord).where(
                            AuthTicketRecord.tenant_id == row.id,
                            AuthTicketRecord.purpose == "preview_session",
                            AuthTicketRecord.token_hash == session_token_hash(raw_preview),
                            AuthTicketRecord.expires_at > utc_now(),
                            AuthTicketRecord.consumed_at.is_(None),
                        )
                    )
                    if grant:
                        catalog = UUID(json.loads(grant.payload)["catalog_id"])
                        preview = True
            if catalog is None:
                raise StoreUnavailableError()
            async with request.app.state.database.transaction(row.id) as session:
                source = await session.scalar(
                    select(Integration).where(
                        Integration.tenant_id == row.id, Integration.id == catalog
                    )
                )
                sample = bool(source and source.non_secret_config.get("sample_data"))
            request.state.catalog_scope = CatalogScope(row.id, catalog, preview, sample)
            with catalog_scope(request.state.catalog_scope):
                yield RequestContext(
                    tenant_id=row.id,
                    actor_id="shopper",
                    roles=set(),
                    auth_mode="session",
                    tenant_source="store",
                )
            return
        owner = await MerchantAuthService(request.app.state.database).authenticate(
            request.cookies.get("open_commerce_merchant_session")
        )
        verify_merchant_intent(owner, intent)
        yield RequestContext(
            tenant_id=owner.tenant_id,
            actor_id=str(owner.user_id),
            roles={"owner"},
            auth_mode="session",
            tenant_source="membership",
        )
        return
    yield RequestContext(
        tenant_id=settings.local_tenant_id,
        actor_id="local-operator",
        roles={"owner", "operator", "viewer"},
    )


def require_roles(*required: str) -> Callable[[RequestContext], RequestContext]:
    """Return a local-demo compatible role dependency."""

    def _require_roles(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> RequestContext:
        if not context.roles.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="actor lacks a required role",
            )
        return context

    return _require_roles
