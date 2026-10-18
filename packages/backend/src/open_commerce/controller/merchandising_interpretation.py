"""Finite merchandising grammar. Every clause is recognized or blocks activation."""

import re
from decimal import Decimal

from pydantic import ValidationError

from open_commerce.controller.goal_interpretation import GoalInterpretation
from open_commerce.controller.models import GoalCreateRequest, PlanningMode
from open_commerce.core.enums import ActionType
from open_commerce.core.merchandising import MerchandisingConstraints

RATES = {
    "max base price change": "max_base_price_change",
    "max cumulative price change": "max_cumulative_price_change",
    "max effective discount": "max_effective_discount",
    "minimum unit margin": "minimum_unit_margin",
    "minimum relevance": "minimum_relevance",
}
FAMILIES = {
    "prices": ActionType.SET_VARIANT_PRICE,
    "promotions": ActionType.CREATE_DISCOUNT,
    "search": ActionType.SET_SEARCH_BOOST,
    "recommendations": ActionType.SET_RECOMMENDATION_POLICY,
}


def interpret_merchandising(
    text: str, *, seed: int, planning_mode: PlanningMode
) -> GoalInterpretation:
    clauses = [clause.strip() for clause in text.lower().removeprefix("merchandising:").split(";")]
    values: dict[str, object] = {}
    unsupported = []
    ambiguities = []
    prohibited = {ActionType.SET_CAMPAIGN_BUDGET}
    no_discount = search_only = False
    objective: dict[str, object] = {}

    def assign(key: str, value: object) -> None:
        if key in values and values[key] != value:
            ambiguities.append(f"Conflicting {key} values require review.")
        values[key] = value

    for clause in clauses:
        if match := re.fullmatch(r"maximize contribution profit in (\d+) days", clause):
            if objective:
                ambiguities.append("Choose one primary objective.")
            objective = {
                "objective_metric": "contribution_profit",
                "objective_direction": "maximize",
                "horizon_days": int(match[1]),
            }
        elif match := re.fullmatch(r"clear (\d+) excess inventory units in (\d+) days", clause):
            if objective:
                ambiguities.append("Choose one primary objective.")
            objective = {
                "objective_metric": "units_sold",
                "objective_direction": "reach",
                "objective_scope": "excess_inventory",
                "target_value": match[1],
                "horizon_days": int(match[2]),
                "scenario_id": "excess_inventory_v1",
            }
        elif match := re.fullmatch(r"maximize search purchases in (\d+) days", clause):
            if objective:
                ambiguities.append("Choose one primary objective.")
            objective = {
                "objective_metric": "search_attributed_purchases",
                "objective_direction": "maximize",
                "horizon_days": int(match[1]),
                "scenario_id": "search_conversion_v1",
            }
        elif match := re.fullmatch(r"(" + "|".join(RATES) + r") (\d+(?:\.\d+)?)%", clause):
            assign(RATES[match[1]], Decimal(match[2]) / 100)
        elif match := re.fullmatch(r"promotion cap \$(\d+(?:\.\d{1,2})?)", clause):
            assign("promotion_cap_minor", int(Decimal(match[1]) * 100))
        elif match := re.fullmatch(r"prohibit (prices|promotions|search|recommendations)", clause):
            prohibited.add(FAMILIES[match[1]])
        elif clause == "no discounts":
            no_discount = True
        elif clause == "search only":
            search_only = True
        else:
            unsupported.append("Unrecognized merchandising clause; no part is silently ignored.")
    if not objective:
        ambiguities.append(
            "Specify contribution profit, search purchases or excess units and days."
        )
    if no_discount:
        if (
            values.get("max_effective_discount", 0) != 0
            or values.get("promotion_cap_minor", 0) != 0
        ):
            ambiguities.append("No discounts conflicts with a positive discount ceiling or cap.")
        values["max_effective_discount"] = Decimal(0)
        values["promotion_cap_minor"] = 0
        prohibited.add(ActionType.CREATE_DISCOUNT)
    values["prohibited_actions"] = prohibited
    if unsupported:
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            unsupported_requests=unsupported,
            template_version="merchandising-interpretation-v1",
        )
    try:
        limits = MerchandisingConstraints.model_validate(values)
        actions = (
            {ActionType.SET_SEARCH_BOOST, ActionType.NO_OP}
            if search_only
            else {
                ActionType.SET_VARIANT_PRICE,
                ActionType.CREATE_DISCOUNT,
                ActionType.DISABLE_DISCOUNT,
                ActionType.SET_SEARCH_BOOST,
                ActionType.SET_RECOMMENDATION_POLICY,
                ActionType.NO_OP,
            }
        ) - prohibited
        draft = GoalCreateRequest.model_validate(
            {
                **objective,
                "name": text[:200],
                "seed": seed,
                "merchandising": limits,
                "allowed_action_types": actions,
                "planning_mode": planning_mode,
            }
        )
    except ValidationError:
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            template_version="merchandising-interpretation-v1",
            unsupported_requests=[
                "Out-of-range merchandising constraints; values are not clamped."
            ],
        )
    if not ambiguities:
        draft.review_hash = draft.configuration_hash
    return GoalInterpretation(
        status="clarification_required" if ambiguities else "ready_for_review",
        draft=draft,
        ambiguities=ambiguities,
        template_version="merchandising-interpretation-v1",
        warnings=[
            "Review all typed constraints, including defaults, before activation.",
            "No acquisition budget or CAC target. Incoming simulator traffic is fixed.",
            "Known unit margin is a hard floor; realized store profit is a measured outcome.",
            "No-discount goals also prohibit effective base markdowns below frozen reference.",
        ],
    )
