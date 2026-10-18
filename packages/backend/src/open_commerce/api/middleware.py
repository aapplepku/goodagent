"""API middleware."""

import re
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind and return a request ID for every HTTP request."""

    def __init__(self, app: ASGIApp, request_id_header: str = "x-request-id") -> None:
        super().__init__(app)
        self.request_id_header = request_id_header

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        provided = request.headers.get(self.request_id_header, "")
        request_id = provided if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", provided) else str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers[self.request_id_header] = request_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()
