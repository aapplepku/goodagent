"""Finite ranking contracts; no provider or framework dependencies."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, FiniteFloat, field_validator, model_validator

from open_commerce.core.types import StrictDomainModel, ensure_utc

RankingTarget = Literal["product_view", "click", "add_to_cart", "purchase"]
RankingMethod = Literal["popularity", "logistic_regression"]


class EngagementEvent(StrictDomainModel):
    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    product_id: str = Field(min_length=1, max_length=240)
    kind: Literal["search", "impression", "click", "product_view", "add_to_cart", "purchase"]
    at: datetime
    session: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class TrainRankingInput(StrictDomainModel):
    goal: str = Field(min_length=8, max_length=500)
    target: RankingTarget
    method: RankingMethod


class RankingModelRef(StrictDomainModel):
    model_id: UUID


class RankingPreviewInput(RankingModelRef):
    query: str = Field(min_length=1, max_length=200)


class RankingApproval(StrictDomainModel):
    model_id: UUID | None
    expected_active_id: UUID | None
    artifact_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    confirm: Literal["APPLY_LOCAL_RANKING", "DISABLE_LOCAL_RANKING"]


class RankingArtifact(StrictDomainModel):
    format: Literal["engagement-ranker-v1"] = "engagement-ranker-v1"
    method: RankingMethod
    target: RankingTarget
    features: list[str]
    coefficients: list[FiniteFloat]
    intercept: FiniteFloat
    scores: dict[str, Annotated[FiniteFloat, Field(ge=0, le=1)]]
    feature_cutoff: datetime
    evaluation_cutoff: datetime
    seed: Literal[42] = 42
    library: str

    @model_validator(mode="after")
    def coherent_artifact(self) -> "RankingArtifact":
        if self.method == "logistic_regression" and len(self.coefficients) != len(self.features):
            raise ValueError("Ranking coefficients must match features")
        if ensure_utc(self.feature_cutoff) > ensure_utc(self.evaluation_cutoff):
            raise ValueError("Evaluation must follow feature collection")
        return self


class RankingModel(StrictDomainModel):
    id: UUID
    catalog_id: UUID
    dataset_id: UUID
    goal: str
    target: RankingTarget
    method: RankingMethod
    status: Literal["queued", "running", "ready", "failed"]
    active: bool
    artifact_hash: str | None
    metrics: dict[str, float | int | str | bool | None]
    error: str | None
    created_at: datetime
    updated_at: datetime


class EngagementSummary(StrictDomainModel):
    id: UUID
    fingerprint: str
    event_count: int
    product_count: int
    event_counts: dict[str, int]
    session_count: int
    start_at: datetime
    end_at: datetime


class RankingOverview(StrictDomainModel):
    catalog_id: UUID | None
    dataset: EngagementSummary | None
    models: list[RankingModel]


class RankingDataError(ValueError):
    """Safe actionable data or approval failure, never a raw provider exception."""
