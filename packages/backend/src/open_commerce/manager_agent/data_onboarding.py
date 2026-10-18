"""Typed, bounded data-onboarding helpers with no provider dependencies."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Iterable

from open_commerce.core.types import utc_now
from open_commerce.manager_agent.errors import ManagerDatasetProfileError
from open_commerce.manager_agent.models import (
    DatasetKind,
    DatasetProfile,
    DataSourceDraft,
    ManagerDataOnboarding,
)

MAX_CSV_BYTES = 524_288
MAX_CSV_COLUMNS = 64
MAX_CSV_ROWS = 10_000

_CATALOG_ALIASES: dict[str, tuple[str, ...]] = {
    "product_id": ("product_id", "product id", "id", "handle", "url handle"),
    "title": ("title", "name", "product_title", "product title"),
    "description": ("description", "body_html", "body html", "product description"),
    "category": ("category", "product category", "type", "product_type"),
    "brand": ("brand", "vendor", "manufacturer"),
    "variant_id": ("variant_id", "variant id"),
    "sku": ("sku", "variant sku"),
    "price": ("price", "price_minor", "price minor", "variant price", "fixed price"),
    "currency": ("currency", "currency_code", "currency code"),
    "inventory_quantity": (
        "inventory_quantity",
        "inventory quantity",
        "available",
        "quantity",
    ),
    "image_url": ("image_url", "image url", "product image url", "image src"),
    "updated_at": ("updated_at", "updated at", "modified_at", "modified at"),
    "tags": ("tags", "product tags"),
    "popularity_score": ("popularity_score", "popularity score", "popularity"),
    "average_rating": ("average_rating", "average rating", "rating"),
    "review_count": ("review_count", "review count", "reviews"),
    "related_product_ids": (
        "related_product_ids",
        "related product ids",
        "related_products",
    ),
}

_ENGAGEMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "event_id": ("event_id", "event id", "id"),
    "event_type": ("event_type", "event type", "event", "name"),
    "occurred_at": ("occurred_at", "occurred at", "timestamp", "event_time", "event time"),
    "product_id": ("product_id", "product id", "item_id", "item id"),
    "anonymous_id": ("anonymous_id", "anonymous id", "visitor_id", "visitor id"),
    "session_id": ("session_id", "session id"),
    "position": ("position", "rank"),
    "query_id": ("query_id", "query id", "request_id", "request id"),
}

_REQUIRED: dict[DatasetKind, tuple[str, ...]] = {
    "catalog": ("product_id", "title"),
    "engagement": ("event_type", "occurred_at", "product_id"),
}

_DIRECT_IDENTIFIER_HEADERS = {
    "email",
    "email_address",
    "phone",
    "phone_number",
    "first_name",
    "last_name",
    "full_name",
    "customer_name",
    "address",
    "street_address",
    "postal_address",
    "ip",
    "ip_address",
}
_DIRECT_IDENTIFIER_VALUE_RE = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\w))",
    re.IGNORECASE,
)


def profile_csv(
    *, dataset_kind: DatasetKind, filename: str, csv_text: str, max_bytes: int = MAX_CSV_BYTES
) -> DatasetProfile:
    """Parse a small UTF-8 CSV and retain structural facts only."""

    encoded = csv_text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ManagerDatasetProfileError(f"CSV exceeds the {max_bytes}-byte upload limit")
    if "\x00" in csv_text:
        raise ManagerDatasetProfileError("CSV contains unsupported null bytes")

    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""), strict=True)
        raw_columns = reader.fieldnames
        if raw_columns is None:
            raise ManagerDatasetProfileError("CSV must include a header row")
        columns = [_clean_header(item) for item in raw_columns]
        if any(not item for item in columns):
            raise ManagerDatasetProfileError("CSV contains an empty column name")
        if len(columns) > MAX_CSV_COLUMNS:
            raise ManagerDatasetProfileError("CSV exceeds the 64-column onboarding preview limit")
        if len(set(_normalized_header(item) for item in columns)) != len(columns):
            raise ManagerDatasetProfileError("CSV contains duplicate column names")
        pii_columns = [item for item in columns if _is_direct_identifier_header(item)]
        if pii_columns:
            raise ManagerDatasetProfileError(
                "Remove direct-identifier columns before upload: " + ", ".join(pii_columns)
            )

        row_count = 0
        non_empty: set[str] = set()
        for row in reader:
            if row_count >= MAX_CSV_ROWS:
                raise ManagerDatasetProfileError(
                    "CSV exceeds the 10,000-row onboarding preview limit"
                )
            if None in row:
                raise ManagerDatasetProfileError("CSV row has more values than the header")
            row_count += 1
            for column, value in row.items():
                if (
                    dataset_kind == "engagement"
                    and value
                    and _DIRECT_IDENTIFIER_VALUE_RE.search(value)
                ):
                    raise ManagerDatasetProfileError(
                        "Remove direct-identifier values before uploading engagement data"
                    )
                if value and value.strip():
                    non_empty.add(_normalized_header(column))
    except (csv.Error, UnicodeError) as exc:
        raise ManagerDatasetProfileError("CSV could not be parsed as bounded UTF-8 data") from exc

    if row_count == 0:
        raise ManagerDatasetProfileError("CSV must include at least one data row")
    mappings = _detect_mappings(dataset_kind, columns)
    missing = [field for field in _REQUIRED[dataset_kind] if field not in mappings]
    warnings = [
        f"Mapped column '{source}' has no populated values in this preview."
        for canonical, source in mappings.items()
        if canonical in _REQUIRED[dataset_kind] and _normalized_header(source) not in non_empty
    ]
    if dataset_kind == "catalog" and "description" not in mappings:
        warnings.append(
            "No description mapping was detected; semantic search quality may be limited."
        )
    if dataset_kind == "engagement" and not {"anonymous_id", "session_id"} & mappings.keys():
        warnings.append(
            "No pseudonymous visitor or session identifier was detected; "
            "personalization is unavailable."
        )
    return DatasetProfile(
        dataset_kind=dataset_kind,
        filename=filename,
        content_sha256=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        byte_count=len(encoded),
        row_count=row_count,
        columns=columns,
        detected_mappings=mappings,
        missing_required=missing,
        warnings=warnings[:12],
        profiled_at=utc_now(),
    )


def attach_profile(
    onboarding: ManagerDataOnboarding, profile: DatasetProfile
) -> ManagerDataOnboarding:
    """Attach a profile without retaining or exposing the uploaded rows."""

    source = DataSourceDraft(
        dataset_kind=profile.dataset_kind,
        source_kind="csv_upload",
        display_name=profile.filename,
        profile=profile,
    )
    updates: dict[str, object] = {profile.dataset_kind: source}
    if profile.dataset_kind == "engagement":
        updates["engagement_decision"] = "provide"
    updated = onboarding.model_copy(update=updates, deep=True)
    return refresh_onboarding_status(updated)


def refresh_onboarding_status(onboarding: ManagerDataOnboarding) -> ManagerDataOnboarding:
    """Derive progress from explicit manager-provided state."""

    if not _source_ready(onboarding.catalog):
        status = "needs_catalog"
    elif onboarding.engagement_decision == "pending":
        status = "needs_engagement_decision"
    elif onboarding.cadence is None:
        status = "needs_schedule"
    else:
        status = "ready_for_review"
    return onboarding.model_copy(update={"status": status})


def onboarding_question(onboarding: ManagerDataOnboarding) -> str | None:
    if onboarding.catalog is None:
        return (
            "Where does your required product catalog live: a CSV file, Snowflake, "
            "or object storage? You can attach a CSV here; do not paste credentials."
        )
    if onboarding.catalog.source_kind == "csv_upload" and onboarding.catalog.profile:
        missing = onboarding.catalog.profile.missing_required
        if missing:
            return (
                "I could not map "
                + ", ".join(missing)
                + ". Can you upload a revised CSV or name a Markdown data-mapping document?"
            )
    if onboarding.catalog.source_kind == "csv_upload" and onboarding.catalog.profile is None:
        return "Attach the catalog CSV here, or download the sample catalog to try the flow."
    if onboarding.catalog.source_kind == "snowflake" and not _source_ready(onboarding.catalog):
        return (
            "What Snowflake account, warehouse, database, schema, and table or view should the "
            "read-only connector use? Do not paste a password, key, or token."
        )
    if onboarding.catalog.source_kind == "object_storage" and not onboarding.catalog.object_uri:
        return "What approved object-storage location contains the catalog export?"
    if onboarding.engagement_decision == "pending":
        return (
            "Would you like to provide optional pseudonymous engagement events now, "
            "or skip them for this first setup?"
        )
    if onboarding.cadence is None:
        return "How often should data refresh: manually, hourly, every six hours, daily, or weekly?"
    return None


def _source_ready(source: DataSourceDraft | None) -> bool:
    if source is None:
        return False
    if source.source_kind == "csv_upload":
        return source.profile is not None and not source.profile.missing_required
    if source.source_kind == "snowflake":
        return all(
            (
                source.account_identifier,
                source.warehouse,
                source.database,
                source.schema_name,
                source.relation,
            )
        )
    return source.object_uri is not None


def _detect_mappings(dataset_kind: DatasetKind, columns: Iterable[str]) -> dict[str, str]:
    aliases = _CATALOG_ALIASES if dataset_kind == "catalog" else _ENGAGEMENT_ALIASES
    by_normalized = {_normalized_header(column): column for column in columns}
    mappings: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            source = by_normalized.get(_normalized_header(candidate))
            if source is not None:
                mappings[canonical] = source
                break
    return mappings


def _clean_header(value: str | None) -> str:
    return " ".join((value or "").strip().split())[:100]


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def _is_direct_identifier_header(value: str) -> bool:
    normalized = _normalized_header(value).replace(" ", "_")
    return normalized in _DIRECT_IDENTIFIER_HEADERS or any(
        token in normalized.split("_") for token in ("email", "phone", "address")
    )
