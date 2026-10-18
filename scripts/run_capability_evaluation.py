"""Explicit local-only capability evaluation; no downloads, paid inference or publication."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.engine import make_url

from open_commerce.config import Settings
from open_commerce.controller.capability_evaluation import evaluate_case, inference_evidence
from open_commerce.controller.capability_fixtures import (
    Arm,
    CapabilityCase,
    CaseSetup,
    prepare_case,
)
from open_commerce.controller.model_goal_interpretation import GOAL_PROMPT, ModelGoalExtraction
from open_commerce.controller.model_protocol import PLANNER_PROMPT, PlannerResponse
from open_commerce.controller.ollama import OllamaBackend
from open_commerce.core.types import JsonObject, canonical_hash, utc_now
from open_commerce.persistence.runtime_db import RuntimeDatabase

ROOT = Path(__file__).resolve().parents[1]


def write_report(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def freeze(settings: Settings, split: str) -> JsonObject:
    registered = ROOT / "examples/eval/capability-v1"
    sources = sorted((ROOT / "packages/backend/src/open_commerce").rglob("*.py"))
    sources.append(Path(__file__))
    return {
        "protocol_version": "planning-capability-v1",
        "split": split,
        "protocol_files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(registered.glob("*.json"))
        },
        "runtime_source_hash": canonical_hash(
            {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        ),
        "planner_prompt_hash": canonical_hash(PLANNER_PROMPT),
        "planner_schema_hash": canonical_hash(PlannerResponse.model_json_schema()),
        "goal_prompt_hash": canonical_hash(GOAL_PROMPT),
        "goal_schema_hash": canonical_hash(ModelGoalExtraction.model_json_schema()),
        "model_id": settings.model_id,
        "model_digest": settings.model_digest,
        "model_limits": settings.model_dump(
            include={
                "model_timeout_seconds",
                "model_max_iterations",
                "model_max_tool_calls",
                "model_max_output_tokens",
                "model_max_input_bytes",
                "model_goal_request_limit",
                "model_goal_token_limit",
                "model_daily_request_limit",
                "model_daily_token_limit",
            }
        ),
        "inference_backend": "ollama_local",
        "model_source": "real_model",
        "cost_limit": "zero provider fees; bounded local requests/tokens; hardware unmeasured",
    }


async def run(output: Path, split: Literal["development", "held_out"], include_model: bool) -> None:
    settings = Settings()
    database_name = make_url(settings.database_url).database or ""
    if not database_name.startswith("opencommerce_capability_"):
        raise ValueError("Use a migrated opencommerce_capability_* database, never a demo database")
    if include_model:
        OllamaBackend(settings).require_enabled()
    manifest = freeze(settings, split)
    manifest["include_model"] = include_model
    freeze_path = output / "freeze.json"
    if freeze_path.exists():
        if json.loads(freeze_path.read_text())["configuration"] != manifest:
            raise ValueError(
                "frozen configuration changed; retain this attempt and use a new evaluation version"
            )
    else:
        write_report(
            freeze_path,
            {
                "experiment_id": str(uuid4()),
                "frozen_at": utc_now().isoformat(),
                "configuration": manifest,
            },
        )
    experiment_id = json.loads(freeze_path.read_text())["experiment_id"]
    registered = ROOT / "examples/eval/capability-v1"
    protocol = json.loads((registered / "protocol.json").read_text())
    seeds: list[int] = protocol["development_seeds" if split == "development" else "held_out_seeds"]
    cases = [
        CapabilityCase.model_validate(c)
        for c in json.loads((registered / "cases.json").read_text())
    ]
    arms: list[Arm] = (
        ["no_intervention", "deterministic", "model_backed"]
        if include_model
        else ["no_intervention", "deterministic"]
    )
    database = RuntimeDatabase(settings)
    failures = 0
    try:
        for seed in seeds:
            for case in cases:
                matched: list[CaseSetup] = []
                for arm in arms:
                    label = f"{case.id}-{seed}-{arm}"
                    tenant = uuid5(NAMESPACE_URL, f"{experiment_id}:{split}:{label}")
                    report_path = output / "cases" / f"{label}.json"
                    setup_path = output / "checkpoints" / f"{label}.json"
                    if report_path.exists():
                        report = json.loads(report_path.read_text())
                        if report.get("status") == "complete":
                            matched.append(CaseSetup.model_validate(report["setup"]))
                            continue
                    print(f"Running {label}", flush=True)
                    try:
                        if setup_path.exists():
                            setup = CaseSetup.model_validate_json(setup_path.read_text())
                        else:
                            setup = await prepare_case(database, tenant, case, seed, arm)
                            write_report(setup_path, setup.model_dump(mode="json"))
                        if matched and (
                            setup.observable_world_hash != matched[0].observable_world_hash
                            or setup.starting_budgets != matched[0].starting_budgets
                            or setup.incremental_target != matched[0].incremental_target
                        ):
                            raise ValueError(
                                "unmatched starting inputs or budget; comparison is invalid"
                            )
                        matched.append(setup)
                        report = await evaluate_case(database, tenant, case, arm, setup)
                        report.update(
                            {
                                "status": "complete",
                                "seed": seed,
                                "split": split,
                                "completed_at": utc_now().isoformat(),
                                "freeze_hash": canonical_hash(manifest),
                            }
                        )
                        write_report(report_path, report)
                        print(
                            json.dumps(
                                {
                                    "case": label,
                                    "objective": report["objective_value"],
                                    "executed": report["executed"],
                                    "planning_failures": report["planning_failures"],
                                    "model_usage": report["inference_usage"],
                                }
                            ),
                            flush=True,
                        )
                    except Exception as exc:
                        failures += 1
                        failure = {
                            "case": label,
                            "status": "failed",
                            "error": type(exc).__name__,
                            "recorded_at": utc_now().isoformat(),
                            "inference_calls": await inference_evidence(database, tenant),
                        }
                        write_report(
                            output
                            / "failures"
                            / f"{label}-{utc_now().strftime('%Y%m%dT%H%M%S%f')}.json",
                            failure,
                        )
                        print(
                            json.dumps(
                                {"case": label, "status": "failed", "error": type(exc).__name__}
                            ),
                            flush=True,
                        )
    finally:
        await database.close()
    if failures:
        raise RuntimeError(
            f"{failures} cases did not complete; retained failure artifacts required"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "held_out"], required=True)
    parser.add_argument(
        "--include-model", action="store_true", help="Explicit opt-in to bounded local inference"
    )
    arguments = parser.parse_args()
    asyncio.run(run(arguments.output, arguments.split, arguments.include_model))
