"""Simulator API routes."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.pagination import paginate_items
from open_commerce.api.services import SimulatorRuntime as SimulatorService
from open_commerce.api.services import resolve
from open_commerce.simulator.models import (
    AdvanceSimulatorRequest,
    BaselineComparisonResponse,
    CreateSimulatorInstanceAliasRequest,
    CreateSimulatorInstanceRequest,
    ResetSimulatorRequest,
    RunUntilSimulatorRequest,
    ScenarioListResponse,
    SimulatorMetricsResponse,
    SimulatorStateResponse,
)
from open_commerce.simulator.service import (
    ScenarioNotFoundError,
    SimulatorBusyError,
    SimulatorError,
    SimulatorInstanceNotFoundError,
)

router = APIRouter(prefix="/v1/simulator", tags=["simulator"])
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]


def get_simulator_service(request: Request) -> SimulatorService:
    """Return the app-level simulator service."""

    return cast(SimulatorService, request.app.state.simulator_service)


@router.get("/scenarios", response_model=ScenarioListResponse)
async def list_simulator_scenarios(
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> ScenarioListResponse:
    """List available deterministic simulator scenarios."""

    return service.list_scenarios()


@router.post(
    "/instances",
    response_model=SimulatorStateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_instance_alias(
    payload: CreateSimulatorInstanceAliasRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Create a simulator instance through the contract root route."""

    try:
        return await resolve(
            service.create_instance(
                tenant_id=context.tenant_id,
                scenario_id=payload.scenario_id,
                seed=payload.seed,
                idempotency_key=idempotency_key,
            )
        )
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found"
        ) from exc


@router.post(
    "/scenarios/{scenario_id}/instances",
    response_model=SimulatorStateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulator_instance(
    scenario_id: str,
    payload: CreateSimulatorInstanceRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Create a tenant-scoped simulator instance."""

    try:
        return await resolve(
            service.create_instance(
                tenant_id=context.tenant_id,
                scenario_id=scenario_id,
                seed=payload.seed,
                idempotency_key=idempotency_key,
            )
        )
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found"
        ) from exc


@router.get("/instances/{instance_id}", response_model=SimulatorStateResponse)
async def get_simulator_instance_alias(
    instance_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Return simulator instance state through the contract root route."""

    return await get_simulator_state(
        instance_id=instance_id,
        context=context,
        service=service,
    )


@router.get("/instances/{instance_id}/state", response_model=SimulatorStateResponse)
async def get_simulator_state(
    instance_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Return simulator instance state."""

    try:
        return await resolve(
            service.get_state(tenant_id=context.tenant_id, instance_id=instance_id)
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc


@router.post("/instances/{instance_id}/advance", response_model=SimulatorStateResponse)
async def advance_simulator_instance(
    instance_id: UUID,
    payload: AdvanceSimulatorRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Advance simulator virtual time by hours."""

    try:
        return await resolve(
            service.advance(
                tenant_id=context.tenant_id,
                instance_id=instance_id,
                hours=payload.hours,
                idempotency_key=idempotency_key,
            )
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc
    except SimulatorBusyError:
        raise
    except (SimulatorError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/run-until", response_model=SimulatorStateResponse)
async def run_simulator_until(
    instance_id: UUID,
    payload: RunUntilSimulatorRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Run simulator virtual time until a timestamp."""

    try:
        return await resolve(
            service.run_until(
                tenant_id=context.tenant_id,
                instance_id=instance_id,
                timestamp=payload.timestamp,
                idempotency_key=idempotency_key,
            )
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc
    except SimulatorBusyError:
        raise
    except (SimulatorError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/reset", response_model=SimulatorStateResponse)
async def reset_simulator_instance(
    instance_id: UUID,
    payload: ResetSimulatorRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> SimulatorStateResponse:
    """Reset a simulator instance to its scenario start."""

    try:
        return await resolve(
            service.reset(
                tenant_id=context.tenant_id,
                instance_id=instance_id,
                seed=payload.seed,
                idempotency_key=idempotency_key,
            )
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc


@router.get("/instances/{instance_id}/metrics", response_model=SimulatorMetricsResponse)
async def get_simulator_metrics(
    instance_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
    cursor: str | None = None,
    limit: int = Query(default=60, ge=1, le=400),
) -> SimulatorMetricsResponse:
    """Return simulator metrics."""

    try:
        response = await resolve(
            service.metrics(tenant_id=context.tenant_id, instance_id=instance_id)
        )
        items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
        return SimulatorMetricsResponse(
            instance_id=response.instance_id,
            items=items,
            next_cursor=next_cursor,
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc


@router.get("/instances/{instance_id}/compare-baseline", response_model=BaselineComparisonResponse)
async def compare_simulator_baseline(
    instance_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[SimulatorService, Depends(get_simulator_service)],
) -> BaselineComparisonResponse:
    """Compare current simulator outcomes with a no-intervention baseline."""

    try:
        return await resolve(
            service.compare_baseline(tenant_id=context.tenant_id, instance_id=instance_id)
        )
    except SimulatorInstanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instance not found"
        ) from exc
