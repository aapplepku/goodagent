from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from open_commerce.core.enums import Capability, ExecutionStatus
from open_commerce.core.money import Money
from open_commerce.core.providers import (
    CreateDiscountCommand,
    ExecutionRef,
    SetCampaignBudgetCommand,
    SetVariantPricesCommand,
)
from open_commerce.core.types import ProviderRef
from open_commerce.simulator.engine import advance_state, create_initial_state, totals_for_metrics
from open_commerce.simulator.provider import SetSearchBoostCommand, SimulatorProvider
from open_commerce.simulator.scenarios import get_scenario

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_simulator_provider_capabilities_and_idempotent_budget_write() -> None:
    state = create_initial_state(
        definition=get_scenario("acquisition_v1"),
        tenant_id=TENANT_ID,
        seed=42,
    )
    provider = SimulatorProvider(state)

    capabilities = await provider.capabilities()
    assert Capability.WRITE_CAMPAIGN_BUDGET in capabilities.capabilities
    assert Capability.WRITE_INVENTORY not in capabilities.capabilities

    command = SetCampaignBudgetCommand(
        tenant_id=TENANT_ID,
        idempotency_key="budget-1",
        campaign_id="paid_search_intent",
        budget=Money(amount_minor=40_000, currency="USD"),
    )
    first = await provider.set_campaign_budget(command)
    second = await provider.set_campaign_budget(command)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.provider_request_id == first.provider_request_id
    assert len(state.command_history) == 1
    assert (
        next(c for c in state.campaigns if c.id == "paid_search_intent").daily_budget_minor
        == 40_000
    )


@pytest.mark.asyncio
async def test_provider_discount_changes_later_outcomes_and_rolls_back() -> None:
    definition = get_scenario("acquisition_v1")
    baseline = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    treated = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    provider = SimulatorProvider(treated)

    starts_at = treated.current_time
    command = CreateDiscountCommand(
        tenant_id=TENANT_ID,
        idempotency_key="discount-1",
        code="WELCOME10",
        discount_kind="percentage",
        value="0.10",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=30),
        product_scope={"category_paths": ["apparel", "footwear"]},
    )
    result = await provider.create_discount(command)

    assert result.status == ExecutionStatus.SUCCEEDED
    assert len(treated.discounts) == 1

    advance_state(state=baseline, definition=definition, hours=5 * 24)
    advance_state(state=treated, definition=definition, hours=5 * 24)

    assert totals_for_metrics(treated.metrics, include_history=False) != totals_for_metrics(
        baseline.metrics,
        include_history=False,
    )

    execution_id = treated.command_history[0].execution_id
    rollback = await provider.rollback(execution_id=execution_id, idempotency_key="rollback-1")

    assert rollback.status == ExecutionStatus.SUCCEEDED
    assert not treated.discounts[0].active


@pytest.mark.asyncio
async def test_search_boost_command_is_reconciled() -> None:
    definition = get_scenario("search_conversion_v1")
    state = create_initial_state(definition=definition, tenant_id=TENANT_ID, seed=42)
    provider = SimulatorProvider(state)
    command = SetSearchBoostCommand(
        tenant_id=TENANT_ID,
        idempotency_key="boost-1",
        query_text="electronics",
        category="electronics",
        multiplier=Decimal("1.5"),
        starts_at=state.current_time,
        ends_at=state.current_time + timedelta(days=10),
    )

    result = await provider.set_search_boost(command)

    assert result.status == ExecutionStatus.SUCCEEDED
    assert state.search_boosts[0].active


async def test_reversed_price_batch_reconciles_and_rolls_back_once() -> None:
    state = create_initial_state(definition=get_scenario("acquisition_v1"), tenant_id=TENANT_ID)
    variants = [state.products[1].variants[0], state.products[0].variants[0]]
    before = [variant.price_minor for variant in variants]
    command = SetVariantPricesCommand(
        tenant_id=TENANT_ID,
        idempotency_key="reverse-batch",
        changes=[
            {"variant_id": variant.id, "new_price_minor": variant.price_minor + 1}
            for variant in variants
        ],
    )
    provider = SimulatorProvider(state)
    result = await provider.set_variant_prices(command)
    assert result.status == ExecutionStatus.SUCCEEDED
    ref = ExecutionRef(
        tenant_id=TENANT_ID,
        execution_id=state.command_history[0].execution_id,
        action_id=uuid4(),
        provider=ProviderRef(
            provider_type="simulator",
            integration_id=None,
            resource_type="simulator_instance",
            resource_id=str(state.id),
        ),
    )
    assert (await provider.reconcile(ref)).status == ExecutionStatus.RECONCILED
    wrong = await provider.reconcile(ref.model_copy(update={"tenant_id": uuid4()}))
    assert wrong.status == ExecutionStatus.FAILED and wrong.observed_remote_state == {}
    rollback = await provider.rollback(execution_id=ref.execution_id, idempotency_key="rollback")
    assert rollback.status == ExecutionStatus.SUCCEEDED
    assert [variant.price_minor for variant in variants] == before
    assert (
        await provider.rollback(execution_id=ref.execution_id, idempotency_key="rollback-again")
        == rollback
    )
    assert len(state.command_history) == 2
    rollback_ref = ref.model_copy(update={"execution_id": state.command_history[-1].execution_id})
    assert (await provider.reconcile(rollback_ref)).status == ExecutionStatus.RECONCILED


@pytest.mark.parametrize("bad_target", ["missing", "duplicate", "boolean"])
async def test_invalid_price_batch_never_partially_changes_state(bad_target: str) -> None:
    state = create_initial_state(definition=get_scenario("acquisition_v1"), tenant_id=TENANT_ID)
    variant = state.products[0].variants[0]
    before = variant.price_minor
    result = await SimulatorProvider(state).set_variant_prices(
        SetVariantPricesCommand(
            tenant_id=TENANT_ID,
            idempotency_key="invalid-batch",
            changes=[
                {"variant_id": variant.id, "new_price_minor": before + 1},
                {
                    "variant_id": variant.id
                    if bad_target == "duplicate"
                    else state.products[1].variants[0].id
                    if bad_target == "boolean"
                    else "missing",
                    "new_price_minor": True if bad_target == "boolean" else before,
                },
            ],
        )
    )
    assert result.status == ExecutionStatus.FAILED
    assert variant.price_minor == before
    assert state.command_history == []
