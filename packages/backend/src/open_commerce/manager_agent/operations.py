"""Read-only store operations; no customer records or commerce mutators reach the model."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import active_catalog_integration, catalog_index_status
from open_commerce.core.money import Money
from open_commerce.core.types import JsonObject, utc_now
from open_commerce.manager_agent.catalog_operations import (
    audit_catalog,
    catalog_facts,
    review_stock,
)
from open_commerce.manager_agent.model_provider import ManagerToolCall
from open_commerce.manager_agent.operations_models import (
    ActivityPeriod,
    CatalogAuditInput,
    CheckoutReview,
    DailyOperationsBrief,
    OperationsAction,
    OperationsWindow,
    PerformanceReview,
    StockReviewInput,
    StoreOperationsReadiness,
)
from open_commerce.persistence.models.commerce import (
    PaymentAttemptRecord,
    ShopperCartLineRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.models.shopper_activity import ShopperActivityRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.models import StoreError
from open_commerce.stores.setup import StoreSetupService

OPERATIONS_DESCRIPTIONS = {
    "review_store_day": (
        "Give the merchant a daily store briefing: setup, catalog issues, stock risks, "
        "demo checkout and shopper activity, with prioritized next actions. Read-only. "
        "Hours is a rolling UTC window (default 24). Exclude preview/sample activity "
        "unless explicitly requested. Does not schedule a recurring briefing."
    ),
    "audit_catalog_quality": (
        "Find missing descriptions/images/categories, image ingestion failures, "
        "missing or duplicate SKUs and price flags in the latest indexed catalog. "
        "Return bounded product IDs and issues for correction. Does not edit products "
        "or fetch image URLs."
    ),
    "review_inventory_risks": (
        "Find low, unavailable, unknown or stale stock by variant, subtracting "
        "unexpired local reservations. Default low threshold 5 units and stale after "
        "24 hours. Observations are uploaded snapshots, not live inventory; no restock "
        "or quantity writes."
    ),
    "review_checkout_operations": (
        "Review complete demo order/payment aggregates in a rolling UTC time window, "
        "separate currencies, stuck processing and inactive nonempty carts. Includes "
        "all local demo commerce records, not revenue or fulfillment. "
        "include_test_sessions applies only to activity reports, not this tool."
    ),
    "review_shopper_performance": (
        "Compare aggregate shopper activity in the selected rolling window with the "
        "preceding equal window. Search failures, measured empty searches, product "
        "selections, cart additions and demo completions. Exclude preview/sample "
        "events unless explicitly requested. No individual shoppers, raw queries or "
        "causal sales claims."
    ),
    "inspect_store_readiness": (
        "Read persisted setup, indexed versus shared catalog versions, preview checks "
        "and sharing state. Explain the next owner control. Does not publish, mint "
        "preview grants, or test live AI connectivity."
    ),
}


class StoreOperations:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def execute(self, call: ManagerToolCall, tenant: UUID) -> JsonObject:
        if call.name == "inspect_store_readiness":
            return (await self.readiness(tenant)).model_dump(mode="json")
        if call.name == "audit_catalog_quality":
            args = CatalogAuditInput.model_validate(call.arguments)
            return audit_catalog(await catalog_facts(self.database, tenant), args).model_dump(
                mode="json"
            )
        if call.name == "review_inventory_risks":
            stock_args = StockReviewInput.model_validate(call.arguments)
            return review_stock(await catalog_facts(self.database, tenant), stock_args).model_dump(
                mode="json"
            )
        window = OperationsWindow.model_validate(call.arguments)
        if call.name == "review_checkout_operations":
            return (await self.checkout(tenant, window)).model_dump(mode="json")
        if call.name == "review_shopper_performance":
            return (await self.performance(tenant, window)).model_dump(mode="json")
        if call.name != "review_store_day":
            return {"error": "UNKNOWN_TOOL"}
        facts = await catalog_facts(self.database, tenant)
        catalog = audit_catalog(facts, CatalogAuditInput(limit=3))
        stock = review_stock(facts, StockReviewInput(limit=3))
        readiness = await self.readiness(tenant)
        checkout = await self.checkout(tenant, window)
        performance = await self.performance(tenant, window)
        priorities = [
            action
            for section in (readiness, catalog, stock, checkout, performance)
            for action in section.next_actions
        ]
        priorities.sort(key=lambda action: {"high": 0, "medium": 1, "low": 2}[action.priority])
        return DailyOperationsBrief(
            checked_at=utc_now(),
            readiness=readiness,
            catalog=catalog,
            stock=stock,
            checkout=checkout,
            performance=performance,
            priorities=priorities[:8],
        ).model_dump(mode="json")

    async def readiness(self, tenant: UUID) -> StoreOperationsReadiness:
        now = utc_now()
        async with self.database.transaction(tenant) as session:
            active = await active_catalog_integration(session, tenant_id=tenant)
            index = await catalog_index_status(session, tenant_id=tenant)
        try:
            state = await StoreSetupService(self.database).readiness(tenant)
        except StoreError as exc:
            if exc.status_code != 404:
                raise
            return StoreOperationsReadiness(
                checked_at=now,
                setup_available=False,
                sharing_enabled=None,
                published_catalog_id=None,
                indexed_catalog_id=active.id if active else None,
                latest_index_state=index.status,
                replacement_pending=False,
                checklist={},
                ai_checked_at=None,
                next_actions=[
                    OperationsAction(
                        priority="medium",
                        topic="setup",
                        evidence=(
                            "No self-service store setup record; sharing readiness is unknown."
                        ),
                        next_step=(
                            "Use owner setup for a new store. Existing legacy-demo "
                            "data has not been assigned or published."
                        ),
                        execution="owner_control",
                    )
                ],
            )
        actions = []
        next_steps = {
            "catalog_verified": (
                "Open Products in Store setup; confirm the reviewed upload or retry "
                "failed indexing."
            ),
            "images_reviewed": (
                "Review the image failures in Preview; correct the source or "
                "explicitly acknowledge the issues."
            ),
            "search_tested": (
                "Open the private shopper preview and test a search for this exact catalog."
            ),
            "ai_verified": (
                "Use Check AI in Store setup to verify the configured connection; "
                "browsing does not require AI."
            ),
            "demo_checkout_acknowledged": (
                "Review and acknowledge demo-only checkout in Ready to share."
            ),
            "sharing_enabled": (
                "Enable the store link only when you intend to share it, using Ready to share."
            ),
        }
        for key, passed in state.checklist.items():
            if not passed:
                actions.append(
                    OperationsAction(
                        priority="high" if key == "catalog_verified" else "low",
                        topic=key,
                        evidence=f"Setup check {key} has not passed.",
                        next_step=next_steps[key],
                        execution="owner_control",
                    )
                )
        replacement = bool(
            active
            and state.store.published_catalog_id
            and active.id != state.store.published_catalog_id
        )
        if replacement:
            actions.insert(
                0,
                OperationsAction(
                    priority="medium",
                    topic="catalog_replacement",
                    evidence="The indexed catalog differs from the previously shared catalog.",
                    next_step=(
                        "Preview the new version, test search, then explicitly approve "
                        "its replacement. The shared version has not been changed by "
                        "this review."
                    ),
                    execution="owner_control",
                ),
            )
        checked = state.store.readiness.get("ai_checked_at")
        return StoreOperationsReadiness(
            checked_at=now,
            setup_available=True,
            sharing_enabled=state.store.sharing_enabled,
            published_catalog_id=state.store.published_catalog_id,
            indexed_catalog_id=active.id if active else None,
            latest_index_state=state.indexing.status,
            replacement_pending=replacement,
            checklist=state.checklist,
            ai_checked_at=checked if isinstance(checked, str) else None,
            next_actions=actions,
        )

    async def checkout(self, tenant: UUID, args: OperationsWindow) -> CheckoutReview:
        now = utc_now()
        start = now - timedelta(hours=args.hours)
        async with self.database.transaction(tenant) as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            order_rows = (
                await session.execute(
                    select(ShopperOrderRecord.status, func.count())
                    .where(
                        ShopperOrderRecord.tenant_id == tenant,
                        ShopperOrderRecord.created_at >= start,
                        ShopperOrderRecord.created_at < now,
                    )
                    .group_by(ShopperOrderRecord.status)
                )
            ).all()
            totals = (
                await session.execute(
                    select(ShopperOrderRecord.currency, func.sum(ShopperOrderRecord.amount_minor))
                    .where(
                        ShopperOrderRecord.tenant_id == tenant,
                        ShopperOrderRecord.status == "paid",
                        ShopperOrderRecord.created_at >= start,
                        ShopperOrderRecord.created_at < now,
                    )
                    .group_by(ShopperOrderRecord.currency)
                    .order_by(ShopperOrderRecord.currency)
                )
            ).all()
            payment_rows = (
                await session.execute(
                    select(PaymentAttemptRecord.status, func.count())
                    .where(
                        PaymentAttemptRecord.tenant_id == tenant,
                        PaymentAttemptRecord.created_at >= start,
                        PaymentAttemptRecord.created_at < now,
                    )
                    .group_by(PaymentAttemptRecord.status)
                )
            ).all()
            overdue = int(
                await session.scalar(
                    select(func.count())
                    .select_from(PaymentAttemptRecord)
                    .where(
                        PaymentAttemptRecord.tenant_id == tenant,
                        PaymentAttemptRecord.status == "processing",
                        PaymentAttemptRecord.updated_at < now - timedelta(minutes=15),
                    )
                )
                or 0
            )
            has_lines = (
                select(ShopperCartLineRecord.id)
                .where(
                    ShopperCartLineRecord.tenant_id == tenant,
                    ShopperCartLineRecord.cart_id == ShopperCartRecord.id,
                    ShopperCartLineRecord.account_id == ShopperCartRecord.account_id,
                )
                .exists()
            )
            carts, inactive = (
                await session.execute(
                    select(
                        func.count(),
                        func.count().filter(
                            ShopperCartRecord.updated_at < now - timedelta(hours=24)
                        ),
                    )
                    .select_from(ShopperCartRecord)
                    .where(
                        ShopperCartRecord.tenant_id == tenant,
                        ShopperCartRecord.status == "open",
                        ShopperCartRecord.created_at < now,
                        has_lines,
                    )
                )
            ).one()
        orders = {status: count for status, count in order_rows}
        payments = {status: count for status, count in payment_rows}
        actions = []
        if overdue:
            actions.append(
                OperationsAction(
                    priority="high",
                    topic="checkout_processing",
                    evidence=(
                        f"{overdue} demo payments have remained processing without an "
                        f"update for more than 15 minutes (all ages)."
                    ),
                    next_step=(
                        "Inspect service status and the Commerce panel before "
                        "retrying. Do not mark orders paid or promise a refund."
                    ),
                    execution="read_only_tool",
                )
            )
        if payments.get("requires_payment_method", 0):
            actions.append(
                OperationsAction(
                    priority="medium",
                    topic="checkout_declines",
                    evidence=(
                        f"{payments['requires_payment_method']} demo payment attempts "
                        f"currently require another payment method."
                    ),
                    next_step=(
                        "Inspect the Commerce panel and test checkout explicitly in "
                        "the shopper preview; no real payment was charged."
                    ),
                    execution="owner_control",
                )
            )
        if inactive:
            actions.append(
                OperationsAction(
                    priority="low",
                    topic="inactive_carts",
                    evidence=(
                        f"{inactive} nonempty open carts have not changed for at least 24 hours."
                    ),
                    next_step=(
                        "Compare shopper activity for checkout errors. These carts are "
                        "not proven abandonment; recovery emails are not connected."
                    ),
                    execution="read_only_tool",
                )
            )
        return CheckoutReview(
            checked_at=now,
            start_at=start,
            end_at=now,
            hours=args.hours,
            orders_by_status=orders,
            demo_paid_totals=[
                Money(currency=currency, amount_minor=int(amount)) for currency, amount in totals
            ],
            payments_by_status=payments,
            overdue_processing=overdue,
            nonempty_open_carts=carts,
            inactive_open_carts=inactive,
            next_actions=actions,
        )

    async def performance(self, tenant: UUID, args: OperationsWindow) -> PerformanceReview:
        now = utc_now()
        start = now - timedelta(hours=args.hours)
        previous_start = start - timedelta(hours=args.hours)
        async with self.database.transaction(tenant) as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            current = await activity_period(session, tenant, args, start, now)
            previous = await activity_period(session, tenant, args, previous_start, start)
        actions = []
        if not current.events:
            actions.append(
                OperationsAction(
                    priority="low",
                    topic="activity_missing",
                    evidence="No recorded shopper events in this window and scope.",
                    next_step=(
                        "Test the shopper journey or explicitly include test sessions "
                        "for diagnostics. No traffic or conversion conclusion can be "
                        "drawn."
                    ),
                    execution="read_only_tool",
                )
            )
        if current.empty_result_percent is not None and current.empty_result_percent >= 20:
            actions.append(
                OperationsAction(
                    priority="medium",
                    topic="empty_searches",
                    evidence=(
                        f"{current.empty_searches} of {current.measured_searches} "
                        f"successful measured searches returned no products."
                    ),
                    next_step=(
                        "Test representative catalog searches; inspect catalog "
                        "coverage before changing ranking. A store empty-result "
                        "monitor can track recurrence."
                    ),
                    execution="read_only_tool",
                )
            )
        if sum(current.unsuccessful_by_kind.values()):
            actions.append(
                OperationsAction(
                    priority="medium",
                    topic="shopper_errors",
                    evidence=(
                        f"{sum(current.unsuccessful_by_kind.values())} error or "
                        f"fallback events in the observed window."
                    ),
                    next_step=(
                        "Inspect shopping activity by event type, then check service "
                        "status. Set an in-app monitor only when requested."
                    ),
                    execution="read_only_tool",
                )
            )
        return PerformanceReview(
            checked_at=now,
            hours=args.hours,
            include_test_sessions=args.include_test_sessions,
            current=current,
            previous=previous,
            previous_window_within_retention=previous_start >= now - timedelta(days=30),
            next_actions=actions,
        )


async def activity_period(
    session: AsyncSession, tenant: UUID, args: OperationsWindow, start: datetime, end: datetime
) -> ActivityPeriod:
    scope = [
        ShopperActivityRecord.tenant_id == tenant,
        ShopperActivityRecord.occurred_at >= start,
        ShopperActivityRecord.occurred_at < end,
    ]
    if not args.include_test_sessions:
        scope.extend(
            [
                ShopperActivityRecord.is_preview.is_(False),
                ShopperActivityRecord.is_sample.is_(False),
            ]
        )
    rows = (
        await session.execute(
            select(
                ShopperActivityRecord.kind,
                ShopperActivityRecord.status,
                func.count(),
                func.count(ShopperActivityRecord.result_count),
                func.count().filter(ShopperActivityRecord.result_count == 0),
                func.max(ShopperActivityRecord.occurred_at),
            )
            .where(*scope)
            .group_by(ShopperActivityRecord.kind, ShopperActivityRecord.status)
        )
    ).all()
    successful: dict[str, int] = {}
    unsuccessful: dict[str, int] = {}
    measured, empty, total = 0, 0, 0
    last = None
    for kind, status, count, recorded, zero, occurred_at in rows:
        total += count
        bucket = successful if status == "ok" else unsuccessful
        bucket[kind] = bucket.get(kind, 0) + count
        last = max(last, occurred_at) if last else occurred_at
        if kind == "search" and status == "ok":
            measured, empty = recorded, zero
    return ActivityPeriod(
        start_at=start,
        end_at=end,
        events=total,
        successful_by_kind=successful,
        unsuccessful_by_kind=unsuccessful,
        measured_searches=measured,
        empty_searches=empty,
        empty_result_percent=round(empty * 100 / measured, 2) if measured >= 5 else None,
        last_event_at=last,
    )
