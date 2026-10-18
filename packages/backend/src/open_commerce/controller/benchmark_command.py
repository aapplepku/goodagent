"""Disposable database lifecycle and generated artifacts for controller evaluation."""

import asyncio
import gzip
import json
import os
import platform
import sys
from collections.abc import AsyncIterator
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from importlib.metadata import version
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from open_commerce.config import Settings
from open_commerce.controller.benchmark import (
    SCENARIOS,
    Arm,
    BenchmarkEvidence,
    BenchmarkRow,
    Variant,
    run_case,
    summarize,
)
from open_commerce.core.types import JsonObject, canonical_hash
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.models import ENGINE_VERSION, ScenarioId


@asynccontextmanager
async def scratch_database(settings: Settings) -> AsyncIterator[RuntimeDatabase]:
    url = make_url(settings.database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1", "postgres"}:
        raise ValueError("release benchmark requires an explicitly local PostgreSQL server")
    name = f"opencommerce_bench_{uuid4().hex}"
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created = False
    database: RuntimeDatabase | None = None
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
        created = True
        database_url = url.set(database=name).render_as_string(hide_password=False)
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            env={**os.environ, "OPEN_COMMERCE_DATABASE_URL": database_url},
        )
        if await child.wait():
            raise RuntimeError("benchmark scratch database migration failed")
        database = RuntimeDatabase(
            settings.model_copy(
                update={
                    "database_url": database_url,
                    "environment": "test",
                }
            )
        )
        yield database
    finally:
        if database:
            await database.close()
        if created:
            async with admin.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


def source_fingerprint(root: Path) -> str:
    paths = sorted((root / "packages/backend/src/open_commerce").rglob("*.py"))
    paths += sorted((root / "examples/scenarios").rglob("*.json"))
    return canonical_hash({str(p.relative_to(root)): canonical_hash(p.read_text()) for p in paths})


def _process_case(
    settings: Settings,
    scenario: ScenarioId,
    seed: int,
    variant: Variant,
    arm: Arm,
    days: int,
) -> BenchmarkRow:
    """Each local evaluation process owns its event loop and database pool."""

    async def evaluate() -> BenchmarkRow:
        database = RuntimeDatabase(settings)
        try:
            return await run_case(
                database, scenario=scenario, seed=seed, variant=variant, arm=arm, days=days
            )
        finally:
            await database.close()

    return asyncio.run(evaluate())


async def run_controller_benchmark(
    *,
    settings: Settings,
    seeds: list[int],
    output: Path,
    verify: Path | None = None,
    days: int = 30,
    concurrency: int = 4,
) -> JsonObject:
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("provide nonempty distinct seeds")
    if not 1 <= days <= 366:
        raise ValueError("days must be in 1..366")
    if not 1 <= concurrency <= 8:
        raise ValueError("benchmark concurrency must be in 1..8")
    evidence = BenchmarkEvidence()
    started = perf_counter()
    environment: JsonObject = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlalchemy": version("sqlalchemy"),
        "asyncpg": version("asyncpg"),
        "engine_version": ENGINE_VERSION,
        "source_fingerprint": source_fingerprint(Path.cwd()),
    }
    timings: list[JsonObject] = []
    variants: tuple[Variant, ...] = ("standard", "inventory_infeasible")
    arms: tuple[Arm, ...] = ("no_intervention", "goal_conditioned_controller")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".partial.jsonl")
    async with scratch_database(settings) as database:
        async with database.transaction(settings.local_tenant_id) as session:
            environment["postgresql"] = await session.scalar(text("SHOW server_version"))
        cases = [
            (scenario, variant, seed, arm)
            for scenario in SCENARIOS
            for variant in variants
            for seed in seeds
            for arm in arms
        ]
        semaphore = asyncio.Semaphore(concurrency)
        executor = ProcessPoolExecutor(max_workers=concurrency, mp_context=get_context("spawn"))
        with executor, partial.open("w", encoding="utf-8") as journal:
            journal.write(
                json.dumps(
                    {
                        "complete": False,
                        "environment": environment,
                        "cases": cases,
                        "horizon_days": days,
                    }
                )
                + "\n"
            )
            journal.flush()

            async def evaluate(index: int) -> None:
                scenario, variant, seed, arm = cases[index]
                case: JsonObject = {
                    "scenario": scenario,
                    "variant": variant,
                    "seed": seed,
                    "arm": arm,
                }
                async with semaphore:
                    case_started = perf_counter()
                    try:
                        row = await asyncio.get_running_loop().run_in_executor(
                            executor,
                            _process_case,
                            database.settings,
                            scenario,
                            seed,
                            variant,
                            arm,
                            days,
                        )
                    except Exception as exc:
                        failure = {**case, "error_type": type(exc).__name__}
                        evidence.failures.append(failure)
                        journal.write(json.dumps({"failure": failure}) + "\n")
                        journal.flush()
                        raise
                    evidence.rows.append(row)
                    elapsed = round(perf_counter() - case_started, 3)
                    timings.append({**case, "elapsed_seconds": elapsed})
                    journal.write(row.model_dump_json() + "\n")
                    journal.flush()
                    print(
                        f"{len(evidence.rows)}/{len(cases)} {scenario} {variant} seed={seed} "
                        f"{arm}: {elapsed}s",
                        file=sys.stderr,
                        flush=True,
                    )

            async with asyncio.TaskGroup() as tasks:
                for index in range(len(cases)):
                    tasks.create_task(evaluate(index))
        order = {case: index for index, case in enumerate(cases)}
        evidence.rows.sort(key=lambda row: order[(row.scenario, row.variant, row.seed, row.arm)])
    payload: JsonObject = {
        "complete": True,
        **evidence.model_dump(mode="json"),
        "seeds": seeds,
        "horizon_days": days,
        "coverage": "release_seed_sweep" if len(seeds) >= 100 and days == 30 else "smoke_only",
        "concurrency": concurrency,
        "case_execution": "isolated local processes; one event loop/database pool per case",
        "environment": environment,
        "quality_evidence_hash": evidence.evidence_hash,
        "summary": summarize(evidence.rows),
        "timings": timings,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "method": {
            "storage": "fresh migrated PostgreSQL database; never an in-memory repository",
            "controller": "deployed durable controller and JobRunner; deterministic planner",
            "approvals": "synthetic owner/operator approves exact proposed hash; not autonomous",
            "delivery": "real worker nodes in-process; measurement delivery backoff accelerated",
            "baseline": "same seed, horizon and total/daily spend caps; no controller actions",
            "fixed_rule_baseline": "not separately implemented; no additional comparison claimed",
            "measurement": "measured breaches pause planning; no automatic unpause or rollback",
            "hard_policy_violations": "dispatch, receipt, reconciliation and budget invariants",
            "outcome_guardrails": (
                "observational CAC/margin breaches reported separately; "
                "not prevented by action gates"
            ),
            "statistics": (
                "population standard deviation; linearly interpolated percentiles; "
                "null CAC excluded with missing count"
            ),
            "limitations": "synthetic economics; no merchant lift, calibration or causal claim",
        },
    }
    _write(output, payload)
    if verify:
        expected = json.loads(
            gzip.decompress(verify.read_bytes()) if verify.suffix == ".gz" else verify.read_bytes()
        )
        if expected.get("quality_evidence_hash") != evidence.evidence_hash:
            raise RuntimeError("controller benchmark reproduction failed; new evidence retained")
    if any(row.hard_violations for row in evidence.rows):
        raise RuntimeError("controller benchmark found hard violations; see raw evidence")
    return {k: v for k, v in payload.items() if k not in {"rows", "timings"}}


def _write(path: Path, payload: JsonObject) -> None:
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)
