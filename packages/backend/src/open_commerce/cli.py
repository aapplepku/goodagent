"""Command line entrypoint for local Open Commerce workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from open_commerce.config import get_settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.benchmark import run_search_benchmark
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import SearchRequest
from open_commerce.simulator.golden import GOLDEN_TENANT_ID, verify_golden_suite
from open_commerce.simulator.service import ScenarioNotFoundError, SimulatorService


def main(argv: Sequence[str] | None = None) -> None:
    """Run the command line interface."""

    parser = argparse.ArgumentParser(prog="commerce-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulator = subparsers.add_parser("simulator")
    simulator_subparsers = simulator.add_subparsers(dest="simulator_command", required=True)

    simulator_subparsers.add_parser("list")

    run_parser = simulator_subparsers.add_parser("run")
    run_parser.add_argument("scenario_id")
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--days", type=int, default=30)

    simulator_subparsers.add_parser("golden")

    search = subparsers.add_parser("search")
    search_subparsers = search.add_subparsers(dest="search_command", required=True)
    reindex_parser = search_subparsers.add_parser("reindex")
    reindex_parser.add_argument("--tenant", default=str(get_settings().local_tenant_id))
    reindex_parser.add_argument("--goal", type=UUID, default=None)
    query_parser = search_subparsers.add_parser("query")
    query_parser.add_argument("query")
    query_parser.add_argument("--tenant", default=str(get_settings().local_tenant_id))
    query_parser.add_argument("--goal", type=UUID, default=None)
    query_parser.add_argument(
        "--mode",
        choices=["sparse", "dense", "hybrid", "hybrid_reranked", "hybrid_boosted"],
        default="hybrid",
    )
    query_parser.add_argument("--top-k", type=int, default=10)

    eval_parser = subparsers.add_parser("eval")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    search_eval = eval_subparsers.add_parser("search")
    search_eval.add_argument("--tenant", default=str(GOLDEN_TENANT_ID))
    search_eval.add_argument("--dataset", default="examples/eval/search_queries_v2.jsonl")
    search_eval.add_argument("--output", type=Path)
    search_eval.add_argument("--verify", type=Path)

    controller = subparsers.add_parser("controller")
    controller_subparsers = controller.add_subparsers(dest="controller_command", required=True)
    controller_eval = controller_subparsers.add_parser("evaluate")
    controller_eval.add_argument("--seeds", default=",".join(str(seed) for seed in range(100)))
    controller_eval.add_argument("--days", type=int, default=30)
    controller_eval.add_argument("--concurrency", type=int, default=4)
    controller_eval.add_argument(
        "--output", type=Path, default=Path("examples/eval/results/controller-v2-durable.json.gz")
    )
    controller_eval.add_argument("--verify", type=Path)

    args = parser.parse_args(argv)
    if args.command == "simulator":
        _handle_simulator(args)
    if args.command == "search":
        asyncio.run(_handle_search(args))
    if args.command == "eval":
        asyncio.run(_handle_eval(args))
    if args.command == "controller":
        asyncio.run(_handle_controller(args))


def _handle_simulator(args: argparse.Namespace) -> None:
    service = SimulatorService()
    if args.simulator_command == "list":
        scenarios = service.list_scenarios()
        print(json.dumps(scenarios.model_dump(mode="json"), indent=2, sort_keys=True))
        return
    if args.simulator_command == "run":
        try:
            created = service.create_instance(
                tenant_id=GOLDEN_TENANT_ID,
                scenario_id=args.scenario_id,
                seed=args.seed,
                idempotency_key=f"cli-create:{args.scenario_id}:{args.seed}",
            )
        except ScenarioNotFoundError as exc:
            raise SystemExit(f"unknown scenario: {args.scenario_id}") from exc
        service.advance(
            tenant_id=GOLDEN_TENANT_ID,
            instance_id=created.id,
            hours=args.days * 24,
            idempotency_key=f"cli-run:{args.scenario_id}:{args.seed}:{args.days}",
        )
        comparison = service.compare_baseline(tenant_id=GOLDEN_TENANT_ID, instance_id=created.id)
        print(json.dumps(comparison.model_dump(mode="json"), indent=2, sort_keys=True))
        return
    if args.simulator_command == "golden":
        results = verify_golden_suite()
        payload = [
            {
                "scenario_id": result.scenario_id,
                "seed": result.seed,
                "days": result.days,
                "result_hash": result.result_hash,
                "totals": result.totals.model_dump(mode="json"),
            }
            for result in results
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))


async def _handle_search(args: argparse.Namespace) -> None:
    tenant_id = UUID(args.tenant)
    database = RuntimeDatabase(get_settings())
    service = DurableSearchService(database)
    try:
        await database.initialize_tenant(tenant_id)
        if args.search_command == "reindex":
            count = await service.reindex(tenant_id=tenant_id, goal_context_id=args.goal)
            print(json.dumps({"indexed": count, "tenant_id": str(tenant_id)}, sort_keys=True))
        elif args.search_command == "query":
            response = await service.search(
                tenant_id=tenant_id,
                request=SearchRequest(
                    query=args.query,
                    top_k=args.top_k,
                    debug=True,
                    goal_context_id=args.goal,
                    mode=args.mode,
                ),
            )
            print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))
    finally:
        await service.close()
        await database.close()


async def _handle_eval(args: argparse.Namespace) -> None:
    if args.eval_command == "search":
        payload = await run_search_benchmark(
            dataset_path=Path(args.dataset),
            tenant_id=UUID(args.tenant),
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        if args.verify is not None:
            expected = json.loads(args.verify.read_text(encoding="utf-8"))
            for key in (
                "benchmark_version",
                "query_set_version",
                "catalog_version",
                "quality_evidence_hash",
            ):
                if expected.get(key) != payload.get(key):
                    raise SystemExit(f"Search benchmark reproduction failed: {key}")
        print(
            json.dumps(
                {key: value for key, value in payload.items() if key != "queries"},
                indent=2,
                sort_keys=True,
            )
        )
        results = payload["results"]
        assert isinstance(results, list)
        if any(item["hard_violation_count"] for item in results):
            raise SystemExit("Search benchmark found hard constraint violations; see raw evidence")


async def _handle_controller(args: argparse.Namespace) -> None:
    if args.controller_command == "evaluate":
        from open_commerce.controller.benchmark_command import run_controller_benchmark

        result = await run_controller_benchmark(
            settings=get_settings(),
            seeds=[int(v) for v in args.seeds.split(",") if v],
            days=args.days,
            concurrency=args.concurrency,
            output=args.output,
            verify=args.verify,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return


if __name__ == "__main__":
    main()
