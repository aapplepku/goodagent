"""Common API error envelope handling."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

from open_commerce.api.schemas import ApiError, ErrorEnvelope, ErrorType
from open_commerce.catalog.errors import CatalogCSVError
from open_commerce.catalog.sources import CatalogSourceError
from open_commerce.commerce.errors import (
    CommerceConflictError,
    CommerceNotFoundError,
    CommercePolicyDeniedError,
    CommercePreconditionError,
)
from open_commerce.core.errors import BudgetOverspendError
from open_commerce.manager_agent.errors import (
    ManagerDatasetProfileError,
    ManagerMemoryImmutableError,
    ManagerMemoryNotFoundError,
    ManagerModelUnavailableError,
    ManagerThreadBusyError,
    ManagerThreadInvalidError,
    ManagerThreadNotFoundError,
)
from open_commerce.persistence.repositories.requests import IdempotencyConflictError
from open_commerce.persistence.runtime_db import DatabaseUnavailableError
from open_commerce.ranking.models import RankingDataError
from open_commerce.search.errors import (
    SearchConstraintsError,
    SearchContextNotFoundError,
    SearchUnavailableError,
)
from open_commerce.shopper_agent.errors import (
    ShopperAccountConflictError,
    ShopperAuthenticationError,
    ShopperConversationNotFoundError,
    ShopperMemoryNotFoundError,
    ShopperUnsafeInputError,
)
from open_commerce.simulator.service import SimulatorBusyError
from open_commerce.stores.models import StoreError, StoreUnavailableError


def register_exception_handlers(app: FastAPI) -> None:
    """Register redacted public error handlers on a FastAPI app."""

    @app.exception_handler(StoreError)
    async def store_error(request: Request, exc: StoreError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=exc.status_code,
            error_type=_type_for_status(exc.status_code, detail=str(exc)),
            code="STORE_UNAVAILABLE"
            if isinstance(exc, StoreUnavailableError)
            else "STORE_REQUEST_BLOCKED",
            message=str(exc),
            retryable=exc.status_code in {429, 503},
        )

    @app.exception_handler(RankingDataError)
    async def ranking_invalid(request: Request, exc: RankingDataError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=422,
            error_type="validation_error",
            code="RANKING_BLOCKED",
            message=str(exc),
        )

    @app.exception_handler(SearchUnavailableError)
    async def search_unavailable(request: Request, exc: SearchUnavailableError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=503,
            error_type="temporarily_unavailable",
            code="SEARCH_UNAVAILABLE",
            message="Search is temporarily unavailable. Retry after recovery.",
            retryable=True,
        )

    @app.exception_handler(CommerceNotFoundError)
    async def commerce_not_found(request: Request, exc: CommerceNotFoundError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=404,
            error_type="not_found",
            code="COMMERCE_NOT_FOUND",
            message=str(exc),
        )

    @app.exception_handler(CommercePreconditionError)
    async def commerce_precondition(
        request: Request, exc: CommercePreconditionError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=412,
            error_type="precondition_failed",
            code="COMMERCE_PRECONDITION_FAILED",
            message=str(exc),
        )

    @app.exception_handler(CommercePolicyDeniedError)
    async def commerce_policy_denied(
        request: Request, exc: CommercePolicyDeniedError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="policy_denied",
            code="COMMERCE_POLICY_DENIED",
            message=str(exc),
        )

    @app.exception_handler(CommerceConflictError)
    async def commerce_conflict(request: Request, exc: CommerceConflictError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="conflict",
            code="COMMERCE_CONFLICT",
            message=str(exc),
            retryable=True,
        )

    @app.exception_handler(SearchContextNotFoundError)
    async def search_context_missing(
        request: Request, exc: SearchContextNotFoundError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=404,
            error_type="not_found",
            code="NOT_FOUND",
            message="The requested catalog context was not found.",
        )

    @app.exception_handler(SearchConstraintsError)
    async def search_constraints(request: Request, exc: SearchConstraintsError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=422,
            error_type="validation_error",
            code="CONFLICTING_CONSTRAINTS",
            message="Shopper constraints conflict; none were relaxed.",
        )

    @app.exception_handler(ManagerThreadNotFoundError)
    @app.exception_handler(ManagerMemoryNotFoundError)
    async def manager_not_found(request: Request, exc: Exception) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=404,
            error_type="not_found",
            code="NOT_FOUND",
            message=str(exc),
        )

    @app.exception_handler(ManagerMemoryImmutableError)
    async def manager_memory_immutable(
        request: Request, exc: ManagerMemoryImmutableError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="conflict",
            code="MEMORY_IMMUTABLE",
            message=str(exc),
        )

    @app.exception_handler(ManagerThreadBusyError)
    async def manager_thread_busy(request: Request, exc: ManagerThreadBusyError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="conflict",
            code="MANAGER_THREAD_BUSY",
            message=str(exc),
            retryable=True,
        )

    @app.exception_handler(ManagerThreadInvalidError)
    async def manager_thread_invalid(
        request: Request, exc: ManagerThreadInvalidError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=422,
            error_type="validation_error",
            code="INVALID_MANAGER_THREAD",
            message=str(exc),
        )

    @app.exception_handler(ManagerDatasetProfileError)
    @app.exception_handler(CatalogCSVError)
    @app.exception_handler(CatalogSourceError)
    async def manager_dataset_invalid(
        request: Request, exc: ManagerDatasetProfileError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=422,
            error_type="validation_error",
            code="INVALID_DATASET",
            message=str(exc),
        )

    @app.exception_handler(ManagerModelUnavailableError)
    async def manager_model_unavailable(
        request: Request, exc: ManagerModelUnavailableError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=503,
            error_type="temporarily_unavailable",
            code="MANAGER_MODEL_UNAVAILABLE",
            message="The conversation model is temporarily unavailable. Retry shortly.",
            retryable=True,
        )

    @app.exception_handler(ShopperAuthenticationError)
    async def shopper_authentication(
        request: Request, exc: ShopperAuthenticationError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=401,
            error_type="authentication_error",
            code="SHOPPER_AUTHENTICATION_REQUIRED",
            message=str(exc),
        )

    @app.exception_handler(ShopperAccountConflictError)
    async def shopper_account_conflict(
        request: Request, exc: ShopperAccountConflictError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="conflict",
            code="SHOPPER_USERNAME_TAKEN",
            message=str(exc),
        )

    @app.exception_handler(ShopperConversationNotFoundError)
    @app.exception_handler(ShopperMemoryNotFoundError)
    async def shopper_conversation_not_found(
        request: Request, exc: ShopperConversationNotFoundError | ShopperMemoryNotFoundError
    ) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=404,
            error_type="not_found",
            code=(
                "SHOPPER_MEMORY_NOT_FOUND"
                if isinstance(exc, ShopperMemoryNotFoundError)
                else "SHOPPER_CONVERSATION_NOT_FOUND"
            ),
            message=str(exc),
        )

    @app.exception_handler(ShopperUnsafeInputError)
    async def shopper_unsafe_input(request: Request, exc: ShopperUnsafeInputError) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=422,
            error_type="validation_error",
            code="SHOPPER_INPUT_REDACTED",
            message=str(exc),
        )

    @app.exception_handler(IdempotencyConflictError)
    @app.exception_handler(BudgetOverspendError)
    @app.exception_handler(SimulatorBusyError)
    async def conflict_handler(request: Request, exc: Exception) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=409,
            error_type="conflict",
            code="IDEMPOTENCY_CONFLICT"
            if isinstance(exc, IdempotencyConflictError)
            else "SIMULATOR_BUSY"
            if isinstance(exc, SimulatorBusyError)
            else "BUDGET_UNAVAILABLE",
            message=str(exc)
            if isinstance(exc, SimulatorBusyError)
            else "The request conflicts with a durable operation or available budget.",
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        return _json_error(
            request=request,
            status_code=503,
            error_type="temporarily_unavailable",
            code="DATABASE_UNAVAILABLE",
            message="The authoritative database is temporarily unavailable.",
            retryable=True,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        error_type = _type_for_status(exc.status_code, detail=exc.detail)
        message = (
            exc.detail if isinstance(exc.detail, str) else _message_for_status(exc.status_code)
        )
        return _json_error(
            request=request,
            status_code=exc.status_code,
            error_type=error_type,
            code=_code_for(error_type, message),
            message=message,
            retryable=exc.status_code
            in {
                status.HTTP_408_REQUEST_TIMEOUT,
                status.HTTP_409_CONFLICT,
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = {
            "errors": [
                {
                    "loc": list(error.get("loc", [])),
                    "msg": error.get("msg", "validation error"),
                    "type": error.get("type", "value_error"),
                }
                for error in exc.errors()
            ]
        }
        return _json_error(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_type="validation_error",
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=details,
        )

    @app.exception_handler(Exception)
    async def internal_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _ = exc
        return _json_error(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="internal_error",
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            retryable=True,
        )


def _json_error(
    *,
    request: Request,
    status_code: int,
    error_type: ErrorType,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    envelope = ErrorEnvelope(
        error=ApiError(
            type=error_type,
            code=code,
            message=message,
            details=details or {},
            request_id=request_id,
            retryable=retryable,
        )
    )
    response = JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(envelope),
        headers=headers,
    )
    response.headers.setdefault("x-request-id", request_id)
    return response


def _type_for_status(status_code: int, *, detail: Any) -> ErrorType:
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "validation_error"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "authentication_error"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "authorization_error"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code == status.HTTP_409_CONFLICT:
        text = str(detail).lower()
        if "policy" in text or "kill switch" in text or "approval" in text:
            return "policy_denied"
        return "conflict"
    if status_code == status.HTTP_412_PRECONDITION_FAILED:
        return "precondition_failed"
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "rate_limited"
    if status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
        return "temporarily_unavailable"
    return "internal_error" if status_code >= 500 else "validation_error"


def _message_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _code_for(error_type: ErrorType, message: str) -> str:
    if error_type == "not_found":
        return "NOT_FOUND"
    if error_type == "policy_denied":
        return "POLICY_DENIED"
    if error_type == "conflict":
        return "CONFLICT"
    if error_type == "authorization_error":
        return "AUTHORIZATION_ERROR"
    return "_".join(message.upper().replace(".", "").replace("-", " ").split())[:80]
