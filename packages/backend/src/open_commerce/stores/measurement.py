"""Factual setup and shopping measurements; demo totals are never called revenue."""

from datetime import timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from open_commerce.core.types import StrictDomainModel, utc_now
from open_commerce.persistence.models.model_usage import ModelUsageRecord
from open_commerce.persistence.models.shopper_activity import ShopperActivityRecord
from open_commerce.persistence.models.store_setup import SetupEventRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.setup import StoreSetupService, store_records
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.activity_models import ActivityKind, ActivityQuery


class StoreMeasurements(StrictDomainModel):
    setup_complete: bool
    seconds_to_first_preview: float | None
    ai_requests_today: int
    reserved_tokens_today: int
    successful_searches: int
    product_selections: int
    searching_accounts: int = 0
    searchers_with_selection: int = 0
    cart_additions: int
    demo_checkouts: int
    preview_and_sample_excluded: bool = True


class MonitoringPreset(StrictDomainModel):
    name: Literal["failed_imports", "unavailable_ai", "empty_results"]
    enabled: bool


async def measurements(db: RuntimeDatabase, tenant: UUID) -> StoreMeasurements:
    async with db.transaction(tenant) as session:
        _, setup = await store_records(session, tenant)
        preview = await session.scalar(
            select(func.min(SetupEventRecord.occurred_at)).where(
                SetupEventRecord.tenant_id == tenant, SetupEventRecord.kind == "preview_created"
            )
        )
        counts: dict[str, int] = {
            kind: count
            for kind, count in (
                await session.execute(
                    select(ShopperActivityRecord.kind, func.count())
                    .where(
                        ShopperActivityRecord.tenant_id == tenant,
                        ShopperActivityRecord.status == "ok",
                        ShopperActivityRecord.is_preview.is_(False),
                        ShopperActivityRecord.is_sample.is_(False),
                        ShopperActivityRecord.occurred_at >= utc_now() - timedelta(hours=24),
                    )
                    .group_by(ShopperActivityRecord.kind)
                )
            ).all()
        }
        requests, tokens = (
            await session.execute(
                select(
                    func.count(ModelUsageRecord.id),
                    func.coalesce(func.sum(ModelUsageRecord.reserved_tokens), 0),
                ).where(
                    ModelUsageRecord.tenant_id == tenant, ModelUsageRecord.day == utc_now().date()
                )
            )
        ).one()
        # A temporal, account-level cohort, not attribution to a particular query or model.
        first_search = (
            select(
                ShopperActivityRecord.account_id,
                func.min(ShopperActivityRecord.occurred_at).label("first_at"),
            )
            .where(
                ShopperActivityRecord.tenant_id == tenant,
                ShopperActivityRecord.kind == "search",
                ShopperActivityRecord.status == "ok",
                ShopperActivityRecord.is_preview.is_(False),
                ShopperActivityRecord.is_sample.is_(False),
                ShopperActivityRecord.occurred_at >= utc_now() - timedelta(hours=24),
            )
            .group_by(ShopperActivityRecord.account_id)
            .subquery()
        )
        selection = aliased(ShopperActivityRecord)
        selected_after = (
            select(selection.id)
            .where(
                selection.tenant_id == tenant,
                selection.account_id == first_search.c.account_id,
                selection.kind == "product_select",
                selection.status == "ok",
                selection.is_preview.is_(False),
                selection.is_sample.is_(False),
                selection.occurred_at >= first_search.c.first_at,
            )
            .exists()
        )
        searchers = int(await session.scalar(select(func.count()).select_from(first_search)) or 0)
        selected = int(
            await session.scalar(
                select(func.count()).select_from(first_search).where(selected_after)
            )
            or 0
        )
        return StoreMeasurements(
            setup_complete=setup.sharing_enabled,
            seconds_to_first_preview=max(0, (preview - setup.created_at).total_seconds())
            if preview
            else None,
            ai_requests_today=requests,
            reserved_tokens_today=tokens,
            successful_searches=counts.get("search", 0),
            product_selections=counts.get("product_select", 0),
            searching_accounts=searchers,
            searchers_with_selection=selected,
            cart_additions=counts.get("cart_add", 0),
            demo_checkouts=counts.get("checkout_confirm", 0),
        )


async def configure_monitor(db: RuntimeDatabase, tenant: UUID, preset: MonitoringPreset) -> None:
    async with db.transaction(tenant, write=True) as session:
        _, setup = await store_records(session, tenant)
        setup.readiness = {
            **setup.readiness,
            f"monitor_{preset.name}": preset.enabled,
            "monitor_next_check": 0,
        }


async def check_monitors(db: RuntimeDatabase, tenant: UUID) -> None:
    now = utc_now()
    async with db.transaction(tenant) as session:
        _, setup = await store_records(session, tenant)
        facts = dict(setup.readiness)
    next_check = facts.get("monitor_next_check")
    if isinstance(next_check, int | float) and now.timestamp() < next_check:
        return
    statuses: dict[str, str | int | bool] = {
        "monitor_next_check": int(now.timestamp()) + 300,
        "monitor_checked_at": now.isoformat(),
    }
    if facts.get("monitor_failed_imports"):
        readiness = await StoreSetupService(db).readiness(tenant)
        statuses["alert_failed_imports"] = (
            "Import failed. Retry indexing or upload corrected products."
            if readiness.indexing.status == "failed"
            else "No failed indexing job."
        )
    if facts.get("monitor_unavailable_ai"):
        statuses["alert_unavailable_ai"] = (
            "AI check failed. Check credentials and usage limits, then retry."
            if facts.get("ai_checked_at") and not facts.get("ai_verified")
            else "No failed AI connection check."
        )
    if facts.get("monitor_empty_results"):
        overview = await ActivityService(db).overview(
            tenant_id=tenant,
            account_id=None,
            query=ActivityQuery(kind=ActivityKind.SEARCH, window_minutes=60),
        )
        searches = [e for e in overview.events if e.status == "ok" and e.result_count is not None]
        empty = sum(e.result_count == 0 for e in searches)
        statuses["alert_empty_results"] = (
            "Not enough searches yet (minimum 5)."
            if len(searches) < 5
            else "Empty results exceed 20%. Review recent searches."
            if empty / len(searches) >= 0.2
            else "Empty results below 20%."
        )
    async with db.transaction(tenant, write=True) as session:
        _, setup = await store_records(session, tenant)
        setup.readiness = {**setup.readiness, **statuses}
