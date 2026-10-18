"""Small cursor pagination helper for in-process collections."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from fastapi import HTTPException, status

T = TypeVar("T")


def paginate_items(
    items: Sequence[T],
    *,
    cursor: str | None,
    limit: int,
) -> tuple[list[T], str | None]:
    """Return a bounded slice plus the next cursor."""

    try:
        start = int(cursor) if cursor is not None else 0
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid cursor",
        ) from exc
    if start < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid cursor")
    end = start + limit
    page = list(items[start:end])
    next_cursor = str(end) if end < len(items) else None
    return page, next_cursor
