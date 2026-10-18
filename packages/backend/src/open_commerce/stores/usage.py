"""Per-task model scope and serialized, fail-closed model admission."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, text

from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.persistence.models.model_usage import ModelUsageRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase


class ModelQuotaExceeded(ManagerModelUnavailableError):
    """The model is available but this store exhausted its configured allowance."""


@dataclass(frozen=True)
class UsageScope:
    database: RuntimeDatabase
    tenant_id: UUID
    account_id: UUID | None


_scope: ContextVar[UsageScope | None] = ContextVar("model_usage_scope", default=None)


@contextmanager
def model_scope(
    database: RuntimeDatabase, tenant_id: UUID, account_id: UUID | None = None
) -> Iterator[None]:
    token = _scope.set(UsageScope(database, tenant_id, account_id))
    try:
        yield
    finally:
        _scope.reset(token)


async def admit_model_call(input_bytes: int, max_output_tokens: int) -> None:
    scope = _scope.get()
    if scope is None:
        raise ManagerModelUnavailableError("Model request has no authenticated store budget")
    settings = scope.database.settings
    if settings.runtime_profile == "legacy_demo":
        return
    # JSON bytes + output cap deliberately over-reserve instead of guessing tokenization.
    # Uncertain provider outcomes remain charged; no retry can spend the same allowance twice.
    reservation = input_bytes + max_output_tokens + 512
    today = utc_now().date()
    async with scope.database.transaction(scope.tenant_id) as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(1130003)"))
        requests, tokens = (
            await session.execute(
                select(
                    func.count(ModelUsageRecord.id),
                    func.coalesce(func.sum(ModelUsageRecord.reserved_tokens), 0),
                ).where(
                    ModelUsageRecord.tenant_id == scope.tenant_id, ModelUsageRecord.day == today
                )
            )
        ).one()
        if (
            requests >= settings.model_daily_request_limit
            or tokens + reservation > settings.model_daily_token_limit
        ):
            raise ModelQuotaExceeded(
                "This store's daily AI allowance is used up. Browsing is still available."
            )
        if settings.runtime_profile == "hosted":
            # The deployment ceiling is a control-plane aggregate, never returned to stores.
            total_requests, total_tokens = (
                await session.execute(
                    select(
                        func.count(ModelUsageRecord.id),
                        func.coalesce(func.sum(ModelUsageRecord.reserved_tokens), 0),
                    ).where(ModelUsageRecord.day == today)
                )
            ).one()
            if total_requests >= (
                settings.hosted_daily_request_limit or 0
            ) or total_tokens + reservation > (settings.hosted_daily_token_limit or 0):
                raise ModelQuotaExceeded(
                    "AI capacity is temporarily exhausted. Browsing is still available."
                )
        session.add(
            ModelUsageRecord(
                tenant_id=scope.tenant_id,
                account_id=scope.account_id,
                day=today,
                reserved_tokens=reservation,
                purpose="shopper" if scope.account_id else "merchant",
                created_at=utc_now(),
            )
        )
