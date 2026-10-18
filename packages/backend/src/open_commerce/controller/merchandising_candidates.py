"""Finite merchandising alternatives with explicit evidence gates, not a profit optimizer."""

from datetime import timedelta
from decimal import Decimal
from statistics import median
from typing import Literal

from pydantic import Field

from open_commerce.controller.merchandising_observation import (
    observe_surface,
    reassess,
    recent_window,
    recorded_price_window,
)
from open_commerce.core.enums import ActionType, MetricName
from open_commerce.core.goals import GoalSpec
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash
from open_commerce.simulator.merchandising_economics import (
    candidate_economics,
    intervention_targets,
    investigate_variant,
)
from open_commerce.simulator.merchandising_models import RecommendationPolicyState
from open_commerce.simulator.models import SimulatorState

MAX_DRAFTS = 64
FAMILIES = (
    ActionType.SET_SEARCH_BOOST,
    ActionType.SET_RECOMMENDATION_POLICY,
    ActionType.SET_VARIANT_PRICE,
    ActionType.CREATE_DISCOUNT,
    ActionType.DISABLE_DISCOUNT,
)


class DecisionCandidate(StrictDomainModel):
    key: str
    action_type: ActionType
    parameters: JsonObject = Field(default_factory=dict)
    evidence: JsonObject = Field(default_factory=dict)
    allowed_by_goal: bool = False
    opportunity_detected: bool = False
    sufficient_observations: bool = False
    candidate_generated: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    classification: Literal["unchanged", "experiment", "constraint_stop", "observed_stop"]
    objective: Literal["profit", "clearance", "search"]
    excess_units: int = 0
    affected_variants: int = 0
    rank_class: int = 2
    draft_id: str | None = None
    opportunity_id: str | None = None
    compiler_result: str = "not_submitted"
    policy_result: JsonObject | None = None
    selected: bool = False
    disposition: str = "precompile_rejected"
    predicted_profit_minor: None = None
    comparison: str = "unchanged; demand response and incremental profit unknown"


def objective_kind(goal: GoalSpec) -> Literal["profit", "clearance", "search"]:
    if goal.objective.scope == "excess_inventory":
        return "clearance"
    if goal.objective.metric in {
        MetricName.SEARCH_ATTRIBUTED_PURCHASES,
        MetricName.SEARCH_CONVERSION_RATE,
    } or goal.allowed_action_types <= {
        ActionType.SET_SEARCH_BOOST,
        ActionType.SET_RECOMMENDATION_POLICY,
        ActionType.NO_OP,
    }:
        return "search"
    return "profit"


def candidate_order(candidate: DecisionCandidate) -> tuple[int, int, int, int, str]:
    """Lexicographic declared preferences, never a sum of incomparable metrics."""
    stop = candidate.classification in {"constraint_stop", "observed_stop"}
    return (
        0 if stop else 1,
        -candidate.excess_units if candidate.objective == "clearance" else 0,
        candidate.rank_class,
        candidate.affected_variants,
        candidate.key,
    )


def generate_candidates(goal: GoalSpec, state: SimulatorState) -> list[DecisionCandidate]:
    merch, limits = state.merchandising, goal.merchandising
    if state.tenant_id != goal.tenant_id or merch is None or limits is None:
        raise ValueError("tenant-owned merchandising goal required")
    kind = objective_kind(goal)
    start, end = recent_window(state)
    complete_metrics = [
        m for m in state.metrics if not m.is_history and start.date() <= m.metric_date < end.date()
    ]
    global_reasons = []
    if len(complete_metrics) < 2 or sum(m.sessions for m in complete_metrics) < 200:
        global_reasons.append("INSUFFICIENT_COMPLETE_DAYS_OR_RECORDED_SESSIONS")
    remaining = int((goal.horizon.end_at - state.current_time).total_seconds() // 86400) * 24
    duration = min(168, limits.max_duration_hours // 24 * 24, remaining)
    if duration < 48:
        global_reasons.append("INSUFFICIENT_REMAINING_MEASUREMENT_WINDOW")
    if len(state.products) > 128 or len(state.discounts) > 64:
        return [
            DecisionCandidate(
                key=a.value,
                action_type=a,
                allowed_by_goal=a in goal.allowed_action_types - limits.prohibited_actions,
                objective=kind,
                classification="experiment",
                reason_codes=["CATALOG_OR_PROMOTION_DIAGNOSTIC_BOUND_EXCEEDED"],
            )
            for a in FAMILIES
        ] + [
            DecisionCandidate(
                key="unchanged",
                action_type=ActionType.NO_OP,
                allowed_by_goal=True,
                opportunity_detected=True,
                sufficient_observations=True,
                candidate_generated=True,
                classification="unchanged",
                objective=kind,
                disposition="comparison",
                reason_codes=["CATALOG_OR_PROMOTION_DIAGNOSTIC_BOUND_EXCEEDED"],
                evidence={
                    "product_count": len(state.products),
                    "promotion_count": len(state.discounts),
                },
            )
        ]
    products = sorted(state.products, key=lambda p: p.id)
    reports = {}
    search = {}
    for p in products:
        available = sorted(
            (v for v in p.variants if v.available and v.inventory > 5),
            key=lambda v: (v.price_minor, v.id),
        )
        if available:
            reports[p.id] = investigate_variant(
                state, tenant_id=goal.tenant_id, product_id=p.id, variant_id=available[0].id
            )
        search[p.id] = observe_surface(
            merch, start=start, end=end, surface="search", product_ids={p.id}
        )
    rows: list[DecisionCandidate] = []

    def add(
        action: ActionType,
        key: str,
        parameters: JsonObject,
        evidence: JsonObject,
        reasons: list[str],
        *,
        opportunity: bool,
        enough: bool,
        classification: Literal["experiment", "constraint_stop", "observed_stop"] = "experiment",
        excess: int = 0,
        variants: int = 0,
        rank: int = 2,
    ) -> None:
        allowed = action in goal.allowed_action_types - limits.prohibited_actions
        errors = list(reasons)
        if not allowed:
            errors.append("GOAL_PROHIBITS_FAMILY")
        if classification == "experiment":
            errors.extend(global_reasons)
            if kind == "clearance" and excess == 0:
                errors.append("OUTSIDE_EXCESS_INVENTORY_OBJECTIVE")
            if kind == "search" and action not in {
                ActionType.SET_SEARCH_BOOST,
                ActionType.SET_RECOMMENDATION_POLICY,
            }:
                errors.append("MONETARY_CHANGE_OUTSIDE_SEARCH_OBJECTIVE")
        if (
            action in {ActionType.SET_VARIANT_PRICE, ActionType.SET_RECOMMENDATION_POLICY}
            and duration < 24
        ):
            errors.append("NO_REMAINING_CONTROL_WINDOW")
        if not opportunity:
            errors.append("NO_SUPPORTED_OPPORTUNITY")
        if not enough and classification != "constraint_stop":
            errors.append("INSUFFICIENT_MATCHED_OBSERVATIONS")
        rows.append(
            DecisionCandidate(
                key=key,
                action_type=action,
                parameters=parameters,
                evidence=evidence,
                allowed_by_goal=allowed,
                opportunity_detected=opportunity,
                sufficient_observations=enough,
                reason_codes=sorted(set(errors)),
                classification=classification,
                objective=kind,
                excess_units=excess,
                affected_variants=variants,
                rank_class=rank,
            )
        )

    for product in products:
        report = reports.get(product.id)
        observed = search[product.id]
        peers = [
            p
            for p in products
            if p.id != product.id
            and p.id in reports
            and p.category == product.category
            and p.attributes.get("product_type") == product.attributes.get("product_type")
            and product.attributes.get("product_type")
        ]
        search_interventions = [r for r in state.search_boosts if product.id in r.product_ids]
        search_start = max([start] + [r.ends_at for r in search_interventions])
        peer_search = {
            p.id: observe_surface(
                merch, start=search_start, end=end, surface="search", product_ids={p.id}
            )
            for p in peers
        }
        peer_queries = {query for p in peers for query in peer_search[p.id].queries}
        scoped = observe_surface(
            merch,
            start=search_start,
            end=end,
            surface="search",
            product_ids={product.id},
            queries=peer_queries,
        )
        peer_exposures = [peer_search[p.id].exposures for p in peers]
        eligible = bool(
            report
            and not product.low_stock
            and all(v.available and v.inventory > 5 for v in product.variants)
        )
        excess = product.total_inventory if product.excess_inventory else 0
        known_relevance = (
            scoped.minimum_relevance is None or scoped.minimum_relevance >= limits.minimum_relevance
        )
        gap = bool(
            peer_exposures
            and sum(peer_exposures) >= 200
            and scoped.exposures * len(peers) * 2 < sum(peer_exposures)
        )
        search_reasons = []
        if not eligible:
            search_reasons.append("UNAVAILABLE_OR_LOW_STOCK_TARGET")
        if not known_relevance or not scoped.constraints_hold:
            search_reasons.append("OBSERVED_RELEVANCE_OR_CONSTRAINT_FAILURE")
        if any(
            product.id in r.product_ids
            and r.active
            and r.starts_at <= state.current_time < r.ends_at
            for r in state.search_boosts
        ):
            search_reasons.append("SEARCH_INTERVENTION_STILL_ACTIVE")
        search_history = [
            r
            for r in state.command_history
            if r.action_type == "set_search_boost"
            and intervention_targets(r.after_state or {}, product.id, "")
        ]
        if search_history and state.current_time - max(
            r.created_at for r in search_history
        ) < timedelta(days=7):
            search_reasons.append("WAIT_FOR_PRIOR_SEARCH_MEASUREMENT")
        if (search_history or search_interventions) and (
            not search_interventions or not any(len(p.days) >= 2 for p in peer_search.values())
        ):
            search_reasons.append("WAIT_FOR_FRESH_POST_EXPIRY_SEARCH_COHORT")
        add(
            ActionType.SET_SEARCH_BOOST,
            f"search:{product.id}",
            {
                "product_id": product.id,
                "category": product.category,
                "query_text": product.category,
                "multiplier": "1.10",
                "duration_hours": duration,
            },
            {
                "product_id": product.id,
                "search": scoped.model_dump(mode="json"),
                "peer_ids": [p.id for p in peers],
                "peer_exposures": peer_exposures,
                "zero_exposure_relationship": "same declared type/category as observed peers",
                "displacement_profit": "unknown; observe all affected queries and substitutes",
            },
            search_reasons,
            opportunity=gap,
            enough=bool(
                peers
                and sum(peer_exposures) >= 200
                and any(len(p.days) >= 2 for p in peer_search.values())
            ),
            excess=excess,
            variants=len(product.variants),
            rank=0,
        )
        if report is None:
            for action in (ActionType.SET_VARIANT_PRICE, ActionType.CREATE_DISCOUNT):
                add(
                    action,
                    f"{action.value}:{product.id}",
                    {},
                    {"product_id": product.id},
                    ["NO_AVAILABLE_VARIANT"],
                    opportunity=False,
                    enough=False,
                )
            continue
        monetary_reasons = []
        if not eligible:
            monetary_reasons.append("UNAVAILABLE_OR_LOW_STOCK_TARGET")
        if report.active_promotions:
            monetary_reasons.append("REASSESS_ACTIVE_PROMOTION_BEFORE_NEW_MONETARY_CHANGE")
        revision = merch.prices[report.variant_id]
        if revision.expires_at is not None:
            monetary_reasons.append("REASSESS_ACTIVE_PRICE_BEFORE_NEW_MONETARY_CHANGE")
        monetary_history = [
            r
            for r in state.command_history
            if r.action_type in {"set_variant_price", "create_discount", "disable_discount"}
            and any(
                intervention_targets(r.before_state, product.id, v.id)
                or intervention_targets(r.after_state or {}, product.id, v.id)
                for v in product.variants
            )
        ]
        if monetary_history:
            monetary_reasons.append("NO_REPEAT_MONETARY_EXPERIMENT_WITHOUT_RESPONSE_IDENTIFICATION")
        if (
            observed.minimum_relevance is None
            or observed.minimum_relevance < limits.minimum_relevance
            or not observed.constraints_hold
        ):
            monetary_reasons.append("RELEVANCE_NOT_ESTABLISHED")
        comparable = [
            p
            for p in peers
            if set(search[p.id].queries) == set(observed.queries)
            and search[p.id].enough
            and search[p.id].clicks >= 20
        ]
        peer_clicks = sum(search[p.id].clicks for p in comparable)
        peer_orders = sum(search[p.id].orders for p in comparable)
        peer_prices = [reports[p.id].current.effective_price_minor for p in comparable]
        if not peer_prices or peer_clicks == 0:
            monetary_reasons.append("NO_OBSERVED_COMPARABLE_PEER_COHORT")
        elif report.current.effective_price_minor < median(peer_prices):
            monetary_reasons.append("CURRENT_PRICE_ALREADY_BELOW_OBSERVED_PEER_MEDIAN")
        low = (
            observed.clicks >= 20
            and observed.orders * 10 < observed.clicks
            and peer_orders * 10 >= peer_clicks
            and peer_clicks >= 20
        )
        evidence: JsonObject = {
            "product_id": product.id,
            "search": observed.model_dump(mode="json"),
            "economics": report.model_dump(mode="json"),
            "comparable_peer_ids": [p.id for p in comparable],
            "peer_effective_prices_minor": peer_prices,
            "peer_search_clicks": peer_clicks,
            "peer_search_orders": peer_orders,
            "product_monetary_interventions": [str(r.execution_id) for r in monetary_history[-20:]],
            "uncertainty": "Observed peer difference is not identified price sensitivity",
        }
        lower = [
            c
            for c in report.candidates
            if c.promotion_rate == 0 and c.base_price_minor < report.current.base_price_minor
        ]
        for c in lower:
            add(
                ActionType.SET_VARIANT_PRICE,
                f"price:{product.id}:{c.base_price_minor}",
                {
                    "product_id": product.id,
                    "variant_id": report.variant_id,
                    "new_price_minor": c.base_price_minor,
                    "expected_version": report.current_version,
                    "duration_hours": duration,
                },
                evidence,
                monetary_reasons + c.reason_codes,
                opportunity=low,
                enough=observed.enough and observed.clicks >= 20,
                excess=report.available_inventory if product.excess_inventory else 0,
                variants=1,
            )
        if not lower:
            add(
                ActionType.SET_VARIANT_PRICE,
                f"price:{product.id}:unchangeable",
                {},
                evidence,
                [*monetary_reasons, "NO_NONZERO_BOUNDED_PRICE_STEP"],
                opportunity=low,
                enough=observed.enough,
                excess=excess,
                variants=1,
            )
        promotions = [
            c
            for c in report.candidates
            if c.promotion_rate > 0 and c.base_price_minor == report.current.base_price_minor
        ]
        for c in promotions:
            reasons = monetary_reasons + c.reason_codes
            if c.promotion_rate > min(item.promotion_rate for item in promotions):
                reasons.append("LARGER_DISCOUNT_WITHOUT_RESPONSE_EVIDENCE")
            add(
                ActionType.CREATE_DISCOUNT,
                f"promotion:{product.id}:{c.promotion_rate}",
                {
                    "product_id": product.id,
                    "discount_percentage": str(c.promotion_rate),
                    "duration_hours": duration,
                },
                evidence,
                reasons,
                opportunity=low,
                enough=observed.enough and observed.clicks >= 20,
                excess=excess,
                variants=len(product.variants),
            )
        if not promotions:
            add(
                ActionType.CREATE_DISCOUNT,
                f"promotion:{product.id}:prohibited",
                {},
                evidence,
                ["NO_NONZERO_PROMOTION_WITHIN_REVIEWED_LIMITS"],
                opportunity=low,
                enough=observed.enough,
                excess=excess,
            )
    for product in products:
        for variant in sorted(product.variants, key=lambda v: v.id):
            if variant.id not in merch.prices:
                continue
            revision = merch.prices[variant.id]
            if revision.last_changed_at is None:
                continue
            report = investigate_variant(
                state, tenant_id=goal.tenant_id, product_id=product.id, variant_id=variant.id
            )
            period = recorded_price_window(state, report.variant_id)
            assessment = reassess(
                merch,
                product_ids={product.id},
                started=period[0] if period else revision.last_changed_at,
                now=state.current_time,
                ends_at=period[1] if period else revision.expires_at,
            )
            restore = revision.revert_price_minor
            hard = restore is not None and (
                report.current.unit_margin is None
                or report.current.unit_margin < limits.minimum_unit_margin
                or report.current.effective_discount_rate > limits.max_effective_discount
            )
            reasons = []
            if restore is None:
                reasons.append("PRICE_ALREADY_EXPIRED_OR_RESTORED_HISTORY_RETAINED")
            if restore is not None:
                safety = candidate_economics(
                    state,
                    tenant_id=goal.tenant_id,
                    product_id=product.id,
                    variant_id=report.variant_id,
                    base_price_minor=restore,
                    promotion_rate=Decimal(0),
                )
                reasons += safety.reason_codes
            add(
                ActionType.SET_VARIANT_PRICE,
                f"price-reassessment:{report.variant_id}",
                {
                    "product_id": product.id,
                    "variant_id": report.variant_id,
                    "new_price_minor": restore or report.current.base_price_minor,
                    "expected_version": report.current_version,
                    "duration_hours": max(24, duration),
                },
                {
                    "assessment": assessment.model_dump(mode="json"),
                    "prior_interventions": report.prior_interventions,
                    "known_bounds_violated": hard,
                    "rollback": "Restore future configuration only; prior losses/orders remain",
                },
                [*reasons, *([] if hard or assessment.review_required else [assessment.reason])],
                opportunity=hard or assessment.review_required,
                enough=assessment.classification != "insufficient",
                classification="constraint_stop" if hard else "observed_stop",
                variants=1,
                rank=0,
            )

    for discount in sorted(state.discounts, key=lambda d: d.id):
        if not discount.active or not discount.starts_at <= state.current_time < discount.ends_at:
            continue
        targets = {p.id for p in products if discount.applies_to(p, state.current_time)}
        relevant = [
            investigate_variant(state, tenant_id=goal.tenant_id, product_id=p.id, variant_id=v.id)
            for p in products
            if p.id in targets
            for v in p.variants
        ]
        hard = any(
            r.current.unit_margin is None
            or r.current.unit_margin < limits.minimum_unit_margin
            or r.current.effective_discount_rate > limits.max_effective_discount
            for r in relevant
        )
        assessment = reassess(
            merch,
            product_ids=targets,
            started=discount.starts_at,
            now=state.current_time,
            ends_at=discount.ends_at,
        )
        add(
            ActionType.DISABLE_DISCOUNT,
            f"disable:{discount.id}",
            {
                "provider_discount_id": discount.id,
            },
            {
                "assessment": assessment.model_dump(mode="json"),
                "target_products": sorted(targets),
                "known_bounds_violated": hard,
                "economics": [r.model_dump(mode="json") for r in relevant],
                "rollback": "Does not erase redemptions, orders, cap use or losses",
            },
            [] if hard or assessment.review_required else [assessment.reason],
            opportunity=hard or assessment.review_required,
            enough=assessment.classification != "insufficient",
            classification="constraint_stop" if hard else "observed_stop",
            rank=0,
        )
    if not any(r.action_type == ActionType.DISABLE_DISCOUNT for r in rows):
        add(
            ActionType.DISABLE_DISCOUNT,
            "disable:none",
            {},
            {},
            ["NO_ACTIVE_PROMOTION"],
            opportunity=False,
            enough=False,
            classification="observed_stop",
        )

    policy = merch.recommendation_policy
    pair_evidence: list[JsonObject] = []
    useful_pairs: list[JsonObject] = []
    for pair in sorted(
        merch.compatibility, key=lambda p: (p.anchor_product_id, p.complement_product_id)
    ):
        complement = next((p for p in products if p.id == pair.complement_product_id), None)
        panel = observe_surface(
            merch,
            start=start,
            end=end,
            surface="product_detail",
            product_ids={pair.complement_product_id},
            anchor_id=pair.anchor_product_id,
            policy_version=policy.version,
        )
        fact: JsonObject = {
            "pair": pair.model_dump(mode="json"),
            "anchor_panel": panel.model_dump(mode="json"),
        }
        pair_evidence.append(fact)
        if (
            panel.eligible_sessions >= 100
            and len(panel.days) >= 2
            and panel.exposures < 20
            and complement is not None
            and complement.id not in policy.controls.excluded_product_ids
            and not complement.low_stock
            and complement.id in reports
            and search[complement.id].orders > 0
        ):
            useful_pairs.append(fact)
    history = [r for r in state.command_history if r.action_type == "set_recommendation_policy"]
    pdp_reasons = []
    prior_pdp: JsonObject | None = None
    for record in sorted(history, key=lambda r: r.created_at, reverse=True):
        previous = RecommendationPolicyState.model_validate(
            (record.after_state or {})["recommendation_policy"]
        )
        if previous.controls.strategy != "complements":
            continue
        previous_assessment = reassess(
            merch,
            product_ids=None,
            started=record.created_at,
            now=state.current_time,
            surface="product_detail",
            ends_at=previous.ends_at,
        )
        prior_pdp = previous_assessment.model_dump(mode="json")
        if previous_assessment.classification == "insufficient":
            pdp_reasons.append("PRIOR_PDP_OUTCOME_INSUFFICIENT_FOR_RETEST")
        elif previous_assessment.review_required:
            pdp_reasons.append("PRIOR_PDP_OBSERVED_POOR_NO_SUPPORT_FOR_TOGGLING_BACK")
        break
    if history and state.current_time - max(r.created_at for r in history) < timedelta(days=7):
        pdp_reasons.append("WAIT_FOR_PRIOR_PDP_MEASUREMENT_AND_NEW_VERSION_COHORT")
    controls = policy.controls.model_copy(deep=True)
    controls.strategy = "complements"
    controls.inventory_priority = Decimal("0.05") if kind == "clearance" else Decimal(0)
    controls.minimum_relevance = max(controls.minimum_relevance, limits.minimum_relevance)
    if policy.controls.strategy == "complements":
        pdp_reasons.append("COMPLEMENTS_ALREADY_ACTIVE_REASSESS_INSTEAD_OF_REPEAT")
    add(
        ActionType.SET_RECOMMENDATION_POLICY,
        "pdp:complements",
        {
            "expected_version": policy.version,
            "controls": controls.model_dump(mode="json"),
            "duration_hours": duration,
        },
        {
            "current_policy": policy.model_dump(mode="json", exclude={"command_key"}),
            "prior_complement_outcome": prior_pdp,
            "pair_observations": pair_evidence[:128],
            "matching_pair_count": len(pair_evidence),
            "supported_pair_count": len(useful_pairs),
            "observational_gap": (
                "compatible product absent beside its explicit anchor, not all PDPs"
            ),
        },
        pdp_reasons,
        opportunity=bool(useful_pairs),
        enough=bool(useful_pairs),
        excess=sum(
            p.total_inventory
            for p in products
            if p.excess_inventory
            and any(link.complement_product_id == p.id for link in merch.compatibility)
        ),
        variants=sum(len(p.variants) for p in products),
        rank=1,
    )
    if policy.starts_at is not None:
        assessment = reassess(
            merch,
            product_ids=None,
            started=policy.starts_at,
            now=state.current_time,
            surface="product_detail",
            ends_at=policy.ends_at,
        )
        controls = policy.controls.model_copy(deep=True)
        controls.strategy = "alternatives"
        add(
            ActionType.SET_RECOMMENDATION_POLICY,
            "pdp:reassess",
            {
                "expected_version": policy.version,
                "controls": controls.model_dump(mode="json"),
                "duration_hours": max(24, duration),
            },
            {"assessment": assessment.model_dump(mode="json"), "policy_version": policy.version},
            [
                reason
                for reason in pdp_reasons
                if reason == "WAIT_FOR_PRIOR_PDP_MEASUREMENT_AND_NEW_VERSION_COHORT"
            ]
            + ([] if assessment.review_required else [assessment.reason]),
            opportunity=assessment.review_required and policy.controls.strategy == "complements",
            enough=assessment.classification != "insufficient",
            classification="observed_stop",
            rank=0,
        )

    for row in rows:
        row.reason_codes = sorted(set(row.reason_codes))
    eligible_candidates = sorted((r for r in rows if not r.reason_codes), key=candidate_order)
    for index, row in enumerate(eligible_candidates):
        if index >= MAX_DRAFTS:
            row.reason_codes.append("BOUNDED_CANDIDATE_CAP_DEFERRED")
            row.disposition = "deferred"
        else:
            row.candidate_generated = True
            row.disposition = "awaiting_compilation_and_policy"
    rows.append(
        DecisionCandidate(
            key="unchanged",
            action_type=ActionType.NO_OP,
            allowed_by_goal=True,
            opportunity_detected=True,
            sufficient_observations=True,
            candidate_generated=True,
            classification="unchanged",
            objective=kind,
            disposition="comparison",
            reason_codes=[
                "RETAIN_CURRENT_CONFIGURATION_UNLESS_A_SUPPORTED_CANDIDATE_PASSES_POLICY"
            ],
            evidence={
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "economic_effect": "no new intervention; existing controls still expire",
            },
        )
    )
    return sorted(rows, key=lambda r: r.key)


def observation_fingerprint(rows: list[DecisionCandidate]) -> str:
    return canonical_hash([{"key": r.key, "evidence": r.evidence} for r in rows])
