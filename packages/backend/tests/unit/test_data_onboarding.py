"""Bounded CSV profiling and data-onboarding contract tests."""

from uuid import UUID

import pytest

from open_commerce.catalog.csv_import import normalize_catalog_csv
from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.manager_agent.data_onboarding import attach_profile, profile_csv
from open_commerce.manager_agent.errors import ManagerDatasetProfileError
from open_commerce.manager_agent.models import ManagerDataOnboarding, ManagerDatasetProfileRequest


def test_catalog_csv_is_profiled_without_retaining_rows() -> None:
    raw = (
        "product_id,title,description,price,updated_at\n"
        "p-1,Trail Boot,Waterproof hiking boot,129.00,2026-09-01T12:00:00Z\n"
    )

    profile = profile_csv(dataset_kind="catalog", filename="catalog.csv", csv_text=raw)
    onboarding = attach_profile(
        ManagerDataOnboarding(tenant_id=UUID("00000000-0000-0000-0000-000000000001")),
        profile,
    )

    assert profile.row_count == 1
    assert profile.detected_mappings["product_id"] == "product_id"
    assert profile.missing_required == []
    assert "Trail Boot" not in profile.model_dump_json()
    assert onboarding.catalog is not None
    assert onboarding.status == "needs_engagement_decision"
    assert onboarding.scheduled_loads_active is False


def test_shopify_style_headers_map_to_canonical_catalog_fields() -> None:
    profile = profile_csv(
        dataset_kind="catalog",
        filename="shopify.csv",
        csv_text=(
            "URL handle,Title,Description,Variant price\ntrail-boot,Trail Boot,Good grip,129\n"
        ),
    )

    assert profile.detected_mappings == {
        "product_id": "URL handle",
        "title": "Title",
        "description": "Description",
        "price": "Variant price",
    }
    assert profile.missing_required == []


def test_catalog_csv_normalizes_search_fields_and_ranking_signals() -> None:
    raw = (
        "product_id,variant_id,sku,title,description,category,brand,price,currency,"
        "inventory_quantity,color,tags,popularity_score,average_rating,updated_at\n"
        "boot,boot-9,B-9,Trail Boot,Waterproof boot,Footwear > Hiking,Northline,129,"
        "USD,4,blue,hiking|waterproof,92,4.5,2026-09-01T12:00:00Z\n"
    )
    profile = profile_csv(dataset_kind="catalog", filename="catalog.csv", csv_text=raw)

    products = normalize_catalog_csv(csv_text=raw, profile=profile)

    assert len(products) == 1
    assert products[0].source_product_id == "boot"
    assert products[0].category_path == ["Footwear", "Hiking"]
    assert products[0].attributes["popularity_score"] == "0.9200"
    assert products[0].attributes["quality_score"] == "0.9000"
    assert products[0].variants[0].price_minor == 12900
    assert products[0].variants[0].available is True


def test_catalog_normalization_rejects_duplicate_variants() -> None:
    raw = "product_id,variant_id,title\np-1,v-1,Boot\np-1,v-1,Boot\n"
    profile = profile_csv(dataset_kind="catalog", filename="catalog.csv", csv_text=raw)

    with pytest.raises(CatalogCSVError, match="duplicate variant_id"):
        normalize_catalog_csv(csv_text=raw, profile=profile)


def test_engagement_csv_rejects_direct_identifier_columns() -> None:
    with pytest.raises(ManagerDatasetProfileError, match="direct-identifier"):
        profile_csv(
            dataset_kind="engagement",
            filename="events.csv",
            csv_text=(
                "event_type,occurred_at,product_id,email\n"
                "view,2026-09-01T12:00:00Z,p-1,shopper@example.com\n"
            ),
        )

    with pytest.raises(ManagerDatasetProfileError, match="direct-identifier values"):
        profile_csv(
            dataset_kind="engagement",
            filename="events.csv",
            csv_text=(
                "event_type,occurred_at,product_id,anonymous_id\n"
                "view,2026-09-01T12:00:00Z,p-1,shopper@example.com\n"
            ),
        )


def test_dataset_request_strips_local_paths_and_requires_csv() -> None:
    request = ManagerDatasetProfileRequest(
        dataset_kind="catalog",
        filename="/Users/example/exports/catalog.csv",
        csv_text="id,title\np-1,Trail Boot\n",
    )

    assert request.filename == "catalog.csv"
    with pytest.raises(ValueError, match="filename must end in .csv"):
        ManagerDatasetProfileRequest(
            dataset_kind="catalog",
            filename="catalog.xlsx",
            csv_text="id,title\np-1,Trail Boot\n",
        )
