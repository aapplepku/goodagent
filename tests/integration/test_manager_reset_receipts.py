"""A later manager reset must not turn an older retry into another deletion."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.manager_agent.models import (
    ManagerMessageRequest,
    ManagerThreadCreateRequest,
    ManagerWorkspaceResetRequest,
)
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.requests import (
    IdempotencyConflictError,
    RequestRepository,
)
from open_commerce.persistence.runtime_db import RuntimeDatabase

pytestmark = pytest.mark.integration


async def test_old_reset_replays_after_later_reset_without_erasing_new_work(
    integration_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    erased = "Synthetic private topic that reset must remove"
    retained = ManagerMessageRequest(content="Synthetic unrelated receipt")
    request = ManagerWorkspaceResetRequest(confirmation="RESET")
    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        service = DurableManagerAgentService(db)
        prior = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title=erased),
            idempotency_key="old-create",
        )
        await service.send_message(
            tenant_id=tenant,
            thread_id=prior.thread.id,
            request=ManagerMessageRequest(content=f"Remember that {erased}"),
            idempotency_key="old-memory",
        )
        async with db.transaction(tenant, write=True) as session:
            RequestRepository(session, tenant).remember(
                scope="unrelated:retained",
                key="retained",
                request=retained,
                response=retained,
            )
        first = await service.reset_workspace(
            tenant_id=tenant, request=request, idempotency_key="R1"
        )
        second = await service.reset_workspace(
            tenant_id=tenant, request=request, idempotency_key="R2"
        )
        current = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title="Intervening new work"),
            idempotency_key="new-work",
        )
        foreign = await service.create_thread(
            tenant_id=other,
            request=ManagerThreadCreateRequest(title="Other tenant work"),
            idempotency_key="R1",
        )
        for key, original in [("R1", first), ("R2", second), ("R1", first)]:
            replay = await service.reset_workspace(
                tenant_id=tenant, request=request, idempotency_key=key
            )
            workspace = await service.get_workspace(tenant_id=tenant)
            assert current.thread.id in {channel.id for channel in workspace.channels}
            assert replay == original
            assert erased not in replay.model_dump_json()
            assert {
                channel.id for channel in workspace.channels if channel.channel_kind == "onboarding"
            } == {
                channel.id
                for channel in second.workspace.channels
                if channel.channel_kind == "onboarding"
            }
        assert (
            await service.get_thread(tenant_id=other, thread_id=foreign.thread.id)
        ).thread == foreign.thread
        assert (await service.list_memories(tenant_id=tenant)).items == []
        async with db.transaction(tenant) as session:
            receipts = list(
                await session.scalars(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.tenant_id == tenant,
                    )
                )
            )
            resets = [row for row in receipts if row.scope == "manager:workspace:reset"]
            assert {row.key for row in resets} == {"R1", "R2"}
            assert not any(row.key in {"old-create", "old-memory"} for row in receipts)
            assert all(erased not in str(row.response) for row in receipts)
            assert await RequestRepository(session, tenant).replay(
                scope="unrelated:retained",
                key="retained",
                request=retained,
            ) == retained.model_dump(mode="json")
        async with db.transaction(other) as session:
            assert (
                await RequestRepository(session, other).replay(
                    scope="manager:workspace:reset",
                    key="R1",
                    request=request,
                )
                is None
            )
        async with db.transaction(tenant) as session:
            with pytest.raises(IdempotencyConflictError):
                await RequestRepository(session, tenant).replay(
                    scope="manager:workspace:reset",
                    key="R1",
                    request={"confirmation": "different"},
                )
        assert (
            await service.get_thread(tenant_id=tenant, thread_id=current.thread.id)
        ).thread == current.thread
        foreign_reset = await service.reset_workspace(
            tenant_id=other,
            request=request,
            idempotency_key="R1",
        )
        assert foreign_reset.workspace.onboarding.tenant_id == other
        assert (
            await service.get_thread(tenant_id=tenant, thread_id=current.thread.id)
        ).thread == current.thread
        before = await service.get_workspace(tenant_id=tenant)
        monkeypatch.setattr(
            service,
            "_ensure_default_channels",
            AsyncMock(
                side_effect=RuntimeError("Synthetic post-deletion failure"),
            ),
        )
        with pytest.raises(RuntimeError, match="Synthetic post-deletion failure"):
            await service.reset_workspace(tenant_id=tenant, request=request, idempotency_key="R3")
        assert await service.get_workspace(tenant_id=tenant) == before
        async with db.transaction(tenant) as session:
            assert (
                await RequestRepository(session, tenant).replay(
                    scope="manager:workspace:reset",
                    key="R3",
                    request=request,
                )
                is None
            )
            assert await RequestRepository(session, tenant).replay(
                scope="manager:workspace:reset",
                key="R1",
                request=request,
            ) == first.model_dump(mode="json")
    finally:
        await db.close()
