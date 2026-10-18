"""Finite, no-key goal interpretation; unrecognized meaning is not executable."""

import re
from decimal import Decimal
from typing import Literal

from pydantic import Field, ValidationError

from open_commerce.controller.models import GoalCreateRequest, PlanningMode
from open_commerce.core.enums import ActionType, ConstraintOperator, MetricName
from open_commerce.core.goals import ConstraintSpec
from open_commerce.core.money import Money
from open_commerce.core.types import StrictDomainModel

NUMBER = r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
BOUND = (
    r"\s*(?:is|of|to|at least|at most|no more than|maximum|minimum|"
    r"above|below|under|over|<=|>=|:)?\s*"
)


class GoalInterpretation(StrictDomainModel):
    """A provisional form is not an activation command or a policy decision."""

    status: Literal["ready_for_review", "clarification_required", "unsupported"]
    draft: GoalCreateRequest | None
    warnings: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    interpretation_mode: Literal["deterministic", "model_backed", "replay", "typed_review"] = (
        "deterministic"
    )
    template_version: str = "goal-interpretation-v1"
    inference_ref: str | None = None


def interpret_goal(
    text: str, *, seed: int = 42, planning_mode: PlanningMode = "deterministic"
) -> GoalInterpretation:
    """Recognize supported clauses without silently ignoring other requested rules."""
    normalized = " ".join(text.lower().split())
    if normalized.startswith("merchandising:"):
        from open_commerce.controller.merchandising_interpretation import interpret_merchandising

        return interpret_merchandising(normalized, seed=seed, planning_mode=planning_mode)
    unsupported = _unsupported(normalized)
    if unsupported:
        return GoalInterpretation(
            status="unsupported", draft=None, unsupported_requests=unsupported
        )
    metric: str
    scope = "store"
    direction = "reach"
    target: Decimal | None = None
    ambiguities: list[str] = []
    if "contribution profit" in normalized:
        metric, direction = "contribution_profit", "maximize"
        amount = re.search(r"contribution profit" + BOUND + r"\$" + NUMBER, normalized)
        if amount:
            target, direction = _decimal(amount[1]) * 100, "reach"
    elif re.search(r"search(?:-attributed)? (?:purchases?|orders?)", normalized):
        metric = "search_attributed_purchases"
        target = _count_before(normalized, r"search(?:-attributed)? (?:purchases?|orders?)")
    elif re.search(r"excess inventory|overstock|clearance|clear .*inventory", normalized):
        metric, scope = "units_sold", "excess_inventory"
        target = _count_before(normalized, r"(?:excess inventory )?units?")
    elif re.search(r"(?:new )?customers?", normalized):
        metric = "new_customers"
        target = _count_before(normalized, r"(?:new )?customers?")
    else:
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            unsupported_requests=[
                *unsupported,
                "Supported objectives: new customers, contribution profit, excess inventory "
                "units and search-attributed purchases. Specify one measurable objective.",
            ],
        )
    objective_mentions = sum(
        [
            "contribution profit" in normalized,
            bool(
                re.search(
                    r"(?:acquire|reach|win|gain) " + NUMBER + r" (?:new )?customers?", normalized
                )
            ),
            bool(re.search(r"(?:reach|increase) " + NUMBER + r" search", normalized)),
            bool(re.search(r"clear " + NUMBER + r".*units?", normalized)),
        ]
    )
    if objective_mentions > 1:
        ambiguities.append(
            "Choose one primary measurable objective; other goals need separate review."
        )
    if target is None and direction == "reach":
        ambiguities.append("Specify a numeric target for the objective.")
    if (
        target is not None
        and metric != "contribution_profit"
        and target != target.to_integral_value()
    ):
        unsupported.append("Count targets must be whole numbers.")
    days = _single_value(
        normalized, NUMBER + r"\s*(?:simulated |virtual )?days?", ambiguities, "horizon"
    )
    if days is None:
        ambiguities.append("Specify the horizon in whole simulated days.")
    elif days != days.to_integral_value() or not 1 <= days <= 366:
        unsupported.append(
            "The supported horizon is 1 to 366 whole simulated days; it is not clamped."
        )
    daily_matches = list(
        re.finditer(
            r"(?:daily budget|budget per day)"
            + BOUND
            + r"\$"
            + NUMBER
            + r"|\$"
            + NUMBER
            + r"\s*(?:per day|/day|daily budget)",
            normalized,
        )
    )
    daily_values = {_decimal(m[1] or m[2]) for m in daily_matches}
    if len(daily_values) > 1:
        ambiguities.append("Conflicting daily budgets need clarification.")
    budget_text = normalized
    for match in reversed(daily_matches):
        budget_text = budget_text[: match.start()] + " " + budget_text[match.end() :]
    budget_matches = list(
        re.finditer(
            r"(?:total budget|budget)"
            + BOUND
            + r"\$"
            + NUMBER
            + r"|\$"
            + NUMBER
            + r"\s*(?:total |promotion )?budget",
            budget_text,
        )
    )
    budget_values = {_decimal(m[1] or m[2]) for m in budget_matches}
    if not budget_values:
        ambiguities.append("Specify the total USD business budget, including zero if intended.")
    if len(budget_values) > 1:
        ambiguities.append("Conflicting total budgets need clarification.")
    budget = next(iter(sorted(budget_values)), None)
    daily = next(iter(sorted(daily_values)), None)
    warnings = [
        "Review every typed value before activation; this is not an execution instruction.",
        "CAC is an observed guardrail, not a guarantee about future business outcomes.",
        "Margin and discount bounds also remain subject to stricter tenant policy.",
    ]
    if daily is None:
        daily = min(budget if budget is not None else Decimal(250), Decimal(250))
        warnings.append(f"Daily budget was omitted: proposed ${daily} per virtual day for review.")
    if budget is not None and daily > budget:
        ambiguities.append("Daily budget exceeds total budget; confirm revised amounts.")
    try:
        constraints = _constraints(normalized, warnings, ambiguities)
    except ValueError:
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            unsupported_requests=["Money amounts require nonnegative integer USD cents."],
        )
    actions = {
        ActionType.CREATE_DISCOUNT,
        ActionType.SET_SEARCH_BOOST,
        ActionType.SET_CAMPAIGN_BUDGET,
    }
    if re.search(
        r"no discounts?|prohibit discounts?|without discounts?|do not discount|never discount",
        normalized,
    ):
        actions.discard(ActionType.CREATE_DISCOUNT)
        explicit = [c for c in constraints if c.metric == MetricName.DISCOUNT_RATE]
        if any(c.value != Decimal(0) for c in explicit):
            # An omitted ceiling is a proposed default, not a conflicting owner instruction.
            if re.search(r"discounts?" + BOUND + NUMBER + r"\s*%", normalized):
                ambiguities.append(
                    "No-discount prohibition conflicts with a positive discount bound."
                )
        constraints = [c for c in constraints if c.metric != MetricName.DISCOUNT_RATE] + [
            ConstraintSpec(
                metric=MetricName.DISCOUNT_RATE, operator=ConstraintOperator.LTE, value=Decimal(0)
            )
        ]
    if re.search(
        r"no campaign(?: budget)? changes|no advertising|do not change campaign budgets", normalized
    ):
        actions.discard(ActionType.SET_CAMPAIGN_BUDGET)
    if re.search(r"no search boosts?|do not boost search", normalized):
        actions.discard(ActionType.SET_SEARCH_BOOST)
    if not actions:
        actions = {ActionType.NO_OP}
    allow_clause = re.search(r"(?:allowed actions?[: ]+|only (?:allow )?)([^.;]+)", normalized)
    if allow_clause:
        clause = allow_clause[1]
        selected = set()
        for pattern, action in (
            (r"search(?: boosts?)?", ActionType.SET_SEARCH_BOOST),
            (r"discounts?|promotions?", ActionType.CREATE_DISCOUNT),
            (r"campaign(?: budgets?)?", ActionType.SET_CAMPAIGN_BUDGET),
            (r"no[- ]?op|read[- ]only", ActionType.NO_OP),
        ):
            if re.search(pattern, clause):
                selected.add(action)
        leftovers = re.sub(
            r"search(?: boosts?)?|discounts?|promotions?|campaign(?: budgets?)?|"
            r"no[- ]?op|read[- ]only|\band\b|,",
            "",
            clause,
        ).strip()
        if not selected or leftovers:
            unsupported.append(
                "Allowed actions: search boosts, discounts, campaign budgets or no-op only."
            )
        if ActionType.CREATE_DISCOUNT in selected and ActionType.CREATE_DISCOUNT not in actions:
            ambiguities.append("Allowed discounts conflict with the no-discount prohibition.")
        actions = selected.intersection(actions | {ActionType.NO_OP}) or {ActionType.NO_OP}
    if unsupported:
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            warnings=warnings,
            ambiguities=ambiguities,
            unsupported_requests=unsupported,
        )
    scenario = (
        "excess_inventory_v1"
        if scope == "excess_inventory"
        else "search_conversion_v1"
        if metric == "search_attributed_purchases"
        else "acquisition_v1"
    )
    try:
        draft = GoalCreateRequest.model_validate(
            {
                "name": text[:200],
                "seed": seed,
                "scenario_id": scenario,
                "objective_metric": metric,
                "objective_direction": direction,
                "objective_scope": scope,
                "target_value": target,
                "horizon_days": int(days) if days is not None else 30,
                "budget": _money(budget if budget is not None else Decimal(0)),
                "daily_budget": _money(daily),
                "constraints": constraints,
                "allowed_action_types": actions,
                "planning_mode": planning_mode,
            }
        )
    except (ValueError, ValidationError):
        return GoalInterpretation(
            status="unsupported",
            draft=None,
            warnings=warnings,
            unsupported_requests=[
                "Invalid goal amounts, constraints or horizon; no values were clamped."
            ],
        )
    if not ambiguities:
        draft.review_hash = draft.configuration_hash
    return GoalInterpretation(
        status="clarification_required" if ambiguities else "ready_for_review",
        draft=draft,
        warnings=warnings,
        ambiguities=ambiguities,
    )


def _constraints(text: str, warnings: list[str], ambiguities: list[str]) -> list[ConstraintSpec]:
    result: list[ConstraintSpec] = []
    for label, metric, operator, default, money in (
        ("cac", MetricName.CAC, ConstraintOperator.LTE, Decimal(40), True),
        (
            "(?:contribution )?margin(?: floor)?",
            MetricName.CONTRIBUTION_MARGIN_RATE,
            ConstraintOperator.GTE,
            Decimal(25),
            False,
        ),
        (
            "(?:maximum |max )?discounts?(?: percentage)?",
            MetricName.DISCOUNT_RATE,
            ConstraintOperator.LTE,
            Decimal(15),
            False,
        ),
    ):
        pattern = label + BOUND + (r"\$" if money else "") + NUMBER + ("" if money else r"\s*%")
        value = _single_value(text, pattern, ambiguities, metric.value)
        if value is None:
            value = default
            warnings.append(
                f"Proposed default {metric.value}: {value}{' USD' if money else '%'}. Review it."
            )
        result.append(
            ConstraintSpec(
                metric=metric, operator=operator, value=_money(value) if money else value / 100
            )
        )
    return result


def _single_value(text: str, pattern: str, ambiguities: list[str], field: str) -> Decimal | None:
    values = {_decimal(m[1]) for m in re.finditer(pattern, text)}
    if len(values) > 1:
        ambiguities.append(f"Conflicting {field} values need clarification.")
    return next(iter(sorted(values)), None)


def _count_before(text: str, marker: str) -> Decimal | None:
    values = {_decimal(found[1]) for found in re.finditer(NUMBER + r"\s+" + marker, text)}
    return next(iter(values)) if len(values) == 1 else None


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _money(value: Decimal) -> Money:
    minor = value * 100
    if minor != minor.to_integral_value():
        raise ValueError("USD amounts have at most two decimal places")
    return Money(amount_minor=int(minor), currency="USD")


def _unsupported(text: str) -> list[str]:
    reasons = []
    if re.search(
        r"refund|fulfill|payment|shopify|google ads|meta ads|real (?:store|money)|"
        r"inventory (?:write|mutation)|lifetime value|\bltv\b|churn|search conversion rate|"
        r"days of supply|\bEUR\b|\bGBP\b|[\u20ac\u00a3]",
        text,
        re.I,
    ):
        reasons.append(
            "Requested live capability, currency or metric is not supported by this simulator."
        )
    if re.search(r"guarantee|strictly|(?:margin|discount|cac).*?\b(?:equals|exactly)\b", text):
        reasons.append("Guaranteed outcomes or strict/equality constraints are unsupported.")
    if re.search(r"(?:-|minus\s+)\s*\$?\d|\$\s*-\d", text):
        reasons.append("Negative amounts or counts are unsupported in natural-language drafting.")
    if re.search(r"(?:cac|discounts?)\s*(?:above|over|>=)|margin\s*(?:below|under|<=)", text):
        reasons.append("Supported bounds are maximum CAC/discount and minimum contribution margin.")
    # The offline parser has a declared finite vocabulary, not a general-language claim.
    vocabulary = set(
        (
            "acquire reach win gain new customers customer in simulated virtual days day with a an "
            "total daily promotion budget per keep cac below under above over margin contribution "
            "floor minimum maximum max discount discounts percentage and no prohibit without "
            "do not never only allow allowed action actions search boosts boost campaign changes "
            "budgets read noop op clear excess inventory units unit overstock clearance safely "
            "purchases purchase orders order attributed increase prioritize maximise maximize "
            "profit of to is at least most more than usd dollars dollar avoid low stock products "
            "relevance high safely campaigns"
        ).split()
    )
    words = set(re.findall(r"[a-z]+", text))
    if words - vocabulary:
        reasons.append(
            "Language outside offline grammar; clarify with supported goal and constraint clauses."
        )
    return reasons
