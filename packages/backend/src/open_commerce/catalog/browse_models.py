"""Read-only contracts for browsing the verified published catalog."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.money import Money
from open_commerce.core.types import StrictDomainModel


class CatalogBrowseQuery(StrictDomainModel):
    q: str = Field(default="", max_length=200)
    product_id: str | None = Field(default=None, max_length=240)
    category: str = Field(default="", max_length=240)
    sort: Literal["title", "title_desc", "price_asc", "price_desc"] = "title"
    in_stock: bool = False
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=24, ge=1, le=48)


class PublishedCatalog(StrictDomainModel):
    id: UUID
    filename: str
    source_version: str
    product_count: int
    published_at: datetime | None


class CatalogVariant(StrictDomainModel):
    id: str
    title: str
    options: dict[str, str | int | bool | list[str]]
    price: Money
    available: bool
    availability: Literal["available", "out_of_stock", "unknown"] = "unknown"


class CatalogBrowseProduct(StrictDomainModel):
    product_id: str
    title: str
    description: str
    brand: str | None
    category: str
    image_url: str | None
    variant_id: str
    price: Money
    availability: Literal["available", "out_of_stock", "unknown"]
    provenance: str | None
    variants: list[CatalogVariant] = Field(default_factory=list)


class CatalogBrowseResponse(StrictDomainModel):
    catalog: PublishedCatalog | None
    indexing: CatalogIndexStatus
    categories: list[str]
    items: list[CatalogBrowseProduct]
    total: int
    offset: int
    limit: int
