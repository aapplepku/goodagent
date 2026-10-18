"""Authored observation fixtures for contract/path tests, never effectiveness evidence."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from open_commerce.controller.models import GoalCreateRequest, GoalRecord
from open_commerce.controller.service import ControllerService
from open_commerce.core.merchandising import MerchandisingConstraints, unit_economics
from open_commerce.simulator.merchandising_models import PromotionRedemption, ServingBatch
from open_commerce.simulator.models import DailyMetrics, SimulatorState


def fixture() -> tuple[ControllerService, GoalRecord, SimulatorState]:
    service = ControllerService()
    tenant = uuid4()
    goal = service.create_goal(
        tenant_id=tenant,
        request=GoalCreateRequest(merchandising=MerchandisingConstraints(promotion_cap_minor=5000)),
        idempotency_key="merch",
    )
    state = service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    return service, goal, state


def add_observation(state: SimulatorState) -> None:
    state.metrics.append(
        DailyMetrics(
            metric_date=state.current_time.date(),
            day_index=0,
            sessions=1000,
            impressions=3000,
            clicks=200,
            carts=100,
            orders=50,
            units_sold=50,
            new_customers=20,
            gross_revenue_minor=50000,
            discounts_minor=0,
            cogs_minor=25000,
            variable_fees_minor=1000,
            ad_spend_minor=0,
            contribution_profit_minor=24000,
            conversion_rate=Decimal("0.05"),
            cac_minor=None,
            contribution_margin_rate=Decimal("0.48"),
            discount_rate=Decimal(0),
            search_attributed_purchases=50,
            ending_inventory_units=10000,
        )
    )


def history(state: SimulatorState, days: int = 4) -> None:
    for day in range(days):
        add_observation(state)
        state.metrics[-1].metric_date = (state.start_at + timedelta(days=day)).date()
        state.metrics[-1].day_index = day
    state.current_time = state.start_at + timedelta(days=days)


def batch(
    state: SimulatorState,
    product: str,
    *,
    day: int,
    exposures: int = 200,
    clicks: int = 40,
    orders: int = 0,
    anchor: str | None = None,
    displayed: bool = True,
    version: int = 0,
    unit_profit: int = 500,
) -> None:
    assert state.merchandising is not None
    merch = state.merchandising
    date = state.start_at + timedelta(days=day)
    p = next(p for p in state.products if p.id == product)
    key = f"fixture:{day}:{product}:{anchor}:{version}:{displayed}"
    row = ServingBatch(
        day=date.date().isoformat(),
        surface="product_detail" if anchor else "search",
        query=None if anchor else str(p.attributes["product_type"]),
        anchor_product_id=anchor,
        policy_version=version if anchor else None,
        ranking_version="authored-test-fixture",
        embedding_model="none",
        product_ids=[product] if displayed else [],
        relevance={product: Decimal(1)} if displayed else {},
        constraint_matches={product: {"available": True}} if displayed else {},
        eligible_sessions=exposures,
        clicks={product: clicks} if displayed else {},
        recommendation_strategy="alternatives" if anchor else None,
    )
    for n in range(orders):
        order = f"{key}:{n}"
        row.order_keys.append(order)
        merch.redemptions[order] = PromotionRedemption(
            order_key=order,
            request_hash="authored-fixture",
            product_id=product,
            variant_id=p.variants[0].id,
            occurred_at=date,
            status="redeemed",
            reason="fixture",
            discount_id=None,
            economics=unit_economics(
                reference_price_minor=1000,
                base_price_minor=1000,
                effective_price_minor=1000,
                cost_minor=1000 - unit_profit,
                fee_rate=Decimal(0),
                promotion_applied=False,
            ),
        )
    merch.serving_log[key] = row
