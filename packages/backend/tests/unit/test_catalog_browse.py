"""Role and query validation for read-only catalog browsing."""

from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.manager import router


async def test_manager_catalog_requires_operator_role() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        tenant_id=uuid4(), actor_id="viewer", roles={"viewer"}
    )
    app.dependency_overrides[get_catalog_browser] = lambda: None
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/v1/manager/catalog")
    assert response.status_code == 403
