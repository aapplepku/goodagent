"""Authored observation fixtures prove decision contracts, not simulator effectiveness."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from scripts.merchandising_decision_fixtures import batch, fixture, history

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.merchandising_candidates import generate_candidates
from open_commerce.controller.merchandising_observation import observe_surface, reassess
from open_commerce.controller.merchandising_planner import (
    MerchandisingPlan,
    plan_merchandising,
    select_merchandising,
)
from open_commerce.controller.models import (
    ControllerActionRecord,
    ControllerPolicyConfig,
    GoalRecord,
)
from open_commerce.controller.service import ControllerService
from open_commerce.core.enums import ActionType, ExecutionStatus, MetricName
from open_commerce.simulator.merchandising_models import (
    PriceRevision,
)
from open_commerce.simulator.models import (
    DiscountState,
    ProductState,
    SearchBoostState,
    SimulatorCommandRecord,
    SimulatorState,
)
from open_commerce.simulator.scenarios import SIMULATOR_CAPABILITIES


def finish(
    service: ControllerService,
    goal: GoalRecord,
    state: SimulatorState,
    *,
    allow: set[ActionType] | None = None,
) -> tuple[MerchandisingPlan, list[ControllerActionRecord]]:
    plan = plan_merchandising(goal=goal.spec, state=state, run_id=uuid4())
    compiled = ActionCompiler().compile_candidates(goal=goal.spec, state=state, drafts=plan.drafts)
    policy = ControllerPolicyConfig(
        tenant_id=state.tenant_id,
        updated_at=state.current_time,
        allowed_action_types=allow if allow is not None else goal.spec.allowed_action_types,
    )
    records = [
        service._record_for_action(
            action=a,
            goal=goal.spec,
            state=state,
            policy=policy,
            capabilities=SIMULATOR_CAPABILITIES,
            actions_in_run=1,
        )
        for a in compiled.actions
    ]
    selected = select_merchandising(plan.decision, records, compiler_rejections=compiled.rejections)
    return plan, selected


def test_surface_orders_exclude_other_panels_future_declines_and_partial_days() -> None:
    _, _, state = fixture()
    history(state)
    p = state.products[0].id
    batch(state, p, day=0, orders=2)
    batch(state, p, day=1, orders=2)
    batch(state, p, day=1, orders=5, anchor=state.products[1].id)
    batch(state, p, day=4, orders=7)
    assert state.merchandising is not None
    observed = observe_surface(
        state.merchandising,
        start=state.start_at,
        end=state.current_time,
        surface="search",
        product_ids={p},
    )
    assert (observed.orders, observed.exposures, len(observed.days)) == (4, 400, 2)
    observed = observe_surface(
        state.merchandising,
        start=state.start_at + timedelta(hours=1),
        end=state.current_time,
        surface="search",
        product_ids={p},
    )
    assert observed.orders == 2
    receipt = next(iter(state.merchandising.redemptions.values()))
    receipt.status = "declined"
    assert (
        observe_surface(
            state.merchandising,
            start=state.start_at,
            end=state.current_time,
            surface="search",
            product_ids={p},
        ).orders
        == 3
    )


def test_pdp_reassessment_counts_whole_checkouts_not_only_alternatives_or_addons() -> None:
    _, _, state = fixture()
    history(state)
    assert state.merchandising is not None
    merch = state.merchandising
    primary, addon = state.products[0].id, state.products[1].id
    batch(state, primary, day=0, orders=2)
    batch(state, addon, day=0, anchor=primary, orders=1)
    batch(state, addon, day=1, anchor=primary, displayed=False)
    primary_keys = [k for k, r in merch.redemptions.items() if r.product_id == primary]
    addon_key = next(k for k, r in merch.redemptions.items() if r.product_id == addon)
    merch.checkout_lines = {
        "checkout-one": [primary_keys[0], addon_key],
        "checkout-two": [primary_keys[1]],
    }
    observed = observe_surface(
        merch, start=state.start_at, end=state.current_time, surface="product_detail"
    )
    assert observed.orders == 2
    assert observed.contribution_profit_minor == 1500
    assert observed.exposures == observed.eligible_sessions == 400
    assert len(observed.days) == 2 and "whole" in observed.population
    with pytest.raises(ValueError, match="unfiltered"):
        observe_surface(
            merch,
            start=state.start_at,
            end=state.current_time,
            surface="product_detail",
            policy_version=1,
        )
    merch.checkout_lines["duplicate"] = [primary_keys[0], primary_keys[0]]
    assert (
        observe_surface(
            merch, start=state.start_at, end=state.current_time, surface="product_detail"
        ).contribution_profit_minor
        == 1500
    )


def test_search_repetition_uses_only_fresh_post_expiry_peer_observations() -> None:
    _, goal, state = fixture()
    history(state, 9)
    family = [p for p in state.products if p.attributes["product_type"] == "hiking_boots"]
    target = family[-1]
    for day in range(5, 9):
        for p in family[:2]:
            batch(state, p.id, day=day, orders=10)
    state.search_boosts.append(
        SearchBoostState(
            id="prior-search",
            query_text=target.category,
            category=target.category,
            product_ids=[target.id],
            multiplier=Decimal("1.10"),
            starts_at=state.start_at,
            ends_at=state.start_at + timedelta(days=8),
            active=False,
            created_by_command="fixture",
        )
    )
    row = next(r for r in generate_candidates(goal.spec, state) if r.key == f"search:{target.id}")
    assert not row.candidate_generated
    assert row.evidence["peer_exposures"] == [200, 200, 0]
    # One complete post-expiry day is not enough despite the older large cohort.
    assert not row.sufficient_observations


def test_all_search_candidates_are_generated_independent_of_input_product_order() -> None:
    service, goal, state = fixture()
    history(state)
    goal.spec.allowed_action_types = {ActionType.NO_OP, ActionType.SET_SEARCH_BOOST}
    family = [p for p in state.products if p.attributes["product_type"] == "hiking_boots"]
    for p in family[:2]:
        for day in range(4):
            batch(state, p.id, day=day, orders=10)
    first = plan_merchandising(goal=goal.spec, state=state, run_id=goal.spec.id)
    assert {d.parameters["product_id"] for d in first.drafts} >= {p.id for p in family[2:]}
    state.products.reverse()
    assert plan_merchandising(goal=goal.spec, state=state, run_id=goal.spec.id) == first
    for p in state.products:
        p.quality_score, p.popularity_score = Decimal(0), Decimal(1)
    state.seed = 777
    assert plan_merchandising(goal=goal.spec, state=state, run_id=goal.spec.id) == first
    plan, selected = finish(service, goal, state)
    assert len(selected) == 1
    rows = plan.decision["candidates"]
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) and r["reason_codes"] for r in rows)
    assert sum(isinstance(r, dict) and bool(r["selected"]) for r in rows) == 1


def monetary_fixture() -> tuple[ControllerService, GoalRecord, SimulatorState, ProductState]:
    service, goal, state = fixture()
    history(state)
    family = [p for p in state.products if p.attributes["product_type"] == "hiking_boots"]
    target = family[-1]
    target.excess_inventory = True
    for day in range(4):
        for peer in family:
            batch(state, peer.id, day=day, orders=0 if peer == target else 10)
    goal.spec.allowed_action_types = {
        ActionType.NO_OP,
        ActionType.SET_VARIANT_PRICE,
        ActionType.CREATE_DISCOUNT,
    }
    return service, goal, state, target


def test_profit_and_clearance_choose_different_scopes_without_fake_profit_score() -> None:
    service, goal, state, target = monetary_fixture()
    plan, selected = finish(service, goal, state)
    assert selected[0].action.intent.type == "set_variant_price"
    goal.spec.objective.metric = MetricName.UNITS_SOLD
    goal.spec.objective.scope = "excess_inventory"
    plan, selected = finish(service, goal, state)
    assert selected[0].action.intent.type == "create_discount"
    assert selected[0].action.intent.product_scope.product_ids == [target.id]
    assert plan.decision["predicted_profit_minor"] is None
    goal.spec.objective.scope = "store"
    goal.spec.objective.metric = MetricName.SEARCH_ATTRIBUTED_PURCHASES
    plan, selected = finish(service, goal, state)
    assert selected == [] and plan.decision["selected_key"] == "unchanged"


def test_complete_policy_rejection_reasons_and_explicit_unchanged() -> None:
    service, goal, state, _ = monetary_fixture()
    plan, selected = finish(service, goal, state, allow={ActionType.NO_OP})
    assert not selected
    rows = plan.decision["candidates"]
    assert isinstance(rows, list)
    rejected = [
        r
        for r in rows
        if isinstance(r, dict) and r["candidate_generated"] and r["key"] != "unchanged"
    ]
    assert rejected and all(r["disposition"] == "policy_rejected" for r in rejected)
    assert all(r["policy_result"] and r["reason_codes"] for r in rejected)
    assert plan.decision["kind"] == "wait"


@pytest.mark.parametrize("version", [0, 2, 9])
def test_pdp_uses_anchor_specific_exposure_and_can_update_after_version_zero(version: int) -> None:
    service, goal, state = fixture()
    history(state)
    assert state.merchandising is not None
    merch = state.merchandising
    merch.recommendation_policy.version = version
    pair = merch.compatibility[0]
    for day in range(4):
        batch(state, pair.complement_product_id, day=day, orders=2)
        batch(
            state,
            pair.complement_product_id,
            day=day,
            anchor=pair.anchor_product_id,
            displayed=False,
            version=version,
        )
        batch(
            state,
            pair.complement_product_id,
            day=day,
            anchor=state.products[-1].id,
            orders=5,
            version=version,
        )
    goal.spec.allowed_action_types = {ActionType.NO_OP, ActionType.SET_RECOMMENDATION_POLICY}
    plan, selected = finish(service, goal, state)
    assert len(selected) == 1
    assert selected[0].action.intent.type == "set_recommendation_policy"
    assert selected[0].action.intent.expected_version == version
    assert selected[0].action.intent.controls.strategy == "complements"
    merch.recommendation_policy.version += 1
    stale = ActionCompiler().compile_candidates(goal=goal.spec, state=state, drafts=plan.drafts)
    errors = stale.actions[0].normalized_parameters["merchandising_errors"]
    assert isinstance(errors, list) and "STALE_RECOMMENDATION_POLICY_VERSION" in errors


def test_insufficient_and_satisfactory_price_evidence_both_wait() -> None:
    _, goal, state, target = monetary_fixture()
    assert state.merchandising is not None
    for row in state.merchandising.serving_log.values():
        if target.id in row.product_ids:
            row.clicks[target.id] = 0
    assert not plan_merchandising(goal=goal.spec, state=state, run_id=uuid4()).drafts
    for day in range(4):
        batch(state, target.id, day=day, orders=12)
    assert not plan_merchandising(goal=goal.spec, state=state, run_id=uuid4()).drafts


def test_outcome_stop_requires_matched_samples_and_never_claims_causality() -> None:
    _, _, state = fixture()
    history(state, 8)
    target = state.products[0].id
    for day in range(8):
        batch(state, target, day=day, orders=10, unit_profit=600 if day < 4 else 300)
    assert state.merchandising is not None
    result = reassess(
        state.merchandising,
        product_ids={target},
        started=state.start_at + timedelta(days=4),
        now=state.current_time,
    )
    assert result.classification == "observed_poor_performance" and not result.causal
    assert result.before.orders == result.after.orders == 40
    result = reassess(
        state.merchandising,
        product_ids={target},
        started=state.start_at + timedelta(days=4),
        now=state.start_at + timedelta(days=5),
    )
    assert result.classification == "insufficient" and not result.review_required


def test_all_families_have_a_reason_even_when_prohibited() -> None:
    _, goal, state = fixture()
    rows = generate_candidates(goal.spec, state)
    assert {r.action_type for r in rows} == set(ActionType) - {ActionType.SET_CAMPAIGN_BUDGET}
    assert all(r.reason_codes for r in rows)
    assert not any(r.candidate_generated and r.action_type != ActionType.NO_OP for r in rows)


def test_candidate_cap_is_explicit_and_does_not_hide_generated_alternatives() -> None:
    _, goal, state = fixture()
    history(state)
    assert state.merchandising is not None
    goal.spec.allowed_action_types = {
        ActionType.NO_OP,
        ActionType.SET_VARIANT_PRICE,
        ActionType.CREATE_DISCOUNT,
    }
    for p in state.products:
        for v in p.variants:
            v.price_minor, v.cost_minor = 10000, 4000
            state.merchandising.prices[v.id] = PriceRevision(reference_price_minor=10000)
        for day in range(4):
            batch(state, p.id, day=day, orders=20 if p.id.endswith("_1") else 0)
    plan = plan_merchandising(goal=goal.spec, state=state, run_id=uuid4())
    assert len(plan.drafts) == 64
    rows = plan.decision["candidates"]
    assert isinstance(rows, list)
    assert any(
        isinstance(r, dict) and "BOUNDED_CANDIDATE_CAP_DEFERRED" in r["reason_codes"] for r in rows
    )
    assert len(rows) > len(plan.drafts)


def test_catalog_diagnostic_bound_still_records_explicit_unchanged_and_permissions() -> None:
    _, goal, state = fixture()
    state.products = [state.products[0].model_copy(deep=True) for _ in range(129)]
    rows = generate_candidates(goal.spec, state)
    unchanged = [r for r in rows if r.key == "unchanged"]
    assert len(unchanged) == 1 and unchanged[0].classification == "unchanged"
    assert all(
        r.allowed_by_goal == (r.action_type in goal.spec.allowed_action_types)
        for r in rows
        if r.key != "unchanged"
    )
    assert not any(r.candidate_generated for r in rows if r.key != "unchanged")


def test_known_bad_active_price_is_a_constraint_stop_without_claiming_observed_harm() -> None:
    _, goal, state = fixture()
    assert state.merchandising is not None
    p = state.products[0]
    variant = p.variants[0]
    variant.price_minor, variant.cost_minor = 9500, 7200
    state.current_time += timedelta(days=4)
    state.merchandising.prices[variant.id] = PriceRevision(
        reference_price_minor=10000,
        version=1,
        cumulative_change_minor=500,
        last_changed_at=state.start_at,
        revert_price_minor=10000,
        expires_at=state.start_at + timedelta(days=7),
    )
    rows = generate_candidates(goal.spec, state)
    candidate = next(r for r in rows if r.key == f"price-reassessment:{variant.id}")
    assert candidate.classification == "constraint_stop"
    assert candidate.candidate_generated and not candidate.sufficient_observations
    assert candidate.evidence["known_bounds_violated"] is True
    assert candidate.predicted_profit_minor is None


def test_price_reassessment_includes_an_active_noncheapest_variant() -> None:
    _, goal, state = fixture()
    assert state.merchandising is not None
    variant = state.products[0].variants[-1]
    variant.price_minor, variant.cost_minor = 19000, 14200
    state.current_time += timedelta(days=4)
    state.merchandising.prices[variant.id] = PriceRevision(
        reference_price_minor=20000,
        version=1,
        cumulative_change_minor=1000,
        last_changed_at=state.start_at,
        revert_price_minor=20000,
        expires_at=state.start_at + timedelta(days=7),
    )
    rows = generate_candidates(goal.spec, state)
    candidates = [r for r in rows if r.key == f"price-reassessment:{variant.id}"]
    assert len(candidates) == 1
    assert candidates[0].classification == "constraint_stop"
    assert candidates[0].candidate_generated


def test_active_promotion_reassessment_distinguishes_insufficient_poor_and_constraint_stop() -> (
    None
):
    _, goal, state = fixture()
    history(state, 8)
    assert state.merchandising is not None
    p = state.products[0]
    for day in range(8):
        batch(state, p.id, day=day, orders=10, unit_profit=600 if day < 4 else 300)
    state.discounts.append(
        DiscountState(
            id="observed-offer",
            code=None,
            discount_kind="percentage",
            value=Decimal("0.05"),
            starts_at=state.start_at + timedelta(days=4),
            ends_at=state.start_at + timedelta(days=14),
            product_ids=[p.id],
            maximum_cost_minor=5000,
            created_by_command="authored-initial-world",
        )
    )
    row = next(
        r for r in generate_candidates(goal.spec, state) if r.key == "disable:observed-offer"
    )
    assert row.classification == "observed_stop" and row.candidate_generated
    assert row.evidence["known_bounds_violated"] is False
    state.current_time = state.start_at + timedelta(days=5)
    row = next(
        r for r in generate_candidates(goal.spec, state) if r.key == "disable:observed-offer"
    )
    assert not row.candidate_generated and not row.sufficient_observations
    # The second variant is intentionally unsafe; inspecting only the cheapest
    # variant would miss this independent deterministic stop reason.
    p.variants[-1].cost_minor = p.variants[-1].price_minor
    row = next(
        r for r in generate_candidates(goal.spec, state) if r.key == "disable:observed-offer"
    )
    assert row.classification == "constraint_stop" and row.candidate_generated


def test_prior_price_blocks_follow_on_promotion_even_on_another_variant() -> None:
    _, goal, state, p = monetary_fixture()
    variant = p.variants[-1]
    revision = PriceRevision(
        reference_price_minor=variant.price_minor,
        version=1,
        last_changed_at=state.start_at,
        expires_at=state.start_at + timedelta(days=2),
        revert_price_minor=variant.price_minor,
    )
    state.command_history.append(
        SimulatorCommandRecord(
            execution_id=uuid4(),
            tenant_id=state.tenant_id,
            instance_id=state.id,
            status=ExecutionStatus.SUCCEEDED,
            action_type="set_variant_price",
            idempotency_key="authored-price",
            created_at=state.start_at,
            before_state={
                "changes": [{"variant_id": variant.id, "price_minor": variant.price_minor}]
            },
            after_state={
                "changes": [
                    {
                        "variant_id": variant.id,
                        "price_minor": variant.price_minor,
                        "price_revision": revision.model_dump(mode="json"),
                    }
                ]
            },
            rollback_state={},
        )
    )
    rows = [
        r
        for r in generate_candidates(goal.spec, state)
        if r.action_type == ActionType.CREATE_DISCOUNT and r.parameters.get("product_id") == p.id
    ]
    assert rows and all(not r.candidate_generated for r in rows)
    assert all(
        "NO_REPEAT_MONETARY_EXPERIMENT_WITHOUT_RESPONSE_IDENTIFICATION" in r.reason_codes
        for r in rows
    )
