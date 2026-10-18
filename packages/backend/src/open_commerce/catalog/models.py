"""Typed catalog upload and indexing state."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from open_commerce.core.types import StrictDomainModel, ensure_utc

CatalogIndexState = Literal["not_configured", "queued", "running", "ready", "failed"]


class CatalogVariantInput(StrictDomainModel):
    source_variant_id: str = Field(min_length=1, max_length=240)
    sku: str | None = Field(default=None, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    price_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    available: bool
    inventory_quantity: int | None = Field(default=None, ge=0)
    option_values: dict[str, str] = Field(default_factory=dict, max_length=24)


class CatalogProductInput(StrictDomainModel):
    source_product_id: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=500)
    description_text: str = Field(default="", max_length=4000)
    brand: str | None = Field(default=None, max_length=160)
    category_path: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=40)
    attributes: dict[str, str | int | bool | list[str]] = Field(default_factory=dict, max_length=32)
    primary_image_url: str | None = Field(default=None, max_length=2000)
    source_updated_at: datetime
    variants: list[CatalogVariantInput] = Field(min_length=1, max_length=200)

    @field_validator("source_updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class CatalogIndexStatus(StrictDomainModel):
    status: CatalogIndexState = "not_configured"
    job_id: UUID | None = None
    catalog_id: UUID | None = None
    filename: str | None = Field(default=None, max_length=255)
    source_version: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    product_count: int = Field(default=0, ge=0)
    indexed_product_count: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=120)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    serving_catalog_id: UUID | None = None
    serving_product_count: int = Field(default=0, ge=0)

    @field_validator("created_at", "updated_at", "completed_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None
