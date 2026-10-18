"""Private operational events and scoped, data-driven views and threshold monitoring."""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.scope import current_catalog
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.models.shopper_activity import (
    ActivityCheckRecord,
    ActivityRuleRecord,
    ShopperActivityRecord,
)
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.telemetry.activity_models import (
    ActivityCheck,
    ActivityEvent,
    ActivityEventInput,
    ActivityKind,
    ActivityOverview,
    ActivityQuery,
    ActivityRule,
    ActivityRuleInput,
)


class ActivityRuleError(ValueError):
    """A bounded, safe configuration error."""


def evaluate_metric(
    definition: ActivityRuleInput,
    events: list[ActivityEvent],
    *,
    now: datetime,
    truncated: bool = False,
) -> ActivityCheck:
    if not definition.enabled:
        return ActivityCheck(checked_at=now, state="paused")
    if definition.threshold is None:
        return ActivityCheck(checked_at=now, state="log_only", sample_count=len(events))
    eligible = events
    if definition.metric == "empty_result_rate":
        eligible = [
            item for item in events if item.status == "ok" and item.result_count is not None
        ]
    count = len(eligible)
    if truncated or count < definition.minimum_samples:
        return ActivityCheck(
            checked_at=now, state="insufficient_data", sample_count=count, truncated=truncated
        )
    if definition.metric == "count":
        value = float(count)
    elif definition.metric == "error_rate":
        value = 100 * sum(item.status != "ok" for item in eligible) / count
    elif definition.metric == "empty_result_rate":
        value = 100 * sum(item.result_count == 0 for item in eligible) / count
    else:
        value = float(sorted(item.duration_ms for item in eligible)[ceil(count * 0.95) - 1])
    return ActivityCheck(
        checked_at=now,
        state="alert" if value >= definition.threshold else "ok",
        sample_count=count,
        value=round(value, 3),
    )


class ActivityService:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def record(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        event: ActivityEventInput,
        key: str,
        account_version: int | None = None,
    ) -> None:
        async with self.database.transaction(tenant_id, write=True) as session:
            account = await self._account(session, tenant_id, account_id, account_version)
            scope = current_catalog.get()
            preview = bool(scope and scope.preview) or bool(account.preview_catalog_id)
            sample = bool(scope and scope.sample) or bool(
                await session.scalar(
                    select(StoreSetupRecord.sample_data).where(
                        StoreSetupRecord.tenant_id == tenant_id
                    )
                )
            )
            await session.execute(
                insert(ShopperActivityRecord)
                .values(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    account_id=account_id,
                    is_preview=preview,
                    is_sample=sample,
                    event_key=canonical_hash(key),
                    **event.model_dump(mode="json"),
                    occurred_at=utc_now(),
                )
                .on_conflict_do_nothing(constraint="uq_shopper_activity_key")
            )

    async def record_best_effort(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        event: ActivityEventInput,
        key: str,
        account_version: int | None = None,
    ) -> None:
        try:
            await self.record(
                tenant_id=tenant_id,
                account_id=account_id,
                event=event,
                key=key,
                account_version=account_version,
            )
        except ActivityRuleError:
            return
        except Exception as exc:
            # Observability outages must not turn a completed cart or memory command into a retry.
            structlog.get_logger(__name__).warning(
                "shopper.activity_unavailable", error_type=type(exc).__name__
            )

    async def overview(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID | None,
        query: ActivityQuery,
    ) -> ActivityOverview:
        now = utc_now()
        async with self.database.transaction(tenant_id) as session:
            events = await self._events(session, tenant_id, account_id, query, now, limit=100)
            counts_query = (
                select(ShopperActivityRecord.kind, func.count())
                .where(
                    ShopperActivityRecord.tenant_id == tenant_id,
                    ShopperActivityRecord.occurred_at
                    >= now - timedelta(minutes=query.window_minutes),
                )
                .group_by(ShopperActivityRecord.kind)
            )
            if account_id is not None:
                counts_query = counts_query.where(ShopperActivityRecord.account_id == account_id)
            elif not query.include_test_sessions:
                counts_query = counts_query.where(
                    ShopperActivityRecord.is_preview.is_(False),
                    ShopperActivityRecord.is_sample.is_(False),
                )
            counts = dict((await session.execute(counts_query)).tuples().all())
            rows = await session.scalars(
                select(ActivityRuleRecord)
                .where(
                    ActivityRuleRecord.tenant_id == tenant_id,
                    ActivityRuleRecord.owner_key == str(account_id or "store"),
                )
                .order_by(ActivityRuleRecord.updated_at.desc())
                .limit(20)
            )
            return ActivityOverview(
                scope="my_activity" if account_id else "store_activity",
                observed_counts=counts,
                events=events,
                rules=[self._rule(row) for row in rows],
                checked_at=now,
            )

    async def configure(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID | None,
        definition: ActivityRuleInput,
        key: str,
        account_version: int | None = None,
    ) -> ActivityRule:
        owner = str(account_id or "store")
        scope = f"activity:configure:{owner}"
        now = utc_now()
        async with self.database.transaction(tenant_id, write=True) as session:
            if account_id is not None:
                await self._account(session, tenant_id, account_id, account_version)
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope=scope, key=key, request=definition)
            if cached is not None:
                result = ActivityRule.model_validate(cached)
                if (
                    account_id is not None
                    and await session.scalar(
                        select(ActivityRuleRecord.id).where(
                            ActivityRuleRecord.tenant_id == tenant_id,
                            ActivityRuleRecord.account_id == account_id,
                            ActivityRuleRecord.owner_key == owner,
                            ActivityRuleRecord.id == result.id,
                        )
                    )
                    is None
                ):
                    raise ActivityRuleError("This activity rule is no longer available.")
                return result
            row = await session.scalar(
                select(ActivityRuleRecord).where(
                    ActivityRuleRecord.tenant_id == tenant_id,
                    ActivityRuleRecord.owner_key == owner,
                    ActivityRuleRecord.name_key == definition.name.lower(),
                )
            )
            if row is None:
                count = await session.scalar(
                    select(func.count())
                    .select_from(ActivityRuleRecord)
                    .where(
                        ActivityRuleRecord.tenant_id == tenant_id,
                        ActivityRuleRecord.owner_key == owner,
                    )
                )
                if (count or 0) >= (5 if account_id else 20):
                    raise ActivityRuleError("Rule limit reached; update or pause an existing rule")
                row = ActivityRuleRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    account_id=account_id,
                    owner_key=owner,
                    name_key=definition.name.lower(),
                )
                session.add(row)
            row.definition = definition.model_dump(mode="json")
            row.updated_at = now
            row.last_check = ActivityCheck(checked_at=now, state="pending").model_dump(mode="json")
            await session.flush()
            await self._evaluate(session, tenant_id, row, now)
            await session.flush()
            result = self._rule(row)
            receipts.remember(scope=scope, key=key, request=definition, response=result)
            return result

    async def evaluate_due(self, tenant_id: UUID, *, now: datetime | None = None) -> int:
        checked_at = now or utc_now()
        async with self.database.transaction(tenant_id, write=True) as session:
            rows = list(
                await session.scalars(
                    select(ActivityRuleRecord)
                    .where(
                        ActivityRuleRecord.tenant_id == tenant_id,
                        ActivityRuleRecord.next_check_at <= checked_at,
                    )
                    .order_by(ActivityRuleRecord.next_check_at)
                    .limit(50)
                )
            )
            evaluated = 0
            for row in rows:
                if row.account_id is not None:
                    try:
                        await self._account(session, tenant_id, row.account_id, None)
                    except ActivityRuleError:
                        continue
                await self._evaluate(session, tenant_id, row, checked_at)
                evaluated += 1
            cutoff = checked_at - timedelta(days=30)
            for table, time_column in (
                (ShopperActivityRecord, ShopperActivityRecord.occurred_at),
                (ActivityCheckRecord, ActivityCheckRecord.checked_at),
            ):
                await session.execute(
                    delete(table).where(table.tenant_id == tenant_id, time_column < cutoff)
                )
            return evaluated

    async def _account(
        self, session: AsyncSession, tenant_id: UUID, account_id: UUID, account_version: int | None
    ) -> ShopperAccountRecord:
        row = await session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == tenant_id,
                ShopperAccountRecord.id == account_id,
                ShopperAccountRecord.status == "active",
            )
        )
        if (
            row is None
            or (row.expires_at is not None and row.expires_at <= utc_now())
            or (account_version is not None and row.version != account_version)
        ):
            raise ActivityRuleError("Your shopping data is no longer available for this request.")
        return row

    async def _evaluate(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        row: ActivityRuleRecord,
        now: datetime,
    ) -> None:
        definition = ActivityRuleInput.model_validate(row.definition)
        events = (
            await self._events(
                session, tenant_id, row.account_id, definition.query, now, limit=5001
            )
            if definition.enabled
            else []
        )
        result = evaluate_metric(definition, events[:5000], now=now, truncated=len(events) > 5000)
        row.last_check = result.model_dump(mode="json")
        row.next_check_at = (
            now + timedelta(minutes=definition.interval_minutes)
            if definition.enabled and definition.threshold is not None
            else None
        )
        session.add(
            ActivityCheckRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                rule_id=row.id,
                definition=row.definition,
                result=row.last_check,
                checked_at=now,
            )
        )

    @staticmethod
    async def _events(
        session: AsyncSession,
        tenant_id: UUID,
        account_id: UUID | None,
        query: ActivityQuery,
        now: datetime,
        *,
        limit: int,
    ) -> list[ActivityEvent]:
        statement = select(ShopperActivityRecord).where(
            ShopperActivityRecord.tenant_id == tenant_id,
            ShopperActivityRecord.occurred_at >= now - timedelta(minutes=query.window_minutes),
            ShopperActivityRecord.occurred_at <= now,
        )
        if account_id is not None:
            statement = statement.where(ShopperActivityRecord.account_id == account_id)
        elif not query.include_test_sessions:
            statement = statement.where(
                ShopperActivityRecord.is_preview.is_(False),
                ShopperActivityRecord.is_sample.is_(False),
            )
        if query.kind is not None:
            statement = statement.where(ShopperActivityRecord.kind == query.kind)
        if query.status is not None:
            statement = statement.where(ShopperActivityRecord.status == query.status)
        if query.empty_results_only:
            statement = statement.where(ShopperActivityRecord.result_count == 0)
        rows = await session.scalars(
            statement.order_by(
                ShopperActivityRecord.occurred_at.desc(), ShopperActivityRecord.id.desc()
            ).limit(limit)
        )
        return [
            ActivityEvent(
                id=row.id,
                kind=ActivityKind(row.kind),
                status=row.status,
                duration_ms=row.duration_ms,
                result_count=row.result_count,
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]

    @staticmethod
    def _rule(row: ActivityRuleRecord) -> ActivityRule:
        return ActivityRule(
            id=row.id,
            definition=ActivityRuleInput.model_validate(row.definition),
            check=ActivityCheck.model_validate(row.last_check),
            next_check_at=row.next_check_at,
        )
