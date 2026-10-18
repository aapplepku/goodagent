"""Registered three-arm durable evaluation; planner substitution is not action injection."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import make_url, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.merchandising_planner import plan_merchandising
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerRunRequest,
    GoalCreateRequest,
    PolicyUpdateRequest,
)
from open_commerce.core.enums import ActionStatus, ActionType, AutonomyMode, GoalStatus
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state
from open_commerce.simulator.merchandising_models import PriceRevision
from open_commerce.simulator.models import DiscountState, SimulatorState, TrafficChannel
from open_commerce.telemetry.diagnostics import exception_diagnostic
from open_commerce.worker.jobs import JobRunner
from scripts.merchandising_v1_frozen import plan_merchandising as frozen_planner
from scripts.run_merchandising_evaluation import encode, summarize

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "examples/eval/merchandising-decisions-v2/protocol.md"
PROTOCOL_HASH = "af7ae6eb13655beab4f99885afa383f9de10cd6d8f8a07d9cd07b019e38758d1"
AMENDMENT = PROTOCOL.with_name("protocol-amendment-1.md")
AMENDMENT_HASH = "3f801ff613e50d5774cb1d18d19fe7a69586cdc458574fa14b2bf5d2fd122f04"
FROZEN_HASH = "d10569cc8f3cee53a205ea2e0b5698ee4302fa79023a6287c997784fb8121252"
CONDITIONS = {
    "development": ("crowded_boots", "compatible_panels", "bounded_offer", "thin_history"),
    "held_out": (
        "crowded_storage",
        "compatible_outdoors",
        "offer_with_alternatives",
        "satisfactory_stock",
    ),
}
SEEDS = {"development": (71,), "held_out": (107, 131, 163)}
ARMS = ("no_intervention", "frozen_v1", "revised")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources() -> dict[str, str]:
    paths = sorted((ROOT / "packages/backend/src").rglob("*.py"))
    paths += [
        Path(__file__),
        ROOT / "scripts/merchandising_v1_frozen.py",
        ROOT / "scripts/run_merchandising_evaluation.py",
        PROTOCOL,
        AMENDMENT,
        ROOT / "uv.lock",
    ]
    paths += sorted((ROOT / "examples/scenarios").rglob("*.json"))
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def request_for(case: str, seed: int) -> GoalCreateRequest:
    limits = MerchandisingConstraints(promotion_cap_minor=30_000)
    options: dict[str, object] = {
        "merchandising": limits,
        "seed": seed,
        "horizon_days": 16 if case == "thin_history" else 24,
    }
    if case.startswith("crowded_"):
        limits.max_effective_discount = Decimal(0)
        limits.promotion_cap_minor = 0
        limits.prohibited_actions.add(ActionType.CREATE_DISCOUNT)
        options.update(
            objective_metric="units_sold",
            objective_scope="excess_inventory",
            objective_direction="maximize",
        )
    if case.startswith("compatible_"):
        options.update(
            objective_metric="search_attributed_purchases",
            objective_scope="store",
            objective_direction="maximize",
            allowed_action_types={
                ActionType.NO_OP,
                ActionType.SET_SEARCH_BOOST,
                ActionType.SET_RECOMMENDATION_POLICY,
            },
        )
    return GoalCreateRequest.model_validate(options)


def configure(state: SimulatorState, case: str) -> None:
    """Evaluator-owned initial conditions only; no outcomes or actions are inserted."""
    assert state.merchandising is not None and not state.metrics
    state.traffic_channels = [
        TrafficChannel(
            id=f"fixed_{n}", label=f"Fixed external {n}", base_sessions=600, search_surface=True
        )
        for n in range(3)
    ]
    if case.startswith("crowded_"):
        family = "hiking_boots" if case == "crowded_boots" else "food_containers"
        count, stock, excess_stock = (8, 180, 600) if case == "crowded_boots" else (9, 200, 700)
        original = next(p for p in state.products if p.id == f"merch_{family}_1")
        for n in range(5, count + 1):
            clone = original.model_copy(deep=True)
            clone.id = clone.source_product_id = f"merch_{family}_{n}"
            clone.brand = f"RegisteredBrand{n}"
            clone.title = original.title.replace(original.brand, clone.brand)
            for i, variant in enumerate(clone.variants, start=1):
                variant.id = variant.source_variant_id = f"{clone.id}:v{i}"
                variant.sku = f"REGISTERED-{family}-{n}-{i}"
                state.merchandising.prices[variant.id] = PriceRevision(
                    reference_price_minor=variant.original_price_minor
                )
            state.products.append(clone)
        for p in state.products:
            if p.attributes.get("product_type") == family:
                p.excess_inventory = p.id == f"merch_{family}_{count}"
                for v in p.variants:
                    v.inventory = v.initial_inventory = (
                        excess_stock if p.excess_inventory else stock
                    )
    if case in {"compatible_panels", "compatible_outdoors", "satisfactory_stock"}:
        for p in state.products:
            stock = (
                400
                if case == "compatible_outdoors" and p.category == "outdoor"
                else 160
                if case == "compatible_outdoors"
                else 300
            )
            for v in p.variants:
                v.inventory = v.initial_inventory = stock
            if case == "satisfactory_stock":
                p.quality_score, p.excess_inventory = Decimal("0.90"), False
    if case in {"bounded_offer", "offer_with_alternatives"}:
        family = "wall_chargers" if case == "bounded_offer" else "headphones"
        targets = [p for p in state.products if p.attributes.get("product_type") == family]
        for p in targets:
            p.quality_score = Decimal("0.10") if case == "bounded_offer" else Decimal("0.20")
        state.discounts.append(
            DiscountState(
                id="registered_existing_offer",
                code=None,
                discount_kind="percentage",
                value=Decimal("0.05") if case == "bounded_offer" else Decimal("0.10"),
                starts_at=state.current_time + timedelta(days=2),
                ends_at=state.current_time + timedelta(days=24),
                product_ids=[p.id for p in targets],
                created_by_command="registered_initial_world",
                maximum_cost_minor=30_000,
            )
        )


async def run_arm(database: RuntimeDatabase, case: str, seed: int, arm: str) -> dict[str, Any]:
    tenant = uuid4()
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    request = request_for(case, seed)
    goal = await service.create_goal(tenant_id=tenant, request=request, idempotency_key="create")
    await service.update_policy(
        tenant_id=tenant,
        request=PolicyUpdateRequest(
            allowed_action_types=request.allowed_action_types,
            per_action_modes={
                a: AutonomyMode.APPROVAL_REQUIRED for a in request.allowed_action_types
            },
        ),
        idempotency_key="same-operator-policy",
    )
    async with database.transaction(tenant, write=True) as session:
        state = await load_state(session, tenant, goal.simulator_instance_id)
        configure(state, case)
        await SqlSimulatorRepository(session).save_state(state)
        world = state.model_dump(mode="json")
    warmup, days = (0, 1) if case == "thin_history" else (6, 12)
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
    decisions, actions, errors, observed = [], [], [], []
    counts: Counter[str] = Counter()
    planner = frozen_planner if arm == "frozen_v1" else plan_merchandising
    # Only implementation selection is substituted. No draft or selected action is injected.
    with patch("open_commerce.controller.durable.plan_merchandising", planner):
        for day in range(days):
            print(json.dumps({"progress": [case, seed, arm, day]}), flush=True)
            active = (
                await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
            ).spec.status == GoalStatus.ACTIVE
            if arm != "no_intervention" and not active:
                counts["safety_paused_waits"] += 1
            if arm != "no_intervention" and active:
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
                    records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
                    counts["waits"] += int(not records)
                    for record in records:
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
                        actions.append(record.model_dump(mode="json"))
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
            state = await service.simulator_service.get_full_state(
                tenant_id=tenant, instance_id=goal.simulator_instance_id
            )
            async with database.transaction(tenant) as session:
                measurement_jobs = list(
                    await session.scalars(
                        select(WorkflowJob).where(
                            WorkflowJob.tenant_id == tenant,
                            WorkflowJob.kind == "measure",
                            WorkflowJob.instance_id == goal.simulator_instance_id,
                        )
                    )
                )
            for job in measurement_jobs:
                await JobRunner(database, tenant)._measure(job)
            observed.append(
                {
                    "day": day,
                    "time": state.current_time.isoformat(),
                    "metrics": state.metrics[-1].model_dump(mode="json"),
                    "goal_status": (
                        await service.get_goal(tenant_id=tenant, goal_id=goal.spec.id)
                    ).spec.status.value,
                }
            )
    final = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    actions = [
        (await service.get_action(tenant_id=tenant, action_id=record.action.id)).model_dump(
            mode="json"
        )
        for record in (await service.list_actions(tenant_id=tenant, goal_id=goal.spec.id)).items
    ]
    return {
        "case": case,
        "seed": seed,
        "arm": arm,
        "goal": goal.model_dump(mode="json"),
        "initial_world": world,
        "initial_observed_state": initial.model_dump(mode="json"),
        "final_state": final.model_dump(mode="json"),
        "decisions": decisions,
        "actions": actions,
        "observations": observed,
        "counts": dict(counts),
        "errors": errors,
        "summary": summarize(initial, final),
        "model_calls": 0,
        "manual_action_injection": False,
        "measurement_dispatch": (
            "existing scoped JobRunner._measure handler; queue timing not graded"
        ),
    }


async def main(args: argparse.Namespace) -> None:
    assert digest(PROTOCOL) == PROTOCOL_HASH
    assert digest(AMENDMENT) == AMENDMENT_HASH
    assert digest(ROOT / "scripts/merchandising_v1_frozen.py") == FROZEN_HASH
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an evaluation")
    if args.split == "held_out":
        if not args.frozen_commit:
            raise SystemExit("Held-out requires the full pre-outcome frozen commit SHA")
        head = (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            )
        ).strip()
        dirty = await asyncio.to_thread(
            subprocess.check_output, ["git", "status", "--porcelain"], cwd=ROOT
        )
        if head != args.frozen_commit or dirty:
            raise SystemExit("Held-out requires a clean exact frozen checkout before outcomes")
    cases = [args.case] if args.case else list(CONDITIONS[args.split])
    if any(c not in CONDITIONS[args.split] for c in cases):
        raise SystemExit("Case is not in the registered split")
    arms = [args.arm] if args.arm else ARMS
    args.output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "version": "merchandising-decisions-v2",
        "split": args.split,
        "protocol_sha256": PROTOCOL_HASH,
        "protocol_amendment_sha256": AMENDMENT_HASH,
        "source_hashes": sources(),
        "frozen_commit": args.frozen_commit,
        "artifacts": [],
        "rows": [],
        "model_calls": 0,
    }
    (args.output / "registration.json").write_bytes(encode(manifest))
    archive = gzip.compress(
        encode({p: (ROOT / p).read_text() for p in manifest["source_hashes"]}), mtime=0
    )
    (args.output / "sources.json.gz").write_bytes(archive)
    manifest["source_archive_sha256"] = hashlib.sha256(archive).hexdigest()
    url = make_url(os.environ["OPEN_COMMERCE_TEST_ADMIN_DATABASE_URL"])
    name = f"opencommerce_decisions_{uuid4().hex}"
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    database, created = None, False
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
        database = RuntimeDatabase(
            Settings().model_copy(
                update={
                    "database_url": database_url,
                    "environment": "test",
                    "search_embedding_backend": "minilm",
                    "search_model_directory": args.model_directory.resolve(),
                }
            )
        )
        for case in cases:
            for seed in SEEDS[args.split]:
                for arm in arms:
                    if sources() != manifest["source_hashes"]:
                        raise RuntimeError(
                            "Source changed; retain partial results, do not mix versions"
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
                    manifest["rows"].append(row)
                    (args.output / "manifest.json").write_bytes(encode(manifest))
                    if sources() != manifest["source_hashes"]:
                        raise RuntimeError(
                            "Source changed during an arm; retained result is diagnostic only"
                        )
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
    parser.add_argument("--split", choices=CONDITIONS, default="development")
    parser.add_argument("--case")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--frozen-commit")
    asyncio.run(main(parser.parse_args()))
