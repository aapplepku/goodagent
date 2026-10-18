"""Store-owned catalog review contracts, never included in model prompts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from open_commerce.catalog.models import CatalogIndexStatus, CatalogProductInput
from open_commerce.core.types import StrictDomainModel


class ImportMapping(StrictDomainModel):
    mapping: dict[str, str] = Field(default_factory=dict, max_length=30)
    currency: Literal["USD", "EUR", "GBP", "CAD", "AUD"] | None = None


class ImportConfirmRequest(StrictDomainModel):
    expected_review_fingerprint: str = Field(
        min_length=71, max_length=71, pattern=r"^sha256:[0-9a-f]{64}$"
    )


class ImportIssue(StrictDomainModel):
    row: int = Field(ge=1)
    message: str = Field(max_length=1000)


class ImportReview(StrictDomainModel):
    review_fingerprint: str | None = Field(
        default=None, min_length=71, max_length=71, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    sample_data: bool = False
    id: UUID
    filename: str
    status: str
    expires_at: datetime
    columns: list[str]
    mapping: dict[str, str]
    currency: str | None
    row_count: int
    product_count: int = 0
    errors: list[ImportIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    products: list[CatalogProductInput] = Field(default_factory=list, max_length=20)
    indexing: CatalogIndexStatus | None = None
    catalog_id: UUID | None = None
