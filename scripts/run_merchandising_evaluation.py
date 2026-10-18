#!/usr/bin/env python3
"""Registered paired evaluation through real durable services; no model planning calls."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.merchandising_evidence import merchandising_evidence
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerRunRequest,
    GoalCreateRequest,
    PolicyUpdateRequest,
)
from open_commerce.core.enums import ActionStatus, ActionType, AutonomyMode, GoalStatus
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.learned_embeddings import MiniLMEmbeddingProvider
from open_commerce.simulator.durable import load_state
from open_commerce.simulator.merchandising_catalog import FAMILIES
from open_commerce.simulator.merchandising_models import PriceRevision, ProductOutcomes
from open_commerce.simulator.models import DiscountState, SimulatorState, TrafficChannel
from open_commerce.telemetry.diagnostics import exception_diagnostic

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "examples/eval/merchandising-v1/protocol.md"
CASES = (
    "overstock_exposure",
    "poor_conversion",
    "active_promotion",
    "uncertain_price_response",
    "irrelevant_high_margin",
    "explicit_complements",
    "no_discount_clearance",
    "insufficient_data",
    "already_good",
)
SEEDS = (11, 23, 47)


def encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2, default=str).encode() + b"\n"


def sources() -> dict[str, str]:
    paths = sorted((ROOT / "packages/backend/src").rglob("*.py"))
    paths += [ROOT / "uv.lock", PROTOCOL, Path(__file__)]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def goal_request(case: str, seed: int) -> GoalCreateRequest:
    limits = MerchandisingConstraints(promotion_cap_minor=50_000)
    values: dict[str, object] = {"merchandising": limits, "seed": seed, "horizon_days": 14}
    if case == "no_discount_clearance":
        limits.max_effective_discount = Decimal(0)
        limits.promotion_cap_minor = 0
        limits.prohibited_actions.add(ActionType.CREATE_DISCOUNT)
        values.update(
            objective_metric="units_sold",
            objective_direction="maximize",
            objective_scope="excess_inventory",
        )
    if case in {"uncertain_price_response", "explicit_complements"}:
        values["allowed_action_types"] = {
            ActionType.NO_OP,
            ActionType.SET_VARIANT_PRICE
            if case == "uncertain_price_response"
            else ActionType.SET_RECOMMENDATION_POLICY,
        }
    return GoalCreateRequest.model_validate(values)


def configure_world(state: SimulatorState, case: str) -> None:
    """Declared exogenous fixtures only, before any observation or action."""
    assert state.merchandising is not None and not state.metrics
    state.traffic_channels = [
        TrafficChannel(
            id=f"fixed_{n}", label=f"Fixed external {n}", base_sessions=400, search_surface=True
        )
        for n in range(3)
    ]
    if case == "overstock_exposure":
        original = next(p for p in state.products if p.id == "merch_hiking_boots_1")
        for n in range(5, 9):
            clone = original.model_copy(deep=True)
            clone.id = clone.source_product_id = f"merch_hiking_boots_{n}"
            clone.brand = f"FixtureBrand{n}"
            clone.title = f"{clone.brand} Waterproof Hiking Boots"
            clone.excess_inventory = n == 8
            for i, variant in enumerate(clone.variants):
                variant.id = variant.source_variant_id = f"{clone.id}_v{i + 1}"
                variant.sku = f"FIXTURE-BOOT-{n}-{i + 1}"
                variant.inventory = variant.initial_inventory = 240 if n == 8 else 90
                state.merchandising.prices[variant.id] = PriceRevision(
                    reference_price_minor=variant.original_price_minor
                )
            state.products.append(clone)
    if case == "poor_conversion":
        for product in state.products:
            if "hiking_boots" in product.id:
                product.quality_score = Decimal("0.05")
    if case == "active_promotion":
        state.discounts.append(
            DiscountState(
                id="fixture_existing_boot_offer",
                code=None,
                discount_kind="percentage",
                value=Decimal("0.10"),
                starts_at=state.current_time,
                ends_at=state.current_time + timedelta(days=14),
                product_ids=[p.id for p in state.products if "hiking_boots" in p.id],
                created_by_command="pre-existing-evaluation-world",
                maximum_cost_minor=50_000,
            )
        )
    if case == "irrelevant_high_margin":
        for product in state.products:
            if "headphones" in product.id:
                product.excess_inventory = True
                for variant in product.variants:
                    variant.cost_minor = 1
    if case == "already_good":
        for product in state.products:
            product.quality_score = Decimal("0.95")
            product.excess_inventory = False


def divide(a: int | float, b: int | float) -> float | None:
    return a / b if b else None


def observed_conditions(state: SimulatorState) -> dict[str, object]:
    merch = state.merchandising
    assert merch is not None
    rows = {}
    for product in state.products:
        outcome = merch.product_outcomes.get(product.id, ProductOutcomes())
        peers = [
            merch.product_outcomes.get(p.id, ProductOutcomes()).search_exposures
            for p in state.products
            if p.category == product.category and p.id != product.id
        ]
        rows[product.id] = {
            "outcomes": outcome.model_dump(mode="json"),
            "conversion_per_search_exposure": divide(outcome.orders, outcome.search_exposures),
            "observed_exposure_gap": bool(
                peers
                and sum(peers) >= 200
                and outcome.orders >= 1
                and outcome.search_exposures * len(peers) * 2 < sum(peers)
            ),
            "high_exposure_low_conversion": outcome.search_exposures >= 200
            and outcome.orders * 100 < outcome.search_exposures,
        }
    return {"eligible_sessions": sum(m.sessions for m in state.metrics), "products": rows}


def summarize(initial: SimulatorState, final: SimulatorState) -> dict[str, Any]:
    assert initial.merchandising is not None and final.merchandising is not None
    before, merch = initial.merchandising, final.merchandising
    metrics = final.metrics[len(initial.metrics) :]

    def total(field: str) -> int:
        return sum(int(getattr(m, field)) for m in metrics)

    net = total("gross_revenue_minor") - total("discounts_minor")
    profit, sessions, orders = (
        total("contribution_profit_minor"),
        total("sessions"),
        total("orders"),
    )
    products = {}
    categories: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    for product in initial.products:
        left = before.product_outcomes.get(product.id, ProductOutcomes()).model_dump()
        right = merch.product_outcomes.get(product.id, ProductOutcomes()).model_dump()
        changes = {key: value - left[key] for key, value in right.items()}
        for key, value in changes.items():
            categories[product.category][key] += value
        categories[product.category]["starting_inventory_units"] += product.total_inventory
        products[product.id] = {
            **changes,
            "category": product.category,
            "excess_inventory": product.excess_inventory,
            "starting_inventory_units": product.total_inventory,
            "sell_through": divide(changes["units"], product.total_inventory),
            "net_realized_unit_price_minor": divide(changes["net_revenue_minor"], changes["units"]),
        }
    for row in categories.values():
        row["sell_through"] = divide(row["units"], row["starting_inventory_units"])
    receipts = [r for key, r in merch.redemptions.items() if key not in before.redemptions]
    redeemed = [r for r in receipts if r.status == "redeemed"]
    floor_breaches = [
        r.order_key
        for r in redeemed
        if r.economics.unit_margin is None
        or r.economics.unit_margin < merch.constraints.minimum_unit_margin
    ]
    discount_breaches = [
        r.order_key
        for r in redeemed
        if r.economics.effective_discount_rate > merch.constraints.max_effective_discount
    ]
    products_by_id = {p.id: p for p in final.products}
    pairs = {(p.anchor_product_id, p.complement_product_id) for p in merch.compatibility}
    serving: Counter[str] = Counter()
    violations = []
    for batch in merch.serving_log.values():
        if batch.day < initial.current_time.date().isoformat():
            continue
        for product_id in batch.product_ids:
            weight = batch.eligible_sessions
            serving[f"{batch.surface}_exposures"] += weight
            if batch.relevance[product_id] < merch.constraints.minimum_relevance:
                violations.append({"kind": "relevance_floor", "product_id": product_id})
            if not all(batch.constraint_matches[product_id].values()):
                violations.append({"kind": "hard_constraint", "product_id": product_id})
            if batch.surface == "search":
                family = next(
                    (f for f in FAMILIES if f"{f.category} {f.title}" == batch.query), None
                )
                relevant = (
                    family is not None
                    and products_by_id[product_id].attributes.get("product_type") == family.id
                )
                serving["search_authored_family_relevant_exposures"] += weight * relevant
            else:
                assert batch.anchor_product_id is not None
                anchor = products_by_id[batch.anchor_product_id]
                related = (
                    (anchor.id, product_id) in pairs
                    if batch.recommendation_strategy == "complements"
                    else (
                        anchor.category == products_by_id[product_id].category
                        and anchor.attributes["product_type"]
                        == products_by_id[product_id].attributes["product_type"]
                    )
                )
                serving["pdp_explicitly_eligible_exposures"] += weight * related
                if not related:
                    violations.append(
                        {"kind": "unsupported_relationship", "product_id": product_id}
                    )
    return {
        "contribution_profit_minor": profit,
        "eligible_sessions": sessions,
        "profit_per_eligible_session_minor": divide(profit, sessions),
        "conversion_rate": divide(orders, sessions),
        "orders": orders,
        "units": total("units_sold"),
        "net_revenue_minor": net,
        "net_average_order_value_minor": divide(net, orders),
        "promotion_redemption_value_minor": merch.promotion_spent_minor
        - before.promotion_spent_minor,
        "promotion_spent_total_minor": merch.promotion_spent_minor,
        "ad_spend_minor": total("ad_spend_minor"),
        "model_calls": 0,
        "model_cost_minor": 0,
        "products": products,
        "categories": dict(categories),
        "serving": dict(serving),
        "search_authored_family_precision": divide(
            serving["search_authored_family_relevant_exposures"], serving["search_exposures"]
        ),
        "pdp_eligibility_rate": divide(
            serving["pdp_explicitly_eligible_exposures"], serving["product_detail_exposures"]
        ),
        "hard_policy_violations": violations
        + [{"kind": "promotion_cap"}]
        * int(merch.promotion_spent_minor > merch.constraints.promotion_cap_minor),
        "known_unit_floor_breaches": floor_breaches,
        "combined_discount_breaches": discount_breaches,
        "negative_aggregate_profit_days": sum(m.contribution_profit_minor < 0 for m in metrics),
        "aggregate_net_margin_below_unit_floor_days": sum(
            m.gross_revenue_minor > m.discounts_minor
            and Decimal(m.contribution_profit_minor) / (m.gross_revenue_minor - m.discounts_minor)
            < merch.constraints.minimum_unit_margin
            for m in metrics
        ),
        "declined_redemptions": dict(Counter(r.reason for r in receipts if r.status == "declined")),
    }


async def run_arm(database: RuntimeDatabase, case: str, seed: int, arm: str) -> dict[str, Any]:
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    request = goal_request(case, seed)
    goal = await service.create_goal(tenant_id=tenant, request=request, idempotency_key="create")
    await service.update_policy(
        tenant_id=tenant,
        request=PolicyUpdateRequest(
            allowed_action_types=request.allowed_action_types,
            per_action_modes={
                a: AutonomyMode.APPROVAL_REQUIRED for a in request.allowed_action_types
            },
        ),
        idempotency_key="evaluation-operator-reviewed-policy",
    )
    async with database.transaction(tenant, write=True) as session:
        state = await load_state(session, tenant, goal.simulator_instance_id)
        configure_world(state, case)
        await SqlSimulatorRepository(session).save_state(state)
        world = state.model_dump(mode="json")
    warmup = 0 if case == "insufficient_data" else 4
    if warmup:
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=24 * warmup,
            idempotency_key="warmup",
        )
    initial = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    await service.set_goal_status(
        tenant_id=tenant, goal_id=goal.spec.id, status=GoalStatus.ACTIVE, idempotency_key="activate"
    )
    records = []
    decisions = []
    errors = []
    observations = []
    counts: Counter[str] = Counter()
    for day in range(1 if case == "insufficient_data" else 4):
        if arm == "deterministic":
            try:
                run = await service.run_goal(
                    tenant_id=tenant,
                    goal_id=goal.spec.id,
                    request=ControllerRunRequest(),
                    idempotency_key=f"cycle-{day}",
                )
                run = await service.process_run(tenant_id=tenant, run_id=run.id)
                decisions.append(run.model_dump(mode="json"))
                counts["cycles"] += 1
                rejections = run.summary.get("compiler_rejections", [])
                assert isinstance(rejections, list)
                counts["compiler_rejections"] += len(rejections)
                counts["waits"] += int(not run.intent_drafts)
                for record in (await service.list_actions(tenant_id=tenant, run_id=run.id)).items:
                    counts["proposals"] += 1
                    counts[f"proposed_{record.action.intent.type}"] += 1
                    if record.action.status == ActionStatus.AWAITING_APPROVAL:
                        record = await service.approve_action(
                            tenant_id=tenant,
                            action_id=record.action.id,
                            request=ActionApprovalRequest(
                                action_version_hash=record.action_version_hash
                            ),
                            actor_roles={"owner", "operator"},
                            decision="approve",
                            idempotency_key=f"approve-{record.action.id}",
                        )
                    if record.action.status in {ActionStatus.APPROVED, ActionStatus.EXECUTABLE}:
                        record = await service.execute_action(
                            tenant_id=tenant,
                            action_id=record.action.id,
                            idempotency_key=f"execute-{record.action.id}",
                        )
                    counts[f"final_{record.action.status.value}"] += 1
                    records.append(record.model_dump(mode="json"))
            except Exception as exc:
                errors.append(
                    {"phase": "controller", "day": day, "diagnostic": exception_diagnostic(exc)}
                )
        await service.simulator_service.advance(
            tenant_id=tenant,
            instance_id=goal.simulator_instance_id,
            hours=24,
            idempotency_key=f"observe-{day}",
        )
        current = await service.simulator_service.get_full_state(
            tenant_id=tenant, instance_id=goal.simulator_instance_id
        )
        observations.append(merchandising_evidence(current, tenant_id=tenant, view="outcomes"))
    final = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    return {
        "case": case,
        "seed": seed,
        "arm": arm,
        "split": "held_out_seed" if seed == 47 else "development",
        "goal": goal.model_dump(mode="json"),
        "initial_world": world,
        "warmup_conditions": observed_conditions(initial),
        "initial_observed_state": initial.model_dump(mode="json"),
        "final_state": final.model_dump(mode="json"),
        "decisions": decisions,
        "actions": records,
        "observations": observations,
        "counts": dict(counts),
        "errors": errors,
        "summary": summarize(initial, final),
    }


def comparisons(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for case in CASES:
        pairs = []
        for seed in SEEDS:
            items = {r["arm"]: r for r in rows if r["case"] == case and r["seed"] == seed}
            if len(items) != 2 or any("summary" not in r for r in items.values()):
                continue
            base, agent = items["no_intervention"]["summary"], items["deterministic"]["summary"]
            pairs.append(
                {
                    "seed": seed,
                    "matched_sessions": base["eligible_sessions"] == agent["eligible_sessions"],
                    "contribution_profit_delta_minor": agent["contribution_profit_minor"]
                    - base["contribution_profit_minor"],
                    "profit_per_session_delta_minor": agent["profit_per_eligible_session_minor"]
                    - base["profit_per_eligible_session_minor"],
                    "orders_delta": agent["orders"] - base["orders"],
                    "units_delta": agent["units"] - base["units"],
                    "product_deltas": {
                        key: {
                            field: agent["products"][key][field] - base["products"][key][field]
                            for field in [
                                "search_exposures",
                                "recommendation_exposures",
                                "orders",
                                "units",
                                "contribution_profit_minor",
                            ]
                        }
                        for key in base["products"]
                    },
                }
            )
        deltas = [p["contribution_profit_delta_minor"] for p in pairs]
        interval = None
        if len(deltas) == 3:
            mean = statistics.mean(deltas)
            half = 4.302652730 * statistics.stdev(deltas) / math.sqrt(3)
            interval = [mean - half, mean + half]
        result[case] = {
            "pairs": pairs,
            "mean_profit_delta_minor": statistics.mean(deltas) if deltas else None,
            "descriptive_95_percent_t_interval_minor": interval,
        }
    return result


async def main(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise SystemExit(
            "Refusing to overwrite an evaluation; choose a new explicit reproduction directory"
        )
    args.output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "source_hashes": sources(),
        "model_id": MiniLMEmbeddingProvider.model_id,
        "model_calls": 0,
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "artifacts": [],
        "rows": [],
    }
    prior_rows: list[dict[str, Any]] = []
    if args.recover_from:
        prior_path = args.recover_from / "manifest.json"
        prior = json.loads(prior_path.read_bytes())
        driver = str(Path(__file__).resolve().relative_to(ROOT))
        previous_sources = {k: v for k, v in prior["source_hashes"].items() if k != driver}
        current_sources = {k: v for k, v in manifest["source_hashes"].items() if k != driver}
        if previous_sources != current_sources:
            raise RuntimeError("Recovery requires identical scenario and product sources")
        prior_rows = [r for r in prior["rows"] if "summary" in r]
        manifest["recovery"] = {
            "prior_run": args.recover_from.name,
            "prior_manifest_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
            "reason": "Local Compose dependency restart interrupted first-pass evaluation",
            "new_independent_cases": 0,
            "retained_prior_successes": len(prior_rows),
            "prior_error_records": len(prior["rows"]) - len(prior_rows),
            "driver_change": (
                "Recovery orchestration only; runtime and fixture source hashes unchanged"
            ),
        }
    (args.output / "registration.json").write_bytes(encode(manifest))
    source_archive = {name: (ROOT / name).read_text() for name in manifest["source_hashes"]}
    archive = gzip.compress(encode(source_archive), mtime=0)
    (args.output / "sources.json.gz").write_bytes(archive)
    manifest["source_archive_sha256"] = hashlib.sha256(archive).hexdigest()
    url = make_url(os.environ["OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL"])
    name = f"opencommerce_merch_eval_{uuid4().hex}"
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    database = None
    created = False
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
        created = True
        database_url = url.set(database=name).render_as_string(hide_password=False)
        await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            cwd=ROOT,
            env={**os.environ, "OPEN_COMMERCE_DATABASE_URL": database_url},
        )
        settings = Settings().model_copy(
            update={
                "database_url": database_url,
                "environment": "test",
                "search_embedding_backend": "minilm",
                "search_model_directory": args.model_directory.resolve(),
            }
        )
        database = RuntimeDatabase(settings)
        rows = list(prior_rows)
        for case in CASES:
            for seed in SEEDS:
                for arm in ("no_intervention", "deterministic"):
                    if any(
                        r["case"] == case and r["seed"] == seed and r["arm"] == arm
                        for r in prior_rows
                    ):
                        continue
                    if sources() != manifest["source_hashes"]:
                        raise RuntimeError(
                            "Evaluation sources changed during rollout; preserve partial evidence"
                        )
                    try:
                        raw = await run_arm(database, case, seed, arm)
                    except Exception as exc:
                        raw = {
                            "case": case,
                            "seed": seed,
                            "arm": arm,
                            "error": exception_diagnostic(exc),
                        }
                    filename = f"{case}-{seed}-{arm}.json.gz"
                    content = gzip.compress(encode(raw), mtime=0)
                    (args.output / filename).write_bytes(content)
                    manifest["artifacts"].append(
                        {"path": filename, "sha256": hashlib.sha256(content).hexdigest()}
                    )
                    row = {
                        k: v
                        for k, v in raw.items()
                        if k in {"case", "seed", "arm", "summary", "counts", "errors", "error"}
                    }
                    rows.append(row)
                    manifest["rows"] = rows
                    manifest["comparisons"] = comparisons(rows)
                    (args.output / "manifest.json").write_bytes(encode(manifest))
                    print(
                        json.dumps(
                            {
                                "case": case,
                                "seed": seed,
                                "arm": arm,
                                "profit_minor": raw.get("summary", {}).get(
                                    "contribution_profit_minor"
                                ),
                                "counts": raw.get("counts"),
                                "error": raw.get("error"),
                                "controller_errors": len(raw.get("errors", [])),
                            }
                        ),
                        flush=True,
                    )
    finally:
        if database:
            await database.close()
        if created:
            async with admin.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--recover-from", type=Path)
    asyncio.run(main(parser.parse_args()))
