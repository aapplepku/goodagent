"""Store-wide access denial is distinct from a missing product or transient error."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.errors import register_exception_handlers
from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import DatabaseUnavailableError
from open_commerce.stores.models import StoreError, StoreUnavailableError


@pytest.mark.parametrize(
    ("error", "code", "status", "retryable"),
    [
        (StoreUnavailableError(), "STORE_UNAVAILABLE", 404, False),
        (
            StoreUnavailableError("Open a store link to start shopping."),
            "STORE_UNAVAILABLE",
            404,
            False,
        ),
        (StoreError("Product not found.", 404), "STORE_REQUEST_BLOCKED", 404, False),
        (
            StoreError("This store is not accepting shoppers yet.", 404),
            "STORE_REQUEST_BLOCKED",
            404,
            False,
        ),
        (StoreError("Sign in to continue.", 401), "STORE_REQUEST_BLOCKED", 401, False),
        (StoreError("Not allowed.", 403), "STORE_REQUEST_BLOCKED", 403, False),
        (StoreError("Try again later.", 503), "STORE_REQUEST_BLOCKED", 503, True),
    ],
)
async def test_store_error_classification(
    error: StoreError, code: str, status: int, retryable: bool
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    async def fail() -> None:
        raise error

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test")
    assert response.status_code == status
    detail = response.json()["error"]
    assert detail["code"] == code
    assert detail["message"] == str(error)
    assert detail["retryable"] is retryable
    assert detail["details"] == {}
    assert response.headers["x-request-id"] == detail["request_id"]


async def test_dependency_outage_is_not_store_revocation() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    async def fail() -> None:
        raise DatabaseUnavailableError("synthetic-private-database-detail")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["retryable"] is True
    assert "synthetic-private" not in response.text


@pytest.mark.parametrize("headers", [{}, {"x-store-slug": "x" * 121}])
async def test_missing_or_overlong_store_context_denied_before_database(
    headers: dict[str, str],
) -> None:
    app = FastAPI()
    app.state.settings = Settings(_env_file=None, runtime_profile="self_hosted")
    app.state.database = object()
    register_exception_handlers(app)

    @app.get("/v1/shopper/store")
    async def store(context: Annotated[RequestContext, Depends(get_request_context)]) -> None:
        raise AssertionError("Invalid context must not reach the route")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/shopper/store", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STORE_UNAVAILABLE"
    assert response.json()["error"]["details"] == {}
