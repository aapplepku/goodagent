"""Deterministic simulator engine and aggregate metrics."""

from __future__ import annotations

import math
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from open_commerce.core.types import canonical_hash, ensure_utc
from open_commerce.simulator.catalog import generate_catalog, generate_initial_history
from open_commerce.simulator.demand import (
    campaign_quality,
    campaign_sessions,
    click_probability,
    effective_price_minor,
    purchase_probability,
    utility,
    variable_fee_minor,
)
from open_commerce.simulator.exposure import DefaultExposurePolicy, ExposurePolicy
from open_commerce.simulator.models import (
    ENGINE_VERSION,
    PAIRED_ENGINE_VERSION,
    BaselineComparisonResponse,
    CampaignSummary,
    CatalogSummary,
    CustomerSegment,
    DailyMetrics,
    DiscountState,
    Exposure,
    MetricTotals,
    ProductState,
    ProductVariantState,
    ScenarioDefinition,
    SimulatorEvent,
    SimulatorSnapshot,
    SimulatorState,
    SimulatorStateResponse,
)
from open_commerce.simulator.randomness import KeyedExogenous, RandomStreams


def create_initial_state(
    *,
    definition: ScenarioDefinition,
    tenant_id: UUID,
    seed: int | None = None,
    instance_id: UUID | None = None,
    paired_exogenous: bool = False,
) -> SimulatorState:
    """Create deterministic initial simulator state for a tenant."""

    resolved_seed = definition.seed if seed is None else seed
    products = generate_catalog(definition, resolved_seed)
    campaigns = [campaign.model_copy(deep=True) for campaign in definition.campaigns]
    history = generate_initial_history(definition, products, campaigns, resolved_seed)
    state = SimulatorState(
        id=instance_id or uuid4(),
        tenant_id=tenant_id,
        scenario_id=definition.id,
        scenario_version=definition.version,
        engine_version=PAIRED_ENGINE_VERSION if paired_exogenous else ENGINE_VERSION,
        seed=resolved_seed,
        current_time=definition.start_at,
        start_at=definition.start_at,
        day=0,
        status="created",
        products=products,
        customer_segments=[
            segment.model_copy(deep=True) for segment in definition.customer_segments
        ],
        traffic_channels=[channel.model_copy(deep=True) for channel in definition.traffic_channels],
        campaigns=campaigns,
        metrics=history,
    )
    _append_snapshot(state, label="initial")
    return state


def summarize_state(state: SimulatorState) -> SimulatorStateResponse:
    """Return a compact public state response."""

    from open_commerce.simulator.merchandising_models import MerchandisingSummary

    merch = state.merchandising
    summary = (
        MerchandisingSummary(
            promotion_cap_minor=merch.constraints.promotion_cap_minor,
            promotion_redeemed_value_minor=merch.promotion_spent_minor,
            promotion_remaining_minor=max(
                0, merch.constraints.promotion_cap_minor - merch.promotion_spent_minor
            ),
            recommendation_policy_version=merch.recommendation_policy.version,
            recommendation_strategy=merch.recommendation_policy.controls.strategy,
            serving_batches=len(merch.serving_log),
            recorded_checkouts=len(merch.checkout_lines),
            net_revenue_minor=sum(o.net_revenue_minor for o in merch.product_outcomes.values()),
            contribution_profit_minor=sum(
                o.contribution_profit_minor for o in merch.product_outcomes.values()
            ),
        )
        if merch
        else None
    )

    return SimulatorStateResponse(
        id=state.id,
        tenant_id=state.tenant_id,
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        engine_version=state.engine_version,
        seed=state.seed,
        current_time=state.current_time,
        start_at=state.start_at,
        day=state.day,
        status=state.status,
        state_hash=state.state_hash,
        catalog=summarize_catalog(state.products),
        campaigns=[
            CampaignSummary(
                id=campaign.id,
                name=campaign.name,
                channel_id=campaign.channel_id,
                daily_budget_minor=campaign.daily_budget_minor,
                active=campaign.active,
            )
            for campaign in state.campaigns
        ],
        active_discounts=sum(1 for discount in state.discounts if discount.active),
        active_search_boosts=sum(1 for boost in state.search_boosts if boost.active),
        latest_metrics=latest_runtime_metric(state),
        command_count=len(state.command_history),
        merchandising=summary,
    )


def summarize_catalog(products: list[ProductState]) -> CatalogSummary:
    """Summarize simulator catalog state."""

    return CatalogSummary(
        product_count=len(products),
        variant_count=sum(len(product.variants) for product in products),
        inventory_units=sum(product.total_inventory for product in products),
        cold_start_products=sum(1 for product in products if product.cold_start),
        excess_inventory_products=sum(1 for product in products if product.excess_inventory),
        low_stock_products=sum(1 for product in products if product.low_stock),
    )


def latest_runtime_metric(state: SimulatorState) -> DailyMetrics | None:
    """Return the latest non-history metric, if present."""

    runtime_metrics = [metric for metric in state.metrics if not metric.is_history]
    return runtime_metrics[-1] if runtime_metrics else None


def advance_state(
    *,
    state: SimulatorState,
    definition: ScenarioDefinition,
    hours: int,
    exposure_policy: ExposurePolicy | None = None,
) -> SimulatorState:
    """Advance virtual time by hours and run crossed daily steps."""

    if hours <= 0:
        raise ValueError("hours must be positive")
    target = state.current_time + timedelta(hours=hours)
    return run_until_state(
        state=state,
        definition=definition,
        timestamp=target,
        exposure_policy=exposure_policy,
    )


def run_until_state(
    *,
    state: SimulatorState,
    definition: ScenarioDefinition,
    timestamp: datetime,
    exposure_policy: ExposurePolicy | None = None,
) -> SimulatorState:
    """Advance virtual time to a timestamp without wall-clock sleeps."""

    if state.engine_version not in {ENGINE_VERSION, PAIRED_ENGINE_VERSION}:
        raise ValueError("simulator engine changed; retain this run and create a fresh goal")
    target = ensure_utc(timestamp)
    if target < state.current_time:
        raise ValueError("timestamp must be at or after current simulator time")

    policy = exposure_policy or DefaultExposurePolicy()
    current = state.current_time
    while True:
        next_boundary = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=UTC)
        if next_boundary > target:
            break
        _simulate_day(state=state, definition=definition, policy=policy, metric_time=current)
        state.day += 1
        current = next_boundary
        state.current_time = current
        state.status = "running"

    state.current_time = target
    return state


def reset_state(
    *,
    state: SimulatorState,
    definition: ScenarioDefinition,
    seed: int | None = None,
) -> SimulatorState:
    """Reset an existing simulator instance, preserving its ID and tenant."""

    if state.engine_version == PAIRED_ENGINE_VERSION or state.merchandising is not None:
        raise ValueError("paired evaluation fixtures require a new registered case, not demo reset")

    reset = create_initial_state(
        definition=definition,
        tenant_id=state.tenant_id,
        seed=state.seed if seed is None else seed,
        instance_id=state.id,
    )
    reset.generation = state.generation + 1
    reset.command_history = list(state.command_history)
    return reset


def compare_to_baseline(
    *,
    state: SimulatorState,
    definition: ScenarioDefinition,
    exposure_policy: ExposurePolicy | None = None,
) -> BaselineComparisonResponse:
    """Run a no-intervention baseline for the same scenario, seed, and elapsed days."""

    if state.engine_version == PAIRED_ENGINE_VERSION or state.merchandising is not None:
        raise ValueError(
            "paired evaluation requires its matched fixture baseline, not demo defaults"
        )

    baseline = create_initial_state(
        definition=definition, tenant_id=state.tenant_id, seed=state.seed
    )
    baseline.total_spend_limit_minor = state.total_spend_limit_minor
    baseline.daily_spend_limit_minor = state.daily_spend_limit_minor
    if state.day > 0:
        advance_state(
            state=baseline,
            definition=definition,
            hours=state.day * 24,
            exposure_policy=exposure_policy,
        )
    current_totals = totals_for_metrics(state.metrics, include_history=False)
    baseline_totals = totals_for_metrics(baseline.metrics, include_history=False)
    delta = subtract_totals(current_totals, baseline_totals)
    baseline_hash = canonical_hash(
        {
            "scenario_id": definition.id,
            "scenario_version": definition.version,
            "engine_version": ENGINE_VERSION,
            "total_spend_limit_minor": state.total_spend_limit_minor,
            "daily_spend_limit_minor": state.daily_spend_limit_minor,
            "seed": state.seed,
            "days": state.day,
            "totals": baseline_totals,
        }
    )
    return BaselineComparisonResponse(
        instance_id=state.id,
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        seed=state.seed,
        current=current_totals,
        baseline=baseline_totals,
        delta=delta,
        baseline_hash=baseline_hash,
    )


def totals_for_metrics(metrics: list[DailyMetrics], *, include_history: bool) -> MetricTotals:
    """Aggregate daily metrics into release-facing totals."""

    selected = [metric for metric in metrics if include_history or not metric.is_history]
    sessions = sum(metric.sessions for metric in selected)
    orders = sum(metric.orders for metric in selected)
    new_customers = sum(metric.new_customers for metric in selected)
    gross = sum(metric.gross_revenue_minor for metric in selected)
    contribution = sum(metric.contribution_profit_minor for metric in selected)
    ad_spend = sum(metric.ad_spend_minor for metric in selected)
    return MetricTotals(
        days=len(selected),
        sessions=sessions,
        orders=orders,
        units_sold=sum(metric.units_sold for metric in selected),
        new_customers=new_customers,
        gross_revenue_minor=gross,
        discounts_minor=sum(metric.discounts_minor for metric in selected),
        cogs_minor=sum(metric.cogs_minor for metric in selected),
        variable_fees_minor=sum(metric.variable_fees_minor for metric in selected),
        ad_spend_minor=ad_spend,
        contribution_profit_minor=contribution,
        search_attributed_purchases=sum(metric.search_attributed_purchases for metric in selected),
        conversion_rate=_rate(orders, sessions),
        cac_minor=ad_spend // new_customers if new_customers > 0 else None,
        contribution_margin_rate=_rate(contribution, gross),
    )


def subtract_totals(left: MetricTotals, right: MetricTotals) -> MetricTotals:
    """Differences in counts and rates, not a misleading ratio of count differences."""

    sessions = left.sessions - right.sessions
    orders = left.orders - right.orders
    new_customers = left.new_customers - right.new_customers
    gross = left.gross_revenue_minor - right.gross_revenue_minor
    contribution = left.contribution_profit_minor - right.contribution_profit_minor
    ad_spend = left.ad_spend_minor - right.ad_spend_minor
    return MetricTotals(
        days=left.days - right.days,
        sessions=sessions,
        orders=orders,
        units_sold=left.units_sold - right.units_sold,
        new_customers=new_customers,
        gross_revenue_minor=gross,
        discounts_minor=left.discounts_minor - right.discounts_minor,
        cogs_minor=left.cogs_minor - right.cogs_minor,
        variable_fees_minor=left.variable_fees_minor - right.variable_fees_minor,
        ad_spend_minor=ad_spend,
        contribution_profit_minor=contribution,
        search_attributed_purchases=(
            left.search_attributed_purchases - right.search_attributed_purchases
        ),
        conversion_rate=left.conversion_rate - right.conversion_rate,
        cac_minor=left.cac_minor - right.cac_minor
        if left.cac_minor is not None and right.cac_minor is not None
        else None,
        contribution_margin_rate=left.contribution_margin_rate - right.contribution_margin_rate,
    )


def _simulate_day(
    *,
    state: SimulatorState,
    definition: ScenarioDefinition,
    policy: ExposurePolicy,
    metric_time: datetime,
) -> None:
    day_date = metric_time.date()
    rng = RandomStreams(state.seed).rng(f"day:{day_date.isoformat()}")
    customer_rng = RandomStreams(state.seed).rng(f"customers:{day_date.isoformat()}")
    paired = (
        KeyedExogenous(state.seed, day_date.isoformat())
        if state.engine_version == PAIRED_ENGINE_VERSION
        else None
    )
    product_by_id = {product.id: product for product in state.products}
    products_by_category = _products_by_category(state.products)
    rank_cache: dict[tuple[str, str], list[Exposure]] = {}
    spent = sum(
        item.ad_spend_minor + item.discounts_minor for item in state.metrics if not item.is_history
    )
    limits = [
        value
        for value in (
            state.daily_spend_limit_minor,
            max(0, state.total_spend_limit_minor - spent)
            if state.total_spend_limit_minor is not None
            else None,
        )
        if value is not None
    ]
    day_budget = min(limits) if limits else None
    ad_limits = [value for value in (day_budget, state.ad_spend_limit_minor) if value is not None]
    campaign_budgets = _funded_campaign_budgets(state, min(ad_limits) if ad_limits else None)
    source_counts = _traffic_sources(
        state=state,
        day_index=state.day,
        rng_jitter=paired.draw("traffic_jitter") if paired else rng.random(),
        campaign_budgets=campaign_budgets,
    )
    ad_spend = sum(campaign_budgets.values())

    sessions = sum(count for _, _, count, _ in source_counts)
    impressions = 0
    clicks = 0
    carts = 0
    orders = 0
    units_sold = 0
    new_customers = 0
    gross_revenue = 0
    discounts = 0
    cogs = 0
    fees = 0
    search_attributed = 0

    for channel_id, campaign_id, count, quality in source_counts:
        for session_index in range(count):

            def session_draw(
                purpose: str,
                product: str = "",
                *,
                channel: str = channel_id,
                campaign: str | None = campaign_id,
                session: int = session_index,
            ) -> float:
                assert paired is not None
                return paired.draw(
                    purpose,
                    channel=channel,
                    campaign=campaign,
                    session=session,
                    product=product,
                )

            segment = _choose_segment(
                state.customer_segments, session_draw("segment") if paired else rng.random()
            )
            new_customer = (
                Decimal(str(session_draw("new_customer") if paired else customer_rng.random()))
                <= segment.new_customer_probability
            )
            category = _choose_category(
                segment, session_draw("category") if paired else rng.random()
            )
            query = _query_for(category=category, segment=segment, session_index=session_index)
            candidates = products_by_category.get(category, state.products)
            cache_key = (category, query)
            cached = rank_cache.get(cache_key)
            if cached is None:
                exposures = policy.rank(
                    query_text=query,
                    category=category,
                    products=candidates,
                    boosts=state.search_boosts,
                    at=metric_time,
                    limit=5,
                )
                rank_cache[cache_key] = list(exposures)
            else:
                exposures = cached
            impressions += len(exposures)
            for exposure in exposures:
                product = product_by_id[exposure.product_id]
                variant = _select_variant(product)
                if variant is None:
                    continue
                discount = _select_discount(state.discounts, product, metric_time)
                if discount is not None and (
                    (discount.new_customers_only and not new_customer)
                    or (
                        discount.minimum_subtotal_minor is not None
                        and variant.price_minor < discount.minimum_subtotal_minor
                    )
                    or product.low_stock
                    or variant.inventory <= 5
                ):
                    discount = None
                discount_kind = discount.discount_kind if discount is not None else None
                discount_value = discount.value if discount is not None else Decimal("0")
                effective_price = effective_price_minor(
                    variant.price_minor,
                    discount_kind,
                    discount_value,
                )
                unit_discount = variant.price_minor - effective_price
                if discount is not None and (
                    (
                        discount.maximum_cost_minor is not None
                        and discount.spent_minor + unit_discount > discount.maximum_cost_minor
                    )
                    or (
                        discount.spend_cap_for_day_minor is not None
                        and discount.spent_minor + unit_discount > discount.spend_cap_for_day_minor
                    )
                    or (
                        day_budget is not None and ad_spend + discounts + unit_discount > day_budget
                    )
                ):
                    discount = None
                    effective_price = variant.price_minor
                promotion_lift = (
                    definition.economics.promotion_urgency_lift
                    + segment.discount_elasticity * Decimal("0.12")
                    if discount is not None
                    else Decimal("0")
                )
                seasonality = _seasonality(state.day, definition.economics.seasonality_amplitude)
                noise = Decimal(
                    str(
                        round(
                            session_draw("noise", product.id) * 0.32 - 0.16
                            if paired
                            else rng.uniform(-0.16, 0.16),
                            4,
                        )
                    )
                )
                utility_value = utility(
                    relevance=exposure.relevance,
                    segment=segment,
                    product_quality=product.quality_score,
                    effective_price_minor_value=effective_price,
                    reference_price_minor=variant.original_price_minor,
                    promotion_lift=promotion_lift,
                    personalization_affinity=segment.category_affinities[category]
                    * Decimal("0.35"),
                    seasonality=seasonality,
                    noise=noise,
                )
                click_p = click_probability(
                    utility_value=utility_value,
                    position=exposure.position,
                    economics=definition.economics,
                )
                if (
                    Decimal(str(session_draw("click", product.id) if paired else rng.random()))
                    > click_p
                ):
                    continue
                clicks += 1
                if (
                    Decimal(str(session_draw("cart", product.id) if paired else rng.random()))
                    <= definition.economics.cart_rate
                ):
                    carts += 1
                purchase_p = purchase_probability(
                    utility_value=utility_value,
                    economics=definition.economics,
                    availability=Decimal("0.45") if variant.inventory > 3 else Decimal("0.12"),
                    campaign_quality_value=quality,
                )
                if (
                    Decimal(str(session_draw("purchase", product.id) if paired else rng.random()))
                    > purchase_p
                ):
                    break
                gross_revenue += variant.price_minor
                discounts += variant.price_minor - effective_price
                if discount is not None:
                    discount.spent_minor += variant.price_minor - effective_price
                cogs += variant.cost_minor
                fees += variable_fee_minor(effective_price, definition.economics)
                variant.inventory -= 1
                variant.available = variant.inventory > 0
                orders += 1
                units_sold += 1
                if new_customer:
                    new_customers += 1
                channel = next(
                    channel for channel in state.traffic_channels if channel.id == channel_id
                )
                if channel.search_surface:
                    search_attributed += 1
                break

    contribution = gross_revenue - discounts - cogs - fees - ad_spend
    metric = DailyMetrics(
        metric_date=day_date,
        day_index=state.day,
        sessions=sessions,
        impressions=impressions,
        clicks=clicks,
        carts=carts,
        orders=orders,
        units_sold=units_sold,
        new_customers=new_customers,
        gross_revenue_minor=gross_revenue,
        discounts_minor=discounts,
        cogs_minor=cogs,
        variable_fees_minor=fees,
        ad_spend_minor=ad_spend,
        contribution_profit_minor=contribution,
        conversion_rate=_rate(orders, sessions),
        cac_minor=ad_spend // new_customers if new_customers > 0 else None,
        contribution_margin_rate=_rate(contribution, gross_revenue),
        discount_rate=_rate(discounts, gross_revenue),
        search_attributed_purchases=search_attributed,
        ending_inventory_units=sum(product.total_inventory for product in state.products),
    )
    state.metrics.append(metric)
    state.events.extend(_events_for_metric(state=state, metric=metric, occurred_at=metric_time))
    _append_snapshot(state, label=f"day-{state.day + 1}")


def _products_by_category(products: list[ProductState]) -> dict[str, list[ProductState]]:
    grouped: dict[str, list[ProductState]] = {}
    for product in products:
        grouped.setdefault(product.category, []).append(product)
    return grouped


def _traffic_sources(
    *,
    state: SimulatorState,
    day_index: int,
    rng_jitter: float,
    campaign_budgets: dict[str, int] | None = None,
) -> list[tuple[str, str | None, int, Decimal]]:
    sources: list[tuple[str, str | None, int, Decimal]] = []
    for channel in state.traffic_channels:
        if channel.paid:
            continue
        jitter = Decimal(str(0.94 + (rng_jitter * 0.12)))
        seasonal = Decimal("1") + _seasonality(day_index, Decimal("0.05"))
        sessions = int((Decimal(channel.base_sessions) * jitter * seasonal).quantize(Decimal("1")))
        sources.append((channel.id, None, max(0, sessions), Decimal("0")))
    for campaign in state.campaigns:
        if not campaign.active:
            continue
        if campaign_budgets is not None:
            campaign = campaign.model_copy(
                update={"daily_budget_minor": campaign_budgets.get(campaign.id, 0)}
            )
        sessions = campaign_sessions(
            budget_minor=campaign.daily_budget_minor,
            max_reach=campaign.max_reach,
            scale_minor=campaign.scale_minor,
        )
        quality = campaign_quality(campaign)
        sources.append((campaign.channel_id, campaign.id, sessions, quality))
    return sources


def _funded_campaign_budgets(state: SimulatorState, limit: int | None) -> dict[str, int]:
    requested = {item.id: item.daily_budget_minor for item in state.campaigns if item.active}
    total = sum(requested.values())
    if limit is None or total <= limit:
        return requested
    if total == 0:
        return requested
    funded = {key: amount * limit // total for key, amount in requested.items()}
    remainder = limit - sum(funded.values())
    for key in sorted(requested, key=lambda key: (-(requested[key] * limit % total), key))[
        :remainder
    ]:
        funded[key] += 1
    return funded


def _choose_segment(segments: list[CustomerSegment], draw: float) -> CustomerSegment:
    cumulative = Decimal("0")
    target = Decimal(str(draw)) * sum(segment.share for segment in segments)
    for segment in segments:
        cumulative += segment.share
        if target <= cumulative:
            return segment
    return segments[-1]


def _choose_category(segment: CustomerSegment, draw: float) -> str:
    cumulative = Decimal("0")
    target = Decimal(str(draw)) * sum(segment.category_affinities.values())
    for category, weight in sorted(segment.category_affinities.items()):
        cumulative += weight
        if target <= cumulative:
            return category
    return next(reversed(segment.category_affinities))


def _query_for(*, category: str, segment: CustomerSegment, session_index: int) -> str:
    intents = ["daily", "travel", "gift", "performance", "workspace"]
    intent = intents[(session_index + len(segment.id)) % len(intents)]
    if segment.id == "low_intent_browser":
        return f"{category} ideas"
    return f"{category} {intent}"


def _select_variant(product: ProductState) -> ProductVariantState | None:
    available = [
        variant for variant in product.variants if variant.inventory > 0 and variant.available
    ]
    if not available:
        return None
    return min(available, key=lambda variant: (variant.price_minor, variant.id))


def _select_discount(
    discounts: list[DiscountState],
    product: ProductState,
    at: datetime,
) -> DiscountState | None:
    active = [discount for discount in discounts if discount.applies_to(product, at)]
    if not active:
        return None
    return max(active, key=lambda discount: discount.value)


def _seasonality(day_index: int, amplitude: Decimal) -> Decimal:
    value = math.sin((day_index % 365) / 365 * 2 * math.pi)
    return Decimal(str(round(value, 6))) * amplitude


def _rate(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.0001"),
        rounding=ROUND_HALF_UP,
    )


def _events_for_metric(
    *,
    state: SimulatorState,
    metric: DailyMetrics,
    occurred_at: datetime,
) -> list[SimulatorEvent]:
    prefix = f"{state.id}:{metric.metric_date.isoformat()}"
    return [
        SimulatorEvent(
            id=f"{prefix}:sessions",
            occurred_at=occurred_at,
            type="session_started",
            count=metric.sessions,
            metrics={"sessions": metric.sessions},
        ),
        SimulatorEvent(
            id=f"{prefix}:impressions",
            occurred_at=occurred_at,
            type="product_impression",
            count=metric.impressions,
            metrics={"impressions": metric.impressions},
        ),
        SimulatorEvent(
            id=f"{prefix}:clicks",
            occurred_at=occurred_at,
            type="product_clicked",
            count=metric.clicks,
            metrics={"clicks": metric.clicks},
        ),
        SimulatorEvent(
            id=f"{prefix}:purchases",
            occurred_at=occurred_at,
            type="purchase",
            count=metric.orders,
            metrics={
                "orders": metric.orders,
                "gross_revenue_minor": metric.gross_revenue_minor,
            },
        ),
    ]


def _append_snapshot(state: SimulatorState, *, label: str) -> None:
    summary = summarize_state(state).model_dump(mode="json")
    state.snapshots.append(
        SimulatorSnapshot(
            id=f"{state.id}:{label}",
            label=label,
            virtual_time=state.current_time,
            state_hash=state.state_hash,
            summary=summary,
        )
    )
