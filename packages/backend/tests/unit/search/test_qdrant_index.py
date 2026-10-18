"""Adapter semantics with the real SDK's local engine, not durability evidence."""

from collections.abc import AsyncIterator
from decimal import Decimal
from itertools import permutations
from uuid import UUID, uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from open_commerce.search.models import (
    ProductFilters,
    ProductSearchDocument,
    RankingMode,
    SearchVariant,
)
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.qdrant_index import (
    QdrantProductSearchIndex,
    _stable_branch_order,
    build_qdrant_filter,
)

from .helpers import OTHER_TENANT_ID, TENANT_ID, make_document

INSTANCE_ID = UUID("00000000-0000-0000-0000-000000000099")


@pytest.fixture
async def client() -> AsyncIterator[AsyncQdrantClient]:
    value = AsyncQdrantClient(":memory:")
    try:
        yield value
    finally:
        await value.close()


def document(product_id: str, **updates: object) -> ProductSearchDocument:
    return ProductSearchDocument.model_validate(
        {
            **make_document(product_id, search_text="trail outdoor shell").model_dump(),
            "instance_id": INSTANCE_ID,
            **updates,
        }
    )


def test_qdrant_filter_contains_tenant_instance_and_same_variant_constraints() -> None:
    payload = build_qdrant_filter(
        TENANT_ID,
        ProductFilters(max_price_minor=15000),
        instance_id=INSTANCE_ID,
    ).model_dump(mode="json", exclude_none=True)
    assert {"key": "tenant_id", "match": {"value": str(TENANT_ID)}} in payload["must"]
    assert {"key": "instance_id", "match": {"value": str(INSTANCE_ID)}} in payload["must"]
    nested = next(item["nested"] for item in payload["must"] if "nested" in item)
    assert nested["key"] == "variants"
    assert {"key": "in_stock", "match": {"value": True}} in nested["filter"]["must"]
    assert {"key": "price_minor", "range": {"lte": 15000.0}} in nested["filter"]["must"]


@pytest.mark.parametrize("mode", ["sparse", "dense", "hybrid", "hybrid_reranked", "hybrid_boosted"])
async def test_selected_branches_are_real_and_catalog_scoped(
    client: AsyncQdrantClient, mode: RankingMode
) -> None:
    index = QdrantProductSearchIndex(client=client, instance_id=INSTANCE_ID)
    other = QdrantProductSearchIndex(client=client, instance_id=uuid4())
    await index.upsert_documents(tenant_id=TENANT_ID, documents=[document("visible")])
    await index.upsert_documents(
        tenant_id=OTHER_TENANT_ID,
        documents=[
            document("hidden-tenant", tenant_id=OTHER_TENANT_ID),
        ],
    )
    await other.upsert_documents(
        tenant_id=TENANT_ID,
        documents=[
            document("hidden-instance", instance_id=other.instance_id),
        ],
    )
    intent = parse_search_intent("trail outdoor shell")
    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=5,
        mode=mode,
        rules=[],
    )
    assert [item.product_id for item in results] == ["visible"]
    ranks = results[0].branch_ranks
    assert (ranks["sparse"] is not None) == (mode != "dense")
    assert (ranks["dense"] is not None) == (mode != "sparse")
    assert await index.document_count(tenant_id=TENANT_ID) == 1
    await index.delete_documents(tenant_id=TENANT_ID, product_ids=["visible", "hidden-tenant"])
    assert await index.document_count(tenant_id=TENANT_ID) == 0
    assert await index.document_count(tenant_id=OTHER_TENANT_ID) == 1
    assert await other.document_count(tenant_id=TENANT_ID) == 1


async def test_stock_price_attributes_and_exclusions_fail_closed(client: AsyncQdrantClient) -> None:
    index = QdrantProductSearchIndex(client=client, instance_id=INSTANCE_ID)
    gap = document(
        "gap",
        variants=[
            SearchVariant(id="a", price_minor=1000, in_stock=True),
            SearchVariant(id="b", price_minor=20000, in_stock=True),
        ],
    )
    cheap_unavailable = document(
        "cheap-unavailable",
        variants=[
            SearchVariant(id="a", price_minor=10000, in_stock=False),
            SearchVariant(id="b", price_minor=20000, in_stock=True),
        ],
    )
    await index.upsert_documents(
        tenant_id=TENANT_ID,
        documents=[
            document("ok"),
            gap,
            cheap_unavailable,
            document("wrong-attribute", attributes={"material": "cotton"}),
            document("excluded", search_text="trail outdoor shell heavy insulation"),
            document("wrong-currency", currency="EUR"),
        ],
    )
    filters = ProductFilters(
        min_price_minor=5000,
        max_price_minor=15000,
        currency="USD",
        brand="NORTHLINE",
        attributes={"material": ["nylon"]},
        excluded_attributes={"text": ["insulation"]},
    )
    intent = parse_search_intent("trail outdoor shell", filters)
    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=20,
        mode="hybrid_boosted",
        rules=[],
    )
    assert [item.product_id for item in results] == ["ok"]
    assert all(all(item.constraint_matches.values()) for item in results)


async def test_invalid_upsert_is_atomic_before_first_network_write(
    client: AsyncQdrantClient,
) -> None:
    index = QdrantProductSearchIndex(client=client, instance_id=INSTANCE_ID)
    with pytest.raises(ValueError, match="scope"):
        await index.upsert_documents(
            tenant_id=TENANT_ID,
            documents=[
                document("good"),
                document("bad", tenant_id=OTHER_TENANT_ID),
            ],
        )
    assert await index.document_count(tenant_id=TENANT_ID) == 0


def test_near_ties_crossing_rounding_boundaries_have_stable_ranks() -> None:
    # Adjacent float reductions can straddle a six-place rounding bucket.
    for a, b in (("8.12345649", "8.12345651"), ("8.12345651", "8.12345649")):
        points = [(document("a"), Decimal(a)), (document("b"), Decimal(b))]
        points += [(document("c"), Decimal("8.1233"))]
        for order in permutations(points):
            ranked = _stable_branch_order(list(order))
            assert [item.product_id for item, _ in ranked] == ["a", "b", "c"]


def test_near_tie_groups_do_not_chain_into_materially_different_scores() -> None:
    points = [
        (document("c"), Decimal("1.000020")),
        (document("b"), Decimal("1.000011")),
        (document("a"), Decimal("1.000002")),
    ]
    assert [item.product_id for item, _ in _stable_branch_order(points)] == ["b", "c", "a"]
