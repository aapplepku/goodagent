"""Short-transaction inference journal. Unknown dispatches are never retried."""

import json
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import or_, select

from open_commerce.controller.ollama import InferenceResult, OllamaBackend
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.persistence.models.inference import InferenceCall
from open_commerce.persistence.runtime_db import RuntimeDatabase


class InferencePendingError(ValueError):
    """Another worker still owns a bounded in-flight call."""


class InferenceStoppedError(ValueError):
    """Budget, integrity, or uncertain prior dispatch blocks further inference."""


class InferenceJournal:
    def __init__(self, database: RuntimeDatabase, backend: OllamaBackend | None = None) -> None:
        self.database = database
        self.backend = backend or OllamaBackend(database.settings)

    async def invoke(
        self,
        *,
        tenant_id: UUID,
        scope: str,
        operation_key: str,
        messages: list[dict[str, str]],
        schema: dict[str, object],
        template_version: str,
    ) -> tuple[UUID, InferenceResult, bool]:
        settings = self.database.settings
        self.backend.require_enabled()
        request = {
            "messages": messages,
            "schema": schema,
            "template_version": template_version,
            "model_id": settings.model_id,
            "model_digest": settings.model_digest,
            "max_output_tokens": settings.model_max_output_tokens,
        }
        request_hash = canonical_hash(request)
        # UTF-8 bytes plus framing/schema overhead conservatively reserve token capacity.
        reserved = len(json.dumps(request, ensure_ascii=False).encode()) + 1024
        reserved += settings.model_max_output_tokens
        if reserved > 32768:
            raise InferenceStoppedError("inference context reservation exceeds fixed context")
        call_id = uuid5(NAMESPACE_URL, f"{tenant_id}:inference:{operation_key}")
        stop = False
        async with self.database.transaction(tenant_id, write=True) as session:
            existing = await session.scalar(
                select(InferenceCall).where(
                    InferenceCall.tenant_id == tenant_id,
                    InferenceCall.operation_key == operation_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash or existing.scope != scope:
                    raise InferenceStoppedError("inference request changed under its stable ID")
                if existing.status == "completed":
                    return call_id, InferenceResult.model_validate(existing.response_data), True
                if existing.status != "dispatched":
                    raise InferenceStoppedError(f"prior inference is {existing.status}; no retry")
                if existing.lease_until > utc_now():
                    raise InferencePendingError("inference request remains leased")
                existing.status, existing.error_code = "uncertain", "DISPATCH_OUTCOME_UNKNOWN"
                existing.completed_at = utc_now()
                stop = True
            else:
                now = utc_now()
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                calls = list(
                    await session.scalars(
                        select(InferenceCall).where(
                            InferenceCall.tenant_id == tenant_id,
                            or_(
                                InferenceCall.scope == scope, InferenceCall.created_at >= day_start
                            ),
                        )
                    )
                )
                for records, max_calls, max_tokens in (
                    (
                        [r for r in calls if r.scope == scope],
                        settings.model_goal_request_limit,
                        settings.model_goal_token_limit,
                    ),
                    (
                        [r for r in calls if r.created_at >= day_start],
                        settings.model_daily_request_limit,
                        settings.model_daily_token_limit,
                    ),
                ):
                    if (
                        len(records) >= max_calls
                        or sum(r.reserved_tokens for r in records) + reserved > max_tokens
                    ):
                        raise InferenceStoppedError("independent inference budget exhausted")
                session.add(
                    InferenceCall(
                        id=call_id,
                        tenant_id=tenant_id,
                        scope=scope,
                        operation_key=operation_key,
                        request_hash=request_hash,
                        status="dispatched",
                        reserved_tokens=reserved,
                        request_data=request,
                        created_at=now,
                        lease_until=now + timedelta(seconds=settings.model_timeout_seconds + 15),
                    )
                )
        if stop:
            raise InferenceStoppedError(
                "prior dispatch is uncertain; reservation retained, no retry"
            )
        # The durable reservation commits before the only network call; no tenant lock held.
        try:
            result = await self.backend.complete(messages=messages, schema=schema)
            if result.prompt_tokens + result.output_tokens > reserved:
                raise InferenceStoppedError("reported usage exceeds conservative reservation")
        except Exception as exc:
            await self._settle(tenant_id, call_id, None, type(exc).__name__)
            raise
        await self._settle(tenant_id, call_id, result, None)
        return call_id, result, False

    async def _settle(
        self, tenant_id: UUID, call_id: UUID, result: InferenceResult | None, error: str | None
    ) -> None:
        async with self.database.transaction(tenant_id, write=True) as session:
            call = await session.scalar(
                select(InferenceCall).where(
                    InferenceCall.tenant_id == tenant_id, InferenceCall.id == call_id
                )
            )
            if call is None or call.status != "dispatched":
                raise InferenceStoppedError(
                    "inference lease settled by recovery; late response rejected"
                )
            call.status = "completed" if result else "failed"
            call.response_data = result.model_dump(mode="json") if result else None
            call.error_code, call.completed_at = error, utc_now()
