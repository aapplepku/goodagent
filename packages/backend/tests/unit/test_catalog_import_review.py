"""CSV review is explicit, bounded, and reports invalid rows without dropping them."""

import csv
import io
import socket

import pytest
from PIL import Image

from open_commerce.catalog.shopify_csv import ShopifyProductsExcluded, shopify_csv
from open_commerce.providers.catalog_images import ImageIngestionError, public_addresses, raster
from open_commerce.stores.import_models import ImportMapping
from open_commerce.stores.import_validation import validate_import


@pytest.fixture(params=["legacy", "current"])
def shopify_export(request: pytest.FixtureRequest) -> str:
    headers = (
        [
            "Handle",
            "Title",
            "Body (HTML)",
            "Option1 Value",
            "Variant SKU",
            "Variant Price",
            "Image Src",
            "Status",
            "Published",
        ]
        if request.param == "legacy"
        else [
            "URL handle",
            "Title",
            "Description",
            "Option1 value",
            "SKU",
            "Price",
            "Product image URL",
            "Status",
            "Published on online store",
        ]
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(
        [
            ["mug", "Mug", "<p>Test mug</p>", "Red", "MUG-R", "12.50", "", "active", "true"],
            ["mug", "", "", "Blue", "MUG-B", "14.00", "", "", ""],
            ["mug", "", "", "", "", "", "https://images.example/mug.png", "", ""],
            ["draft", "Draft", "", "", "D", "8", "", "draft", "true"],
            ["archived", "Archived", "", "", "A", "8", "", "archived", "true"],
            ["unpublished", "Unpublished", "", "", "U", "8", "", "active", "false"],
        ]
    )
    return output.getvalue()


def test_shopify_review_matches_native_parser_and_explains_exclusions(shopify_export: str) -> None:
    initial, products, errors = validate_import(shopify_export, "shopify.csv")
    assert not products and errors[0].row == 1
    assert "currency" in errors[0].message
    mapping = ImportMapping(mapping=initial.detected_mappings, currency="CAD")
    profile, products, errors = validate_import(shopify_export, "shopify.csv", mapping)
    assert not errors
    native = shopify_csv(shopify_export, "CAD")
    assert native is not None
    assert [p.model_dump(exclude={"source_updated_at"}) for p in products] == [
        p.model_dump(exclude={"source_updated_at"}) for p in native
    ]
    assert [p.source_product_id for p in products] == ["mug"]
    product = products[0]
    assert product.description_text == "Test mug"
    assert product.primary_image_url == "https://images.example/mug.png"
    assert [v.price_minor for v in product.variants] == [1250, 1400]
    assert [v.option_values for v in product.variants] == [{"option1": "Red"}, {"option1": "Blue"}]
    excluded = [w for w in profile.warnings if "Shopify product excluded" in w]
    assert len(excluded) == 3
    assert [w.split(":")[0] for w in excluded] == [
        "Rows starting at 5",
        "Rows starting at 6",
        "Rows starting at 7",
    ]


def test_shopify_review_does_not_treat_unpriced_variant_as_image(shopify_export: str) -> None:
    data = shopify_export.replace("Blue,MUG-B,14.00", "Blue,MUG-B,")
    initial, _, _ = validate_import(data, "shopify.csv")
    _, products, errors = validate_import(
        data, "shopify.csv", ImportMapping(mapping=initial.detected_mappings, currency="USD")
    )
    assert not products
    assert errors and "variant is missing its price" in errors[0].message


def test_shopify_review_rejects_all_excluded_catalog_with_row_warnings(shopify_export: str) -> None:
    data = "\n".join(line for line in shopify_export.splitlines() if not line.startswith("mug,"))
    initial, _, _ = validate_import(data, "shopify.csv")
    profile, products, errors = validate_import(
        data, "shopify.csv", ImportMapping(mapping=initial.detected_mappings, currency="USD")
    )
    assert not products
    assert errors[0].row == 1 and "No published, priced products" in errors[0].message
    assert len([w for w in profile.warnings if "Shopify product excluded" in w]) == 3
    with pytest.raises(ShopifyProductsExcluded):
        shopify_csv(data, "USD")


def test_shopify_empty_source_remains_invalid() -> None:
    from open_commerce.catalog.errors import CatalogCSVError

    with pytest.raises(CatalogCSVError, match="at least one data row"):
        shopify_csv("URL handle,Title,Price\n", "USD")


@pytest.mark.parametrize("handle", ["Handle", "URL handle"])
@pytest.mark.parametrize("variant", ["variant_id", "Variant ID"])
@pytest.mark.parametrize("currency", ["currency", "Currency Code"])
def test_generic_native_looking_headers_preserve_explicit_variants(
    handle: str, variant: str, currency: str
) -> None:
    data = (
        f"{handle},Title,{variant},Price,{currency}\nmug,Mug,red,12.50,CAD\nmug,,blue,14.00,CAD\n"
    )
    _, products, errors = validate_import(data, "generic.csv")
    assert not errors and len(products) == 1
    assert [v.source_variant_id for v in products[0].variants] == ["red", "blue"]
    assert [v.price_minor for v in products[0].variants] == [1250, 1400]
    assert {v.currency for v in products[0].variants} == {"CAD"}
    assert shopify_csv(data, None) is None


@pytest.mark.parametrize("handle", ["Handle", "URL handle"])
def test_generic_native_looking_headers_preserve_per_row_currency(handle: str) -> None:
    data = f"{handle},Title,Price,currency\nmug,Mug,12.50,EUR\n"
    _, products, errors = validate_import(data, "generic.csv")
    assert not errors and products[0].variants[0].currency == "EUR"
    assert shopify_csv(data, None) is None


@pytest.mark.parametrize("generic", ["currency", "variant_id"])
@pytest.mark.parametrize(
    "marker,value",
    [
        ("Status", "draft"),
        ("Status", "archived"),
        ("Published", "false"),
        ("Published on online store", "false"),
    ],
)
def test_generic_columns_cannot_bypass_shopify_publication_exclusions(
    generic: str, marker: str, value: str
) -> None:
    data = f"URL handle,Title,Price,{generic},{marker}\nmug,Mug,12,USD,{value}\n"
    initial, _, _ = validate_import(data, "shopify.csv")
    profile, products, errors = validate_import(
        data, "shopify.csv", ImportMapping(mapping=initial.detected_mappings, currency="USD")
    )
    assert not products and errors
    assert any("Rows starting at 2" in w for w in profile.warnings)
    with pytest.raises(ShopifyProductsExcluded):
        shopify_csv(data, "USD")


def test_currency_and_edited_mapping_and_row_errors() -> None:
    csv = "key,label,cost,stock\na,Mug,12,4\nb,Throw,invalid,3\n"
    _, _, errors = validate_import(csv, "custom.csv")
    assert errors[0].row == 1
    mapping = ImportMapping(
        mapping={
            "product_id": "key",
            "title": "label",
            "price": "cost",
            "inventory_quantity": "stock",
        },
        currency="USD",
    )
    _, products, errors = validate_import(csv, "custom.csv", mapping)
    assert len(products) == 1 and errors[0].row == 3
    _, products, errors = validate_import(csv.replace("invalid", "35"), "custom.csv", mapping)
    assert not errors and len(products) == 2 and products[0].variants[0].price_minor == 1200
    _, _, errors = validate_import(csv, "custom.csv", ImportMapping(mapping={"run_shell": "key"}))
    assert errors


def test_missing_price_currency_and_duplicate_variant_are_not_invented() -> None:
    _, _, errors = validate_import("product_id,title,price\na,Mug,12\n", "catalog.csv")
    assert "currency" in errors[0].message
    _, _, errors = validate_import(
        "product_id,title,price,currency,variant_id\na,Mug,12,USD,x\na,Mug,14,USD,x\n",
        "catalog.csv",
    )
    assert errors and "duplicate" in errors[0].message


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.png",
        "https://u:p@example.com/a",
        "https://example.com:22/a",
        "file:///etc/passwd",
    ],
)
def test_unsafe_image_urls_are_rejected_without_dns(url: str) -> None:
    with pytest.raises(ImageIngestionError):
        public_addresses(url)


def test_dns_mixed_public_private_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ImageIngestionError):
        public_addresses("https://images.example/a.png")


def test_images_are_reencoded_and_svg_rejected() -> None:
    source = io.BytesIO()
    Image.new("RGB", (80, 80), "teal").save(source, format="JPEG")
    result = raster(source.getvalue())
    assert result.startswith(b"\x89PNG")
    with pytest.raises(ImageIngestionError):
        raster(b'<svg onload="evil()"/>')


async def test_trickling_image_download_is_aborted(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    from unittest.mock import MagicMock

    from open_commerce.providers import catalog_images

    interrupted = threading.Event()
    secure = MagicMock()
    secure.shutdown.side_effect = lambda *_: interrupted.set()
    context = MagicMock()
    context.wrap_socket.return_value = secure
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 200
    response.getheader.return_value = "image/png"

    def stalled_read(_limit: int) -> bytes:
        assert interrupted.wait(2), "The total deadline did not interrupt the download"
        return b"partial raster"

    response.read.side_effect = stalled_read
    monkeypatch.setattr(catalog_images, "MAX_DOWNLOAD_SECONDS", 0.02)
    monkeypatch.setattr(
        catalog_images,
        "public_addresses",
        lambda _: ("images.example", "/a.png", ["93.184.216.34"]),
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.socket.create_connection", MagicMock()
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.ssl.create_default_context", lambda: context
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.http.client.HTTPSConnection",
        lambda *_a, **_k: connection,
    )
    with pytest.raises(ImageIngestionError):
        await catalog_images.SafeCatalogImages().fetch("https://images.example/a.png")
    secure.shutdown.assert_called_once_with(socket.SHUT_RDWR)
    connection.close.assert_called_once()
