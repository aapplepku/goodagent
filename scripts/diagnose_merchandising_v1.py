"""Replay retained v1 initial decisions; hypothetical alternatives never execute."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from open_commerce.controller.compiler import ActionCompiler
from open_commerce.controller.models import ControllerPolicyConfig
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.core.enums import ActionType, AutonomyMode
from open_commerce.core.goals import GoalSpec
from open_commerce.core.money import Money
from open_commerce.simulator.merchandising_economics import investigate_variant
from open_commerce.simulator.merchandising_models import ProductOutcomes
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.scenarios import SIMULATOR_CAPABILITIES
from scripts.merchandising_v1_frozen import plan_merchandising

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = (
    ActionType.DISABLE_DISCOUNT,
    ActionType.SET_SEARCH_BOOST,
    ActionType.SET_RECOMMENDATION_POLICY,
    ActionType.SET_VARIANT_PRICE,
    ActionType.CREATE_DISCOUNT,
    ActionType.NO_OP,
)


def product_predicates(state: SimulatorState) -> list[dict[str, object]]:
    merch = state.merchandising
    assert merch is not None
    rows: list[dict[str, object]] = []
    for product in sorted(state.products, key=lambda p: p.id):
        variants = sorted(
            (v for v in product.variants if v.available and v.inventory > 5),
            key=lambda v: (v.price_minor, v.id),
        )
        observed = merch.product_outcomes.get(product.id, ProductOutcomes())
        peers = [
            merch.product_outcomes.get(p.id, ProductOutcomes()).search_exposures
            for p in state.products
            if p.category == product.category and p.id != product.id
        ]
        report = (
            investigate_variant(
                state, tenant_id=state.tenant_id, product_id=product.id, variant_id=variants[0].id
            )
            if variants
            else None
        )
        search_batches = [
            b
            for b in merch.serving_log.values()
            if b.surface == "search" and product.id in b.product_ids
        ]
        search_keys = {key for b in search_batches for key in b.order_keys}
        search_orders = sum(
            r.status == "redeemed" and r.product_id == product.id
            for key, r in merch.redemptions.items()
            if key in search_keys
        )
        rows.append(
            {
                "product_id": product.id,
                "eligible_variant": variants[0].id if variants else None,
                "excess_inventory": product.excess_inventory,
                "search_exposures": observed.search_exposures,
                "orders_all_surfaces": observed.orders,
                "orders_from_search_batches_only": search_orders,
                "clicks_all_surfaces": observed.clicks,
                "pdp_exposures": observed.recommendation_exposures,
                "peer_exposures_same_category": peers,
                "search_predicate": bool(
                    report
                    and product.excess_inventory
                    and observed.orders > 0
                    and peers
                    and sum(peers) >= 200
                    and observed.search_exposures * len(peers) * 2 < sum(peers)
                    and not any(
                        product.id in r.product_ids
                        and r.active
                        and r.starts_at <= state.current_time < r.ends_at
                        for r in state.search_boosts
                    )
                ),
                "monetary_predicate": bool(
                    report
                    and observed.search_exposures >= 200
                    and observed.orders * 100 < observed.search_exposures
                    and not report.active_promotions
                ),
                "economics": report.model_dump(mode="json") if report else None,
            }
        )
    return rows


def main(output: Path) -> None:
    if output.exists():
        raise SystemExit("Refusing to overwrite retained diagnosis")
    cases = {}
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    inputs = []
    directory = ROOT / "examples/eval/merchandising-v1/results"
    for source in ("registered-first-pass", "infrastructure-recovery"):
        for path in sorted((directory / source).glob("*-deterministic.json.gz")):
            raw = json.loads(gzip.decompress(path.read_bytes()))
            if "summary" not in raw:
                continue
            cases[(raw["case"], raw["seed"])] = (path, raw)
    ledgers = []
    for (case, seed), (path, raw) in sorted(cases.items()):
        inputs.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        counts.update(raw["counts"])
        for decision in raw["decisions"]:
            reasons[decision["summary"]["merchandising_decision"]["reason"]] += 1
        if seed != 11:
            continue
        state = SimulatorState.model_validate(raw["initial_observed_state"])
        goal = GoalSpec.model_validate(raw["goal"]["spec"])
        assert state.merchandising is not None and goal.merchandising is not None
        merch = state.merchandising
        first = raw["decisions"][0]
        run_id = UUID(first["id"])
        replay = plan_merchandising(goal=goal, state=state, run_id=run_id)
        assert replay.decision == first["summary"]["merchandising_decision"]
        assert [d.model_dump(mode="json") for d in replay.drafts] == first["intent_drafts"]
        policy = ControllerPolicyConfig(
            tenant_id=goal.tenant_id,
            allowed_action_types=goal.allowed_action_types,
            per_action_modes={a: AutonomyMode.APPROVAL_REQUIRED for a in goal.allowed_action_types},
            updated_at=state.current_time,
        )
        predicates = product_predicates(state)
        rows = []
        for family in FAMILIES:
            isolated_goal = goal.model_copy(deep=True)
            # Remove only allowlist suppression to expose v1's own family gates.
            assert isolated_goal.merchandising is not None
            isolated_goal.merchandising.prohibited_actions.discard(family)
            isolated_goal.allowed_action_types = {family, ActionType.NO_OP}
            isolated = plan_merchandising(goal=isolated_goal, state=state, run_id=run_id)
            drafts = [d for d in isolated.drafts if d.action_type == family]
            compiled = []
            for draft in drafts:
                action = ActionCompiler().compile_draft(goal=goal, state=state, draft=draft)
                result = PolicyEngine().decide(
                    PolicyContext(
                        goal=goal,
                        policy=policy,
                        action=action,
                        capabilities=SIMULATOR_CAPABILITIES,
                        sample_size=sum(m.sessions for m in state.metrics[-7:]),
                        data_age_minutes={
                            k: 0 for k in ("catalog", "inventory", "orders", "campaigns")
                        },
                        budget_remaining=Money(
                            amount_minor=min(
                                (b.amount.amount_minor for b in goal.budgets), default=0
                            ),
                            currency="USD",
                        ),
                        actions_in_run=1,
                        active_target_keys=set(),
                        recent_target_keys=set(),
                        decision_time=state.current_time,
                    )
                )
                compiled.append(
                    {
                        "action": action.model_dump(mode="json"),
                        "policy": result.model_dump(mode="json"),
                    }
                )
            allowed = family in goal.allowed_action_types - goal.merchandising.prohibited_actions
            selected = (
                not replay.drafts
                if family == ActionType.NO_OP
                else any(d.action_type == family for d in replay.drafts)
            )
            rows.append(
                {
                    "family": family.value,
                    "allowed_by_goal": allowed,
                    "opportunity_under_v1_predicates": bool(drafts),
                    "sufficient_global_observations": sum(m.sessions for m in state.metrics) >= 200,
                    "sufficient_remaining_window": goal.horizon.end_at - state.current_time
                    >= timedelta(hours=24),
                    "global_cooldown": bool(
                        state.command_history
                        and state.current_time - state.command_history[-1].created_at
                        < timedelta(hours=48)
                    ),
                    "hypothetical_draft_when_other_families_suppressed": [
                        d.model_dump(mode="json") for d in drafts
                    ],
                    "actually_generated": any(d.action_type == family for d in replay.drafts),
                    "rejected_before_compilation": not selected,
                    "compiler_policy_diagnostic_only": compiled,
                    "selected": selected,
                    "reason": replay.decision["reason"]
                    if selected
                    else "GOAL_PROHIBITS_FAMILY"
                    if not allowed
                    else "EARLIER_FAMILY_OR_PRODUCT_RETURN"
                    if drafts
                    else isolated.decision["reason"],
                }
            )
        ledgers.append(
            {
                "case": case,
                "seed": seed,
                "classification": "development_regression_replay",
                "first_decision_exactly_reproduced": True,
                "original_selection": replay.decision,
                "family_ledger": rows,
                "product_predicates": predicates,
                "recommendation_version": merch.recommendation_policy.version,
                "recommendation_strategy": merch.recommendation_policy.controls.strategy,
                "compatibility_predicates": [
                    {
                        "pair": p.model_dump(mode="json"),
                        "anchor_clicks_all_surfaces": merch.product_outcomes.get(
                            p.anchor_product_id, ProductOutcomes()
                        ).clicks,
                        "anchor_at_least_100_clicks": merch.product_outcomes.get(
                            p.anchor_product_id, ProductOutcomes()
                        ).clicks
                        >= 100,
                        "complement_has_order": merch.product_outcomes.get(
                            p.complement_product_id, ProductOutcomes()
                        ).orders
                        > 0,
                        "complement_under_20_pdp_exposures": merch.product_outcomes.get(
                            p.complement_product_id, ProductOutcomes()
                        ).recommendation_exposures
                        < 20,
                    }
                    for p in merch.compatibility
                ],
            }
        )
    payload = {
        "frozen_source_sha256": hashlib.sha256(
            (ROOT / "scripts/merchandising_v1_frozen.py").read_bytes()
        ).hexdigest(),
        "inputs": inputs,
        "archived_counts": dict(counts),
        "archived_decision_reasons": dict(reasons),
        "ledgers": ledgers,
        "hypothetical_compilations_executed": False,
        "conversion_warning": (
            "v1 mixes all-surface orders with search-only exposures; "
            "diagnostic reports both numerators"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress((json.dumps(payload, sort_keys=True, indent=2) + "\n").encode(), mtime=0)
    )
    print(
        json.dumps(
            {"counts": dict(counts), "reasons": dict(reasons), "replayed": len(ledgers)}, indent=2
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
