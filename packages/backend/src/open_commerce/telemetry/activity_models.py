"""Bounded operational telemetry contracts; no free-form event payloads or personal text."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from open_commerce.core.redaction import contains_direct_pii_or_secret
from open_commerce.core.types import StrictDomainModel


class ActivityKind(StrEnum):
    CHAT = "chat"
    SEARCH = "search"
    MEMORY_SAVE = "memory_save"
    CATALOG_BROWSE = "catalog_browse"
    PRODUCT_SELECT = "product_select"
    CART_ADD = "cart_add"
    CART_CHANGE = "cart_change"
    CHECKOUT_PREVIEW = "checkout_preview"
    CHECKOUT_CONFIRM = "checkout_confirm"


class ActivityEventInput(StrictDomainModel):
    kind: ActivityKind
    status: Literal["ok", "error", "fallback"]
    duration_ms: int = Field(ge=0, le=3600000)
    result_count: int | None = Field(default=None, ge=0, le=1000000)


class ActivityEvent(ActivityEventInput):
    id: UUID
    occurred_at: datetime


class ActivityQuery(StrictDomainModel):
    include_test_sessions: bool = False
    kind: ActivityKind | None = None
    status: Literal["ok", "error", "fallback"] | None = None
    empty_results_only: bool = False
    window_minutes: int = Field(default=1440, ge=5, le=43200)


class ActivityRuleInput(StrictDomainModel):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
    query: ActivityQuery = Field(default_factory=ActivityQuery)
    metric: Literal["count", "error_rate", "empty_result_rate", "p95_duration_ms"] = "count"
    threshold: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    minimum_samples: int = Field(default=5, ge=1, le=5000)
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    enabled: bool = True

    @model_validator(mode="after")
    def safe_rule(self) -> "ActivityRuleInput":
        if contains_direct_pii_or_secret(self.name):
            raise ValueError("Use a non-personal label for the log view")
        if self.metric in {"error_rate", "empty_result_rate"} and self.threshold is not None:
            if self.threshold > 100:
                raise ValueError("Rate thresholds use percent from 0 to 100")
        if self.metric == "empty_result_rate" and self.query.kind != ActivityKind.SEARCH:
            raise ValueError("Empty-result rate requires search events")
        if self.metric == "error_rate" and self.query.status is not None:
            raise ValueError("Error-rate denominators must include every outcome")
        if self.metric == "empty_result_rate" and (
            self.query.empty_results_only or self.query.status is not None
        ):
            raise ValueError("Empty-result denominators must include all searches")
        return self


class ActivityCheck(StrictDomainModel):
    checked_at: datetime
    state: Literal["ok", "alert", "insufficient_data", "paused", "log_only", "pending"]
    sample_count: int = 0
    value: float | None = None
    truncated: bool = False


class ActivityRule(StrictDomainModel):
    id: UUID
    definition: ActivityRuleInput
    check: ActivityCheck
    next_check_at: datetime | None = None


class ActivityOverview(StrictDomainModel):
    scope: Literal["my_activity", "store_activity"]
    available_kinds: list[ActivityKind] = Field(
        default_factory=lambda: [kind for kind in ActivityKind]
    )
    available_fields: list[str] = Field(
        default_factory=lambda: [
            "kind",
            "status",
            "duration_ms",
            "result_count",
            "occurred_at",
        ]
    )
    observed_counts: dict[str, int]
    events: list[ActivityEvent]
    rules: list[ActivityRule]
    checked_at: datetime
    retention_days: int = 30
    event_limit: int = 100
    limitation: str = (
        "Operational events only; no chat text, queries, account identifiers or preference "
        "contents. Ad-hoc views use these fields, not arbitrary new tracking. Test checkout "
        "events do not represent real revenue. Monitors report in-app, not external alerts."
    )
