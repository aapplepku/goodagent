"""Merchandising compiler, provider versions, policy and evidence boundaries."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.executor import _dispatch
from open_commerce.controller.models import (
    ControllerActionRecord,
    ControllerPolicyConfig,
    GoalCreateRequest,
    GoalRecord,
    IntentDraft,
)
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.controller.service import ControllerService
from open_commerce.core.enums import ActionType, Capability, ExecutionStatus, PolicyOutcome
from open_commerce.core.merchandising import MerchandisingConstraints, RecommendationControls
from open_commerce.core.money import Money
from open_commerce.core.providers import ExecutionRef, SetRecommendationPolicyCommand
from open_commerce.core.types import JsonObject, TimeWindow
from open_commerce.simulator.merchandising_economics import investigate_variant
from open_commerce.simulator.merchandising_models import PriceRevision
from open_commerce.simulator.models import (
    DiscountState,
    ProductState,
    ProductVariantState,
    SimulatorState,
)
from open_commerce.simulator.provider import SimulatorProvider


def fixture() -> tuple[GoalRecord, SimulatorState, ProductState, ProductVariantState]:
    tenant = uuid4()
    service = ControllerService()
    goal = service.create_goal(
        tenant_id=tenant,
        request=GoalCreateRequest(merchandising=MerchandisingConstraints(promotion_cap_minor=1000)),
        idempotency_key="merch",
    )
    state = service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    assert state.merchandising is not None
    product = state.products[0]
    product.low_stock = False
    variant = product.variants[0]
    variant.price_minor = variant.original_price_minor = 1000
    variant.cost_minor = 400
    variant.inventory = 100
    variant.available = True
    product.variants = [variant]
    state.products = [product]
    state.merchandising.prices = {variant.id: PriceRevision(reference_price_minor=1000)}
    state.merchandising.compatibility = []
    return goal, state, product, variant


def compile_context(
    goal: GoalRecord, state: SimulatorState, action_type: ActionType, parameters: JsonObject
) -> PolicyContext:
    draft = IntentDraft(
        id=uuid4(),
        tenant_id=state.tenant_id,
        run_id=uuid4(),
        hypothesis_id=uuid4(),
        opportunity_ids=[],
        action_type=action_type,
        rationale="Bounded simulator experiment",
        parameters=parameters,
        confidence=Decimal("0.70"),
    )
    action = ActionCompiler().compile_draft(goal=goal.spec, state=state, draft=draft)
    return PolicyContext(
        goal=goal.spec,
        policy=ControllerPolicyConfig(
            tenant_id=state.tenant_id,
            updated_at=state.current_time,
            allowed_action_types=set(ActionType),
        ),
        action=action,
        capabilities=set(Capability),
        sample_size=0,
        data_age_minutes={"catalog": 0, "inventory": 0},
        budget_remaining=Money(amount_minor=0, currency="USD"),
        actions_in_run=1,
        active_target_keys=set(),
        recent_target_keys=set(),
        decision_time=state.current_time,
    )


def record_for(context: PolicyContext) -> ControllerActionRecord:
    return ControllerActionRecord(
        action=context.action,
        action_version_hash=context.action.version_hash,
        policy_decision=PolicyEngine().decide(context),
        created_at=context.action.intent.proposed_at,
        updated_at=context.action.intent.proposed_at,
    )


async def test_price_action_dispatch_reconciliation_replay_and_monotonic_rollback() -> None:
    goal, state, product, variant = fixture()
    assert state.merchandising is not None
    context = compile_context(
        goal,
        state,
        ActionType.SET_VARIANT_PRICE,
        {
            "product_id": product.id,
            "variant_id": variant.id,
            "new_price_minor": 950,
            "expected_version": 0,
            "duration_hours": 48,
        },
    )
    assert PolicyEngine().decide(context).outcome == PolicyOutcome.REQUIRE_APPROVAL
    assert context.action.expected_impact.interval is None
    provider = SimulatorProvider(state)
    record = record_for(context)
    result = await _dispatch(provider=provider, record=record)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert variant.price_minor == 950
    assert state.merchandising.prices[variant.id].reference_price_minor == 1000
    assert state.merchandising.prices[variant.id].version == 1
    assert await _dispatch(provider=provider, record=record) == result
    reconciled = await provider.reconcile(
        ExecutionRef(
            tenant_id=state.tenant_id,
            execution_id=UUID(result.provider_request_id),
            action_id=record.action.id,
            provider=record.action.target_provider,
        )
    )
    assert reconciled.status == ExecutionStatus.RECONCILED
    rolled = await provider.rollback(
        execution_id=UUID(result.provider_request_id), idempotency_key="undo"
    )
    assert rolled.status == ExecutionStatus.SUCCEEDED
    assert variant.price_minor == 1000
    assert state.merchandising.prices[variant.id].version == 2
    assert state.merchandising.prices[variant.id].cumulative_change_minor == 50
    assert len(state.command_history) == 2


@pytest.mark.parametrize(
    ("base", "promotion", "reason"),
    [
        (900, "0.10", "COMBINED_EFFECTIVE_DISCOUNT_LIMIT"),
        (1000, "0.10", None),
    ],
)
def test_combined_price_and_promotion_not_checked_in_isolation(
    base: int,
    promotion: str,
    reason: str | None,
) -> None:
    goal, state, product, variant = fixture()
    variant.price_minor = base
    context = compile_context(
        goal,
        state,
        ActionType.CREATE_DISCOUNT,
        {
            "product_id": product.id,
            "discount_percentage": promotion,
            "duration_hours": 48,
            "projected_margin_rate": "0.999",
            "known_cost_basis": False,
        },
    )
    assert (PolicyEngine().decide(context).outcome == PolicyOutcome.DENY) == (reason is not None)
    assert context.action.normalized_parameters["known_cost_basis"] is True
    if reason:
        errors = context.action.normalized_parameters["merchandising_errors"]
        assert isinstance(errors, list) and reason in errors


def test_stale_price_and_cumulative_cooldown_are_independent_bounds() -> None:
    goal, state, product, variant = fixture()
    assert state.merchandising is not None
    revision = state.merchandising.prices[variant.id]
    revision.version = 1
    revision.last_changed_at = state.current_time
    revision.cumulative_change_minor = 150
    context = compile_context(
        goal,
        state,
        ActionType.SET_VARIANT_PRICE,
        {
            "product_id": product.id,
            "variant_id": variant.id,
            "new_price_minor": 950,
            "expected_version": 0,
            "duration_hours": 48,
        },
    )
    errors = context.action.normalized_parameters["merchandising_errors"]
    assert isinstance(errors, list)
    assert {"STALE_PRICE_VERSION", "PRICE_COOLDOWN", "CUMULATIVE_PRICE_CHANGE_LIMIT"} <= set(errors)


async def test_recommendation_policy_dispatch_replay_stale_and_rollback() -> None:
    goal, state, _, _ = fixture()
    assert state.merchandising is not None
    context = compile_context(
        goal,
        state,
        ActionType.SET_RECOMMENDATION_POLICY,
        {"controls": {"inventory_priority": "0.10"}, "expected_version": 0, "duration_hours": 48},
    )
    assert PolicyEngine().decide(context).outcome == PolicyOutcome.REQUIRE_APPROVAL
    provider = SimulatorProvider(state)
    result = await _dispatch(provider=provider, record=record_for(context))
    assert result.status == ExecutionStatus.SUCCEEDED
    assert state.merchandising.recommendation_policy.version == 1
    assert await _dispatch(provider=provider, record=record_for(context)) == result
    stale = await provider.set_recommendation_policy(
        SetRecommendationPolicyCommand(
            tenant_id=state.tenant_id,
            idempotency_key="stale",
            expected_version=0,
            controls=RecommendationControls(),
            window=TimeWindow(
                start_at=state.current_time, end_at=state.current_time + timedelta(days=2)
            ),
        )
    )
    assert stale.status == ExecutionStatus.FAILED
    rolled = await provider.rollback(
        execution_id=UUID(result.provider_request_id), idempotency_key="undo"
    )
    assert rolled.status == ExecutionStatus.SUCCEEDED
    assert state.merchandising.recommendation_policy.version == 2
    assert state.merchandising.recommendation_policy.controls.inventory_priority == 0
    assert len(state.command_history) == 2


def test_unsupported_controls_and_invented_complements_rejected() -> None:
    goal, state, _, _ = fixture()
    with pytest.raises(ValidationError):
        RecommendationControls.model_validate({"personalized": True})
    context = compile_context(
        goal,
        state,
        ActionType.SET_RECOMMENDATION_POLICY,
        {"controls": {"strategy": "complements"}, "expected_version": 0, "duration_hours": 48},
    )
    errors = context.action.normalized_parameters["merchandising_errors"]
    assert isinstance(errors, list) and "NO_EXPLICIT_COMPATIBILITY_EVIDENCE" in errors
    assert PolicyEngine().decide(context).outcome == PolicyOutcome.DENY


async def test_disable_is_real_not_a_noop() -> None:
    goal, state, product, _ = fixture()
    state.discounts = [
        DiscountState(
            id="existing",
            code=None,
            discount_kind="percentage",
            value=Decimal("0.10"),
            starts_at=state.current_time,
            ends_at=state.current_time + timedelta(days=3),
            product_ids=[product.id],
            created_by_command="fixture",
        )
    ]
    context = compile_context(
        goal, state, ActionType.DISABLE_DISCOUNT, {"provider_discount_id": "existing"}
    )
    result = await _dispatch(provider=SimulatorProvider(state), record=record_for(context))
    assert result.status == ExecutionStatus.SUCCEEDED
    assert state.discounts[0].active is False
    assert state.command_history[0].action_type == "disable_discount"


def test_tools_bound_candidates_and_do_not_expose_hidden_simulator_state() -> None:
    _, state, product, variant = fixture()
    report = investigate_variant(
        state, tenant_id=state.tenant_id, product_id=product.id, variant_id=variant.id
    )
    payload = report.model_dump_json()
    assert all(
        word not in payload
        for word in (
            "price_sensitivity",
            "discount_elasticity",
            "customer_segments",
            "seed",
            "future",
        )
    )
    assert len(report.candidates) <= 9
    assert any(
        c.base_price_minor == variant.price_minor and c.promotion_rate == 0
        for c in report.candidates
    )
    assert all(
        c.predicted_store_profit_minor is None and c.predicted_orders is None
        for c in report.candidates
    )
    with pytest.raises(ValueError, match="tenant"):
        investigate_variant(state, tenant_id=uuid4(), product_id=product.id, variant_id=variant.id)


def test_no_discounts_and_ads_cannot_be_reintroduced_by_forged_goal() -> None:
    goal, state, product, _ = fixture()
    assert state.merchandising is not None
    no_discounts = MerchandisingConstraints(
        max_effective_discount=Decimal(0), promotion_cap_minor=1000
    )
    goal.spec.merchandising = no_discounts
    state.merchandising.constraints = no_discounts
    context = compile_context(
        goal,
        state,
        ActionType.CREATE_DISCOUNT,
        {"product_id": product.id, "discount_percentage": "0.05", "duration_hours": 48},
    )
    assert PolicyEngine().decide(context).outcome == PolicyOutcome.DENY
    campaign = state.campaigns[0]
    context = compile_context(
        goal,
        state,
        ActionType.SET_CAMPAIGN_BUDGET,
        {"campaign_id": campaign.id, "new_budget_minor": 1},
    )
    forged = goal.spec.model_copy(update={"allowed_action_types": set(ActionType)})
    assert (
        "merchandising_bounds" in PolicyEngine().decide(replace(context, goal=forged)).reason_codes
    )
