"""Editable mappings and row-numbered validation; any error blocks confirmation."""

import csv
import io
from collections import defaultdict

from open_commerce.catalog.csv_import import _RESERVED, normalize_catalog_csv
from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.catalog.models import CatalogProductInput
from open_commerce.catalog.shopify_csv import ShopifyProductsExcluded, is_shopify_csv, shopify_csv
from open_commerce.manager_agent.data_onboarding import profile_csv
from open_commerce.manager_agent.models import DatasetProfile
from open_commerce.stores.import_models import ImportIssue, ImportMapping

MAX_UPLOAD = 20 * 1024 * 1024


def validate_import(
    data: str, filename: str, assignments: ImportMapping | None = None
) -> tuple[DatasetProfile, list[CatalogProductInput], list[ImportIssue]]:
    profile = profile_csv(
        dataset_kind="catalog", filename=filename, csv_text=data, max_bytes=MAX_UPLOAD
    )
    if assignments is not None:
        mapping = assignments.mapping
        if any(
            field not in _RESERVED or column not in profile.columns
            for field, column in mapping.items()
        ):
            return (
                profile,
                [],
                [ImportIssue(row=1, message="Choose supported fields and existing columns.")],
            )
        profile.detected_mappings = mapping
        profile.missing_required = [
            field for field in ("product_id", "title", "price") if field not in mapping
        ]
    else:
        profile.missing_required = [
            field
            for field in ("product_id", "title", "price")
            if field not in profile.detected_mappings
        ]
    if profile.missing_required:
        return (
            profile,
            [],
            [
                ImportIssue(
                    row=1, message="Map required fields: " + ", ".join(profile.missing_required)
                )
            ],
        )
    currency = assignments.currency if assignments else None
    if "currency" not in profile.detected_mappings and not currency:
        return (
            profile,
            [],
            [ImportIssue(row=1, message="Confirm the currency before importing prices.")],
        )
    reader = csv.DictReader(io.StringIO(data.lstrip("\ufeff"), newline=""), strict=True)
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    errors: list[ImportIssue] = []
    shopify = is_shopify_csv(profile.columns)
    for row in reader:
        line = reader.line_num
        if any(value is None for value in row.values()):
            errors.append(ImportIssue(row=line, message="Row has fewer values than the header."))
            continue
        price_column = profile.detected_mappings.get("price")
        currency_column = profile.detected_mappings.get("currency")
        shopify_image_row = shopify and not row.get(price_column or "")
        if not shopify_image_row and (
            not row.get(price_column or "", "").strip()
            or (
                currency_column
                and row.get(currency_column, "").strip().upper()
                not in {"USD", "EUR", "GBP", "CAD", "AUD"}
            )
        ):
            errors.append(
                ImportIssue(
                    row=line, message="Each variant needs a price and a supported currency."
                )
            )
            continue
        grouped[row.get(profile.detected_mappings["product_id"], "")].append((line, row))
    products: list[CatalogProductInput] = []
    for rows in grouped.values():
        columns = list(profile.columns)
        local = profile.model_copy(deep=True)
        if not shopify and "currency" not in local.detected_mappings and currency:
            columns.append("__confirmed_currency")
            local.detected_mappings["currency"] = "__confirmed_currency"
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for _, row in rows:
            writer.writerow(
                {
                    **row,
                    **(
                        {"__confirmed_currency": currency}
                        if "__confirmed_currency" in columns
                        else {}
                    ),
                }
            )
        try:
            if shopify:
                result = shopify_csv(output.getvalue(), currency) or []
            else:
                result = normalize_catalog_csv(csv_text=output.getvalue(), profile=local)
            products.extend(result)
        except ShopifyProductsExcluded:
            profile.warnings.append(
                f"Rows starting at {rows[0][0]}: draft/unpublished Shopify product excluded."
            )
        except CatalogCSVError as exc:
            errors.append(ImportIssue(row=rows[0][0], message=str(exc)[:1000]))
    if not products and not errors:
        errors.append(ImportIssue(row=1, message="No published, priced products were found."))
    return profile, products, errors[:100]
