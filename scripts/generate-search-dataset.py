"""Retain legacy judgments and add a deterministic, fully judged boost-scope query."""

import json
from pathlib import Path

from open_commerce.simulator.engine import create_initial_state
from open_commerce.simulator.golden import GOLDEN_TENANT_ID
from open_commerce.simulator.scenarios import get_scenario


def main() -> None:
    rows = [
        json.loads(line)
        for line in Path("examples/eval/search_queries.jsonl").read_text().splitlines()
        if line.strip()
    ]
    state = create_initial_state(
        definition=get_scenario("acquisition_v1"), tenant_id=GOLDEN_TENANT_ID, seed=42
    )
    relevant = sorted(
        product.id
        for product in state.products
        if product.category == "outdoor"
        and "summit" in product.title.lower()
        and any(variant.inventory > 0 for variant in product.variants)
    )
    if not relevant:
        raise ValueError("The catalog-derived boost-scope query has no judgments")
    rows.append(
        {
            "query_id": "q-006",
            "query": "outdoor summit",
            "required_constraints": {"category": "outdoor", "in_stock": True},
            "relevant_product_ids": relevant,
            "graded_relevance": {product_id: 3 for product_id in relevant},
        }
    )
    Path("examples/eval/search_queries_v2.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
