"""Derived comparisons must remain tied to complete, unmodified registered evidence."""

import json
import subprocess
import sys
from pathlib import Path


def test_merchandising_summary_matches_retained_registered_arms() -> None:
    subprocess.run([sys.executable, "scripts/summarize_merchandising.py", "--check"], check=True)


def test_legacy_search_quality_is_preserved_across_availability_projection_version() -> None:
    old = json.loads(Path("examples/eval/results/search-v2-live.json").read_bytes())
    new = json.loads(
        Path(
            "examples/eval/search-merchandising-v1/legacy-availability-regression.json"
        ).read_bytes()
    )
    assert old["catalog_version"] != new["catalog_version"]
    assert old["document_template"] == "product-search-template-v2"
    assert new["document_template"] == "product-search-template-v3-availability"
    for key in ("benchmark_version", "query_set_version", "quality_evidence_hash"):
        assert new[key] == old[key]
    assert [{k: v for k, v in q.items() if k != "latency_ms"} for q in old["queries"]] == [
        {k: v for k, v in q.items() if k != "latency_ms"} for q in new["queries"]
    ]
