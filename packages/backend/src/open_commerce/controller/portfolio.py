"""Deterministic portfolio selection for controller action proposals."""

from __future__ import annotations

from open_commerce.controller.models import ControllerActionRecord, risk_sort_key
from open_commerce.core.enums import ActionStatus


def select_portfolio(
    records: list[ControllerActionRecord],
    *,
    max_actions: int,
) -> list[ControllerActionRecord]:
    """Select a stable bounded portfolio while preserving policy denials."""

    ranked = sorted(records, key=_record_sort_key)
    return ranked[:max_actions]


def _record_sort_key(record: ControllerActionRecord) -> tuple[int, int, str, str]:
    status_order = {
        ActionStatus.EXECUTABLE: 0,
        ActionStatus.AWAITING_APPROVAL: 1,
        ActionStatus.DENIED: 2,
    }
    status_rank = status_order.get(record.action.status, 3)
    return (
        status_rank,
        risk_sort_key(record.action.risk.tier),
        record.action.intent.type,
        str(record.action.id),
    )
