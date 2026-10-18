"""Explicit deterministic policy rules for compiled controller actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from open_commerce.controller.models import (
    ControllerPolicyConfig,
    action_type_for_compiled,
    risk_sort_key,
)
from open_commerce.core.actions import CompiledAction
from open_commerce.core.enums import (
    ActionType,
    ActorRole,
    AutonomyMode,
    Capability,
    ConstraintOperator,
    MetricName,
    PolicyOutcome,
)
from open_commerce.core.goals import GoalSpec
from open_commerce.core.money import Money
from open_commerce.core.policy_types import PolicyDecision, RuleEvaluation
from open_commerce.core.types import JsonObject, canonical_hash, utc_now


@dataclass(frozen=True)
class PolicyContext:
    """Read-only policy facts assembled immediately before decisioning."""

    goal: GoalSpec
    policy: ControllerPolicyConfig
    action: CompiledAction
    capabilities: set[Capability]
    sample_size: int
    data_age_minutes: dict[str, int]
    budget_remaining: Money
    actions_in_run: int
    active_target_keys: set[str]
    recent_target_keys: set[str]
    decision_time: datetime | None = None
    deployment_kill_switch: bool = False
    active_interventions: int = 0


def effective_mode(context: PolicyContext) -> AutonomyMode:
    """The stricter goal or tenant setting wins; shadow always vetoes writes."""
    action_type = action_type_for_compiled(context.action)
    modes = {context.goal.autonomy.mode_for(action_type), context.policy.mode_for(action_type)}
    if (
        AutonomyMode.SHADOW in modes
        or context.goal.autonomy.default_mode == AutonomyMode.SHADOW
        or context.policy.default_mode == AutonomyMode.SHADOW
    ):
        return AutonomyMode.SHADOW
    if AutonomyMode.APPROVAL_REQUIRED in modes:
        return AutonomyMode.APPROVAL_REQUIRED
    return AutonomyMode.BOUNDED_AUTO


def _goal_limit(
    context: PolicyContext, metric: MetricName, default: Decimal, *, lower_bound: bool
) -> Decimal:
    values = [default]
    operators = (
        {ConstraintOperator.GTE, ConstraintOperator.GT}
        if lower_bound
        else {ConstraintOperator.LTE, ConstraintOperator.LT}
    )
    for constraint in context.goal.constraints:
        if constraint.hard and constraint.metric == metric and constraint.operator in operators:
            if isinstance(constraint.value, Decimal):
                adjustment = (
                    Decimal("0.00000001")
                    if constraint.operator in {ConstraintOperator.GT, ConstraintOperator.LT}
                    else Decimal(0)
                )
                values.append(
                    constraint.value + adjustment if lower_bound else constraint.value - adjustment
                )
    return max(values) if lower_bound else min(values)


@dataclass(frozen=True)
class PolicyRuleResult:
    """Policy outcome for one explicit rule."""

    outcome: PolicyOutcome
    evaluation: RuleEvaluation


class PolicyRule:
    """Base class for deterministic policy rules."""

    code = "policy_rule"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        """Evaluate the rule against one compiled action."""

        raise NotImplementedError

    def _pass(self, reason: str, details: JsonObject | None = None) -> PolicyRuleResult:
        return PolicyRuleResult(
            outcome=PolicyOutcome.ALLOW,
            evaluation=RuleEvaluation(
                code=self.code,
                passed=True,
                reason=reason,
                details=details or {},
            ),
        )

    def _deny(self, reason: str, details: JsonObject | None = None) -> PolicyRuleResult:
        return PolicyRuleResult(
            outcome=PolicyOutcome.DENY,
            evaluation=RuleEvaluation(
                code=self.code,
                passed=False,
                reason=reason,
                details=details or {},
            ),
        )

    def _require_approval(self, reason: str, details: JsonObject | None = None) -> PolicyRuleResult:
        return PolicyRuleResult(
            outcome=PolicyOutcome.REQUIRE_APPROVAL,
            evaluation=RuleEvaluation(
                code=self.code,
                passed=True,
                reason=reason,
                details=details or {},
            ),
        )


class KillSwitchRule(PolicyRule):
    code = "kill_switch"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        if context.policy.kill_switch_enabled or context.deployment_kill_switch:
            return self._deny("tenant kill switch is enabled")
        if context.action.target_provider.resource_id in context.policy.blocked_provider_resources:
            return self._deny("provider target kill switch is enabled")
        return self._pass("tenant kill switch is disabled")


class ExecutionBoundaryRule(PolicyRule):
    code = "execution_boundary"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action = context.action
        if (
            action.tenant_id != context.goal.tenant_id
            or action.tenant_id != context.policy.tenant_id
        ):
            return self._deny("action, goal and policy tenants must match")
        if (
            action.target_provider.provider_type != "simulator"
            or action.target_provider.integration_id is not None
        ):
            return self._deny("v0.1 only supports simulator writes")
        if effective_mode(context) == AutonomyMode.SHADOW:
            return self._deny("shadow mode prohibits writes even with approval")
        if (context.decision_time or action.intent.proposed_at) >= action.expires_at:
            return self._deny("action proposal expired")
        if (
            action_type_for_compiled(action) == ActionType.SET_VARIANT_PRICE
            and effective_mode(context) == AutonomyMode.BOUNDED_AUTO
        ):
            return self._deny("base-price changes cannot execute in bounded autonomy")
        return self._pass("tenant, provider, autonomy and expiry boundaries hold")


class ActionAllowlistRule(PolicyRule):
    code = "action_allowlist"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action_type = action_type_for_compiled(context.action)
        allowed_by_goal = action_type in context.goal.allowed_action_types
        allowed_by_policy = action_type in context.policy.allowed_action_types
        details: JsonObject = {
            "action_type": action_type.value,
            "allowed_by_goal": allowed_by_goal,
            "allowed_by_policy": allowed_by_policy,
        }
        if allowed_by_goal and allowed_by_policy:
            return self._pass("action type is allowed", details)
        return self._deny("action type is not allowed by goal and policy", details)


class MerchandisingRule(PolicyRule):
    code = "merchandising_bounds"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        limits = context.goal.merchandising
        if limits is None:
            return self._pass("legacy profile")
        action_type = action_type_for_compiled(context.action)
        if (
            action_type == ActionType.SET_CAMPAIGN_BUDGET
            or action_type in limits.prohibited_actions
        ):
            return self._deny("merchandising prohibits this action family")
        params = context.action.normalized_parameters
        if params.get("merchandising_constraints_hash") != canonical_hash(limits):
            return self._deny("reviewed merchandising constraints do not match current facts")
        errors = params.get("merchandising_errors")
        if not isinstance(errors, list) or errors:
            return self._deny("authoritative merchandising bounds failed", {"reasons": errors})
        if action_type == ActionType.CREATE_DISCOUNT and limits.max_effective_discount == 0:
            return self._deny("no-discount goal")
        return self._pass("combined economics, explicit windows and current versions hold")


class IdempotencyRule(PolicyRule):
    code = "idempotency_key"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        present = context.action.idempotency_key.startswith("idem_")
        if present:
            return self._pass("compiled action has a deterministic idempotency key")
        return self._deny("compiled action is missing a deterministic idempotency key")


class RollbackAvailabilityRule(PolicyRule):
    code = "rollback_available"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action_type = action_type_for_compiled(context.action)
        if action_type == ActionType.NO_OP:
            return self._pass("no-op does not need a provider rollback")
        if context.action.rollback_plan.available:
            return self._pass("rollback metadata is available")
        return self._deny("external writes require rollback metadata")


class MaximumDiscountRule(PolicyRule):
    code = "discount_max_percentage"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action = context.action
        if action_type_for_compiled(action) != ActionType.CREATE_DISCOUNT:
            return self._pass("not a discount creation")
        value = Decimal(str(action.normalized_parameters.get("discount_percentage", "0")))
        maximum = _goal_limit(
            context,
            MetricName.DISCOUNT_RATE,
            context.policy.discount_max_percentage,
            lower_bound=False,
        )
        details: JsonObject = {
            "discount_percentage": str(value),
            "maximum": str(maximum),
        }
        if Decimal(0) < value <= maximum:
            return self._pass("discount is within percentage limit", details)
        return self._deny("discount exceeds maximum percentage", details)


class KnownCostBasisRule(PolicyRule):
    code = "known_cost_basis"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action_type = action_type_for_compiled(context.action)
        if action_type not in {ActionType.CREATE_DISCOUNT, ActionType.SET_VARIANT_PRICE}:
            return self._pass("action does not require product cost basis")
        known = context.action.normalized_parameters.get("known_cost_basis") is True
        if known:
            return self._pass("product cost basis is known")
        return self._deny("margin-sensitive actions require known cost basis")


class ContributionMarginRule(PolicyRule):
    code = "contribution_margin_floor"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        raw_margin = context.action.normalized_parameters.get("projected_margin_rate")
        if raw_margin is None:
            if action_type_for_compiled(context.action) in {
                ActionType.CREATE_DISCOUNT,
                ActionType.SET_VARIANT_PRICE,
            }:
                return self._deny("margin-sensitive actions require a computed margin")
            return self._pass("no projected margin constraint applies")
        margin = Decimal(str(raw_margin))
        minimum = _goal_limit(
            context,
            MetricName.CONTRIBUTION_MARGIN_RATE,
            context.policy.discount_minimum_margin_rate,
            lower_bound=True,
        )
        if context.goal.merchandising is not None:
            minimum = max(
                context.goal.merchandising.minimum_unit_margin,
                context.policy.discount_minimum_margin_rate,
            )
        details: JsonObject = {
            "projected_margin_rate": str(margin),
            "minimum": str(minimum),
        }
        if margin >= minimum:
            return self._pass("projected contribution margin is within policy", details)
        return self._deny("projected contribution margin is below policy floor", details)


class MaximumPriceDeltaRule(PolicyRule):
    code = "price_delta_limit"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        if action_type_for_compiled(context.action) != ActionType.SET_VARIANT_PRICE:
            return self._pass("not a price action")
        delta = Decimal(str(context.action.normalized_parameters.get("max_price_delta_rate", "0")))
        details: JsonObject = {
            "max_price_delta_rate": str(delta),
            "maximum": str(context.policy.price_max_delta_rate),
        }
        if delta <= context.policy.price_max_delta_rate:
            return self._pass("price delta is within policy", details)
        return self._deny("price delta exceeds policy limit", details)


class BudgetAvailabilityRule(PolicyRule):
    code = "budget_available"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        estimated = context.action.estimated_cost
        remaining = context.budget_remaining
        estimated.require_same_currency(remaining)
        details: JsonObject = {
            "estimated_cost_minor": estimated.amount_minor,
            "remaining_minor": remaining.amount_minor,
            "currency": estimated.currency,
        }
        if (
            estimated.amount_minor <= remaining.amount_minor
            and estimated.currency == context.policy.max_total_estimated_cost.currency
            and estimated.amount_minor <= context.policy.max_total_estimated_cost.amount_minor
        ):
            return self._pass("estimated cost fits remaining budget", details)
        return self._deny("estimated cost exceeds remaining budget", details)


class CapabilityRule(PolicyRule):
    code = "provider_capability"

    _REQUIRED: ClassVar[dict[ActionType, Capability]] = {
        ActionType.CREATE_DISCOUNT: Capability.WRITE_DISCOUNTS,
        ActionType.DISABLE_DISCOUNT: Capability.WRITE_DISCOUNTS,
        ActionType.SET_VARIANT_PRICE: Capability.WRITE_PRICE,
        ActionType.SET_SEARCH_BOOST: Capability.WRITE_MERCHANDISING,
        ActionType.SET_RECOMMENDATION_POLICY: Capability.WRITE_MERCHANDISING,
        ActionType.SET_CAMPAIGN_BUDGET: Capability.WRITE_CAMPAIGN_BUDGET,
    }

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action_type = action_type_for_compiled(context.action)
        required = self._REQUIRED.get(action_type)
        if required is None:
            return self._pass("action has no provider write capability requirement")
        details: JsonObject = {"required": required.value}
        if required in context.capabilities:
            return self._pass("provider advertises required capability", details)
        return self._deny("provider does not advertise required capability", details)


class DataFreshnessRule(PolicyRule):
    code = "data_freshness"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        required = {"catalog", "inventory"}
        if action_type_for_compiled(context.action) == ActionType.SET_CAMPAIGN_BUDGET:
            required = {"campaigns", "orders"}
        if required - context.data_age_minutes.keys():
            return self._deny("required data freshness is unknown")
        stale = {
            source: age
            for source, age in context.data_age_minutes.items()
            if age > context.policy.max_data_age_minutes
        }
        if stale:
            return self._deny("required data is stale", {"stale_sources": stale})
        return self._pass("required data is fresh")


class InventoryAvailabilityRule(PolicyRule):
    code = "inventory_guardrail"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        params = context.action.normalized_parameters
        if bool(params.get("inventory_write_requested", False)):
            return self._deny("inventory quantity writes are prohibited in v0.1")
        if bool(params.get("targets_low_stock", False)):
            return self._deny("action targets low-stock inventory")
        return self._pass("action avoids prohibited inventory changes and low-stock targets")


class ActionVolumeRule(PolicyRule):
    code = "action_volume_limit"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        details: JsonObject = {
            "actions_in_run": context.actions_in_run,
            "maximum": context.policy.max_actions_per_run,
        }
        if context.actions_in_run <= context.policy.max_actions_per_run:
            return self._pass("action count is within policy", details)
        return self._deny("run proposes too many actions", details)


class ParallelInterventionRule(PolicyRule):
    code = "parallel_intervention_limit"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        details: JsonObject = {
            "active_interventions": context.active_interventions,
            "maximum": context.policy.max_parallel_interventions,
        }
        if context.active_interventions >= context.policy.max_parallel_interventions:
            return self._deny("goal already has the maximum active interventions", details)
        return self._pass("goal has room for this intervention", details)


class CooldownRule(PolicyRule):
    code = "cooldown_target"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        target_key = str(context.action.normalized_parameters.get("target_key", ""))
        if target_key and target_key in context.recent_target_keys:
            return self._deny("target is still in cooldown", {"target_key": target_key})
        return self._pass("target is not in cooldown")


class MinimumSampleRule(PolicyRule):
    code = "minimum_sample_size"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        mode = effective_mode(context)
        details: JsonObject = {
            "sample_size": context.sample_size,
            "minimum": context.policy.min_observations_for_auto_action,
            "mode": mode.value,
        }
        if mode not in {AutonomyMode.BOUNDED_AUTO, AutonomyMode.DEMO}:
            return self._pass("manual approval mode does not require auto sample size", details)
        if context.sample_size >= context.policy.min_observations_for_auto_action:
            return self._pass("sample size supports bounded automation", details)
        return self._require_approval("sample size is below bounded-auto threshold", details)


class ConfidenceRule(PolicyRule):
    code = "confidence_floor"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        mode = effective_mode(context)
        confidence = context.action.risk.confidence
        details: JsonObject = {
            "confidence": str(confidence),
            "minimum": str(context.policy.min_action_confidence),
            "mode": mode.value,
        }
        if confidence >= context.policy.min_action_confidence:
            return self._pass("action confidence meets policy floor", details)
        if mode in {AutonomyMode.BOUNDED_AUTO, AutonomyMode.DEMO}:
            return self._require_approval("low confidence requires human approval", details)
        return self._pass("manual approval mode covers low confidence", details)


class TargetConflictRule(PolicyRule):
    code = "target_conflict"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        target_key = str(context.action.normalized_parameters.get("target_key", ""))
        if target_key and target_key in context.active_target_keys:
            return self._deny("another active intervention already targets this entity")
        return self._pass("no active target conflict")


class ApprovalRequirementRule(PolicyRule):
    code = "approval_requirement"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        action_type = action_type_for_compiled(context.action)
        mode = effective_mode(context)
        details: JsonObject = {"mode": mode.value, "action_type": action_type.value}
        if mode in {AutonomyMode.APPROVAL_REQUIRED, AutonomyMode.SHADOW}:
            return self._require_approval("action requires human approval", details)
        return self._pass("action is eligible for bounded simulator automation", details)


class SearchRelevanceRule(PolicyRule):
    code = "search_relevance_floor"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        if action_type_for_compiled(context.action) != ActionType.SET_SEARCH_BOOST:
            return self._pass("not a search boost")
        relevance = Decimal(
            str(context.action.normalized_parameters.get("min_relevance_score", "0"))
        )
        details: JsonObject = {
            "min_relevance_score": str(relevance),
            "minimum": str(context.policy.search_boost_min_relevance),
        }
        if relevance >= context.policy.search_boost_min_relevance:
            return self._pass("search boost satisfies relevance floor", details)
        return self._deny("search boost would bypass relevance guardrail", details)


class SearchBoostMultiplierRule(PolicyRule):
    code = "search_boost_multiplier"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        if action_type_for_compiled(context.action) != ActionType.SET_SEARCH_BOOST:
            return self._pass("not a search boost")
        multiplier = Decimal(str(context.action.normalized_parameters.get("multiplier", "1")))
        details: JsonObject = {
            "multiplier": str(multiplier),
            "maximum": str(context.policy.search_boost_max_multiplier),
        }
        if multiplier <= context.policy.search_boost_max_multiplier:
            return self._pass("search boost multiplier is within policy", details)
        return self._deny("search boost multiplier exceeds policy", details)


class CampaignBudgetChangeRule(PolicyRule):
    code = "campaign_budget_delta"

    def evaluate(self, context: PolicyContext) -> PolicyRuleResult:
        if action_type_for_compiled(context.action) != ActionType.SET_CAMPAIGN_BUDGET:
            return self._pass("not a campaign budget action")
        change = Decimal(str(context.action.normalized_parameters.get("budget_change_rate", "0")))
        details: JsonObject = {
            "budget_change_rate": str(change),
            "maximum": str(context.policy.campaign_budget_max_change_rate),
        }
        if change <= context.policy.campaign_budget_max_change_rate:
            return self._pass("campaign budget change is within policy", details)
        return self._deny("campaign budget change exceeds the hard limit", details)


DEFAULT_RULES: tuple[PolicyRule, ...] = (
    KillSwitchRule(),
    ExecutionBoundaryRule(),
    ActionAllowlistRule(),
    IdempotencyRule(),
    RollbackAvailabilityRule(),
    MaximumDiscountRule(),
    KnownCostBasisRule(),
    ContributionMarginRule(),
    MaximumPriceDeltaRule(),
    BudgetAvailabilityRule(),
    CapabilityRule(),
    DataFreshnessRule(),
    InventoryAvailabilityRule(),
    ActionVolumeRule(),
    ParallelInterventionRule(),
    CooldownRule(),
    MinimumSampleRule(),
    ConfidenceRule(),
    TargetConflictRule(),
    SearchRelevanceRule(),
    SearchBoostMultiplierRule(),
    CampaignBudgetChangeRule(),
    ApprovalRequirementRule(),
)


class PolicyEngine:
    """Evaluate explicit policy rules and combine outcomes deterministically."""

    def __init__(self, rules: tuple[PolicyRule, ...] = DEFAULT_RULES) -> None:
        self.rules = rules

    def decide(self, context: PolicyContext) -> PolicyDecision:
        """Return a deterministic policy decision for one action."""

        rule_results = []
        rules = self.rules + ((MerchandisingRule(),) if context.goal.merchandising else ())
        for rule in rules:
            try:
                rule_results.append(rule.evaluate(context))
            except (InvalidOperation, ValueError, TypeError):
                rule_results.append(rule._deny("invalid or non-finite policy fact"))
        outcome = PolicyOutcome.ALLOW
        for result in rule_results:
            if result.outcome == PolicyOutcome.DENY:
                outcome = PolicyOutcome.DENY
                break
            if result.outcome == PolicyOutcome.REQUIRE_APPROVAL:
                outcome = PolicyOutcome.REQUIRE_APPROVAL

        reason_codes = [
            result.evaluation.code
            for result in rule_results
            if not result.evaluation.passed or result.outcome != PolicyOutcome.ALLOW
        ]
        required_roles = self._required_roles(context, outcome)
        return PolicyDecision(
            outcome=outcome,
            reason_codes=reason_codes,
            evaluated_rules=[result.evaluation for result in rule_results],
            required_approver_roles=required_roles,
            valid_until=utc_now() + timedelta(hours=1),
        )

    def _required_roles(
        self,
        context: PolicyContext,
        outcome: PolicyOutcome,
    ) -> set[ActorRole]:
        if outcome != PolicyOutcome.REQUIRE_APPROVAL:
            return set()
        if risk_sort_key(context.action.risk.tier) >= 3:
            return {ActorRole.OWNER}
        if risk_sort_key(context.action.risk.tier) >= 2:
            return {ActorRole.OWNER, ActorRole.OPERATOR}
        return {ActorRole.OPERATOR}
