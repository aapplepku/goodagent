"""Controller, policy, goal, run, and action API routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.pagination import paginate_items
from open_commerce.api.services import ControllerRuntime as ControllerService
from open_commerce.api.services import resolve
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ActionAuditResponse,
    ActionListResponse,
    ActionNotFoundError,
    ApprovalError,
    ControllerActionRecord,
    ControllerGraphResponse,
    ControllerPolicyConfig,
    ControllerRunRecord,
    ControllerRunRequest,
    GoalCreateRequest,
    GoalListResponse,
    GoalNotFoundError,
    GoalProgressResponse,
    GoalRecord,
    GoalUpdateRequest,
    KillSwitchResponse,
    PolicyHistoryResponse,
    PolicyUpdateRequest,
    PolicyValidateRequest,
    PolicyValidationResponse,
    PolicyViolationError,
    RunListResponse,
    RunNotFoundError,
    RunTraceResponse,
)
from open_commerce.core.enums import ActionStatus, GoalStatus
from open_commerce.core.errors import InvalidTransitionError

router = APIRouter(tags=["controller"])
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]


def get_controller_service(request: Request) -> ControllerService:
    """Return the app-level controller service."""

    return cast(ControllerService, request.app.state.controller_service)


@router.get("/v1/controller/graph", response_model=ControllerGraphResponse)
async def get_controller_graph(
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerGraphResponse:
    """Return the documented controller graph and write boundary."""

    return service.graph()


@router.post(
    "/v1/goals",
    response_model=GoalRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_goal(
    payload: GoalCreateRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Create a tenant-scoped local-demo goal."""

    return await resolve(
        service.create_goal(
            tenant_id=context.tenant_id,
            request=payload,
            idempotency_key=idempotency_key,
        )
    )


@router.get("/v1/goals", response_model=GoalListResponse)
async def list_goals(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> GoalListResponse:
    """List local-demo goals."""

    response = await resolve(service.list_goals(tenant_id=context.tenant_id))
    items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
    return GoalListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/goals/{goal_id}", response_model=GoalRecord)
async def get_goal(
    goal_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Return one goal."""

    try:
        return await resolve(service.get_goal(tenant_id=context.tenant_id, goal_id=goal_id))
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal not found") from exc


@router.patch("/v1/goals/{goal_id}", response_model=GoalRecord)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdateRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Patch one goal."""

    try:
        return await resolve(
            service.update_goal(
                tenant_id=context.tenant_id,
                goal_id=goal_id,
                request=payload,
                idempotency_key=idempotency_key,
            )
        )
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal not found") from exc


@router.post("/v1/goals/{goal_id}/activate", response_model=GoalRecord)
async def activate_goal(
    goal_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Activate a goal."""

    return await _set_goal_status(
        service=service,
        context=context,
        goal_id=goal_id,
        goal_status=GoalStatus.ACTIVE,
        idempotency_key=idempotency_key,
    )


@router.post("/v1/goals/{goal_id}/pause", response_model=GoalRecord)
async def pause_goal(
    goal_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Pause a goal."""

    return await _set_goal_status(
        service=service,
        context=context,
        goal_id=goal_id,
        goal_status=GoalStatus.PAUSED,
        idempotency_key=idempotency_key,
    )


@router.post("/v1/goals/{goal_id}/archive", response_model=GoalRecord)
async def archive_goal(
    goal_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalRecord:
    """Archive a goal."""

    return await _set_goal_status(
        service=service,
        context=context,
        goal_id=goal_id,
        goal_status=GoalStatus.ARCHIVED,
        idempotency_key=idempotency_key,
    )


@router.post("/v1/goals/{goal_id}/run", response_model=ControllerRunRecord)
async def run_goal(
    goal_id: UUID,
    payload: ControllerRunRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerRunRecord:
    """Run the deterministic controller graph for a goal."""

    try:
        return await service.run_goal(
            tenant_id=context.tenant_id,
            goal_id=goal_id,
            request=payload,
            idempotency_key=idempotency_key,
        )
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal not found") from exc
    except PolicyViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/v1/goals/{goal_id}/progress", response_model=GoalProgressResponse)
async def get_goal_progress(
    goal_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> GoalProgressResponse:
    """Return goal progress."""

    try:
        return await resolve(service.goal_progress(tenant_id=context.tenant_id, goal_id=goal_id))
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal not found") from exc


@router.get("/v1/runs", response_model=RunListResponse)
async def list_runs(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    goal_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> RunListResponse:
    """List controller runs."""

    response = await resolve(service.list_runs(tenant_id=context.tenant_id, goal_id=goal_id))
    items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
    return RunListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/runs/{run_id}", response_model=ControllerRunRecord)
async def get_run(
    run_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerRunRecord:
    """Return one controller run."""

    try:
        return await resolve(service.get_run(tenant_id=context.tenant_id, run_id=run_id))
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.get("/v1/runs/{run_id}/trace", response_model=RunTraceResponse)
async def get_run_trace(
    run_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> RunTraceResponse:
    """Return ordered run trace."""

    try:
        response = await resolve(service.run_trace(tenant_id=context.tenant_id, run_id=run_id))
        items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
        return RunTraceResponse(run_id=run_id, items=items, next_cursor=next_cursor)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.get(
    "/v1/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def get_run_events(
    run_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream ordered run events with sequence-based resumption."""

    try:
        response = await resolve(service.run_events(tenant_id=context.tenant_id, run_id=run_id))
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc
    last_sequence = _last_sequence(last_event_id)

    async def stream() -> AsyncIterator[str]:
        for event in response.items:
            if event.sequence <= last_sequence:
                continue
            payload = json.dumps(event.model_dump(mode="json"), sort_keys=True)
            yield f"id: {event.sequence}\nevent: trace\ndata: {payload}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/v1/runs/{run_id}/cancel", response_model=ControllerRunRecord)
async def cancel_run(
    run_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerRunRecord:
    """Cancel a run."""

    try:
        return await resolve(
            service.cancel_run(
                tenant_id=context.tenant_id,
                run_id=run_id,
                idempotency_key=idempotency_key,
            )
        )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.post("/v1/runs/{run_id}/resume", response_model=ControllerRunRecord)
async def resume_run(
    run_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerRunRecord:
    """Resume a run for inspection."""

    try:
        return await resolve(
            service.resume_run(
                tenant_id=context.tenant_id,
                run_id=run_id,
                idempotency_key=idempotency_key,
            )
        )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.get("/v1/actions", response_model=ActionListResponse)
async def list_actions(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    goal_id: UUID | None = None,
    run_id: UUID | None = None,
    action_status: ActionStatus | None = Query(default=None, alias="status"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> ActionListResponse:
    """List controller actions."""

    response = await resolve(
        service.list_actions(
            tenant_id=context.tenant_id,
            goal_id=goal_id,
            run_id=run_id,
            status=action_status,
        )
    )
    items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
    return ActionListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/actions/{action_id}", response_model=ControllerActionRecord)
async def get_action(
    action_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Return one controller action."""

    try:
        return await resolve(service.get_action(tenant_id=context.tenant_id, action_id=action_id))
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/v1/actions/{action_id}/approve", response_model=ControllerActionRecord)
async def approve_action(
    action_id: UUID,
    payload: ActionApprovalRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Approve an action by exact version hash."""

    return await _approval_decision(
        service=service,
        context=context,
        action_id=action_id,
        payload=payload,
        idempotency_key=idempotency_key,
        decision="approve",
    )


@router.post("/v1/actions/{action_id}/reject", response_model=ControllerActionRecord)
async def reject_action(
    action_id: UUID,
    payload: ActionApprovalRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Reject an action by exact version hash."""

    return await _approval_decision(
        service=service,
        context=context,
        action_id=action_id,
        payload=payload,
        idempotency_key=idempotency_key,
        decision="reject",
    )


@router.post("/v1/actions/{action_id}/execute", response_model=ControllerActionRecord)
async def execute_action(
    action_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Execute one action through the controller executor."""

    try:
        return await service.execute_action(
            tenant_id=context.tenant_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
        )
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc
    except PolicyViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/v1/actions/{action_id}/cancel", response_model=ControllerActionRecord)
async def cancel_action(
    action_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Cancel one action."""

    try:
        return await resolve(
            service.cancel_action(
                tenant_id=context.tenant_id,
                action_id=action_id,
                idempotency_key=idempotency_key,
            )
        )
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/v1/actions/{action_id}/rollback", response_model=ControllerActionRecord)
async def rollback_action(
    action_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerActionRecord:
    """Rollback one executed simulator action."""

    try:
        return await service.rollback_action(
            tenant_id=context.tenant_id,
            action_id=action_id,
            idempotency_key=idempotency_key,
        )
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc
    except PolicyViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/v1/actions/{action_id}/audit", response_model=ActionAuditResponse)
async def get_action_audit(
    action_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> ActionAuditResponse:
    """Return action audit entries."""

    try:
        response = await resolve(
            service.action_audit(tenant_id=context.tenant_id, action_id=action_id)
        )
        items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
        return ActionAuditResponse(action_id=action_id, items=items, next_cursor=next_cursor)
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc


@router.get("/v1/policy", response_model=ControllerPolicyConfig)
async def get_policy(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerPolicyConfig:
    """Return tenant policy."""

    return await resolve(service.get_policy(tenant_id=context.tenant_id))


@router.put("/v1/policy", response_model=ControllerPolicyConfig)
async def update_policy(
    payload: PolicyUpdateRequest,
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> ControllerPolicyConfig:
    """Update tenant policy."""

    return await resolve(
        service.update_policy(
            tenant_id=context.tenant_id,
            request=payload,
            idempotency_key=idempotency_key,
        )
    )


@router.post("/v1/policy/validate", response_model=PolicyValidationResponse)
async def validate_policy(
    payload: PolicyValidateRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> PolicyValidationResponse:
    """Validate a policy patch."""

    return await resolve(service.validate_policy(tenant_id=context.tenant_id, request=payload))


@router.get("/v1/policy/history", response_model=PolicyHistoryResponse)
async def get_policy_history(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> PolicyHistoryResponse:
    """Return tenant policy history."""

    response = await resolve(service.policy_history(tenant_id=context.tenant_id))
    items, next_cursor = paginate_items(response.items, cursor=cursor, limit=limit)
    return PolicyHistoryResponse(items=items, next_cursor=next_cursor)


@router.post("/v1/kill-switch/enable", response_model=KillSwitchResponse)
async def enable_kill_switch(
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> KillSwitchResponse:
    """Enable the tenant kill switch."""

    return await resolve(
        service.set_kill_switch(
            tenant_id=context.tenant_id,
            enabled=True,
            idempotency_key=idempotency_key,
        )
    )


@router.post("/v1/kill-switch/disable", response_model=KillSwitchResponse)
async def disable_kill_switch(
    idempotency_key: IdempotencyHeader,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> KillSwitchResponse:
    """Disable the tenant kill switch."""

    return await resolve(
        service.set_kill_switch(
            tenant_id=context.tenant_id,
            enabled=False,
            idempotency_key=idempotency_key,
        )
    )


@router.get("/v1/kill-switch", response_model=KillSwitchResponse)
async def get_kill_switch(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ControllerService, Depends(get_controller_service)],
) -> KillSwitchResponse:
    """Return kill-switch state."""

    return await resolve(service.get_kill_switch(tenant_id=context.tenant_id))


async def _set_goal_status(
    *,
    service: ControllerService,
    context: RequestContext,
    goal_id: UUID,
    goal_status: GoalStatus,
    idempotency_key: str,
) -> GoalRecord:
    try:
        return await resolve(
            service.set_goal_status(
                tenant_id=context.tenant_id,
                goal_id=goal_id,
                status=goal_status,
                idempotency_key=idempotency_key,
            )
        )
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="goal not found") from exc


async def _approval_decision(
    *,
    service: ControllerService,
    context: RequestContext,
    action_id: UUID,
    payload: ActionApprovalRequest,
    idempotency_key: str,
    decision: str,
) -> ControllerActionRecord:
    try:
        return await resolve(
            service.approve_action(
                tenant_id=context.tenant_id,
                action_id=action_id,
                request=payload.model_copy(update={"actor_id": context.actor_id}),
                actor_roles=context.roles,
                decision=decision,
                idempotency_key=idempotency_key,
            )
        )
    except ActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="action not found",
        ) from exc
    except ApprovalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _last_sequence(last_event_id: str | None) -> int:
    if last_event_id is None:
        return 0
    try:
        value = int(last_event_id)
        if value < 0 or value > 2147483647:
            raise ValueError("cursor out of range")
        return value
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid event cursor",
        ) from exc
