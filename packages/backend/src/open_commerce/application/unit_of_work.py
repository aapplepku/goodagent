"""Application unit-of-work protocol."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, Self


class UnitOfWork(Protocol):
    """Async transaction boundary for application services."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], Awaitable[UnitOfWork]]
