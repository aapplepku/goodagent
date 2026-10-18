"""Bounded merchant operations contracts, independent of models and transport."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from open_commerce.core.money import Money
from open_commerce.core.types import StrictDomainModel


class OperationsWindow(StrictDomainModel):
    hours: int = Field(default=24, ge=1, le=720)
    include_test_sessions: bool = False


class CatalogAuditInput(StrictDomainModel):
    limit: int = Field(default=10, ge=1, le=25)


class StockReviewInput(CatalogAuditInput):
    low_stock_threshold: int = Field(default=5, ge=0, le=1000)
    stale_after_hours: int = Field(default=24, ge=1, le=8760)


class OperationsAction(StrictDomainModel):
    priority: Literal["high", "medium", "low"]
    topic: str
    evidence: str
    next_step: str
    execution: Literal["read_only_tool", "owner_control", "source_system"]


class CatalogProductFact(StrictDomainModel):
    id: UUID
    product_id: str
    title: str
    missing_description: bool
    missing_image: bool
    image_failed: bool
    missing_category: bool


class CatalogVariantFact(StrictDomainModel):
    product_id: UUID
    variant_id: str
    sku: str | None
    price_minor: int
    cost_minor: int | None
    compare_at_price_minor: int | None
    available: bool
    observed_quantity: int | None
    observed_at: datetime | None
    reserved_quantity: int


class CatalogFacts(StrictDomainModel):
    catalog_id: UUID | None = None
    source_version: str | None = None
    product_count: int = 0
    variant_count: int = 0
    products: list[CatalogProductFact] = Field(default_factory=list)
    variants: list[CatalogVariantFact] = Field(default_factory=list)
    coverage_complete: bool = True
    checked_at: datetime


class ProductIssue(StrictDomainModel):
    product_id: str
    title: str
    variant_id: str | None = None
    issues: list[str]


class CatalogAudit(StrictDomainModel):
    catalog_id: UUID | None
    source_version: str | None
    checked_at: datetime
    product_count: int
    variant_count: int
    products_checked: int
    variants_checked: int
    coverage_complete: bool
    issue_counts: dict[str, int]
    examples: list[ProductIssue]
    examples_truncated: bool
    next_actions: list[OperationsAction]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Audits the operator's latest indexed catalog, not necessarily the shared version.",
            "Image checks use saved ingestion outcomes; external URLs are not fetched.",
            "Counts refer to affected products or variants per issue, not unique broken products.",
            "No product content, prices, or source records were changed.",
        ]
    )


class StockIssue(StrictDomainModel):
    product_id: str
    title: str
    variant_id: str
    state: Literal["unavailable", "unknown", "out", "low", "healthy"]
    observed_quantity: int | None
    reserved_quantity: int
    sellable_quantity: int | None
    observed_at: datetime | None
    stale: bool


class StockReview(StrictDomainModel):
    catalog_id: UUID | None
    checked_at: datetime
    variant_count: int
    variants_checked: int
    coverage_complete: bool
    low_stock_threshold: int
    stale_after_hours: int
    counts: dict[str, int]
    examples: list[StockIssue]
    examples_truncated: bool
    next_actions: list[OperationsAction]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Uploaded stock minus unexpired local reservations; not a live warehouse balance.",
            (
                "Demo purchases do not decrement source stock. No restock quantity or "
                "stockout date is predicted."
            ),
            "Unknown and stale quantities require source verification before acting.",
        ]
    )


class CheckoutReview(StrictDomainModel):
    checked_at: datetime
    start_at: datetime
    end_at: datetime
    hours: int
    orders_by_status: dict[str, int]
    demo_paid_totals: list[Money]
    payments_by_status: dict[str, int]
    overdue_processing: int
    nonempty_open_carts: int
    inactive_open_carts: int
    next_actions: list[OperationsAction]
    payment_mode: Literal["local_test"] = "local_test"
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Demo order values are not revenue. Totals are separate for each currency.",
            "Orders/payments are grouped by creation time and current status, not status history.",
            (
                "Cart counts are current snapshots; inactive means no cart update for "
                "24 hours, not proven abandonment."
            ),
            (
                "All local test commerce records are included; preview/sample "
                "provenance is not stored on these records."
            ),
            "No refunds, fulfillment, shipping, customer contacts or real payments are connected.",
        ]
    )


class ActivityPeriod(StrictDomainModel):
    start_at: datetime
    end_at: datetime
    events: int
    successful_by_kind: dict[str, int]
    unsuccessful_by_kind: dict[str, int]
    measured_searches: int
    empty_searches: int
    empty_result_percent: float | None
    last_event_at: datetime | None


class PerformanceReview(StrictDomainModel):
    checked_at: datetime
    hours: int
    include_test_sessions: bool
    current: ActivityPeriod
    previous: ActivityPeriod
    previous_window_within_retention: bool
    next_actions: list[OperationsAction]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Best-effort operational events retained for 30 days; no historical backfill.",
            (
                "Search empty-result rate covers successful instrumented searches with "
                "a recorded result count, minimum 5."
            ),
            (
                "Event counts are not unique shoppers, an attributed conversion "
                "funnel, or proof of search quality."
            ),
            (
                "Checkout events are demo completions, not revenue. No customer "
                "identities or queries are included."
            ),
        ]
    )


class StoreOperationsReadiness(StrictDomainModel):
    checked_at: datetime
    setup_available: bool
    sharing_enabled: bool | None
    published_catalog_id: UUID | None
    indexed_catalog_id: UUID | None
    latest_index_state: str
    replacement_pending: bool
    checklist: dict[str, bool]
    ai_checked_at: str | None
    next_actions: list[OperationsAction]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Setup checks are persisted evidence, not a new live connection or relevance test.",
            "Sharing and catalog replacement require explicit owner controls, never an agent tool.",
        ]
    )


class DailyOperationsBrief(StrictDomainModel):
    checked_at: datetime
    readiness: StoreOperationsReadiness
    catalog: CatalogAudit
    stock: StockReview
    checkout: CheckoutReview
    performance: PerformanceReview
    priorities: list[OperationsAction]
    read_only: Literal[True] = True
