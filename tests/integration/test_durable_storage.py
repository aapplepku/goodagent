"""Real database tests for restart-safe simulator and request records."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from open_commerce.config import Settings
from open_commerce.persistence.models.audit import AuditEventRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.requests import IdempotencyConflictError
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import DurableSimulatorService
from open_commerce.simulator.service import SimulatorInstanceNotFoundError

pytestmark = pytest.mark.integration


async def test_simulator_state_and_request_receipts_survive_new_process_pool(
    integration_settings: Settings,
) -> None:
    tenant_id = uuid4()
    database = RuntimeDatabase(integration_settings)
    await database.initialize_tenant(tenant_id)
    service = DurableSimulatorService(database)
    first = await service.create_instance(
        tenant_id=tenant_id,
        scenario_id="acquisition_v1",
        seed=42,
        idempotency_key="create",
    )
    advanced = await service.advance(
        tenant_id=tenant_id,
        instance_id=first.id,
        hours=24,
        idempotency_key="day-one",
    )
    await database.close()

    restarted = RuntimeDatabase(integration_settings)
    try:
        service = DurableSimulatorService(restarted)
        replay = await service.advance(
            tenant_id=tenant_id,
            instance_id=first.id,
            hours=24,
            idempotency_key="day-one",
        )
        assert replay == advanced
        assert (await service.get_state(tenant_id=tenant_id, instance_id=first.id)).day == 1
        with pytest.raises(IdempotencyConflictError):
            await service.advance(
                tenant_id=tenant_id,
                instance_id=first.id,
                hours=48,
                idempotency_key="day-one",
            )
        with pytest.raises(SimulatorInstanceNotFoundError):
            await service.get_state(tenant_id=uuid4(), instance_id=first.id)
    finally:
        await restarted.close()


async def test_concurrent_duplicate_requests_mutate_only_once(
    integration_settings: Settings,
) -> None:
    tenant_id = uuid4()
    database = RuntimeDatabase(integration_settings)
    other_process_pool = RuntimeDatabase(integration_settings)
    try:
        await database.initialize_tenant(tenant_id)
        left = DurableSimulatorService(database)
        right = DurableSimulatorService(other_process_pool)
        created = await left.create_instance(
            tenant_id=tenant_id,
            scenario_id="acquisition_v1",
            seed=4,
            idempotency_key="create",
        )
        results = await asyncio.gather(
            *[
                service.advance(
                    tenant_id=tenant_id, instance_id=created.id, hours=24, idempotency_key="advance"
                )
                for service in (left, right, left, right)
            ]
        )
        assert all(result == results[0] for result in results)
        assert (await right.get_state(tenant_id=tenant_id, instance_id=created.id)).day == 1
        async with database.transaction(tenant_id) as session:
            receipts = list(
                await session.scalars(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.tenant_id == tenant_id,
                    )
                )
            )
            assert len(receipts) == 2
    finally:
        await database.close()
        await other_process_pool.close()


async def test_audit_rows_cannot_be_rewritten(integration_settings: Settings) -> None:
    database = RuntimeDatabase(integration_settings)
    tenant_id = uuid4()
    event_id = uuid4()
    try:
        await database.initialize_tenant(tenant_id)
        async with database.transaction(tenant_id, write=True) as session:
            from open_commerce.core.types import utc_now

            session.add(
                AuditEventRecord(
                    id=event_id,
                    tenant_id=tenant_id,
                    actor={"role": "system"},
                    event_type="test",
                    entity_type="test",
                    entity_id=uuid4(),
                    request_id="test",
                    safe_payload={},
                    occurred_at=utc_now(),
                )
            )
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.transaction(tenant_id, write=True) as session:
                await session.execute(
                    text(
                        "UPDATE audit_events SET event_type = 'rewritten' "
                        "WHERE tenant_id = :tenant_id AND id = :event_id"
                    ),
                    {"tenant_id": tenant_id, "event_id": event_id},
                )
    finally:
        await database.close()
