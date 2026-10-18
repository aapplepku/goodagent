"""Deterministic no-key planner for simulator-first controller runs."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from open_commerce.controller.models import Hypothesis, IntentDraft, Opportunity
from open_commerce.core.enums import ActionType


class ModelProvider(Protocol):
    """Planner interface for validated, non-authoritative model output."""

    def generate_hypotheses(self, opportunities: list[Opportunity]) -> list[Hypothesis]:
        """Generate hypotheses from opportunities."""
        ...

    def generate_intent_drafts(
        self,
        *,
        opportunities: list[Opportunity],
        hypotheses: list[Hypothesis],
    ) -> list[IntentDraft]:
        """Generate non-executable action drafts."""
        ...


class DeterministicModelProvider:
    """No-key planner that produces repeatable, schema-validated drafts."""

    def generate_hypotheses(self, opportunities: list[Opportunity]) -> list[Hypothesis]:
        """Generate stable hypotheses from detected opportunities."""

        hypotheses: list[Hypothesis] = []
        for opportunity in opportunities:
            hypotheses.append(
                Hypothesis(
                    id=uuid5(
                        NAMESPACE_URL,
                        f"{opportunity.run_id}:hypothesis:{opportunity.type}",
                    ),
                    tenant_id=opportunity.tenant_id,
                    run_id=opportunity.run_id,
                    opportunity_ids=[opportunity.id],
                    statement=_statement_for(opportunity),
                    confidence=opportunity.confidence,
                    created_at=opportunity.detected_at,
                )
            )
        return hypotheses

    def generate_intent_drafts(
        self,
        *,
        opportunities: list[Opportunity],
        hypotheses: list[Hypothesis],
    ) -> list[IntentDraft]:
        """Generate non-executable candidate intents for compilation."""

        by_type = {opportunity.type: opportunity for opportunity in opportunities}
        by_hypothesis = {
            hypothesis.opportunity_ids[0]: hypothesis
            for hypothesis in hypotheses
            if hypothesis.opportunity_ids
        }
        drafts: list[IntentDraft] = []
        conversion = by_type.get("conversion_gap")
        if conversion is not None:
            hypothesis = by_hypothesis[conversion.id]
            drafts.append(
                _draft(
                    opportunity=conversion,
                    hypothesis_id=hypothesis.id,
                    action_type=ActionType.CREATE_DISCOUNT,
                    suffix="welcome10",
                    rationale="Offer a bounded welcome discount to price-sensitive new customers.",
                    confidence=Decimal("0.81"),
                    parameters={
                        "discount_percentage": "0.10",
                        "category": "apparel",
                        "minimum_subtotal_minor": 3_000,
                        "projected_margin_rate": "0.32",
                        "known_cost_basis": True,
                    },
                )
            )
        campaign = by_type.get("campaign_efficiency")
        if campaign is not None:
            hypothesis = by_hypothesis[campaign.id]
            evidence = campaign.evidence[0].value
            daily_budget_minor = _int_value(evidence["daily_budget_minor"])
            drafts.append(
                _draft(
                    opportunity=campaign,
                    hypothesis_id=hypothesis.id,
                    action_type=ActionType.SET_CAMPAIGN_BUDGET,
                    suffix="campaign_rebalance",
                    rationale="Trim the highest-budget campaign by a reversible 20%.",
                    confidence=Decimal("0.78"),
                    parameters={
                        "campaign_id": campaign.evidence[0].key,
                        "current_budget_minor": daily_budget_minor,
                        "new_budget_minor": int(daily_budget_minor * Decimal("0.80")),
                        "budget_change_rate": "0.20",
                    },
                )
            )
        excess = by_type.get("excess_inventory")
        if excess is not None:
            drafts.append(
                _draft(
                    opportunity=excess,
                    hypothesis_id=by_hypothesis[excess.id].id,
                    action_type=ActionType.CREATE_DISCOUNT,
                    suffix="clearance10",
                    rationale="Test a bounded offer on stocked excess inventory only.",
                    confidence=Decimal("0.77"),
                    parameters={
                        "discount_percentage": "0.10",
                        "category": excess.evidence[0].value["category"],
                        "minimum_subtotal_minor": 3_000,
                        "excess_inventory_only": True,
                    },
                )
            )
        search = by_type.get("search_exposure_gap") or excess
        if search is not None:
            hypothesis = by_hypothesis[search.id]
            category = str(search.evidence[0].value["category"])
            drafts.append(
                _draft(
                    opportunity=search,
                    hypothesis_id=hypothesis.id,
                    action_type=ActionType.SET_SEARCH_BOOST,
                    suffix="search_boost",
                    rationale="Apply a small search boost that stays above the relevance floor.",
                    confidence=Decimal("0.84"),
                    parameters={
                        "query_text": category,
                        "category": category,
                        "multiplier": "1.10",
                        "min_relevance_score": "0.72",
                        "excess_inventory_only": excess is not None,
                    },
                )
            )
        return drafts


def _statement_for(opportunity: Opportunity) -> str:
    statements = {
        "conversion_gap": (
            "A small welcome offer may lift new-customer conversion without breaking margin limits."
        ),
        "campaign_efficiency": (
            "A conservative campaign budget change may improve CAC while preserving reach."
        ),
        "search_exposure_gap": (
            "Relevance-gated merchandising may lift search-attributed purchases."
        ),
        "excess_inventory": (
            "High-inventory products can be exposed without discounting low-stock substitutes."
        ),
        "guardrail_review": "No provider write should occur when evidence is insufficient.",
    }
    return statements[opportunity.type]


def _draft(
    *,
    opportunity: Opportunity,
    hypothesis_id: UUID,
    action_type: ActionType,
    suffix: str,
    rationale: str,
    confidence: Decimal,
    parameters: dict[str, object],
) -> IntentDraft:
    return IntentDraft(
        id=uuid5(NAMESPACE_URL, f"{opportunity.run_id}:draft:{suffix}"),
        tenant_id=opportunity.tenant_id,
        run_id=opportunity.run_id,
        hypothesis_id=hypothesis_id,
        opportunity_ids=[opportunity.id],
        action_type=action_type,
        rationale=rationale,
        parameters=parameters,
        confidence=confidence,
    )


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("expected integer-compatible value")
