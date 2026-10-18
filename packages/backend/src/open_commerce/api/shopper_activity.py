"""Instrument authenticated operations without logging request or response bodies."""

import json
from collections.abc import Callable, Coroutine
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from fastapi.routing import APIRoute

from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.telemetry.activity import ActivityService
from open_commerce.telemetry.activity_models import ActivityEventInput, ActivityKind

OPERATIONS = {
    "chat_with_shopper_agent": ActivityKind.CHAT,
    "browse_shopper_catalog": ActivityKind.CATALOG_BROWSE,
    "add_shopper_cart_item": ActivityKind.CART_CHANGE,
    "update_shopper_cart_item": ActivityKind.CART_CHANGE,
    "delete_shopper_cart_item": ActivityKind.CART_CHANGE,
    "preview_shopper_checkout": ActivityKind.CHECKOUT_PREVIEW,
    "confirm_shopper_checkout": ActivityKind.CHECKOUT_CONFIRM,
}


class ShopperActivityRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            started = monotonic()
            response: Response | None = None
            try:
                response = await original(request)
                return response
            finally:
                kind = OPERATIONS.get(self.name)
                identity = getattr(request.state, "shopper_activity_identity", None)
                database = getattr(request.app.state.shopper_agent_service, "database", None)
                if (
                    kind is not None
                    and identity is not None
                    and isinstance(database, RuntimeDatabase)
                ):
                    status = "error" if response is None or response.status_code >= 400 else "ok"
                    if (
                        response is not None
                        and status == "ok"
                        and kind
                        in {
                            ActivityKind.CHAT,
                            ActivityKind.CHECKOUT_CONFIRM,
                        }
                    ):
                        body = json.loads(bytes(response.body))
                        if body.get("status") in {"failed", "declined"}:
                            status = "error"
                        if any(
                            step.get("status") == "fallback"
                            for step in body.get("assistant_message", {}).get("steps", [])
                        ):
                            status = "fallback"
                    event = ActivityEventInput.model_validate(
                        {
                            "kind": kind,
                            "status": status,
                            "duration_ms": min(3600000, int((monotonic() - started) * 1000)),
                        }
                    )
                    key = request.headers.get("Idempotency-Key") or str(uuid4())
                    await ActivityService(database).record_best_effort(
                        tenant_id=identity[0],
                        account_id=identity[1],
                        event=event,
                        key=f"{self.name}:{key}",
                        account_version=getattr(request.state, "shopper_activity_version", None),
                    )
                    if self.name == "add_shopper_cart_item" and status == "ok":
                        await ActivityService(database).record_best_effort(
                            tenant_id=identity[0],
                            account_id=identity[1],
                            event=ActivityEventInput(
                                kind=ActivityKind.CART_ADD,
                                status="ok",
                                duration_ms=event.duration_ms,
                            ),
                            key=f"cart-add:{key}",
                            account_version=getattr(
                                request.state, "shopper_activity_version", None
                            ),
                        )

        return handle
