"""Fixed-query, read-only Shopify Admin GraphQL adapter for a configured test store."""

import asyncio
import json
import re
from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Any

import httpx
from pydantic import SecretStr

from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.sources import CatalogConnection, CatalogSourceError

API_VERSION = "2026-07"
_CHECK = "query { currentAppInstallation { accessScopes { handle } } shop { currencyCode } }"
_PRODUCTS = """query Catalog($after: String) {
  products(first: 50, after: $after, query: "status:active", sortKey: ID) {
    pageInfo { hasNextPage endCursor }
    nodes { id title description vendor productType tags updatedAt publishedAt
      featuredMedia { preview { image { url } } }
      variants(first: 200) { pageInfo { hasNextPage }
        nodes { id title sku price selectedOptions { name value } }
      }
    }
  }
}"""


class ShopifyCatalogProvider:
    def __init__(
        self, shop: str, token: SecretStr, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\.myshopify\.com", shop):
            raise CatalogSourceError(
                "Configure an exact test-store myshopify.com domain, without a URL or path."
            )
        self.shop, self.token, self.transport = shop, token, transport
        self.currency: str | None = None

    async def _query(
        self, query: str, variables: dict[str, object] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=15, follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    "POST",
                    f"https://{self.shop}/admin/api/{API_VERSION}/graphql.json",
                    headers={"X-Shopify-Access-Token": self.token.get_secret_value()},
                    json={"query": query, "variables": variables or {}},
                ) as response:
                    if response.status_code != 200:
                        raise CatalogSourceError(
                            f"Shopify returned HTTP {response.status_code}; "
                            "check read-only access or retry later."
                        )
                    body = bytearray()
                    async for part in response.aiter_bytes():
                        body.extend(part)
                        if len(body) > 8_000_000:
                            raise CatalogSourceError(
                                "Shopify response exceeds the bounded demo import limit."
                            )
                    data = json.loads(body)
                    if (
                        not isinstance(data, dict)
                        or data.get("errors")
                        or not isinstance(data.get("data"), dict)
                    ):
                        raise CatalogSourceError(
                            "Shopify rejected the catalog query. "
                            "Check scopes and the pinned API version."
                        )
                    return dict(data["data"])
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, CatalogSourceError):
                raise
            raise CatalogSourceError(
                "Shopify could not be reached or returned an invalid response."
            ) from exc

    async def check(self) -> CatalogConnection:
        data = await self._query(_CHECK)
        try:
            scopes = {item["handle"] for item in data["currentAppInstallation"]["accessScopes"]}
            if "read_products" not in scopes or any(scope.startswith("write_") for scope in scopes):
                raise CatalogSourceError(
                    "Use a read-only app with read_products and no Admin write scopes."
                )
            self.currency = str(data["shop"]["currencyCode"])
            if self.currency not in {"USD", "EUR", "GBP", "CAD", "AUD"}:
                raise CatalogSourceError(
                    "This demo importer currently supports USD, EUR, GBP, CAD and AUD only."
                )
        except (KeyError, TypeError) as exc:
            raise CatalogSourceError("Shopify connection metadata was incomplete.") from exc
        return CatalogConnection(
            configured=True,
            connected=True,
            shop=self.shop,
            detail="Read-only product access verified. Inventory is not synchronized.",
        )

    async def fetch_catalog(self) -> list[CatalogProductInput]:
        async with asyncio.timeout(120):
            await self.check()
            products: list[CatalogProductInput] = []
            after: str | None = None
            cursors: set[str] = set()
            for _ in range(200):
                data = await self._query(_PRODUCTS, {"after": after})
                try:
                    page = data["products"]
                    for item in page["nodes"]:
                        if not item["publishedAt"]:
                            continue
                        if item["variants"]["pageInfo"]["hasNextPage"]:
                            raise CatalogSourceError(
                                "A product exceeds 200 variants. "
                                "Import stopped without publishing a partial catalog."
                            )
                        media = item.get("featuredMedia") or {}
                        image = (media.get("preview") or {}).get("image") or {}
                        variants = [
                            CatalogVariantInput(
                                source_variant_id=variant["id"],
                                title=variant["title"],
                                sku=variant.get("sku"),
                                price_minor=_minor(variant["price"]),
                                currency=self.currency or "",
                                available=True,
                                inventory_quantity=None,
                                option_values={
                                    option["name"]: option["value"]
                                    for option in variant["selectedOptions"]
                                },
                            )
                            for variant in item["variants"]["nodes"]
                        ]
                        products.append(
                            CatalogProductInput(
                                source_product_id=item["id"],
                                title=item["title"],
                                description_text=item["description"][:4000],
                                brand=item.get("vendor"),
                                category_path=[item["productType"]] if item["productType"] else [],
                                tags=item["tags"][:40],
                                primary_image_url=image.get("url"),
                                source_updated_at=datetime.fromisoformat(
                                    item["updatedAt"].replace("Z", "+00:00")
                                ),
                                variants=variants,
                                attributes={
                                    "source": "shopify_read_only",
                                    "inventory": "not_synchronized",
                                },
                            )
                        )
                    if not page["pageInfo"]["hasNextPage"]:
                        if not products:
                            raise CatalogSourceError(
                                "No published active products were found. "
                                "The existing catalog was retained."
                            )
                        return products
                    after = page["pageInfo"]["endCursor"]
                    if not after or after in cursors:
                        raise CatalogSourceError(
                            "Shopify pagination did not advance; no partial catalog was published."
                        )
                    cursors.add(after)
                except (KeyError, TypeError, ValueError, DecimalException) as exc:
                    if isinstance(exc, CatalogSourceError):
                        raise
                    raise CatalogSourceError(
                        "Shopify returned unsupported catalog data; "
                        "no partial catalog was published."
                    ) from exc
            raise CatalogSourceError("The catalog exceeds the 10,000-product demo limit.")


def _minor(value: str) -> int:
    amount = Decimal(value) * 100
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise CatalogSourceError("Shopify supplied an unsupported price.")
    return int(amount)
