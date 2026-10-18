"""Fail-closed demo configuration, HTTP resource limits and redacted output."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from io import StringIO

import pytest
import structlog
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from starlette.types import Receive, Scope, Send

from open_commerce.api.main import create_app
from open_commerce.api.security import DemoSecurityMiddleware
from open_commerce.config import Settings
from open_commerce.simulator.service import SimulatorService
from open_commerce.telemetry.logging import configure_logging
from open_commerce.telemetry.redaction import redact_event, redact_text


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/v1/not-a-route", 404),
        ("DELETE", "/v1/search", 405),
    ],
)
async def test_framework_errors_keep_the_safe_envelope(method: str, path: str, status: int) -> None:
    app = create_app(Settings(environment="test"), simulator_service=SimulatorService())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["request_id"] == response.headers["x-request-id"]
    assert "Traceback" not in response.text


@pytest.mark.parametrize("environment", ["production", "staging", "hosted"])
def test_demo_auth_cannot_be_mistaken_for_production(environment: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": environment})


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://evil.example",
        "http://localhost.evil.example",
        "http://localhost/path",
    ],
)
def test_cors_rejects_nonlocal_or_inexact_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(cors_allow_origins=[origin])


async def test_http_security_limits_and_error_redaction() -> None:
    app = create_app(
        Settings(environment="test", max_request_bytes=1024, write_requests_per_minute=3),
        simulator_service=SimulatorService(),
    )

    @app.post("/v1/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    @app.get("/v1/failure")
    async def failure() -> None:
        raise RuntimeError("password=sentinel-secret customer@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        rejected = await client.post(
            "/v1/echo",
            json={},
            headers={"Origin": "https://evil.example"},
        )
        assert rejected.status_code == 403
        rejected = await client.get("/health/live", headers={"Host": "rebind.attacker.example"})
        assert rejected.status_code == 400
        rejected = await client.post(
            "/v1/echo",
            content="{}",
            headers={"Content-Type": "text/plain"},
        )
        assert rejected.status_code == 415
        huge = await client.post("/v1/echo", json={"value": "x" * 1200})
        assert huge.status_code == 413

        async def chunks() -> AsyncIterator[bytes]:
            yield b"x" * 600
            yield b"x" * 600

        chunked = await client.post(
            "/v1/echo",
            content=chunks(),
            headers={"Content-Type": "application/json"},
        )
        assert chunked.status_code == 413
        good = await client.post("/v1/echo", json={})
        assert good.status_code == 200
        limited = await client.post("/v1/echo", json={})
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "60"
        failure_response = await client.get("/v1/failure")
        assert failure_response.status_code == 500
        assert "sentinel-secret" not in failure_response.text
        assert "customer@example.com" not in failure_response.text
        assert "Traceback" not in failure_response.text
        for response in (rejected, huge, chunked, good, limited, failure_response):
            assert response.headers["x-frame-options"] == "DENY"
            assert "default-src 'none'" in response.headers["content-security-policy"]
            assert "x-request-id" in response.headers
            assert "set-cookie" not in response.headers
        invalid_id = await client.get(
            "/health/live",
            headers={"x-request-id": "customer@example.com"},
        )
        assert invalid_id.headers["x-request-id"] != "customer@example.com"


async def test_computational_rate_limit_is_separate_from_reads() -> None:
    app = create_app(
        Settings(environment="test", expensive_requests_per_minute=1),
        simulator_service=SimulatorService(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/v1/search", json={"query": "shoes"})
        assert first.status_code != 429
        second = await client.post("/v1/search", json={"query": "shoes"})
        assert second.status_code == 429
        assert (await client.get("/health/live")).status_code == 200


async def test_concurrent_body_reads_cannot_bypass_computation_limit() -> None:
    release_bodies = asyncio.Event()
    all_bodies_waiting = asyncio.Event()
    all_bodies_delivered = asyncio.Event()
    release_work = asyncio.Event()
    waiting = 0
    delivered = 0
    admitted = 0

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal admitted
        admitted += 1
        await release_work.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def body() -> AsyncIterator[bytes]:
        nonlocal waiting, delivered
        waiting += 1
        if waiting == 3:
            all_bodies_waiting.set()
        await release_bodies.wait()
        yield b"{}"
        delivered += 1
        if delivered == 3:
            all_bodies_delivered.set()

    middleware = DemoSecurityMiddleware(application, Settings(environment="test"))
    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        tasks = [
            asyncio.create_task(
                client.post(
                    "/v1/search", content=body(), headers={"Content-Type": "application/json"}
                )
            )
            for _ in range(3)
        ]
        try:
            async with asyncio.timeout(5):
                await all_bodies_waiting.wait()
                release_bodies.set()
                await all_bodies_delivered.wait()
            assert admitted == 2
            assert middleware.in_flight_expensive == 2
        finally:
            release_bodies.set()
            release_work.set()
            responses = await asyncio.gather(*tasks)
        assert sorted(response.status_code for response in responses) == [200, 200, 429]
        assert middleware.in_flight_expensive == 0
        assert (await client.post("/v1/search", json={})).status_code == 200
        assert middleware.in_flight_expensive == 0


def test_structured_pii_secrets_and_exception_objects_are_redacted() -> None:
    result = redact_event(
        logging.getLogger(),
        "info",
        {
            "event": "safe.event",
            "nested": {
                "email": "customer@example.com",
                "shipping_address": "123 Test Street",
                "access_token": "sentinel-token",
                "items": [{"phone": "+1 212 555 0123"}],
            },
            "exception": ValueError("sentinel-exception"),
            "detail": "postgresql://user:sentinel-password@db/test Bearer sentinel-bearer",
        },
    )
    serialized = json.dumps(result)
    for forbidden in ("customer@example.com", "123 Test Street", "sentinel-", "212 555"):
        assert forbidden not in serialized
    assert result["event"] == "safe.event"
    assert redact_text("call +1 (212) 555-0123 or customer@example.com") == (
        "call [REDACTED] or [REDACTED]"
    )


def test_standard_and_structured_logging_share_json_redaction() -> None:
    configure_logging()
    root = logging.getLogger()
    handler = next(item for item in root.handlers if item.name == "open-commerce-json")
    output = StringIO()
    capture = logging.StreamHandler(output)
    capture.setFormatter(handler.formatter)
    root.addHandler(capture)
    structlog.contextvars.bind_contextvars(request_id="safe-request")
    try:
        logging.getLogger("library").warning("token=sentinel-standard customer@example.com")
        structlog.get_logger("app").warning("safe.event", password="sentinel-structured")
        try:
            raise RuntimeError("sentinel-exception")
        except RuntimeError:
            logging.getLogger("library").exception("failure")
    finally:
        root.removeHandler(capture)
        structlog.contextvars.clear_contextvars()
    content = output.getvalue()
    assert "sentinel-" not in content and "customer@example.com" not in content
    assert "Traceback" not in content
    rows = [json.loads(line) for line in content.splitlines()]
    assert len(rows) == 3
    assert all(row["request_id"] == "safe-request" for row in rows)


def test_uuid_request_correlation_survives_without_exempting_pii() -> None:
    request_id = "12345678-1234-4123-8123-123456789012"
    result = redact_event(
        logging.getLogger(), "info", {"request_id": request_id, "phone": request_id}
    )
    assert result["request_id"] == request_id
    assert result["phone"] == "[REDACTED]"
    for value in ("212-555-0123", "customer@example.com", "token=sentinel-secret"):
        result = redact_event(logging.getLogger(), "info", {"request_id": value})
        assert result["request_id"] == "[REDACTED]"
