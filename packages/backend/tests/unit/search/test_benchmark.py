from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from open_commerce.search.benchmark import _ndcg, distribution, run_search_benchmark
from open_commerce.search.index import InMemoryProductSearchIndex

from .helpers import TENANT_ID


@pytest.mark.asyncio
async def test_benchmark_reports_all_five_modes_without_asserting_a_preferred_winner() -> None:
    payload = await run_search_benchmark(
        dataset_path=Path("examples/eval/search_queries_v2.jsonl"),
        tenant_id=TENANT_ID,
        index=InMemoryProductSearchIndex(),
    )
    items = cast(list[dict[str, str]], payload["results"])
    results = {item["mode"]: item for item in items}

    assert set(results) == {"sparse", "dense", "hybrid", "hybrid_reranked", "hybrid_boosted"}
    assert all(Decimal(str(item["hard_constraint_satisfaction"])) == 1 for item in items)
    assert payload["retrieval_backend"] == "explicit_unit_fixture"
    raw = cast(list[dict[str, object]], payload["queries"])
    assert len(raw) == 30
    assert any(
        item["mode"] == "hybrid_boosted" and int(item["boosted_result_count"]) > 0 for item in items
    )
    assert all("latency_ms" in item and "recall_at_20" in item for item in raw)
    repeated = await run_search_benchmark(
        dataset_path=Path("examples/eval/search_queries_v2.jsonl"),
        tenant_id=TENANT_ID,
        index=InMemoryProductSearchIndex(),
    )
    assert repeated["quality_evidence_hash"] == payload["quality_evidence_hash"]


def test_ndcg_uses_exponential_gain_and_rank_discount() -> None:
    assert _ndcg(["a", "b"], {"a": 3, "b": 1}, 10) == 1
    assert _ndcg([], {"a": 3}, 10) == 0
    assert _ndcg(["a"], {}, 10) == 0
    expected = (Decimal(1) + Decimal(7) / (Decimal(3).ln() / Decimal(2).ln())) / (
        Decimal(7) + Decimal(1) / (Decimal(3).ln() / Decimal(2).ln())
    )
    assert _ndcg(["b", "a"], {"a": 3, "b": 1}, 10) == expected


def test_distribution_uses_population_spread_and_interpolated_percentiles() -> None:
    values = distribution([0.0, 10.0])
    assert values == {
        "mean": "5.000000",
        "stddev": "5.000000",
        "p10": "1.000000",
        "p50": "5.000000",
        "p90": "9.000000",
        "p95": "9.500000",
    }
