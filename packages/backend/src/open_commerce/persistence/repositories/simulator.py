"""Tenant-scoped SQLAlchemy repository for simulator state."""

from __future__ import annotations

from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.errors import TenantScopeError
from open_commerce.persistence.models.simulator import (
    SimulatorCommandRecordModel,
    SimulatorDailyMetricRecord,
    SimulatorEventRecord,
    SimulatorInstanceRecord,
    SimulatorSnapshotRecord,
)
from open_commerce.simulator.models import SimulatorState


class SqlSimulatorRepository:
    """Persist simulator state and derived materializations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_state(self, state: SimulatorState) -> None:
        """Insert or update full simulator state JSON under tenant scope."""

        payload = cast(dict[str, object], state.model_dump(mode="json"))
        record = await self.session.scalar(
            select(SimulatorInstanceRecord).where(
                SimulatorInstanceRecord.tenant_id == state.tenant_id,
                SimulatorInstanceRecord.id == state.id,
            )
        )
        if record is None:
            self.session.add(
                SimulatorInstanceRecord(
                    id=state.id,
                    tenant_id=state.tenant_id,
                    scenario_id=state.scenario_id,
                    scenario_version=state.scenario_version,
                    seed=state.seed,
                    status=state.status,
                    current_time=state.current_time,
                    state_hash=state.state_hash,
                    state=payload,
                )
            )
            return
        if record.tenant_id != state.tenant_id:
            raise TenantScopeError("simulator instance tenant mismatch")
        record.scenario_id = state.scenario_id
        record.scenario_version = state.scenario_version
        record.seed = state.seed
        record.status = state.status
        record.current_time = state.current_time
        record.state_hash = state.state_hash
        record.state = payload

    async def get_state(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        """Load full simulator state for one tenant-owned instance."""

        result = await self.session.execute(
            select(SimulatorInstanceRecord).where(
                SimulatorInstanceRecord.tenant_id == tenant_id,
                SimulatorInstanceRecord.id == instance_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise TenantScopeError("simulator instance not found for tenant")
        return SimulatorState.model_validate(record.state)

    async def replace_materializations(self, state: SimulatorState) -> None:
        """Replace snapshot, metric, event, and command rows from current state."""

        await self.session.execute(
            delete(SimulatorSnapshotRecord).where(
                SimulatorSnapshotRecord.tenant_id == state.tenant_id,
                SimulatorSnapshotRecord.instance_id == state.id,
            )
        )
        await self.session.execute(
            delete(SimulatorDailyMetricRecord).where(
                SimulatorDailyMetricRecord.tenant_id == state.tenant_id,
                SimulatorDailyMetricRecord.instance_id == state.id,
            )
        )
        await self.session.execute(
            delete(SimulatorEventRecord).where(
                SimulatorEventRecord.tenant_id == state.tenant_id,
                SimulatorEventRecord.instance_id == state.id,
            )
        )
        await self.session.execute(
            delete(SimulatorCommandRecordModel).where(
                SimulatorCommandRecordModel.tenant_id == state.tenant_id,
                SimulatorCommandRecordModel.instance_id == state.id,
            )
        )
        self.session.add_all(
            [
                SimulatorSnapshotRecord(
                    id=_uuid_for(snapshot.id),
                    tenant_id=state.tenant_id,
                    instance_id=state.id,
                    label=snapshot.label,
                    virtual_time=snapshot.virtual_time,
                    state_hash=snapshot.state_hash,
                    summary=cast(dict[str, object], snapshot.summary),
                )
                for snapshot in state.snapshots
            ]
        )
        self.session.add_all(
            [
                SimulatorDailyMetricRecord(
                    id=_uuid_for(f"{state.id}:metric:{metric.metric_date.isoformat()}"),
                    tenant_id=state.tenant_id,
                    instance_id=state.id,
                    metric_date=metric.metric_date,
                    day_index=metric.day_index,
                    is_history=metric.is_history,
                    metrics=cast(dict[str, object], metric.model_dump(mode="json")),
                )
                for metric in state.metrics
            ]
        )
        self.session.add_all(
            [
                SimulatorEventRecord(
                    id=_uuid_for(event.id),
                    tenant_id=state.tenant_id,
                    instance_id=state.id,
                    event_type=event.type,
                    occurred_at=event.occurred_at,
                    count=event.count,
                    dimensions=cast(dict[str, object], event.dimensions),
                    metrics=cast(dict[str, object], event.metrics),
                )
                for event in state.events
            ]
        )
        self.session.add_all(
            [
                SimulatorCommandRecordModel(
                    id=record.execution_id,
                    tenant_id=record.tenant_id,
                    instance_id=record.instance_id,
                    idempotency_key=record.idempotency_key,
                    action_type=record.action_type,
                    status=record.status.value,
                    before_state=record.before_state,
                    after_state=record.after_state,
                    rollback_state=record.rollback_state,
                    rollback_of=record.rollback_of,
                )
                for record in state.command_history
            ]
        )


def _uuid_for(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, value)
