"""Shared strict domain value objects and canonical hashing helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence, Set
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JsonScalar = str | int | float | bool | None
JsonObject = dict[str, object]


class StrictDomainModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def utc_now() -> datetime:
    """Return the current timestamp as timezone-aware UTC."""

    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Require an aware datetime and normalize it to UTC."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class TimeWindow(StrictDomainModel):
    """Inclusive-exclusive time window."""

    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_order(self) -> TimeWindow:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class EntityRef(StrictDomainModel):
    """Opaque reference to a domain or provider entity."""

    type: str
    id: str
    tenant_id: UUID | None = None
    version: str | None = None


class ActorRef(StrictDomainModel):
    """Actor that initiated a domain event or decision."""

    type: str = Field(pattern="^(system|user|agent|provider)$")
    id: str
    roles: set[str] = Field(default_factory=set)


class ProviderRef(StrictDomainModel):
    """Provider target for a compiled action."""

    provider_type: str
    integration_id: UUID | None
    resource_type: str
    resource_id: str


class Precondition(StrictDomainModel):
    """Optimistic-concurrency precondition for a write."""

    field: str
    operator: str
    value: object


class SafeError(StrictDomainModel):
    """Redacted error payload suitable for storage and APIs."""

    code: str
    message: str
    retryable: bool = False
    details: JsonObject = Field(default_factory=dict)


class FreshnessStatus(StrictDomainModel):
    """Freshness status for one source."""

    state: str
    observed_at: datetime | None = None
    max_age_seconds: int | None = None

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class ConfidenceSummary(StrictDomainModel):
    """Confidence metadata attached to an observation snapshot."""

    level: Decimal
    sample_size: int | None = None
    notes: list[str] = Field(default_factory=list)


def _canonicalize(value: object) -> object:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, Set) and not isinstance(value, str):
        canonical_items = [_canonicalize(item) for item in value]
        return sorted(canonical_items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonicalize(item) for item in value]
    return value


def canonical_json(value: object) -> str:
    """Serialize a value to deterministic JSON."""

    return json.dumps(
        _canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def canonical_hash(value: object) -> str:
    """Return a stable SHA-256 hash over deterministic JSON."""

    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
