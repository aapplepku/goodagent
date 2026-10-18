"""Catalog CSV normalization tests for the durable manager upload path."""

from decimal import Decimal

import pytest

from open_commerce.catalog.csv_import import normalize_catalog_csv
from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.manager_agent.data_onboarding import profile_csv


def normalize(csv_text: str):  # type: ignore[no-untyped-def]
    profile = profile_csv(dataset_kind="catalog", filename="catalog.csv", csv_text=csv_text)
    return normalize_catalog_csv(csv_text=csv_text, profile=profile)


def test_normalizes_variants_and_bounded_ranking_signals() -> None:
    products = normalize(
        "product_id,variant_id,title,price,currency,inventory_quantity,popularity_score,"
        "average_rating,tags,updated_at\n"
        "lamp,lamp-blue,Reading Lamp,79.50,usd,4,92,4.5,lighting|desk,"
        "2026-09-01T12:00:00Z\n"
        "lamp,lamp-green,Reading Lamp,80,usd,0,92,4.5,lighting|desk,"
        "2026-09-01T12:00:00Z\n"
    )

    assert len(products) == 1
    assert products[0].attributes["popularity_score"] == "0.9200"
    assert products[0].attributes["quality_score"] == "0.9000"
    assert products[0].tags == ["lighting", "desk"]
    assert products[0].variants[0].price_minor == 7950
    assert products[0].variants[1].available is False


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("price", "NaN", "finite"),
        ("currency", "US", "invalid variant"),
        ("inventory_quantity", "1.5", "finite integers"),
        ("popularity_score", "150", "between 0 and 1"),
        ("updated_at", "2026-09-01T12:00:00", "timezone"),
    ],
)
def test_rejects_invalid_catalog_values(column: str, value: str, message: str) -> None:
    fields = {
        "price": "10",
        "currency": "USD",
        "inventory_quantity": "2",
        "popularity_score": "50",
        "updated_at": "2026-09-01T12:00:00Z",
    }
    fields[column] = value
    csv_text = (
        "product_id,title,price,currency,inventory_quantity,popularity_score,updated_at\n"
        f"lamp,Reading Lamp,{fields['price']},{fields['currency']},"
        f"{fields['inventory_quantity']},{fields['popularity_score']},{fields['updated_at']}\n"
    )

    with pytest.raises(CatalogCSVError, match=message):
        normalize(csv_text)


def test_rejects_duplicate_variant_ids_without_persisting_rows() -> None:
    csv_text = (
        "product_id,variant_id,title,price,currency,updated_at\n"
        "lamp,v1,Reading Lamp,10,USD,2026-09-01T12:00:00Z\n"
        "lamp,v1,Reading Lamp,12,USD,2026-09-01T12:00:00Z\n"
    )

    with pytest.raises(CatalogCSVError, match="duplicate variant_id"):
        normalize(csv_text)


def test_minor_unit_price_is_not_rounded_silently() -> None:
    csv_text = (
        "product_id,title,price_minor,currency,updated_at\n"
        "lamp,Reading Lamp,1050.5,USD,2026-09-01T12:00:00Z\n"
    )

    with pytest.raises(CatalogCSVError, match="minor-unit prices must be integers"):
        normalize(csv_text)


def test_price_decimal_is_exact() -> None:
    product = normalize(
        "product_id,title,price,currency,updated_at\n"
        "lamp,Reading Lamp,10.01,USD,2026-09-01T12:00:00Z\n"
    )[0]

    assert product.variants[0].price_minor == 1001
    assert Decimal(product.attributes.get("popularity_score", "0")) == Decimal("0")
