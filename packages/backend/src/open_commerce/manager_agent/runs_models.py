"""Public operator run contracts; private provider state is never serialized here."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from open_commerce.core.types import StrictDomainModel

RunState = Literal["queued", "running", "waiting", "completed", "failed", "cancelled"]
ACTIVE_RUN_STATES = ("queued", "running", "waiting")
LocalService = Literal["api", "manager_web", "shopper_web", "worker"]


class ManagerRun(StrictDomainModel):
    id: UUID
    thread_id: UUID
    user_message_id: UUID
    status: RunState
    phase: str
    error_code: str | None = None
    assistant_message_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ManagerRunEvent(StrictDomainModel):
    sequence: int
    kind: Literal[
        "queued",
        "model",
        "tool_started",
        "tool_result",
        "waiting",
        "completed",
        "failed",
        "cancelled",
    ]
    title: str
    detail: str
    tool: str | None = None
    created_at: datetime


class ManagerRunEvents(StrictDomainModel):
    run: ManagerRun
    items: list[ManagerRunEvent]
    next_cursor: int = Field(ge=0)


class RuntimeRepairInput(StrictDomainModel):
    service: LocalService


class IndexRecoveryInput(StrictDomainModel):
    action: Literal["retry_failed", "rebuild_active"]


class RecommendationTestInput(StrictDomainModel):
    product_id: str | None = Field(default=None, max_length=200)
    strategy: Literal["similar", "popular"] = "popular"
    top_k: int = Field(default=5, ge=1, le=10)


class EmptyToolInput(StrictDomainModel):
    pass
