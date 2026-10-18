"""Catalog service dependency shared by authenticated surface routes."""

from typing import cast

from fastapi import Request

from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.persistence.runtime_db import RuntimeDatabase


def get_catalog_browser(request: Request) -> CatalogBrowseService:
    return CatalogBrowseService(cast(RuntimeDatabase, request.app.state.database))
