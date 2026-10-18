from decimal import Decimal
from uuid import UUID

import pytest

from open_commerce.search.embeddings import sparse_vector
from open_commerce.search.index import InMemoryProductSearchIndex, _ranked_candidate
from open_commerce.search.models import IndexedDocument, ProductFilters, SearchRule
from open_commerce.search.parser import parse_search_intent
from open_commerce.search.service import default_rule_window

from .helpers import OTHER_TENANT_ID, TENANT_ID, make_document


@pytest.mark.asyncio
async def test_search_is_tenant_scoped_and_upserts_are_idempotent() -> None:
    index = InMemoryProductSearchIndex()
    visible = make_document("visible", search_text="green outdoor trail jacket")
    hidden = make_document(
        "hidden",
        tenant_id=OTHER_TENANT_ID,
        search_text="green outdoor trail jacket",
    )

    await index.upsert_documents(tenant_id=TENANT_ID, documents=[visible, visible])
    await index.upsert_documents(tenant_id=OTHER_TENANT_ID, documents=[hidden])
    intent = parse_search_intent("green outdoor trail jacket")
    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=10,
        mode="hybrid",
        rules=[],
    )

    assert index.document_count(TENANT_ID) == 1
    assert [result.product_id for result in results] == ["visible"]


@pytest.mark.asyncio
async def test_search_result_preserves_catalog_image_url() -> None:
    index = InMemoryProductSearchIndex()
    document = make_document(
        "pictured",
        search_text="green outdoor trail jacket",
        image_url="https://example.test/jacket.jpg",
    )
    await index.upsert_documents(tenant_id=TENANT_ID, documents=[document])
    intent = parse_search_intent("green outdoor trail jacket")

    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=1,
        mode="hybrid",
        rules=[],
    )

    assert results[0].image_url == "https://example.test/jacket.jpg"


@pytest.mark.asyncio
async def test_exact_identifier_search_retains_sparse_advantage_in_hybrid() -> None:
    index = InMemoryProductSearchIndex()
    exact = make_document(
        "exact",
        title="Exact Trail Shoe",
        category="footwear",
        search_text="SIM-EXACT-0001-1 exact trail shoe",
    )
    neighbor = make_document(
        "neighbor",
        title="Neighbor Trail Shoe",
        category="footwear",
        search_text="trail shoe for daily running",
    )
    await index.upsert_documents(tenant_id=TENANT_ID, documents=[neighbor, exact])
    intent = parse_search_intent("SIM-EXACT-0001-1")

    sparse_results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=5,
        mode="sparse",
        rules=[],
    )
    hybrid_results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=5,
        mode="hybrid",
        rules=[],
    )

    assert sparse_results[0].product_id == "exact"
    assert hybrid_results[0].product_id == "exact"
    assert hybrid_results[0].branch_ranks["sparse"] == 0


@pytest.mark.asyncio
async def test_semantic_dense_branch_recovers_use_case_without_exact_terms() -> None:
    index = InMemoryProductSearchIndex()
    lexical_tie = make_document(
        "a_lexical_tie",
        title="Kitchen Gift Box",
        category="home",
        search_text="ceramic storage kitchen gift",
    )
    semantic_match = make_document(
        "z_semantic_match",
        title="Summit Shell",
        category="outdoor",
        search_text="summit outdoor trail weatherproof packable shell",
    )
    await index.upsert_documents(
        tenant_id=TENANT_ID,
        documents=[lexical_tie, semantic_match],
    )
    intent = parse_search_intent("hiking rain gear")

    sparse_results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=5,
        mode="sparse",
        rules=[],
    )
    dense_results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=5,
        mode="dense",
        rules=[],
    )

    assert sparse_results == []
    assert dense_results[0].product_id == "z_semantic_match"


@pytest.mark.asyncio
async def test_hard_filters_and_negation_are_enforced_before_return() -> None:
    index = InMemoryProductSearchIndex()
    matching = make_document(
        "matching",
        category="outdoor",
        price_minor=12_000,
        in_stock=True,
        search_text="outdoor trail nylon shell",
    )
    expensive = make_document(
        "expensive",
        category="outdoor",
        price_minor=20_000,
        search_text="outdoor trail nylon shell",
    )
    unavailable = make_document(
        "unavailable",
        category="outdoor",
        price_minor=12_000,
        in_stock=False,
        search_text="outdoor trail nylon shell",
    )
    excluded = make_document(
        "excluded",
        category="outdoor",
        price_minor=12_000,
        search_text="outdoor trail heavy insulation shell",
    )
    await index.upsert_documents(
        tenant_id=TENANT_ID,
        documents=[matching, expensive, unavailable, excluded],
    )
    intent = parse_search_intent(
        "outdoor under $150 without heavy insulation",
        ProductFilters(in_stock=True),
    )

    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=10,
        mode="hybrid",
        rules=[],
    )

    assert [result.product_id for result in results] == ["matching"]
    assert all(all(result.constraint_matches.values()) for result in results)


@pytest.mark.asyncio
async def test_rrf_tie_breaking_is_deterministic() -> None:
    index = InMemoryProductSearchIndex()
    first = make_document("a_product", search_text="trail travel shell")
    second = make_document("b_product", search_text="trail travel shell")
    await index.upsert_documents(tenant_id=TENANT_ID, documents=[second, first])
    intent = parse_search_intent("trail travel shell")

    results = await index.search(
        tenant_id=TENANT_ID,
        intent=intent,
        filters=intent.required_filters,
        top_k=2,
        mode="hybrid",
        rules=[],
    )

    assert [result.product_id for result in results] == ["a_product", "b_product"]


def test_boosts_are_capped_and_do_not_apply_below_relevance_floor() -> None:
    document = make_document("boosted", search_text="trail running shoe")
    indexed = IndexedDocument(
        document=document,
        dense_vector=[0.0 for _ in range(64)],
        sparse_vector=sparse_vector(document.search_text),
    )
    irrelevant = make_document("boosted", search_text="city ceramic mug")
    irrelevant_indexed = IndexedDocument(
        document=irrelevant,
        dense_vector=[0.0 for _ in range(64)],
        sparse_vector=sparse_vector(irrelevant.search_text),
    )
    starts_at, ends_at = default_rule_window()
    active_rule = SearchRule(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        tenant_id=TENANT_ID,
        query_text="trail",
        product_ids=["boosted"],
        multiplier=Decimal("3"),
        starts_at=starts_at,
        ends_at=ends_at,
        reason="test",
    )
    intent = parse_search_intent("trail")

    boosted = _ranked_candidate(
        document=indexed.document,
        intent=intent,
        filters=intent.required_filters,
        ranks={
            "sparse_score": Decimal("5"),
            "dense_score": Decimal("0.9"),
            "sparse_rank": 0,
            "dense_rank": 0,
        },
        rules=[active_rule],
        mode="hybrid_boosted",
    )
    below_floor = _ranked_candidate(
        document=irrelevant_indexed.document,
        intent=intent,
        filters=intent.required_filters,
        ranks={
            "sparse_score": Decimal("0.001"),
            "dense_score": Decimal("-1"),
            "sparse_rank": 100_000,
            "dense_rank": 100_000,
        },
        rules=[active_rule],
        mode="hybrid_boosted",
    )

    assert boosted.score_components.goal_boost == Decimal("0.1500")
    assert below_floor.score_components.goal_boost == Decimal("0.0000")


@pytest.mark.parametrize(
    "filters",
    [
        ProductFilters(max_price_minor=1),
        ProductFilters(min_price_minor=20000),
        ProductFilters(category="electronics"),
        ProductFilters(brand="Different"),
        ProductFilters(currency="EUR"),
        ProductFilters(attributes={"material": ["cotton"]}),
        ProductFilters(excluded_attributes={"text": ["trail"]}),
        ProductFilters(in_stock=False),
    ],
)
def test_maximal_business_boost_cannot_rescue_hard_constraint_failures(
    filters: ProductFilters,
) -> None:
    document = make_document("boosted", search_text="trail running shoe")
    starts, ends = default_rule_window()
    rule = SearchRule(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        tenant_id=TENANT_ID,
        query_text="trail",
        multiplier=Decimal("3"),
        starts_at=starts,
        ends_at=ends,
        reason="adversarial test",
    )
    candidate = _ranked_candidate(
        document=document,
        intent=parse_search_intent("trail"),
        filters=filters,
        ranks={
            "sparse_score": Decimal("999"),
            "dense_score": Decimal("1"),
            "sparse_rank": 0,
            "dense_rank": 0,
        },
        rules=[rule],
        mode="hybrid_boosted",
    )
    assert candidate.score == 0
    assert candidate.score_components.goal_boost == 0
    assert not all(candidate.constraint_matches.values())
