"""Bounded HTTP input and browser isolation for the single-tenant local demo."""

import asyncio
from collections import deque
from time import monotonic

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from open_commerce.api.errors import _json_error
from open_commerce.config import Settings

SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cache-control": "no-store",
    "x-open-commerce-auth": "local-demo-only-not-production-authentication",
}


class DemoSecurityMiddleware:
    """Per-process resource limits; financial correctness remains database-enforced."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.settings = settings
        hosts = ["localhost", "127.0.0.1", "api"]
        if settings.runtime_profile != "legacy_demo":
            hosts.extend(settings.public_hosts)
        if settings.environment == "test":
            hosts.append("test")
        self.app = TrustedHostMiddleware(app, allowed_hosts=hosts, www_redirect=False)
        self.writes: deque[float] = deque()
        self.expensive: deque[float] = deque()
        self.in_flight_expensive = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request = Request(scope)
        started = False
        catalog_upload = (
            scope["path"] == "/v1/merchant/imports/upload" and scope["method"] == "POST"
        )
        request_limit = (
            20 * 1024 * 1024
            if catalog_upload
            else self.settings.manager_dataset_request_bytes
            if scope["path"].endswith("/datasets/profile")
            else self.settings.max_request_bytes
        )

        async def send_secure(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                outgoing = MutableHeaders(scope=message)
                for key, value in SECURITY_HEADERS.items():
                    if (
                        key == "x-open-commerce-auth"
                        and self.settings.runtime_profile != "legacy_demo"
                    ):
                        value = "authenticated-store-sessions"
                    outgoing[key] = value
            await send(message)

        async def reject(code: int, message: str) -> None:
            response = _json_error(
                request=request,
                status_code=code,
                error_type="rate_limited"
                if code == 429
                else "validation_error"
                if code in {400, 413, 415, 431}
                else "authorization_error",
                code=f"HTTP_{code}",
                message=message,
                retryable=code == 429,
                headers={"Retry-After": "60"} if code == 429 else None,
            )
            await response(scope, receive, send_secure)

        if sum(len(key) + len(value) for key, value in scope["headers"]) > 16384:
            await reject(431, "Request headers exceed the limit.")
            return
        if len(scope.get("query_string", b"")) > 4096:
            await reject(400, "Query exceeds the limit.")
            return
        origin = headers.get("origin")
        origins = self.settings.cors_allow_origins + self.settings.public_origins
        if origin is not None and origin not in origins:
            await reject(403, "Browser origin is not allowed for the local demo.")
            return
        oidc_callback = (
            scope["path"] == "/v1/merchant/auth/oidc/callback" and scope["method"] == "GET"
        )
        if headers.get("sec-fetch-site") == "cross-site" and not oidc_callback:
            await reject(403, "Cross-site requests are not allowed for the local demo.")
            return
        if self.settings.runtime_profile != "legacy_demo" and scope["path"].startswith(
            ("/v1/simulator", "/v1/demo")
        ):
            await reject(403, "Simulator APIs require the explicit legacy-demo profile.")
            return
        if len(headers.get("idempotency-key", "")) > 200:
            await reject(400, "Idempotency key exceeds the limit.")
            return
        try:
            length = int(headers.get("content-length", "0"))
        except ValueError:
            await reject(400, "Invalid content length.")
            return
        if length < 0 or length > request_limit:
            await reject(413, "Request body exceeds the limit.")
            return
        write = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if write and not self._admit(self.writes, self.settings.write_requests_per_minute):
            await reject(429, "Local-demo write rate limit reached.")
            return
        # Only computational endpoints share the tighter expensive-work quota.
        computational = scope["path"].endswith(
            (
                "/advance",
                "/run-until",
                "/compare-baseline",
                "/reindex",
                "/draft",
                "/chat",
                "/runs",
            )
        ) or scope["path"] in {"/v1/search", "/v1/recommendations"}
        expensive = computational
        if expensive and (
            self.in_flight_expensive >= 2
            or not self._admit(self.expensive, self.settings.expensive_requests_per_minute)
        ):
            await reject(429, "Local-demo computation limit reached.")
            return
        if catalog_upload:
            if headers.get("content-type", "").split(";", 1)[0] not in {
                "text/csv",
                "application/octet-stream",
            }:
                await reject(415, "Upload a UTF-8 CSV file.")
                return
            # Authenticate in the endpoint dependency before reading any upload bytes.
            # No plaintext temporary file or unbounded multipart parser is involved.
            async with asyncio.timeout(60):
                await self.app(scope, receive, send_secure)
            return
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > request_limit:
                        await reject(413, "Request body exceeds the limit.")
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(400, "Request body timed out.")
            return
        if body and headers.get("content-type", "").split(";", 1)[0] != "application/json":
            await reject(415, "Request bodies must use application/json.")
            return
        consumed = False

        async def receive_body() -> Message:
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        # Reading a streamed body yields; another request may have taken the last slot.
        if expensive and self.in_flight_expensive >= 2:
            await reject(429, "Local-demo computation limit reached.")
            return
        self.in_flight_expensive += int(expensive)
        try:
            await self.app(scope, receive_body, send_secure)
        except Exception as exc:
            structlog.get_logger(__name__).error("api.failed", error_type=type(exc).__name__)
            if started:
                raise
            response = _json_error(
                request=request,
                status_code=500,
                error_type="internal_error",
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                retryable=True,
            )
            await response(scope, receive, send_secure)
        finally:
            self.in_flight_expensive -= int(expensive)

    @staticmethod
    def _admit(events: deque[float], limit: int) -> bool:
        now = monotonic()
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True
