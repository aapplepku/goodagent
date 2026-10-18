"""Reproducible five-mode search evaluation with live Qdrant by default."""

from __future__ import annotations

import json
import platform
import statistics
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import AsyncQdrantClient

from open_commerce.config import get_settings
from open_commerce.core.types import canonical_hash
from open_commerce.search.embeddings import LocalHashEmbeddingProvider
from open_commerce.search.index import RANKING_VERSION, _constraint_matches, _eligible_price
from open_commerce.search.models import ProductFilters, ProductSearchIndex, RankingMode, SearchRule
from open_commerce.search.normalization import TEMPLATE_VERSION
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.qdrant_index import SPARSE_MODEL, QdrantProductSearchIndex
from open_commerce.search.service import documents_from_simulator_state
from open_commerce.simulator.engine import create_initial_state
from open_commerce.simulator.scenarios import get_scenario

BENCHMARK_VERSION = "search-benchmark-v2"
MODES: tuple[RankingMode, ...] = ("sparse", "dense", "hybrid", "hybrid_reranked", "hybrid_boosted")


class BenchmarkQuery(BaseModel):
    """Versioned judgments, independent of retrieved ranks or scores."""

    model_config = ConfigDict(extra="forbid")
    query_id: str
    query: str
    relevant_product_ids: list[str] = Field(default_factory=list)
    required_constraints: ProductFilters = Field(default_factory=ProductFilters)
    graded_relevance: dict[str, Annotated[int, Field(ge=0, le=3)]] = Field(default_factory=dict)


async def run_search_benchmark(
    *,
    dataset_path: Path,
    tenant_id: UUID,
    index: ProductSearchIndex | None = None,
) -> dict[str, object]:
    """Measure the real adapter; explicit index injection is for unit tests only.

    Latency includes query embedding, network retrieval and local ranking, not
    index construction. Reproduction compares non-timing evidence, not wall time.
    """

    rows = _load_dataset(dataset_path)
    state = create_initial_state(
        definition=get_scenario("acquisition_v1"),
        tenant_id=tenant_id,
        seed=42,
        instance_id=uuid5(NAMESPACE_URL, f"{tenant_id}:{BENCHMARK_VERSION}"),
    )
    documents = documents_from_simulator_state(state)
    by_id = {item.product_id: item for item in documents}
    rules = [
        SearchRule(
            id=uuid5(NAMESPACE_URL, f"{tenant_id}:benchmark-business-boost"),
            tenant_id=tenant_id,
            query_text="outdoor",
            category="outdoor",
            product_ids=[
                item.id
                for item in state.products
                if item.excess_inventory and item.category == "outdoor"
            ],
            multiplier=Decimal("1.5"),
            starts_at=state.current_time,
            ends_at=state.current_time + timedelta(days=7),
            evaluation_time=state.current_time,
            reason="Isolated benchmark fixture; not a merchant action",
        )
    ]
    client: AsyncQdrantClient | None = None
    collection = f"benchmark_{uuid4().hex}"
    backend_version = "unit-fixture"
    if index is None:
        client = AsyncQdrantClient(
            url=get_settings().qdrant_url, timeout=10, check_compatibility=False
        )
        index = QdrantProductSearchIndex(
            client=client,
            collection_name=collection,
            instance_id=state.id,
            source_version=documents[0].source_version,
            authoritative_documents=by_id,
        )
    try:
        if client is not None:
            backend_version = (await client.info()).version
        await index.upsert_documents(tenant_id=tenant_id, documents=documents)
        raw: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []
        for mode in MODES:
            ndcgs, recalls, latencies = [], [], []
            violations, bad_results, result_count, empty_count, boosted_results = 0, 0, 0, 0, 0
            for row in rows:
                intent = parse_search_intent(row.query, row.required_constraints)
                started = perf_counter()
                results = await index.search(
                    tenant_id=tenant_id,
                    intent=intent,
                    filters=intent.required_filters,
                    top_k=20,
                    mode=mode,
                    rules=rules,
                )
                latency = (perf_counter() - started) * 1000
                ids = [item.product_id for item in results]
                relevant = set(row.relevant_product_ids)
                recall = (
                    Decimal(len(set(ids) & relevant)) / Decimal(len(relevant))
                    if relevant
                    else Decimal("0")
                )
                ndcg = _ndcg(ids, row.graded_relevance, 10)
                failed = []
                for result in results:
                    document = by_id.get(result.product_id)
                    if document is None:
                        failed.append(f"{result.product_id}:unknown_catalog_id")
                        continue
                    constraints = _constraint_matches(document, intent.required_filters)
                    constraints["displayed_price"] = (
                        result.price.amount_minor
                        == _eligible_price(document, intent.required_filters)
                        and result.price.currency == document.currency
                    )
                    failed.extend(
                        f"{result.product_id}:{key}"
                        for key, passed in constraints.items()
                        if not passed
                    )
                violations += len(failed)
                bad_results += len({item.split(":", 1)[0] for item in failed})
                result_count += len(results)
                boosted_results += sum(result.score_components.goal_boost > 0 for result in results)
                empty_count += not results
                ndcgs.append(float(ndcg))
                recalls.append(float(recall))
                latencies.append(latency)
                raw.append(
                    {
                        "mode": mode,
                        "query_id": row.query_id,
                        "query": row.query,
                        "hard_filters": intent.required_filters.model_dump(mode="json"),
                        "ndcg_at_10": _rounded(ndcg),
                        "recall_at_20": _rounded(recall),
                        "latency_ms": _rounded(latency),
                        "hard_violations": failed,
                        "relevant_product_ids": row.relevant_product_ids,
                        "graded_relevance": row.graded_relevance,
                        "results": [item.model_dump(mode="json") for item in results],
                    }
                )
            summaries.append(
                {
                    "mode": mode,
                    "ndcg_at_10": distribution(ndcgs),
                    "recall_at_20": distribution(recalls),
                    "latency_ms": distribution(latencies),
                    "result_count": result_count,
                    "no_result_count": empty_count,
                    "hard_violation_count": violations,
                    "boosted_result_count": boosted_results,
                    "hard_constraint_satisfaction": _rounded(
                        Decimal(result_count - bad_results) / Decimal(result_count)
                        if result_count
                        else Decimal("1")
                    ),
                }
            )
        quality_evidence = [
            {key: value for key, value in row.items() if key != "latency_ms"} for row in raw
        ]
        return {
            "benchmark_version": BENCHMARK_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": str(dataset_path),
            "query_set_version": canonical_hash([row.model_dump(mode="json") for row in rows]),
            "catalog_version": documents[0].source_version,
            "catalog_count": len(documents),
            "scenario": state.scenario_id,
            "seed": state.seed,
            "engine_version": state.engine_version,
            "ranking_version": RANKING_VERSION,
            "business_rules": [rule.model_dump(mode="json") for rule in rules],
            "document_template": TEMPLATE_VERSION,
            "embedding_model": LocalHashEmbeddingProvider.model_id,
            "sparse_model": SPARSE_MODEL,
            "retrieval_backend": "live_qdrant" if client else "explicit_unit_fixture",
            "qdrant_version": backend_version,
            "qdrant_client_version": version("qdrant-client"),
            "python_version": platform.python_version(),
            "query_count": len(rows),
            "quality_evidence_hash": canonical_hash(quality_evidence),
            "limitations": [
                "Tiny synthetic seed-42 catalog/query set; not evidence of production relevance.",
                "Dense: local signed hashing and semantic expansions, not a neural model.",
                "Sparse: hashed term frequency plus Qdrant IDF, not full BM25.",
                "Reranking: lexical/quality/popularity rules, not a cross-encoder.",
                "Business boost: an isolated bounded fixture, not a commerce action.",
                "Empty relevant sets score zero. Empty responses are counted separately.",
                "Latency excludes indexing and PG snapshot loading; machine/network dependent.",
            ],
            "results": summaries,
            "queries": raw,
        }
    finally:
        if client is not None:
            try:
                if await client.collection_exists(collection):
                    await client.delete_collection(collection)
            finally:
                await client.close()


def _load_dataset(path: Path) -> list[BenchmarkQuery]:
    rows = [
        BenchmarkQuery.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows or len({row.query_id for row in rows}) != len(rows):
        raise ValueError("Benchmark needs nonempty, unique query IDs")
    return rows


def _ndcg(product_ids: list[str], graded: dict[str, int], top_k: int) -> Decimal:
    def dcg(gains: list[int]) -> Decimal:
        return sum(
            (
                Decimal(2**gain - 1) / (Decimal(position + 2).ln() / Decimal(2).ln())
                for position, gain in enumerate(gains[:top_k])
            ),
            Decimal("0"),
        )

    ideal = dcg(sorted(graded.values(), reverse=True))
    return (
        dcg([graded.get(product_id, 0) for product_id in product_ids]) / ideal
        if ideal
        else Decimal("0")
    )


def _rounded(value: Decimal | float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.000001")))


def distribution(values: list[float]) -> dict[str, str]:
    """Population spread and linearly interpolated sample percentiles."""

    if not values:
        raise ValueError("Distribution requires observations")
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        index = (len(ordered) - 1) * fraction
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return {
        key: _rounded(value)
        for key, value in {
            "mean": statistics.mean(values),
            "stddev": statistics.pstdev(values),
            "p10": percentile(0.1),
            "p50": percentile(0.5),
            "p90": percentile(0.9),
            "p95": percentile(0.95),
        }.items()
    }
