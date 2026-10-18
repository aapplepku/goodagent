"""Checkpoint boundary shared by the conversation loop and durable delivery."""

from typing import Protocol
from uuid import UUID

from open_commerce.core.types import JsonObject


class RunSuspended(Exception):
    """An application-owned job is pending; release the worker lease."""


class RunCancelled(Exception):
    """A cancelled or stale run cannot persist another result."""


class RunJournal(Protocol):
    run_id: UUID
    token: UUID
    checkpoint: JsonObject

    async def check(self) -> None: ...

    async def save(self, checkpoint: JsonObject) -> None: ...

    async def event(self, kind: str, title: str, detail: str, tool: str | None = None) -> None: ...
