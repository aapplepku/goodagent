"""Commerce-manager conversation and memory API routes."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from open_commerce.api.catalog import get_catalog_browser
from open_commerce.api.context import RequestContext, get_request_context, require_roles
from open_commerce.catalog.browse import CatalogBrowseService
from open_commerce.catalog.browse_models import CatalogBrowseQuery, CatalogBrowseResponse
from open_commerce.commerce.models import CommerceOverview, CommerceRuntime
from open_commerce.manager_agent.models import (
    ManagerAgentReply,
    ManagerAgentRuntime,
    ManagerChannelClearResponse,
    ManagerDatasetProfileReply,
    ManagerDatasetProfileRequest,
    ManagerMemoryDeleteResponse,
    ManagerMemoryListResponse,
    ManagerMessageRequest,
    ManagerReplyThreadCreateRequest,
    ManagerRuntimeStatus,
    ManagerThreadCreateRequest,
    ManagerThreadDetail,
    ManagerThreadListResponse,
    ManagerThreadUpdateRequest,
    ManagerWorkspaceResetRequest,
    ManagerWorkspaceResetResponse,
    ManagerWorkspaceResponse,
    MemoryLayer,
)
from open_commerce.manager_agent.runs import ManagerRunService
from open_commerce.manager_agent.runs_models import ManagerRun, ManagerRunEvents
from open_commerce.persistence.runtime_db import RuntimeDatabase

router = APIRouter(prefix="/v1/manager", tags=["manager-agent"])
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]
ManagerContext = Annotated[RequestContext, Depends(require_roles("owner", "operator"))]


@router.get("/catalog", response_model=CatalogBrowseResponse)
async def browse_manager_catalog(
    context: ManagerContext,
    query: Annotated[CatalogBrowseQuery, Query()],
    service: Annotated[CatalogBrowseService, Depends(get_catalog_browser)],
) -> CatalogBrowseResponse:
    """Browse the verified active upload; pending uploads never replace it early."""
    return await service.browse(tenant_id=context.tenant_id, query=query)


def get_manager_runs(request: Request) -> ManagerRunService:
    return ManagerRunService(cast(RuntimeDatabase, request.app.state.database))


@router.post("/threads/{thread_id}/runs", response_model=ManagerRun, status_code=202)
async def create_manager_run(
    thread_id: UUID,
    payload: ManagerMessageRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerRunService, Depends(get_manager_runs)],
) -> ManagerRun:
    return await service.submit(
        tenant_id=context.tenant_id,
        thread_id=thread_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/runs/{run_id}", response_model=ManagerRun)
async def get_manager_run(
    run_id: UUID,
    context: ManagerContext,
    service: Annotated[ManagerRunService, Depends(get_manager_runs)],
) -> ManagerRun:
    return await service.get(tenant_id=context.tenant_id, run_id=run_id)


@router.get("/runs/{run_id}/events", response_model=ManagerRunEvents)
async def get_manager_run_events(
    run_id: UUID,
    context: ManagerContext,
    service: Annotated[ManagerRunService, Depends(get_manager_runs)],
    after: Annotated[int, Query(ge=0)] = 0,
) -> ManagerRunEvents:
    return await service.events(tenant_id=context.tenant_id, run_id=run_id, after=after)


@router.post("/runs/{run_id}/cancel", response_model=ManagerRun)
async def cancel_manager_run(
    run_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerRunService, Depends(get_manager_runs)],
) -> ManagerRun:
    return await service.cancel(
        tenant_id=context.tenant_id, run_id=run_id, idempotency_key=idempotency_key
    )


def get_manager_agent_service(request: Request) -> ManagerAgentRuntime:
    return cast(ManagerAgentRuntime, request.app.state.manager_agent_service)


def get_commerce_service(request: Request) -> CommerceRuntime:
    return cast(CommerceRuntime, request.app.state.commerce_service)


@router.post("/workspace/bootstrap", response_model=ManagerWorkspaceResponse)
async def bootstrap_manager_workspace(
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerWorkspaceResponse:
    """Start the bounded interview and create eligible default channels once."""

    return await service.bootstrap_workspace(
        tenant_id=context.tenant_id, idempotency_key=idempotency_key
    )


@router.get("/workspace", response_model=ManagerWorkspaceResponse)
async def get_manager_workspace(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerWorkspaceResponse:
    """Load workspace navigation, onboarding state, and agent capabilities."""

    return await service.get_workspace(tenant_id=context.tenant_id)


@router.post("/workspace/reset", response_model=ManagerWorkspaceResetResponse)
async def reset_manager_workspace(
    payload: ManagerWorkspaceResetRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerWorkspaceResetResponse:
    """Reset manager-only workspace state after an explicit confirmation token."""

    return await service.reset_workspace(
        tenant_id=context.tenant_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/status", response_model=ManagerRuntimeStatus)
async def get_manager_runtime_status(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerRuntimeStatus:
    """Return live read-only service and commerce-surface status."""

    return await service.get_runtime_status(tenant_id=context.tenant_id)


@router.get("/commerce/overview", response_model=CommerceOverview)
async def get_manager_commerce_overview(
    context: ManagerContext,
    service: Annotated[CommerceRuntime, Depends(get_commerce_service)],
) -> CommerceOverview:
    """Return observed inventory and local reservation/order/payment state."""

    return await service.overview(tenant_id=context.tenant_id)


@router.post("/threads", response_model=ManagerThreadDetail)
async def create_manager_thread(
    payload: ManagerThreadCreateRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadDetail:
    """Create one durable manager conversation with an initial assistant turn."""

    return await service.create_thread(
        tenant_id=context.tenant_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/threads", response_model=ManagerThreadListResponse)
async def list_manager_threads(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadListResponse:
    """List tenant-scoped conversations newest first."""

    return await service.list_threads(tenant_id=context.tenant_id)


@router.get("/threads/{thread_id}", response_model=ManagerThreadDetail)
async def get_manager_thread(
    thread_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadDetail:
    """Load conversation history, working state, and recalled durable memories."""

    return await service.get_thread(tenant_id=context.tenant_id, thread_id=thread_id)


@router.patch("/threads/{thread_id}", response_model=ManagerThreadDetail)
async def update_manager_thread(
    thread_id: UUID,
    payload: ManagerThreadUpdateRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadDetail:
    """Rename, archive, or restore one tenant-scoped channel."""

    return await service.update_thread(
        tenant_id=context.tenant_id,
        thread_id=thread_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.delete("/threads/{thread_id}/messages", response_model=ManagerChannelClearResponse)
async def clear_manager_channel_history(
    thread_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerChannelClearResponse:
    """Clear one agent channel and its reply branches, retaining long-term memory."""

    return await service.clear_channel_history(
        tenant_id=context.tenant_id,
        thread_id=thread_id,
        idempotency_key=idempotency_key,
    )


@router.post("/threads/{channel_id}/replies", response_model=ManagerThreadDetail)
async def create_manager_reply_thread(
    channel_id: UUID,
    payload: ManagerReplyThreadCreateRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadDetail:
    """Create or return one durable reply thread for a channel message."""

    return await service.create_reply_thread(
        tenant_id=context.tenant_id,
        channel_id=channel_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/threads/{channel_id}/messages/{root_message_id}/replies",
    response_model=ManagerThreadDetail,
)
async def get_manager_reply_thread(
    channel_id: UUID,
    root_message_id: UUID,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerThreadDetail:
    """Load one durable, one-level reply history."""

    return await service.get_reply_thread(
        tenant_id=context.tenant_id,
        channel_id=channel_id,
        root_message_id=root_message_id,
    )


@router.post("/threads/{thread_id}/messages", response_model=ManagerAgentReply)
async def send_manager_message(
    thread_id: UUID,
    payload: ManagerMessageRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerAgentReply:
    """Prepare one bounded agent response and record the completed turn atomically."""

    return await service.send_message(
        tenant_id=context.tenant_id,
        thread_id=thread_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.post("/threads/{thread_id}/datasets/profile", response_model=ManagerDatasetProfileReply)
async def profile_manager_dataset(
    thread_id: UUID,
    payload: ManagerDatasetProfileRequest,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerDatasetProfileReply:
    """Profile a bounded CSV attachment and retain only safe structural metadata."""

    return await service.profile_dataset(
        tenant_id=context.tenant_id,
        thread_id=thread_id,
        request=payload,
        idempotency_key=idempotency_key,
    )


@router.get("/memories", response_model=ManagerMemoryListResponse)
async def list_manager_memories(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
    layer: Annotated[MemoryLayer | None, Query()] = None,
) -> ManagerMemoryListResponse:
    """Inspect explicit long-term preferences and immutable periodic summaries."""

    return await service.list_memories(tenant_id=context.tenant_id, layer=layer)


@router.delete("/memories/{memory_id}", response_model=ManagerMemoryDeleteResponse)
async def delete_manager_memory(
    memory_id: UUID,
    idempotency_key: IdempotencyHeader,
    context: ManagerContext,
    service: Annotated[ManagerAgentRuntime, Depends(get_manager_agent_service)],
) -> ManagerMemoryDeleteResponse:
    """Forget an explicit long-term preference; periodic summaries are immutable."""

    return await service.delete_memory(
        tenant_id=context.tenant_id,
        memory_id=memory_id,
        idempotency_key=idempotency_key,
    )
