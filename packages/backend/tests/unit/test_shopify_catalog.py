"""Read-only connection contract and native Shopify CSV row semantics."""

import json

import httpx
import pytest
from pydantic import SecretStr

from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.catalog.shopify_csv import shopify_csv
from open_commerce.catalog.sources import CatalogSourceError
from open_commerce.providers.shopify_catalog import ShopifyCatalogProvider

EXPORT = (
    "Handle,Title,Body (HTML),Vendor,Option1 Value,Variant SKU,Variant Price,"
    "Image Src,Status,Published\n"
    "mug,Mug,<p>A <strong>nice</strong> mug</p>,Mugs,Red,MUG-R,12.50,"
    "https://cdn.shopify.com/mug.jpg,active,true\n"
    "mug,,,,Blue,MUG-B,14.00,,,\n"
    "mug,,,,,,,https://cdn.shopify.com/extra.jpg,,\n"
    "secret,Unpublished,,,,X,8,,draft,false\n"
)


def test_shopify_rows_preserve_variants_and_do_not_invent_image_variants() -> None:
    products = shopify_csv(EXPORT, "EUR")
    assert products and len(products) == 1
    assert len(products[0].variants) == 2
    assert products[0].description_text == "A nice mug"
    assert products[0].variants[0].price_minor == 1250
    assert products[0].variants[1].currency == "EUR"
    assert products[0].variants[0].inventory_quantity is None
    assert products[0].primary_image_url == "https://cdn.shopify.com/mug.jpg"
    with pytest.raises(CatalogCSVError, match="currency"):
        shopify_csv(EXPORT, None)
    assert shopify_csv("product_id,title\na,A\n", None) is None


@pytest.mark.parametrize(
    "shop",
    [
        "https://store.myshopify.com",
        "localhost",
        "store.myshopify.com.evil.test",
        "store.myshopify.com/path",
        "store@localhost",
    ],
)
def test_connector_rejects_arbitrary_hosts_and_paths(shop: str) -> None:
    with pytest.raises(CatalogSourceError):
        ShopifyCatalogProvider(shop, SecretStr("test-token"))


async def test_connector_is_fixed_read_only_and_fails_closed_on_writable_tokens() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "test-store.myshopify.com"
        assert b"mutation" not in request.content
        return httpx.Response(
            200,
            json={
                "data": {
                    "currentAppInstallation": {
                        "accessScopes": [{"handle": "read_products"}, {"handle": "write_products"}]
                    },
                    "shop": {"currencyCode": "USD"},
                }
            },
        )

    provider = ShopifyCatalogProvider(
        "test-store.myshopify.com", SecretStr("test-token"), transport=httpx.MockTransport(handle)
    )
    with pytest.raises(CatalogSourceError, match="read-only"):
        await provider.check()


async def test_connection_errors_do_not_expose_tokens_or_provider_bodies() -> None:
    provider = ShopifyCatalogProvider(
        "test-store.myshopify.com",
        SecretStr("private-token"),
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="private-token")),
    )
    with pytest.raises(CatalogSourceError) as error:
        await provider.check()
    assert "private-token" not in str(error.value)


@pytest.mark.parametrize("too_many_variants", [False, True])
async def test_paginated_catalog_is_complete_or_rejected(too_many_variants: bool) -> None:
    cursors: list[str | None] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "mutation" not in body["query"]
        if "currentAppInstallation" in body["query"]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "currentAppInstallation": {"accessScopes": [{"handle": "read_products"}]},
                        "shop": {"currencyCode": "CAD"},
                    }
                },
            )
        cursor = body["variables"]["after"]
        cursors.append(cursor)
        number = 1 if cursor is None else 2
        return httpx.Response(
            200,
            json={
                "data": {
                    "products": {
                        "pageInfo": {"hasNextPage": number == 1, "endCursor": "second"},
                        "nodes": [
                            {
                                "id": f"gid://shopify/Product/{number}",
                                "title": f"Mug {number}",
                                "description": "A mug",
                                "vendor": "Mugs",
                                "productType": "Home",
                                "tags": [],
                                "updatedAt": "2026-01-01T00:00:00Z",
                                "publishedAt": "2026-01-01T00:00:00Z",
                                "featuredMedia": {
                                    "preview": {"image": {"url": "https://cdn.shopify.com/mug.jpg"}}
                                },
                                "variants": {
                                    "pageInfo": {"hasNextPage": too_many_variants and number == 2},
                                    "nodes": [
                                        {
                                            "id": f"gid://shopify/ProductVariant/{number}",
                                            "title": "Red",
                                            "sku": "MUG",
                                            "price": "12.50",
                                            "selectedOptions": [],
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                }
            },
        )

    provider = ShopifyCatalogProvider(
        "test-store.myshopify.com",
        SecretStr("private-token"),
        transport=httpx.MockTransport(handle),
    )
    if too_many_variants:
        with pytest.raises(CatalogSourceError, match="200 variants"):
            await provider.fetch_catalog()
    else:
        products = await provider.fetch_catalog()
        assert len(products) == 2
        assert products[0].variants[0].price_minor == 1250
        assert products[0].variants[0].currency == "CAD"
        assert products[0].variants[0].inventory_quantity is None
        assert "private-token" not in products[0].model_dump_json()
    assert cursors == [None, "second"]


def test_export_with_bom_and_sku_only_variants() -> None:
    products = shopify_csv(
        "\ufeff" + EXPORT.replace(",Red,MUG-R,", ",,MUG-R,").replace(",Blue,MUG-B,", ",,MUG-B,"),
        "USD",
    )
    assert products and len(products[0].variants) == 2
