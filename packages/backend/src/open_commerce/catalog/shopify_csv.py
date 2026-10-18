"""Shopify export normalization: variant rows are not additional image rows."""

import csv
import io
from collections import defaultdict
from collections.abc import Collection
from html.parser import HTMLParser

from open_commerce.catalog.csv_import import normalize_catalog_csv
from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.catalog.models import CatalogProductInput

_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD"}


class ShopifyProductsExcluded(CatalogCSVError):
    """A nonempty native export contained only non-published products."""


def is_shopify_csv(headers: Collection[str]) -> bool:
    names = set(headers)
    if not ({"Handle", "URL handle"} & names and {"Variant Price", "Price"} & names):
        return False
    if {"Handle", "Variant Price"} <= names:
        return True
    # Publication fields must not be bypassed by added generic columns.
    if {"Status", "Published", "Published on online store"} & names:
        return True
    generic = {"variant_id", "variant id", "currency", "currency_code", "currency code"}
    return not generic.intersection(name.strip().casefold() for name in names)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def plain_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())[:4000]


def shopify_csv(csv_text: str, currency: str | None) -> list[CatalogProductInput] | None:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""), strict=True)
    headers = set(reader.fieldnames or [])
    handle_header = "Handle" if "Handle" in headers else "URL handle"
    if not is_shopify_csv(headers):
        return None
    if currency not in _CURRENCIES:
        raise CatalogCSVError(
            "Choose the Shopify export's currency (USD, EUR, GBP, CAD or AUD) "
            "before importing. Currency is not inferred from prices."
        )
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in reader:
        if None in row:
            raise CatalogCSVError("Shopify CSV has more values than its header.")
        handle = (row.get(handle_header) or "").strip()
        if not handle:
            raise CatalogCSVError("Every Shopify row needs its product handle.")
        grouped[handle].append(row)
    if not grouped:
        raise CatalogCSVError("Shopify CSV must include at least one data row.")
    output = io.StringIO(newline="")
    columns = [
        "product_id",
        "variant_id",
        "title",
        "description",
        "brand",
        "category",
        "tags",
        "sku",
        "price",
        "currency",
        "image_url",
        "inventory_quantity",
        "option1",
        "option2",
        "option3",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    written_rows = 0
    for handle, rows in grouped.items():
        first = rows[0]
        if first.get("Status", "active").strip().lower() in {"draft", "archived"}:
            continue
        if (
            first.get("Published", first.get("Published on online store", "true")).strip().lower()
            == "false"
        ):
            continue
        title = first.get("Title", "").strip()
        if not title:
            raise CatalogCSVError("The first row for each Shopify handle must have a title.")
        image = next(
            (
                row.get("Image Src") or row.get("Product image URL")
                for row in rows
                if row.get("Image Src") or row.get("Product image URL")
            ),
            "",
        )
        seen: set[str] = set()
        for row in rows:
            price = row.get("Variant Price", row.get("Price", ""))
            if not price:
                # Shopify uses handle + image-only rows. Never invent a zero-price variant.
                if (
                    row.get("Variant SKU")
                    or row.get("SKU")
                    or row.get("Option1 Value")
                    or row.get("Option1 value")
                ):
                    raise CatalogCSVError("A Shopify variant is missing its price.")
                continue
            options = [
                row.get(f"Option{i} Value", row.get(f"Option{i} value", "")) for i in (1, 2, 3)
            ]
            identity = (
                "|".join(options)
                if any(options)
                else row.get("Variant SKU") or row.get("SKU") or "default"
            )
            if identity in seen:
                raise CatalogCSVError("Shopify export has duplicate variant options.")
            seen.add(identity)
            from hashlib import sha256

            writer.writerow(
                {
                    "product_id": handle,
                    "variant_id": f"{handle}:{sha256(identity.encode()).hexdigest()[:16]}",
                    "title": title,
                    "description": plain_text(
                        first.get("Body (HTML)", first.get("Description", ""))
                    ),
                    "brand": first.get("Vendor", ""),
                    "category": first.get("Product Category")
                    or first.get("Product category")
                    or first.get("Type", ""),
                    "tags": first.get("Tags", ""),
                    "sku": row.get("Variant SKU", row.get("SKU", "")),
                    "price": price,
                    "currency": currency,
                    "image_url": image,
                    "inventory_quantity": row.get(
                        "Variant Inventory Qty", row.get("Inventory quantity", "")
                    ),
                    **{f"option{i}": value for i, value in enumerate(options, 1)},
                }
            )
            written_rows += 1
        if not seen:
            raise CatalogCSVError("A published Shopify product has no priced variants.")
    if not written_rows:
        raise ShopifyProductsExcluded("No published, priced Shopify products were found.")

    from open_commerce.manager_agent.data_onboarding import profile_csv

    normalized = output.getvalue()
    profile = profile_csv(dataset_kind="catalog", filename="shopify.csv", csv_text=normalized)
    return normalize_catalog_csv(csv_text=normalized, profile=profile)
