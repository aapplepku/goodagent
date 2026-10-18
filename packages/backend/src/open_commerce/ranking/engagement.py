"""Allowlisted engagement normalization. Raw text/identifiers never survive intake."""

import csv
import io
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID

from pydantic import ValidationError

from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import canonical_json, utc_now
from open_commerce.ranking.models import EngagementEvent, RankingDataError

_KINDS = {
    "search": "search",
    "search_submitted": "search",
    "impression": "impression",
    "product_impression": "impression",
    "click": "click",
    "product_clicked": "click",
    "product_click": "click",
    "product_view": "product_view",
    "product_viewed": "product_view",
    "view": "product_view",
    "add_to_cart": "add_to_cart",
    "purchase": "purchase",
}


def normalize_engagement(tenant_id: UUID, csv_text: str) -> list[EngagementEvent]:
    from open_commerce.manager_agent.data_onboarding import profile_csv

    profile = profile_csv(dataset_kind="engagement", filename="engagement.csv", csv_text=csv_text)
    if profile.missing_required:
        raise RankingDataError("Engagement needs event_type, occurred_at and product_id columns.")
    mappings = profile.detected_mappings
    events: dict[str, EngagementEvent] = {}
    for row in csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""), strict=True):
        values = {name: (row.get(column) or "").strip() for name, column in mappings.items()}

        def value(name: str, fields: dict[str, str] = values) -> str:
            return fields.get(name, "")

        kind = _KINDS.get(value("event_type").lower())
        if kind is None:
            raise RankingDataError(
                "Unsupported event type. Use impressions, clicks, views, carts or purchases."
            )
        product = value("product_id")
        # Reject credential-shaped content even in columns that will be discarded.
        if any(redact_model_text(item or "") != (item or "") for item in row.values()):
            raise RankingDataError("Remove secrets and direct identifiers from engagement data.")
        try:
            at = datetime.fromisoformat(value("occurred_at").replace("Z", "+00:00"))
            session = value("session_id")
            normalized = {
                "product_id": product,
                "kind": kind,
                "at": at.isoformat(),
                "session": _hash(tenant_id, session) if session else None,
            }
            key = _hash(tenant_id, value("event_id") or canonical_json(normalized))
            event = EngagementEvent.model_validate({"key": key, **normalized})
        except (ValueError, ValidationError) as exc:
            raise RankingDataError(
                "Events need bounded product IDs and timezone-aware ISO timestamps."
            ) from exc
        if event.at > utc_now() + timedelta(minutes=5):
            raise RankingDataError("Future engagement timestamps cannot be used for training.")
        if key in events and events[key] != event:
            raise RankingDataError(
                "One event ID has conflicting values; fix the export before training."
            )
        events[key] = event
    return sorted(events.values(), key=lambda event: (event.at, event.key))


def _hash(tenant_id: UUID, value: str) -> str:
    return sha256(f"{tenant_id}:{value}".encode()).hexdigest()
