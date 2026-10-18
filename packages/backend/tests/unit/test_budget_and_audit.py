from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from open_commerce.application.services.audit import AuditService
from open_commerce.application.services.budget import BudgetAccount, BudgetLedgerEntry
from open_commerce.core.enums import AuditEventType, BudgetEntryType
from open_commerce.core.errors import BudgetOverspendError, TenantScopeError
from open_commerce.core.events import AuditEvent
from open_commerce.core.types import ActorRef


def test_budget_ledger_is_idempotent_and_blocks_overspend() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    account = BudgetAccount(tenant_id=tenant_id, account_id=uuid4(), allocated_minor=1_000)
    entry = BudgetLedgerEntry(
        tenant_id=tenant_id,
        account_id=account.account_id,
        operation_id="reserve-1",
        entry_type=BudgetEntryType.RESERVED,
        amount_minor=400,
    )

    assert account.apply(entry) == 600
    assert account.apply(entry) == 600

    with pytest.raises(BudgetOverspendError):
        account.apply(
            BudgetLedgerEntry(
                tenant_id=tenant_id,
                account_id=account.account_id,
                operation_id="reserve-2",
                entry_type=BudgetEntryType.RESERVED,
                amount_minor=700,
            ),
        )


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, tenant_id: UUID, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_for_entity(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> list[AuditEvent]:
        return [
            event
            for event in self.events
            if event.tenant_id == tenant_id
            and event.entity_type == entity_type
            and event.entity_id == entity_id
        ]


@pytest.mark.asyncio
async def test_audit_service_requires_matching_tenant_scope() -> None:
    tenant_id = uuid4()
    event = AuditEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        actor=ActorRef(type="system", id="test"),
        event_type=AuditEventType.GOAL_CREATED,
        entity_type="goal",
        entity_id=uuid4(),
        request_id="req-test",
        safe_payload={"status": "created"},
        occurred_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    repository = FakeAuditRepository()
    service = AuditService(repository)

    await service.append(tenant_id, event)
    with pytest.raises(TenantScopeError):
        await service.append(uuid4(), event)

    assert repository.events == [event]
