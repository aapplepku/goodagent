"""Surface-matched observed cohorts; never reads simulator response parameters."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import Field

from open_commerce.core.types import StrictDomainModel
from open_commerce.simulator.merchandising_models import MerchandisingState, PriceRevision
from open_commerce.simulator.models import SimulatorState


class SurfaceObservation(StrictDomainModel):
    start_at: datetime
    end_at: datetime
    surface: Literal["search", "product_detail"]
    days: list[str] = Field(default_factory=list)
    eligible_sessions: int = 0
    exposures: int = 0
    clicks: int = 0
    carts: int = 0
    orders: int = 0
    contribution_profit_minor: int = 0
    net_revenue_minor: int = 0
    minimum_relevance: Decimal | None = None
    constraints_hold: bool = True
    queries: list[str] = Field(default_factory=list)
    policy_versions: list[int] = Field(default_factory=list)
    currency: Literal["USD"] = "USD"
    population: str = "recorded surface batches; redeemed lines from those same batches"

    @property
    def enough(self) -> bool:
        return len(self.days) >= 2 and self.exposures >= 200


def day_start(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.min, UTC)


def recent_window(state: SimulatorState) -> tuple[datetime, datetime]:
    end = day_start(state.current_time)
    return max(state.start_at, end - timedelta(days=4)), end


def recorded_price_window(
    state: SimulatorState,
    variant_id: str,
) -> tuple[datetime, datetime | None] | None:
    """Expiry updates the live revision timestamp; retain the actual intervention window."""
    for record in sorted(state.command_history, key=lambda r: r.created_at, reverse=True):
        if record.action_type != "set_variant_price":
            continue
        changes = (record.after_state or {}).get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if isinstance(change, dict) and change.get("variant_id") == variant_id:
                revision = PriceRevision.model_validate(change["price_revision"])
                return record.created_at, revision.expires_at
    return None


def observe_surface(
    merch: MerchandisingState,
    *,
    start: datetime,
    end: datetime,
    surface: Literal["search", "product_detail"],
    product_ids: set[str] | None = None,
    anchor_id: str | None = None,
    policy_version: int | None = None,
    queries: set[str] | None = None,
) -> SurfaceObservation:
    """Count a cohort once per batch; exclude partial days, declines and future receipts.

    With an anchor filter, eligible_sessions includes an empty panel, while
    exposures counts only batches showing a selected product. This distinguishes
    missing compatible exposure from the product's unrelated alternative panels.
    """
    result = SurfaceObservation(start_at=start, end_at=end, surface=surface)
    pdp_cohort = surface == "product_detail" and product_ids is None and anchor_id is None
    if pdp_cohort and (policy_version is not None or queries is not None):
        raise ValueError("Whole-checkout PDP observation requires an unfiltered daily cohort")
    days, found_queries, versions, seen_receipts = set(), set(), set(), set()
    for batch in merch.serving_log.values():
        current = datetime.combine(datetime.fromisoformat(batch.day).date(), time.min, UTC)
        if (
            batch.surface != surface
            or current < start
            or current + timedelta(days=1) > end
            or (anchor_id is not None and batch.anchor_product_id != anchor_id)
            or (policy_version is not None and batch.policy_version != policy_version)
            or (queries is not None and batch.query not in queries)
        ):
            continue
        included = set(batch.product_ids)
        if product_ids is not None:
            included &= product_ids
        if not included and anchor_id is None and not pdp_cohort:
            continue
        days.add(batch.day)
        result.eligible_sessions += batch.eligible_sessions
        if included or pdp_cohort:
            result.exposures += batch.eligible_sessions
        result.clicks += sum(batch.clicks.get(p, 0) for p in included)
        result.carts += sum(batch.carts.get(p, 0) for p in included)
        for product in included:
            relevance = batch.relevance.get(product)
            if relevance is not None:
                result.minimum_relevance = min(
                    relevance,
                    result.minimum_relevance if result.minimum_relevance is not None else relevance,
                )
            constraints = batch.constraint_matches.get(product, {})
            result.constraints_hold &= bool(constraints) and all(constraints.values())
        if batch.query is not None:
            found_queries.add(batch.query)
        if batch.policy_version is not None:
            versions.add(batch.policy_version)
        for key in batch.order_keys:
            receipt = merch.redemptions.get(key)
            if (
                key in seen_receipts
                or receipt is None
                or receipt.status != "redeemed"
                or receipt.product_id not in included
                or not start <= receipt.occurred_at < end
                or receipt.occurred_at.date().isoformat() != batch.day
            ):
                continue
            seen_receipts.add(key)
            result.orders += 1
            result.contribution_profit_minor += receipt.economics.contribution_profit_minor
            result.net_revenue_minor += receipt.economics.effective_price_minor
    result.days = sorted(days)
    result.queries = sorted(found_queries)
    result.policy_versions = sorted(versions)
    if pdp_cohort:
        # Every simulator checkout follows one recorded PDP visit. Alternatives
        # may replace a search line; complements add a line. Panel-only profit
        # would confuse that attribution change with economic deterioration.
        result.population = (
            "all recorded PDP visits including empty panels; whole same-day checkout profit"
        )
        result.orders = result.contribution_profit_minor = result.net_revenue_minor = 0
        checkout_receipts: set[str] = set()
        for keys in merch.checkout_lines.values():
            receipts = [merch.redemptions.get(key) for key in keys]
            if (
                not receipts
                or len(set(keys)) != len(keys)
                or any(
                    receipt is None
                    or receipt.status != "redeemed"
                    or receipt.occurred_at.date().isoformat() not in days
                    or not start <= receipt.occurred_at < end
                    or receipt.order_key in checkout_receipts
                    for receipt in receipts
                )
            ):
                continue
            if len({r.occurred_at.date() for r in receipts if r is not None}) != 1:
                continue
            result.orders += 1
            for receipt in receipts:
                assert receipt is not None
                checkout_receipts.add(receipt.order_key)
                result.contribution_profit_minor += receipt.economics.contribution_profit_minor
                result.net_revenue_minor += receipt.economics.effective_price_minor
    return result


class Reassessment(StrictDomainModel):
    classification: Literal["insufficient", "observed_poor_performance", "no_stop_signal"]
    reason: str
    before: SurfaceObservation
    after: SurfaceObservation
    causal: Literal[False] = False
    review_required: bool = False


def reassess(
    merch: MerchandisingState,
    *,
    product_ids: set[str] | None,
    started: datetime,
    now: datetime,
    surface: Literal["search", "product_detail"] = "search",
    ends_at: datetime | None = None,
) -> Reassessment:
    """Conservative descriptive stop signal, never inferred elasticity or causal lift."""
    end = min(day_start(now), ends_at or day_start(now))
    after_start = started
    before = observe_surface(
        merch,
        start=started - timedelta(days=4),
        end=started,
        surface=surface,
        product_ids=product_ids,
    )
    after = observe_surface(
        merch, start=after_start, end=end, surface=surface, product_ids=product_ids
    )
    common = set(before.queries) & set(after.queries)
    if surface == "search" and common:
        before = observe_surface(
            merch,
            start=before.start_at,
            end=before.end_at,
            surface=surface,
            product_ids=product_ids,
            queries=common,
        )
        after = observe_surface(
            merch,
            start=after.start_at,
            end=after.end_at,
            surface=surface,
            product_ids=product_ids,
            queries=common,
        )
    enough = (
        before.enough
        and after.enough
        and before.orders >= 20
        and after.orders >= 20
        and (surface != "search" or bool(common))
    )
    poor = bool(
        enough
        and before.contribution_profit_minor > 0
        and after.contribution_profit_minor * before.exposures * 4
        < before.contribution_profit_minor * after.exposures * 3
    )
    return Reassessment(
        classification="observed_poor_performance"
        if poor
        else "no_stop_signal"
        if enough
        else "insufficient",
        reason="OBSERVED_PROFIT_PER_EXPOSURE_DOWN_OVER_25_PERCENT_NOT_CAUSAL"
        if poor
        else "NO_OBSERVED_STOP_SIGNAL_NOT_PROOF_OF_BENEFIT"
        if enough
        else "WAIT_FOR_TWO_COMPLETE_DAYS_200_EXPOSURES_20_ORDERS_PER_MATCHED_WINDOW",
        before=before,
        after=after,
        review_required=poor,
    )
