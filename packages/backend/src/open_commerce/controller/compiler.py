"""Compile non-executable planner drafts into typed controller actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from open_commerce.controller.facts import safety_facts
from open_commerce.controller.models import IntentDraft
from open_commerce.core.actions import (
    ActionIntent,
    BudgetReservationRequest,
    CompiledAction,
    CreateDiscountIntent,
    CustomerScope,
    DisableDiscountIntent,
    ImpactEstimate,
    NoOpIntent,
    ProductScope,
    SetCampaignBudgetIntent,
    SetRecommendationPolicyIntent,
    SetSearchBoostIntent,
    SetVariantPriceIntent,
    VariantPriceChange,
    build_action_idempotency_key,
)
from open_commerce.core.enums import ActionType, ConstraintOperator, MetricName, RiskTier
from open_commerce.core.goals import GoalSpec
from open_commerce.core.merchandising import RecommendationControls
from open_commerce.core.metrics import ConfidenceInterval
from open_commerce.core.money import Money
from open_commerce.core.policy_types import RiskAssessment, RollbackPlan
from open_commerce.core.types import (
    ActorRef,
    JsonObject,
    Precondition,
    ProviderRef,
    TimeWindow,
    canonical_hash,
)
from open_commerce.simulator.demand import effective_price_minor, variable_fee_minor
from open_commerce.simulator.models import ProductState, SimulatorState
from open_commerce.simulator.scenarios import get_scenario
from open_commerce.simulator.targets import target_state


class CandidateRejectedError(ValueError):
    """A supported draft has no eligible target; other candidates may still be valid."""


@dataclass
class CompilationBatch:
    actions: list[CompiledAction]
    rejections: list[JsonObject]


class ActionCompiler:
    """Compile validated drafts against current simulator state."""

    def compile_drafts(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        drafts: list[IntentDraft],
    ) -> list[CompiledAction]:
        """Compile all deterministic planner drafts."""

        return [self.compile_draft(goal=goal, state=state, draft=draft) for draft in drafts]

    def compile_candidates(
        self, *, goal: GoalSpec, state: SimulatorState, drafts: list[IntentDraft]
    ) -> CompilationBatch:
        """Reject unavailable candidate scopes without hiding malformed/unknown drafts."""
        batch = CompilationBatch(actions=[], rejections=[])
        keys: set[str] = set()
        for draft in drafts:
            try:
                action = self.compile_draft(goal=goal, state=state, draft=draft)
            except CandidateRejectedError as exc:
                batch.rejections.append(
                    {
                        "draft_id": str(draft.id),
                        "action_type": draft.action_type.value,
                        "reason": str(exc),
                    }
                )
                continue
            if action.idempotency_key in keys:
                batch.rejections.append(
                    {
                        "draft_id": str(draft.id),
                        "action_type": draft.action_type.value,
                        "reason": "DUPLICATE_LOGICAL_CANDIDATE",
                    }
                )
                continue
            keys.add(action.idempotency_key)
            batch.actions.append(action)
        return batch

    def compile_draft(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        """Compile one planner draft into a provider-neutral action."""

        if draft.tenant_id != goal.tenant_id or state.tenant_id != goal.tenant_id:
            raise ValueError("draft and target must belong to the goal tenant")

        if draft.action_type == ActionType.CREATE_DISCOUNT:
            if goal.merchandising is not None:
                return self._compile_merchandising_discount(goal=goal, state=state, draft=draft)
            return self._compile_discount(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.DISABLE_DISCOUNT:
            return self._compile_disable_discount(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.SET_RECOMMENDATION_POLICY:
            return self._compile_recommendation_policy(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.SET_CAMPAIGN_BUDGET:
            return self._compile_campaign_budget(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.SET_SEARCH_BOOST:
            return self._compile_search_boost(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.SET_VARIANT_PRICE:
            return self._compile_price_change(goal=goal, state=state, draft=draft)
        if draft.action_type == ActionType.NO_OP:
            return self._compile_no_op(goal=goal, state=state, draft=draft)
        raise ValueError("unsupported action type")

    def _compile_merchandising_discount(
        self, *, goal: GoalSpec, state: SimulatorState, draft: IntentDraft
    ) -> CompiledAction:
        if goal.merchandising is None or state.merchandising is None:
            raise ValueError("merchandising profile required")
        product_id = str(draft.parameters["product_id"])
        if not any(p.id == product_id for p in state.products):
            raise ValueError("unknown scoped product")
        remaining = (
            goal.merchandising.promotion_cap_minor - state.merchandising.promotion_spent_minor
        )
        if remaining <= 0:
            raise CandidateRejectedError("PROMOTION_CAP_EXHAUSTED")
        window = _merchandising_window(goal, state, draft)
        intent = CreateDiscountIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            discount_kind="percentage",
            value=Decimal(str(draft.parameters["discount_percentage"])),
            starts_at=window.start_at,
            ends_at=window.end_at,
            product_scope=ProductScope(product_ids=[product_id]),
            customer_scope=CustomerScope(),
            maximum_cost_minor=remaining,
            code=None,
        )
        return _merchandising_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            target_key=f"discount:product:{product_id}",
            rollback="Disable this exact promotion; retain redemption and order receipts.",
        )

    def _compile_disable_discount(
        self, *, goal: GoalSpec, state: SimulatorState, draft: IntentDraft
    ) -> CompiledAction:
        discount_id = str(draft.parameters["provider_discount_id"])
        if not any(d.id == discount_id and d.active for d in state.discounts):
            raise CandidateRejectedError("NO_ACTIVE_DISCOUNT_TARGET")
        intent = DisableDiscountIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            provider_discount_id=discount_id,
        )
        return _merchandising_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            target_key=f"discount:disable:{discount_id}",
            rollback="Restore captured promotion configuration; retain redemption history.",
        )

    def _compile_recommendation_policy(
        self, *, goal: GoalSpec, state: SimulatorState, draft: IntentDraft
    ) -> CompiledAction:
        if state.merchandising is None or goal.merchandising is None:
            raise ValueError("recommendation controls require merchandising profile")
        intent = SetRecommendationPolicyIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            expected_version=_int_param(draft.parameters, "expected_version"),
            controls=RecommendationControls.model_validate(draft.parameters["controls"]),
            window=_merchandising_window(goal, state, draft),
        )
        return _merchandising_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            target_key="recommendation_policy:product_detail",
            rollback="Restore previous PDP controls under a new monotonic version.",
        )

    def _compile_discount(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        category = str(draft.parameters.get("category", "apparel"))
        percentage = Decimal(str(draft.parameters["discount_percentage"]))
        starts_at = state.current_time
        ends_at = min(starts_at + timedelta(days=7), goal.horizon.end_at)
        excess_only = draft.parameters.get("excess_inventory_only") is True
        if excess_only and goal.objective.scope != "excess_inventory":
            raise ValueError("Excess-inventory action requires that objective scope")
        economics = get_scenario(state.scenario_id).economics
        floor = max(
            [
                Decimal("0.25"),
                *[
                    item.value
                    for item in goal.constraints
                    if item.hard
                    and item.metric == MetricName.CONTRIBUTION_MARGIN_RATE
                    and item.operator in {ConstraintOperator.GTE, ConstraintOperator.GT}
                    and isinstance(item.value, Decimal)
                ],
            ]
        )
        eligible = set(_eligible_product_ids(state.products, category=category, limit=1000))
        products = []
        for product in state.products:
            if product.id not in eligible or (excess_only and not product.excess_inventory):
                continue
            margins = []
            for variant in product.variants:
                price = effective_price_minor(variant.price_minor, "percentage", percentage)
                margins.append(
                    Decimal(price - variant.cost_minor - variable_fee_minor(price, economics))
                    / Decimal(price)
                    if price
                    else Decimal(-1)
                )
            if min(margins) >= floor:
                products.append(product.id)
        scope = ProductScope(product_ids=sorted(products)[:10])
        if not scope.product_ids:
            raise CandidateRejectedError("NO_ELIGIBLE_DISCOUNT_TARGET")
        intent = CreateDiscountIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            discount_kind="percentage",
            value=percentage,
            starts_at=starts_at,
            ends_at=ends_at,
            product_scope=scope,
            customer_scope=CustomerScope(
                segment="all" if excess_only else "new_customers",
                new_customers_only=not excess_only,
            ),
            minimum_subtotal_minor=_int_param(draft.parameters, "minimum_subtotal_minor"),
            maximum_cost_minor=12_000,
            code=f"{'CLEARANCE' if excess_only else 'WELCOME'}{int(percentage * 100)}",
        )
        estimated_cost = Money(
            amount_minor=intent.maximum_cost_minor or 0,
            currency="USD",
        )
        normalized: JsonObject = {
            "discount_percentage": str(percentage),
            "category": category,
            "minimum_subtotal_minor": intent.minimum_subtotal_minor,
            "maximum_cost_minor": intent.maximum_cost_minor,
            "projected_margin_rate": str(draft.parameters.get("projected_margin_rate", "0.30")),
            "known_cost_basis": bool(draft.parameters.get("known_cost_basis", False)),
            "targets_low_stock": False,
            "target_key": f"discount:{category}:{'excess' if excess_only else 'new_customers'}",
        }
        return _compiled_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            normalized=normalized,
            estimated_cost=estimated_cost,
            risk_tier=RiskTier.R3_HIGH_IMPACT
            if percentage > Decimal("0.15")
            else RiskTier.R2_REVERSIBLE_MATERIAL,
            risk_confidence=draft.confidence,
            rollback_summary="Disable the simulator discount created by this command.",
            expected_metric="units_sold" if excess_only else "new_customers",
            expected_point=Decimal("8"),
            expected_lower=Decimal("2"),
            expected_upper=Decimal("18"),
        )

    def _compile_campaign_budget(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        campaign_id = str(draft.parameters["campaign_id"])
        campaign = next((item for item in state.campaigns if item.id == campaign_id), None)
        if campaign is None:
            raise ValueError("unknown campaign target")
        current_budget = Money(
            amount_minor=campaign.daily_budget_minor,
            currency="USD",
        )
        new_budget = Money(
            amount_minor=_int_param(draft.parameters, "new_budget_minor"),
            currency="USD",
        )
        intent = SetCampaignBudgetIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            campaign_id=campaign_id,
            current_budget=current_budget,
            new_budget=new_budget,
        )
        normalized: JsonObject = {
            "campaign_id": campaign_id,
            "current_budget_minor": current_budget.amount_minor,
            "new_budget_minor": new_budget.amount_minor,
            "budget_change_rate": str(draft.parameters.get("budget_change_rate", "0")),
            "target_key": f"campaign:{campaign_id}",
        }
        return _compiled_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            normalized=normalized,
            estimated_cost=Money(
                amount_minor=max(0, new_budget.amount_minor - current_budget.amount_minor) * 7,
                currency="USD",
            ),
            risk_tier=RiskTier.R2_REVERSIBLE_MATERIAL,
            risk_confidence=draft.confidence,
            rollback_summary="Restore the campaign budget captured in the before-state.",
            expected_metric="cac",
            expected_point=Decimal("-400"),
            expected_lower=Decimal("-900"),
            expected_upper=Decimal("-50"),
        )

    def _compile_search_boost(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        category = str(draft.parameters.get("category", "apparel"))
        multiplier = Decimal(str(draft.parameters.get("multiplier", "1.10")))
        starts_at = state.current_time
        ends_at = min(starts_at + timedelta(days=3), goal.horizon.end_at)
        excess_only = draft.parameters.get("excess_inventory_only") is True
        if excess_only and goal.objective.scope != "excess_inventory":
            raise ValueError("Excess-inventory action requires that objective scope")
        products = [p for p in state.products if not excess_only or p.excess_inventory]
        product_ids = _eligible_product_ids(products, category=category, limit=10)
        if goal.merchandising is not None:
            product = next(
                (p for p in state.products if p.id == draft.parameters.get("product_id")), None
            )
            if product is None or product.category != category:
                raise CandidateRejectedError("UNKNOWN_SCOPED_SEARCH_PRODUCT")
            product_ids = _eligible_product_ids([product], category=category, limit=1)
            window = _merchandising_window(goal, state, draft)
            starts_at, ends_at = window.start_at, window.end_at
        if not product_ids:
            raise CandidateRejectedError("NO_ELIGIBLE_SEARCH_TARGET")
        intent = SetSearchBoostIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            query_pattern={
                "text": str(draft.parameters.get("query_text", category)),
                "category": category,
            },
            product_scope=ProductScope(product_ids=product_ids),
            multiplier=multiplier,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        normalized: JsonObject = {
            "query_text": str(draft.parameters.get("query_text", category)),
            "category": category,
            "product_ids": product_ids,
            "multiplier": str(multiplier),
            "min_relevance_score": str(draft.parameters.get("min_relevance_score", "0.72")),
            "targets_low_stock": False,
            "target_key": f"search_boost:{category}",
        }
        return _compiled_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            normalized=normalized,
            estimated_cost=Money(amount_minor=0, currency="USD"),
            risk_tier=RiskTier.R1_REVERSIBLE_LOW,
            risk_confidence=draft.confidence,
            rollback_summary="Deactivate the simulator search boost.",
            expected_metric="search_attributed_purchases",
            expected_point=Decimal("3"),
            expected_lower=Decimal("0"),
            expected_upper=Decimal("8"),
        )

    def _compile_price_change(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        product = next(
            (item for item in state.products if item.id == draft.parameters.get("product_id")), None
        )
        if product is None:
            raise ValueError("unknown product target")
        variant = next(
            (item for item in product.variants if item.id == draft.parameters.get("variant_id")),
            None,
        )
        if variant is None:
            raise ValueError("unknown variant target")
        current_price = Money(amount_minor=variant.price_minor, currency=variant.currency)
        new_price = Money(
            amount_minor=_int_param(draft.parameters, "new_price_minor"),
            currency=variant.currency,
        )
        intent = SetVariantPriceIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
            changes=[
                VariantPriceChange(
                    product_id=product.id,
                    variant_id=variant.id,
                    current_price=current_price,
                    new_price=new_price,
                )
            ],
            window=_merchandising_window(goal, state, draft) if goal.merchandising else None,
            current_versions={variant.id: _int_param(draft.parameters, "expected_version")}
            if goal.merchandising
            else None,
        )
        normalized: JsonObject = {
            "max_price_delta_rate": "0.05",
            "known_cost_basis": True,
            "target_key": f"price:{variant.id}",
        }
        return _compiled_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            normalized=normalized,
            estimated_cost=Money(amount_minor=0, currency="USD"),
            risk_tier=RiskTier.R3_HIGH_IMPACT,
            risk_confidence=draft.confidence,
            rollback_summary="Restore the captured variant price.",
            expected_metric="conversion_rate",
            expected_point=Decimal("0.002"),
            expected_lower=Decimal("0"),
            expected_upper=Decimal("0.006"),
        )

    def _compile_no_op(
        self,
        *,
        goal: GoalSpec,
        state: SimulatorState,
        draft: IntentDraft,
    ) -> CompiledAction:
        intent = NoOpIntent(
            rationale=draft.rationale,
            opportunity_ids=draft.opportunity_ids,
            requested_by=_agent_actor(),
            source_run_id=draft.run_id,
            proposed_at=state.current_time,
        )
        return _compiled_action(
            goal=goal,
            state=state,
            draft=draft,
            intent=intent,
            normalized={"target_key": "noop"},
            estimated_cost=Money(amount_minor=0, currency="USD"),
            risk_tier=RiskTier.R0_READ_ONLY,
            risk_confidence=draft.confidence,
            rollback_summary="No provider change was made.",
            expected_metric="none",
            expected_point=Decimal("0"),
            expected_lower=Decimal("0"),
            expected_upper=Decimal("0"),
        )


def _compiled_action(
    *,
    goal: GoalSpec,
    state: SimulatorState,
    draft: IntentDraft,
    intent: ActionIntent,
    normalized: JsonObject,
    estimated_cost: Money,
    risk_tier: RiskTier,
    risk_confidence: Decimal,
    rollback_summary: str,
    expected_metric: str,
    expected_point: Decimal,
    expected_lower: Decimal,
    expected_upper: Decimal,
) -> CompiledAction:
    normalized = {**normalized, **safety_facts(state, intent)}
    provider = ProviderRef(
        provider_type="simulator",
        integration_id=None,
        resource_type="simulator_instance",
        resource_id=str(state.id),
    )
    window = TimeWindow(start_at=state.current_time, end_at=state.current_time + timedelta(days=7))
    action_type = draft.action_type
    idempotency_key = build_action_idempotency_key(
        tenant_id=goal.tenant_id,
        goal_id=goal.id,
        action_type=action_type,
        target_provider=provider,
        normalized_parameters=normalized,
        decision_window=window,
    )
    reservations = (
        [
            BudgetReservationRequest(
                budget_kind="goal",
                amount=estimated_cost,
                operation_id=idempotency_key,
            )
        ]
        if estimated_cost.amount_minor > 0
        else []
    )
    return CompiledAction(
        id=uuid5(NAMESPACE_URL, f"{draft.id}:{idempotency_key}"),
        tenant_id=goal.tenant_id,
        goal_id=goal.id,
        run_id=draft.run_id,
        intent=intent,
        target_provider=provider,
        normalized_parameters=normalized,
        preconditions=[
            Precondition(field="simulator.instance_id", operator="eq", value=str(state.id)),
            Precondition(field="simulator.generation", operator="eq", value=state.generation),
            Precondition(
                field="simulator.target_hash",
                operator="eq",
                value=canonical_hash(target_state(state, intent)),
            ),
        ],
        expected_impact=ImpactEstimate(
            metric="contribution_profit",
            interval=None,
            method="known_unit_economics_not_a_demand_forecast",
            assumptions=[
                "Demand response is insufficiently evidenced",
                "Store profit and margin must be measured",
                "Simulator-only evidence",
            ],
            feature_snapshot_ref=state.state_hash,
            out_of_distribution=True,
        )
        if goal.merchandising
        else ImpactEstimate(
            metric=expected_metric,
            interval=ConfidenceInterval(
                lower=expected_lower,
                point=expected_point,
                upper=expected_upper,
                level=Decimal("0.80"),
            ),
            method="deterministic_simulator_heuristic_v1",
            assumptions=["Seeded simulator evidence only", "No paid model or external API used"],
            feature_snapshot_ref=state.state_hash,
        ),
        estimated_cost=estimated_cost,
        budget_reservations=reservations,
        risk=RiskAssessment(
            tier=risk_tier,
            confidence=risk_confidence,
            reasons=["deterministic planner confidence", f"action={action_type.value}"],
        ),
        rollback_plan=RollbackPlan(
            available=True,
            summary=rollback_summary,
            action_type="rollback",
            parameters={"provider": "simulator"},
        ),
        idempotency_key=idempotency_key,
        expires_at=min(state.current_time + timedelta(hours=24), goal.horizon.end_at),
    )


def _merchandising_window(goal: GoalSpec, state: SimulatorState, draft: IntentDraft) -> TimeWindow:
    if goal.merchandising is None:
        raise ValueError("merchandising profile required")
    hours = _int_param(draft.parameters, "duration_hours")
    if not 24 <= hours <= goal.merchandising.max_duration_hours or hours % 24:
        raise ValueError("unsupported intervention duration")
    if goal.horizon.end_at - state.current_time < timedelta(hours=24):
        raise CandidateRejectedError("INSUFFICIENT_MEASUREMENT_HORIZON")
    return TimeWindow(
        start_at=state.current_time,
        end_at=state.current_time
        + timedelta(
            hours=min(
                hours, int((goal.horizon.end_at - state.current_time).total_seconds() // 86400) * 24
            )
        ),
    )


def _merchandising_action(
    *,
    goal: GoalSpec,
    state: SimulatorState,
    draft: IntentDraft,
    intent: ActionIntent,
    target_key: str,
    rollback: str,
) -> CompiledAction:
    return _compiled_action(
        goal=goal,
        state=state,
        draft=draft,
        intent=intent,
        normalized={"target_key": target_key},
        estimated_cost=Money(amount_minor=0, currency="USD"),
        risk_tier=RiskTier.R2_REVERSIBLE_MATERIAL,
        risk_confidence=draft.confidence,
        rollback_summary=rollback,
        expected_metric="none",
        expected_point=Decimal(0),
        expected_lower=Decimal(0),
        expected_upper=Decimal(0),
    )


def _eligible_product_ids(products: list[ProductState], *, category: str, limit: int) -> list[str]:
    eligible = [
        product
        for product in products
        if product.category == category
        and not product.low_stock
        and all(variant.inventory > 5 and variant.available for variant in product.variants)
    ]
    ranked = sorted(
        eligible,
        key=lambda product: (
            -product.quality_score,
            -product.popularity_score,
            product.id,
        ),
    )
    return [product.id for product in ranked[:limit]]


def _agent_actor() -> ActorRef:
    return ActorRef(type="agent", id="deterministic-controller-v1", roles={"system"})


def _int_param(parameters: JsonObject, key: str) -> int:
    value = parameters[key]
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"{key} must be an integer")
