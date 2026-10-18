"""Server-resolved publication snapshot, propagated through shopper service calls."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CatalogScope:
    tenant_id: UUID
    catalog_id: UUID
    preview: bool = False
    sample: bool = False


current_catalog: ContextVar[CatalogScope | None] = ContextVar("catalog_scope", default=None)


@contextmanager
def catalog_scope(scope: CatalogScope) -> Iterator[None]:
    token = current_catalog.set(scope)
    try:
        yield
    finally:
        current_catalog.reset(token)
