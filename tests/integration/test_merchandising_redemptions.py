"""PostgreSQL-serialized promotion checkout, durable retries and rollback."""

import asyncio
from datetime import timedelta
from decimal import Decimal
from typing import TypedDict
from uuid import UUID, uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import DurableSimulatorService, load_state
from open_commerce.simulator.merchandising import redeem_order
from open_commerce.simulator.merchandising_models import PriceRevision
from open_commerce.simulator.models import DiscountState

pytestmark = pytest.mark.integration


class CheckoutArguments(TypedDict):
    tenant_id: UUID
    instance_id: UUID
    product_id: str
    variant_id: str
    expected_price_version: int
    discount_id: str | None


async def test_concurrent_cap_retries_restart_and_transaction_failure(
    integration_settings: Settings,
) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    service = DurableSimulatorService(database)
    try:
        await database.initialize_tenant(tenant)
        goal = await DurableControllerService(database).create_goal(
            tenant_id=tenant,
            request=GoalCreateRequest(
                merchandising=MerchandisingConstraints(promotion_cap_minor=100)
            ),
            idempotency_key="merch-cap",
        )
        instance = goal.simulator_instance_id
        async with database.transaction(tenant, write=True) as session:
            state = await load_state(session, tenant, instance)
            assert state.merchandising is not None
            assert state.metrics == []
            product = state.products[0]
            variant = product.variants[0]
            product.low_stock = False
            variant.price_minor = variant.original_price_minor = 1000
            variant.cost_minor = 400
            variant.inventory = 100
            variant.available = True
            product.variants = [variant]
            state.products = [product]
            state.merchandising.prices = {variant.id: PriceRevision(reference_price_minor=1000)}
            state.discounts = [
                DiscountState(
                    id="test-five-percent",
                    code=None,
                    discount_kind="percentage",
                    value=Decimal("0.05"),
                    starts_at=state.current_time,
                    ends_at=state.current_time + timedelta(days=3),
                    product_ids=[product.id],
                    created_by_command="fixture",
                    maximum_cost_minor=100,
                )
            ]
            await SqlSimulatorRepository(session).save_state(state)
        kwargs: CheckoutArguments = dict(
            tenant_id=tenant,
            instance_id=instance,
            product_id=product.id,
            variant_id=variant.id,
            expected_price_version=0,
            discount_id="test-five-percent",
        )
        with pytest.raises(RuntimeError, match="injected"):
            async with database.transaction(tenant, write=True) as session:
                state = await load_state(session, tenant, instance)
                result = redeem_order(
                    state,
                    tenant_id=tenant,
                    product_id=product.id,
                    variant_id=variant.id,
                    expected_price_version=0,
                    discount_id="test-five-percent",
                    order_key="aborted",
                )
                assert result.status == "redeemed"
                await SqlSimulatorRepository(session).save_state(state)
                raise RuntimeError("injected before commit")
        responses = await asyncio.gather(
            *[
                service.redeem_merchandising_order(**kwargs, order_key=f"concurrent:{i}")
                for i in range(10)
            ]
        )
        assert sum(r.status == "redeemed" for r in responses) == 2
        assert sum(r.reason == "PROMOTION_CAP_EXHAUSTED" for r in responses) == 8
        restarted = DurableSimulatorService(database)
        replay = await restarted.redeem_merchandising_order(**kwargs, order_key="concurrent:0")
        assert replay == responses[0]
        state = await restarted.get_full_state(tenant_id=tenant, instance_id=instance)
        assert state.merchandising is not None
        assert state.merchandising.promotion_spent_minor == 100
        assert "aborted" not in state.merchandising.redemptions
        assert len(state.merchandising.redemptions) == 10
        assert state.products[0].variants[0].inventory == 98
        assert state.merchandising.product_outcomes[product.id].net_revenue_minor == 1900
        assert state.merchandising.product_outcomes[product.id].contribution_profit_minor == 1044
        assert all(b.amount.amount_minor == 0 for b in goal.spec.budgets)
        with pytest.raises(ValueError, match="different request"):
            changed = kwargs.copy()
            changed["expected_price_version"] = 7
            await restarted.redeem_merchandising_order(**changed, order_key="concurrent:0")
        with pytest.raises(ValueError, match="tenant"):
            redeem_order(
                state,
                tenant_id=uuid4(),
                product_id=product.id,
                variant_id=variant.id,
                expected_price_version=0,
                discount_id=None,
                order_key="wrong-tenant",
            )
    finally:
        await database.close()
