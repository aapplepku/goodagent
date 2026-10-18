"""Versioned simulator-only serving, price and promotion records."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from open_commerce.core.merchandising import (
    MerchandisingConstraints,
    RecommendationControls,
    UnitEconomics,
)
from open_commerce.core.types import StrictDomainModel, ensure_utc

MERCHANDISING_ENGINE_VERSION = "simulator.3-merchandising-v1"


class MerchandisingSummary(StrictDomainModel):
    catalog_version: str = "merchandising-catalog-v1"
    promotion_cap_minor: int
    promotion_redeemed_value_minor: int
    promotion_remaining_minor: int
    recommendation_policy_version: int
    recommendation_strategy: Literal["alternatives", "complements"]
    serving_batches: int
    recorded_checkouts: int
    net_revenue_minor: int
    contribution_profit_minor: int
    incoming_traffic: Literal["fixed_external_no_acquisition"] = "fixed_external_no_acquisition"


class PriceRevision(StrictDomainModel):
    reference_price_minor: int = Field(gt=0)
    version: int = Field(default=0, ge=0)
    cumulative_change_minor: int = Field(default=0, ge=0)
    last_changed_at: datetime | None = None
    revert_price_minor: int | None = Field(default=None, gt=0)
    expires_at: datetime | None = None
    command_key: str | None = None

    @field_validator("last_changed_at", "expires_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value else None


class RecommendationPolicyState(StrictDomainModel):
    version: int = Field(default=0, ge=0)
    controls: RecommendationControls = Field(default_factory=RecommendationControls)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    command_key: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value else None


class CompatibilityEvidence(StrictDomainModel):
    anchor_product_id: str
    complement_product_id: str
    evidence_id: str = Field(min_length=1, max_length=160)
    relation: Literal["explicit_catalog_compatibility"] = "explicit_catalog_compatibility"


class ProductOutcomes(StrictDomainModel):
    search_exposures: int = Field(default=0, ge=0)
    recommendation_exposures: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    carts: int = Field(default=0, ge=0)
    orders: int = Field(default=0, ge=0)
    units: int = Field(default=0, ge=0)
    net_revenue_minor: int = Field(default=0, ge=0)
    contribution_profit_minor: int = 0
    redemption_value_minor: int = Field(default=0, ge=0)


class PromotionRedemption(StrictDomainModel):
    order_key: str
    request_hash: str
    product_id: str
    variant_id: str
    discount_id: str | None
    occurred_at: datetime
    status: Literal["redeemed", "declined"]
    reason: str
    economics: UnitEconomics

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class MerchandisingState(StrictDomainModel):
    """Persisted in the tenant-locked simulator transaction, never a global cache."""

    constraints: MerchandisingConstraints
    prices: dict[str, PriceRevision]
    recommendation_policy: RecommendationPolicyState = Field(
        default_factory=RecommendationPolicyState
    )
    compatibility: list[CompatibilityEvidence] = Field(default_factory=list)
    promotion_spent_minor: int = Field(default=0, ge=0)
    redemptions: dict[str, PromotionRedemption] = Field(default_factory=dict)
    checkout_lines: dict[str, list[str]] = Field(default_factory=dict)
    product_outcomes: dict[str, ProductOutcomes] = Field(default_factory=dict)
    serving_log: dict[str, ServingBatch] = Field(default_factory=dict)
    daily_product_outcomes: dict[str, dict[str, ProductOutcomes]] = Field(default_factory=dict)


class ServingBatch(StrictDomainModel):
    """All identical exposed lists aggregated, with complete order references."""

    day: str
    surface: Literal["search", "product_detail"]
    query: str | None = None
    anchor_product_id: str | None = None
    policy_version: int | None = None
    ranking_version: str
    embedding_model: str
    product_ids: list[str]
    relevance: dict[str, Decimal] = Field(default_factory=dict)
    constraint_matches: dict[str, dict[str, bool]] = Field(default_factory=dict)
    recommendation_strategy: Literal["alternatives", "complements"] | None = None
    eligible_sessions: int = Field(default=0, ge=0)
    clicks: dict[str, int] = Field(default_factory=dict)
    carts: dict[str, int] = Field(default_factory=dict)
    order_keys: list[str] = Field(default_factory=list)


MerchandisingState.model_rebuild()
