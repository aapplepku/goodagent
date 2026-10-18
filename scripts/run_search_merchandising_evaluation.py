"""Run the registered search comparisons against isolated live Qdrant collections."""

import argparse
import asyncio
import hashlib
import json
import math
import platform
import resource
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field
from qdrant_client import AsyncQdrantClient

from open_commerce.controller.models import GoalCreateRequest
from open_commerce.controller.service import ControllerService
from open_commerce.core.merchandising import MerchandisingConstraints
from open_commerce.core.types import StrictDomainModel
from open_commerce.search.embeddings import LocalHashEmbeddingProvider
from open_commerce.search.learned_embeddings import MODEL_FILES, MiniLMEmbeddingProvider
from open_commerce.search.models import ProductFilters, RankedCandidate, RankingMode
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.qdrant_index import QdrantProductSearchIndex
from open_commerce.search.service import documents_from_simulator_state
from open_commerce.simulator.merchandising_catalog import FAMILIES
from open_commerce.simulator.models import SimulatorState

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/eval/search-merchandising-v1"


class FamilyJudgment(StrictDomainModel):
    family: str
    exact: str
    material: str
    paraphrase: str
    use_intent: str


class Judgments(StrictDomainModel):
    version: Literal["search-merchandising-v1"]
    catalog_version: Literal["merchandising-catalog-v1"]
    positive_grade: Literal[3]
    families: list[FamilyJudgment] = Field(min_length=12, max_length=12)
    no_result_queries: list[str] = Field(min_length=6, max_length=6)


class Query(StrictDomainModel):
    id: str
    family: str | None
    split: Literal["development", "held_out"]
    kind: str
    text: str
    filters: ProductFilters
    fixture: Literal["base", "first_variant_unavailable"] = "base"
    positive_product_ids: list[str]


def queries(state: SimulatorState, judgments: Judgments) -> list[Query]:
    """Materialize judgments from declared family/constraint facts, not search output."""
    result = []
    families = {family.id: family for family in FAMILIES}
    for item in judgments.families:
        family = families[item.family]
        products = [p for p in state.products if p.attributes["product_type"] == item.family]
        ids = sorted(p.id for p in products)
        budget = family.price_minor + 300
        for kind, split, text, filters, fixture, positive in (
            ("exact", "development", item.exact, ProductFilters(), "base", ids),
            (
                "material",
                "development",
                item.material,
                ProductFilters(attributes={"material": [family.material]}),
                "base",
                ids,
            ),
            (
                "budget",
                "development",
                item.exact,
                ProductFilters(max_price_minor=budget),
                "base",
                sorted(
                    p.id
                    for p in products
                    if any(v.available and v.price_minor <= budget for v in p.variants)
                ),
            ),
            ("paraphrase", "held_out", item.paraphrase, ProductFilters(), "base", ids),
            ("use_intent", "held_out", item.use_intent, ProductFilters(), "base", ids),
            (
                "brand",
                "held_out",
                f"Kanso {item.exact}",
                ProductFilters(brand="Kanso"),
                "base",
                sorted(p.id for p in products if p.brand == "Kanso"),
            ),
            (
                "variant_availability",
                "held_out",
                item.exact,
                ProductFilters(max_price_minor=budget),
                "first_variant_unavailable",
                [],
            ),
        ):
            result.append(
                Query.model_validate(
                    {
                        "id": f"{item.family}:{kind}",
                        "family": item.family,
                        "split": split,
                        "kind": kind,
                        "text": text,
                        "filters": filters,
                        "fixture": fixture,
                        "positive_product_ids": positive,
                    }
                )
            )
    result += [
        Query(
            id=f"no_result:{i + 1}",
            family=None,
            split="held_out",
            kind="no_result",
            text=text,
            filters=ProductFilters(),
            positive_product_ids=[],
        )
        for i, text in enumerate(judgments.no_result_queries)
    ]
    return result


def metrics(
    query: Query, results: list[RankedCandidate], state: SimulatorState
) -> dict[str, object]:
    positive = set(query.positive_product_ids)
    hits = [int(r.product_id in positive) for r in results]
    dcg = sum(7 * hit / math.log2(position + 2) for position, hit in enumerate(hits))
    ideal = sum(7 / math.log2(position + 2) for position in range(min(5, len(positive))))
    violations = []
    products = {p.id: p for p in state.products}
    # Independent check against authored request constraints, not returned pass flags.
    for result in results:
        product = products.get(result.product_id)
        if product is None:
            violations.append({"product_id": result.product_id, "reason": "unknown_product"})
            continue
        limit = query.filters.max_price_minor
        eligible = [
            v
            for v in product.variants
            if v.available and v.inventory > 0 and (limit is None or v.price_minor <= limit)
        ]
        if not eligible or result.price.amount_minor not in {v.price_minor for v in eligible}:
            violations.append(
                {"product_id": result.product_id, "reason": "available_variant_price"}
            )
        if query.filters.brand and product.brand != query.filters.brand:
            violations.append({"product_id": result.product_id, "reason": "brand"})
        for key, values in query.filters.attributes.items():
            if product.attributes.get(key) not in values:
                violations.append({"product_id": result.product_id, "reason": f"attribute:{key}"})
    return {
        "ndcg_at_5": dcg / ideal if positive else None,
        "precision_at_5": sum(hits) / 5 if positive else None,
        "recall_at_5": sum(hits) / len(positive) if positive else None,
        "reciprocal_rank": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0)
        if positive
        else None,
        "empty_result_correct": not results if not positive else None,
        "false_positive_results": len(results) - sum(hits),
        "hard_constraint_violations": violations,
    }


def source_fingerprint() -> str:
    paths = [
        *sorted((ROOT / "packages/backend/src/open_commerce/search").glob("*.py")),
        ROOT / "packages/backend/src/open_commerce/simulator/merchandising_catalog.py",
        ROOT / "uv.lock",
        DATA / "protocol.md",
        DATA / "judgments.json",
        Path(__file__),
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


async def run(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise ValueError("Refusing to replace retained evaluation output")
    judgments = Judgments.model_validate_json((DATA / "judgments.json").read_text())
    tenant = UUID("60166c54-4f0e-487d-a94b-5126d4d52c10")
    controller = ControllerService()
    goal = controller.create_goal(
        tenant_id=tenant,
        request=GoalCreateRequest(seed=42, merchandising=MerchandisingConstraints()),
        idempotency_key="search-merchandising-v1",
    )
    state = controller.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    dataset = queries(state, judgments)
    selected = [query for query in dataset if query.split == args.split]
    created_collections = []
    client = AsyncQdrantClient(url=args.qdrant_url, timeout=60)
    started = time.perf_counter()
    provider_started = time.perf_counter()
    learned = MiniLMEmbeddingProvider(args.model_directory)
    load_seconds = time.perf_counter() - provider_started
    rows: list[dict[str, Any]] = []
    prefix = f"merch_search_eval_{uuid4().hex}"
    indexes: dict[tuple[str, str], tuple[QdrantProductSearchIndex, SimulatorState]] = {}
    try:
        version = (await client.info()).model_dump(mode="json")
        for backend, provider in (("learned", learned), ("hash", LocalHashEmbeddingProvider())):
            for fixture in sorted({q.fixture for q in selected}):
                variant_state = state.model_copy(deep=True)
                if fixture == "first_variant_unavailable":
                    for product in variant_state.products:
                        product.variants[0].available = False
                documents = documents_from_simulator_state(
                    variant_state, embedding_model=provider.model_id
                )
                index = QdrantProductSearchIndex(
                    client=client,
                    instance_id=state.id,
                    source_version=documents[0].source_version,
                    authoritative_documents={d.product_id: d for d in documents},
                    embedding_provider=provider,
                    collection_name=f"{prefix}_{backend}_{fixture}",
                )
                if await client.collection_exists(index.collection_name):
                    raise ValueError("Evaluation collection unexpectedly exists")
                created_collections.append(index.collection_name)
                await index.upsert_documents(tenant_id=tenant, documents=documents)
                indexes[backend, fixture] = index, variant_state
        arms: list[tuple[str, str, RankingMode]] = [
            ("lexical_tfidf", "learned", "sparse"),
            ("learned_dense", "learned", "dense"),
            ("learned_hybrid", "learned", "hybrid"),
            ("hash_dense_test_baseline", "hash", "dense"),
        ]
        for query in selected:
            for arm, backend, mode in arms:
                index, variant_state = indexes[backend, query.fixture]
                intent = parse_search_intent(query.text, query.filters)
                query_started = time.perf_counter()
                results = await index.search(
                    tenant_id=tenant,
                    intent=intent,
                    filters=intent.required_filters,
                    top_k=5,
                    mode=mode,
                    rules=[],
                )
                elapsed = time.perf_counter() - query_started
                serving = [r for r in results if r.score_components.relevance >= Decimal("0.55")]
                rows.append(
                    {
                        "query": query.model_dump(mode="json"),
                        "arm": arm,
                        "interpretation": intent.model_dump(mode="json"),
                        "results": [r.model_dump(mode="json") for r in results],
                        "retrieval_metrics": metrics(query, results, variant_state),
                        "eligible_top_five_metrics": metrics(query, serving, variant_state),
                        "elapsed_seconds": elapsed,
                    }
                )
            print(f"Evaluated {query.id}", flush=True)
        summaries = {}
        for arm, _, _ in arms:
            group = [r["retrieval_metrics"] for r in rows if r["arm"] == arm]
            summaries[arm] = {
                key: sum(values) / len(values) if values else None
                for key in (
                    "ndcg_at_5",
                    "precision_at_5",
                    "recall_at_5",
                    "reciprocal_rank",
                    "empty_result_correct",
                )
                if (values := [m[key] for m in group if m[key] is not None]) is not None
            }
            summaries[arm]["hard_constraint_violations"] = sum(
                len(m["hard_constraint_violations"]) for m in group
            )
            summaries[arm]["query_count"] = len(group)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report = {
            "protocol": judgments.version,
            "split": args.split,
            "evidence_mode": "live_qdrant_learned_encoder_no_llm",
            "source_fingerprint": source_fingerprint(),
            "judgments_sha256": hashlib.sha256((DATA / "judgments.json").read_bytes()).hexdigest(),
            "materialized_queries_sha256": hashlib.sha256(
                json.dumps([q.model_dump(mode="json") for q in dataset], sort_keys=True).encode()
            ).hexdigest(),
            "query_count": len(selected),
            "model_id": learned.model_id,
            "model_files": {name: digest for name, (_, digest) in MODEL_FILES.items()},
            "qdrant": version,
            "platform": {"system": platform.system(), "machine": platform.machine()},
            "model_load_seconds": load_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "process_peak_rss_bytes": peak if platform.system() == "Darwin" else peak * 1024,
            "summary": summaries,
            "rows": rows,
        }
        if args.post_fix_of is not None:
            original = json.loads(args.post_fix_of.read_text())
            if original["split"] != args.split or original["protocol"] != judgments.version:
                raise ValueError("Post-fix reference must identify the same original query split")
            report["evaluation_role"] = "post_fix_regression_on_previously_exposed_queries"
            report["original_result_sha256"] = hashlib.sha256(
                args.post_fix_of.read_bytes()
            ).hexdigest()
            report["unseen_held_out_evidence"] = False
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(summaries, indent=2), flush=True)
    finally:
        for name in created_collections:
            await client.delete_collection(name)
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held_out"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--post-fix-of", type=Path)
    asyncio.run(run(parser.parse_args()))
