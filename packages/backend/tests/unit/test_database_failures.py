"""Driver outages are retryable; schema/programming defects must remain defects."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from open_commerce.api.errors import register_exception_handlers
from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import DatabaseUnavailableError, RuntimeDatabase


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionRefusedError("private connection detail"),
        PoolTimeoutError("private pool detail"),
        OperationalError("private SQL", {}, RuntimeError("private credential")),
    ],
)
async def test_database_connection_failures_return_safe_retryable_503(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    database = RuntimeDatabase(Settings(environment="test"))
    sessions = MagicMock()
    sessions.return_value.__aenter__ = AsyncMock(side_effect=failure)
    monkeypatch.setattr(database, "sessions", sessions)
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/read")
    async def read() -> dict[str, str]:
        async with database.transaction(uuid4()):
            return {"status": "unexpected"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/read")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["retryable"] is True
    assert "private" not in response.text


async def test_database_schema_errors_are_not_mislabeled_as_an_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = RuntimeDatabase(Settings(environment="test"))
    sessions = MagicMock()
    sessions.return_value.__aenter__ = AsyncMock(
        side_effect=ProgrammingError("bad SQL", {}, ValueError())
    )
    monkeypatch.setattr(database, "sessions", sessions)
    with pytest.raises(ProgrammingError) as error:
        async with database.transaction(uuid4()):
            pytest.fail("The invalid schema unexpectedly worked")
    assert not isinstance(error.value, DatabaseUnavailableError)
