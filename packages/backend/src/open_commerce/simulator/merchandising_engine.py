"""Fixed-traffic simulation through the actual shared search and PDP serving code."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from open_commerce.core.merchandising import RecommendationControls, unit_economics
from open_commerce.core.types import canonical_hash
from open_commerce.search.merchandising import (
    MERCHANDISING_RANKING_VERSION,
    serve_pdp,
    serve_search,
)
from open_commerce.search.models import (
    ProductFilters,
    ProductSearchIndex,
    RankedCandidate,
    RecommendationRequest,
    RecommendationResponse,
    SearchRequest,
)
from open_commerce.simulator.demand import (
    click_probability,
    effective_price_minor,
    purchase_probability,
    utility,
)
from open_commerce.simulator.engine import (
    _choose_category,
    _choose_segment,
    _seasonality,
)
from open_commerce.simulator.merchandising import redeem_order
from open_commerce.simulator.merchandising_catalog import FAMILIES
from open_commerce.simulator.merchandising_models import (
    MERCHANDISING_ENGINE_VERSION,
    ProductOutcomes,
    ServingBatch,
)
from open_commerce.simulator.models import (
    CustomerSegment,
    DailyMetrics,
    DiscountState,
    ProductState,
    ProductVariantState,
    SimulatorState,
)
from open_commerce.simulator.randomness import KeyedExogenous
from open_commerce.simulator.scenarios import get_scenario


def expire_controls(state: SimulatorState, *, tenant_id: UUID) -> None:
    if state.tenant_id != tenant_id or state.merchandising is None:
        raise ValueError("tenant-owned merchandising profile required")
    merch = state.merchandising
    variants = {v.id: v for p in state.products for v in p.variants}
    for variant_id, revision in merch.prices.items():
        if revision.expires_at is not None and revision.expires_at <= state.current_time:
            if revision.revert_price_minor is None:
                raise ValueError("price expiry missing rollback price")
            variants[variant_id].price_minor = revision.revert_price_minor
            revision.version += 1
            revision.last_changed_at = state.current_time
            revision.expires_at = None
            revision.revert_price_minor = None
            revision.command_key = None
    policy = merch.recommendation_policy
    if policy.ends_at is not None and policy.ends_at <= state.current_time:
        policy.version += 1
        policy.controls = RecommendationControls(
            minimum_relevance=merch.constraints.minimum_relevance
        )
        policy.starts_at = policy.ends_at = None
        policy.command_key = None


async def simulate_merchandising_day(
    state: SimulatorState, *, tenant_id: UUID, index: ProductSearchIndex, embedding_model: str
) -> None:
    """One daily catalog snapshot, live stock checks, matched incoming opportunities.

    Each session can check out once. An alternative can replace the anchor; an
    explicitly compatible complement can add one unit after the anchor purchase.
    A declined add-on does not undo the anchor. Neither acquires another shopper.
    """
    if (
        state.tenant_id != tenant_id
        or state.merchandising is None
        or state.engine_version != MERCHANDISING_ENGINE_VERSION
    ):
        raise ValueError("tenant-owned merchandising engine required")
    expire_controls(state, tenant_id=tenant_id)
    merch = state.merchandising
    definition = get_scenario(state.scenario_id)
    economics = definition.economics
    day = state.current_time.date().isoformat()
    exogenous = KeyedExogenous(state.seed, day, namespace="merchandising-v1")
    products = {p.id: p for p in state.products}
    before = {key: value.model_copy(deep=True) for key, value in merch.product_outcomes.items()}
    sessions = impressions = clicks = carts = orders = units = new_customers = 0
    gross = discounts = cogs = fees = contribution = search_orders = 0
    cache: dict[str, list[RankedCandidate]] = {}
    pdp_cache: dict[str, RecommendationResponse] = {}

    def exposed(
        surface: Literal["search", "product_detail"],
        results: list[RankedCandidate],
        *,
        query: str | None = None,
        anchor: str | None = None,
    ) -> tuple[list[RankedCandidate], ServingBatch]:
        nonlocal impressions
        live = [
            r
            for r in results
            if any(v.available and v.inventory > 0 for v in products[r.product_id].variants)
        ]
        entry = ServingBatch(
            day=day,
            surface=surface,
            query=query,
            anchor_product_id=anchor,
            policy_version=merch.recommendation_policy.version
            if surface == "product_detail"
            else None,
            ranking_version=MERCHANDISING_RANKING_VERSION,
            embedding_model=embedding_model,
            product_ids=[r.product_id for r in live],
            relevance={r.product_id: r.score_components.relevance for r in live},
            constraint_matches={r.product_id: r.constraint_matches for r in live},
            recommendation_strategy=merch.recommendation_policy.controls.strategy
            if surface == "product_detail"
            else None,
        )
        key = canonical_hash(entry)
        batch = merch.serving_log.setdefault(key, entry)
        batch.eligible_sessions += 1
        impressions += len(live)
        for result in live:
            observed = merch.product_outcomes.setdefault(result.product_id, ProductOutcomes())
            if surface == "search":
                observed.search_exposures += 1
            else:
                observed.recommendation_exposures += 1
        return live, batch

    for channel in state.traffic_channels:
        # Traffic is a fixed external input, not funded by the merchandising goal.
        count = max(
            0,
            int(
                channel.base_sessions
                * (0.97 + 0.06 * exogenous.draw("traffic", channel=channel.id))
            ),
        )
        for session_id in range(count):
            sessions += 1

            def draw(
                purpose: str,
                product: str = "",
                *,
                channel_id: str = channel.id,
                session_index: int = session_id,
            ) -> Decimal:
                return Decimal(
                    str(
                        exogenous.draw(
                            purpose, channel=channel_id, session=session_index, product=product
                        )
                    )
                )

            segment = _choose_segment(state.customer_segments, float(draw("segment")))
            new_customer = draw("new_customer") < segment.new_customer_probability
            category = _choose_category(segment, float(draw("category")))
            families = [family for family in FAMILIES if family.category == category]
            family = families[min(int(draw("query_family") * len(families)), len(families) - 1)]
            query = f"{category} {family.title}"
            if query not in cache:
                response = await serve_search(
                    state,
                    tenant_id=tenant_id,
                    request=SearchRequest(
                        query=query, filters=ProductFilters(category=category), top_k=5
                    ),
                    index=index,
                    embedding_model=embedding_model,
                )
                cache[query] = response.results
            displayed, batch = exposed("search", cache[query], query=query)

            def offer(
                result: RankedCandidate,
                *,
                shopper: CustomerSegment = segment,
                is_new: bool = new_customer,
            ) -> tuple[ProductState, ProductVariantState, DiscountState | None, Decimal]:
                product = products[result.product_id]
                variant = min(
                    (v for v in product.variants if v.available and v.inventory > 0),
                    key=lambda v: (v.price_minor, v.id),
                )
                eligible = [
                    d
                    for d in state.discounts
                    if d.applies_to(product, state.current_time)
                    and (not d.new_customers_only or is_new)
                    and variant.price_minor >= (d.minimum_subtotal_minor or 0)
                    and not product.low_stock
                    and variant.inventory > 5
                ]

                def affordable(discount: DiscountState) -> bool:
                    value = unit_economics(
                        reference_price_minor=merch.prices[variant.id].reference_price_minor,
                        base_price_minor=variant.price_minor,
                        effective_price_minor=effective_price_minor(
                            variant.price_minor, discount.discount_kind, discount.value
                        ),
                        cost_minor=variant.cost_minor,
                        fee_rate=economics.payment_fee_rate,
                        promotion_applied=True,
                    ).promotion_redemption_value_minor
                    return (
                        merch.promotion_spent_minor + value <= merch.constraints.promotion_cap_minor
                        and (
                            discount.maximum_cost_minor is None
                            or discount.spent_minor + value <= discount.maximum_cost_minor
                        )
                    )

                # Stop offering an already exhausted promotion before a shopper
                # decides. Checkout still atomically rechecks and never silently
                # substitutes a higher price after a concurrent cap conflict.
                eligible = [discount for discount in eligible if affordable(discount)]
                discount = (
                    min(
                        eligible,
                        key=lambda d: (
                            effective_price_minor(variant.price_minor, d.discount_kind, d.value),
                            d.id,
                        ),
                    )
                    if eligible
                    else None
                )
                effective = (
                    effective_price_minor(
                        variant.price_minor, discount.discount_kind, discount.value
                    )
                    if discount
                    else variant.price_minor
                )
                score = utility(
                    relevance=result.score_components.relevance,
                    segment=shopper,
                    product_quality=product.quality_score,
                    effective_price_minor_value=effective,
                    reference_price_minor=merch.prices[variant.id].reference_price_minor,
                    promotion_lift=economics.promotion_urgency_lift if discount else Decimal(0),
                    personalization_affinity=shopper.category_affinities.get(
                        product.category, Decimal(0)
                    )
                    * Decimal("0.35"),
                    seasonality=_seasonality(state.day, economics.seasonality_amplitude),
                    noise=draw("noise", product.id) * Decimal("0.32") - Decimal("0.16"),
                )
                return product, variant, discount, score

            anchor_result = None
            for position, result in enumerate(displayed, start=1):
                product, _, _, score = offer(result)
                if draw("search_click", product.id) < click_probability(
                    utility_value=score, position=position, economics=economics
                ):
                    anchor_result = result
                    break
            if anchor_result is None:
                continue
            clicks += 1
            batch.clicks[anchor_result.product_id] = (
                batch.clicks.get(anchor_result.product_id, 0) + 1
            )
            merch.product_outcomes[anchor_result.product_id].clicks += 1
            if anchor_result.product_id not in pdp_cache:
                response_pdp = serve_pdp(
                    state,
                    tenant_id=tenant_id,
                    request=RecommendationRequest(anchor_product_ids=[anchor_result.product_id]),
                )
                pdp_cache[anchor_result.product_id] = response_pdp
            pdp_response = pdp_cache[anchor_result.product_id]
            panel, pdp_batch = exposed(
                "product_detail",
                pdp_response.results,
                anchor=anchor_result.product_id,
            )
            selected, selected_batch, selected_surface = anchor_result, batch, "search"
            add_on = None
            for position, result in enumerate(panel, start=1):
                product, _, _, score = offer(result)
                if draw("pdp_click", product.id) < click_probability(
                    utility_value=score, position=position, economics=economics
                ):
                    if pdp_response.strategy == "complements":
                        add_on = result
                    else:
                        selected, selected_batch, selected_surface = (
                            result,
                            pdp_batch,
                            "product_detail",
                        )
                    clicks += 1
                    pdp_batch.clicks[product.id] = pdp_batch.clicks.get(product.id, 0) + 1
                    merch.product_outcomes[product.id].clicks += 1
                    break
            product, variant, discount, score = offer(selected)
            if draw("cart", product.id) >= economics.cart_rate:
                continue
            carts += 1
            selected_batch.carts[product.id] = selected_batch.carts.get(product.id, 0) + 1
            merch.product_outcomes[product.id].carts += 1
            probability = purchase_probability(
                utility_value=score,
                economics=economics,
                availability=Decimal(1),
                campaign_quality_value=Decimal(0),
            )
            if draw("purchase", product.id) >= probability:
                continue
            checkout_key = f"merch:{state.generation}:{day}:{channel.id}:{session_id}"
            key = f"{checkout_key}:primary"
            receipt = redeem_order(
                state,
                tenant_id=tenant_id,
                order_key=key,
                product_id=product.id,
                variant_id=variant.id,
                expected_price_version=merch.prices[variant.id].version,
                discount_id=discount.id if discount else None,
                new_customer=new_customer,
            )
            selected_batch.order_keys.append(key)
            if receipt.status != "redeemed":
                continue
            orders += 1
            units += 1
            merch.checkout_lines[checkout_key] = [key]
            new_customers += int(new_customer)
            search_orders += int(selected_surface == "search")
            gross += receipt.economics.base_price_minor
            discounts += receipt.economics.offered_discount_minor
            cogs += receipt.economics.cost_minor
            fees += receipt.economics.variable_fee_minor
            contribution += receipt.economics.contribution_profit_minor
            if add_on is not None:
                product, variant, discount, score = offer(add_on)
                if draw("add_on_cart", product.id) >= economics.cart_rate:
                    continue
                merch.product_outcomes[product.id].carts += 1
                pdp_batch.carts[product.id] = pdp_batch.carts.get(product.id, 0) + 1
                if draw("add_on_purchase", product.id) >= purchase_probability(
                    utility_value=score,
                    economics=economics,
                    availability=Decimal(1),
                    campaign_quality_value=Decimal(0),
                ):
                    continue
                add_on_key = f"{checkout_key}:complement"
                add_on_receipt = redeem_order(
                    state,
                    tenant_id=tenant_id,
                    order_key=add_on_key,
                    product_id=product.id,
                    variant_id=variant.id,
                    expected_price_version=merch.prices[variant.id].version,
                    discount_id=discount.id if discount else None,
                    new_customer=new_customer,
                )
                pdp_batch.order_keys.append(add_on_key)
                if add_on_receipt.status != "redeemed":
                    continue
                merch.checkout_lines[checkout_key].append(add_on_key)
                units += 1
                gross += add_on_receipt.economics.base_price_minor
                discounts += add_on_receipt.economics.offered_discount_minor
                cogs += add_on_receipt.economics.cost_minor
                fees += add_on_receipt.economics.variable_fee_minor
                contribution += add_on_receipt.economics.contribution_profit_minor
    daily = {}
    for product_id, observed in merch.product_outcomes.items():
        baseline = before.get(product_id, ProductOutcomes()).model_dump()
        daily[product_id] = ProductOutcomes.model_validate(
            {key: value - baseline[key] for key, value in observed.model_dump().items()}
        )
    merch.daily_product_outcomes[day] = daily
    state.metrics.append(
        DailyMetrics(
            metric_date=state.current_time.date(),
            day_index=state.day,
            sessions=sessions,
            impressions=impressions,
            clicks=clicks,
            carts=carts,
            orders=orders,
            units_sold=units,
            new_customers=new_customers,
            gross_revenue_minor=gross,
            discounts_minor=discounts,
            cogs_minor=cogs,
            variable_fees_minor=fees,
            ad_spend_minor=0,
            contribution_profit_minor=contribution,
            conversion_rate=Decimal(orders) / sessions if sessions else Decimal(0),
            cac_minor=None,
            contribution_margin_rate=Decimal(contribution) / gross if gross else Decimal(0),
            discount_rate=Decimal(discounts) / gross if gross else Decimal(0),
            search_attributed_purchases=search_orders,
            ending_inventory_units=sum(p.total_inventory for p in state.products),
        )
    )
    state.day += 1
    state.current_time = datetime.combine(
        state.current_time.date() + timedelta(days=1), time.min, UTC
    )
    state.status = "running"
    expire_controls(state, tenant_id=tenant_id)
