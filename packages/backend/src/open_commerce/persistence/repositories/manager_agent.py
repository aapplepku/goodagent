"""Tenant-scoped repository for manager conversation and memory records."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.manager_agent.errors import (
    ManagerMemoryImmutableError,
    ManagerMemoryNotFoundError,
    ManagerThreadNotFoundError,
)
from open_commerce.manager_agent.models import (
    AgentStep,
    ManagerChannelKind,
    ManagerDataOnboarding,
    ManagerMemory,
    ManagerMemoryDeleteResponse,
    ManagerMessage,
    ManagerMessageRole,
    ManagerThread,
    ManagerThreadStatus,
    ManagerThreadType,
    ManagerWorkingMemory,
    MemoryLayer,
    MemorySource,
)
from open_commerce.persistence.models.manager_agent import (
    ManagerDataOnboardingRecord,
    ManagerMemoryRecord,
    ManagerMessageRecord,
    ManagerThreadRecord,
)
from open_commerce.persistence.models.workflow import IdempotencyRecord


class ManagerAgentRepository:
    """All reads and writes are explicitly constrained by one tenant."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def create_thread(
        self,
        *,
        thread_id: UUID,
        title: str,
        now: datetime,
        thread_type: ManagerThreadType = "channel",
        channel_kind: ManagerChannelKind | None = "custom",
        slug: str | None = None,
        description: str | None = None,
        position: int = 100,
        parent_thread_id: UUID | None = None,
        root_message_id: UUID | None = None,
    ) -> ManagerThread:
        row = ManagerThreadRecord(
            id=thread_id,
            tenant_id=self.tenant_id,
            title=title,
            status="active",
            thread_type=thread_type,
            channel_kind=channel_kind,
            slug=slug,
            description=description,
            position=position,
            parent_thread_id=parent_thread_id,
            root_message_id=root_message_id,
            working_memory=ManagerWorkingMemory().model_dump(mode="json"),
            user_turn_count=0,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.session.add(row)
        await self.session.flush()
        return self._thread(row)

    async def get_thread(self, thread_id: UUID) -> ManagerThread:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.id == thread_id,
            )
        )
        if row is None:
            raise ManagerThreadNotFoundError("Manager conversation was not found")
        return self._thread(row)

    async def list_threads(self) -> list[ManagerThread]:
        rows = await self.session.scalars(
            select(ManagerThreadRecord)
            .where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.thread_type == "channel",
            )
            .order_by(
                ManagerThreadRecord.position,
                ManagerThreadRecord.created_at,
                ManagerThreadRecord.id,
            )
        )
        return [self._thread(row) for row in rows]

    async def get_channel_by_kind(self, kind: ManagerChannelKind) -> ManagerThread | None:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.thread_type == "channel",
                ManagerThreadRecord.channel_kind == kind,
            )
        )
        return self._thread(row) if row is not None else None

    async def get_channel_by_slug(self, slug: str) -> ManagerThread | None:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.thread_type == "channel",
                ManagerThreadRecord.slug == slug,
            )
        )
        return self._thread(row) if row is not None else None

    async def next_channel_position(self) -> int:
        current = await self.session.scalar(
            select(func.max(ManagerThreadRecord.position)).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.thread_type == "channel",
            )
        )
        return int(current or 0) + 10

    async def get_reply_thread(
        self, *, parent_thread_id: UUID, root_message_id: UUID
    ) -> ManagerThread | None:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.thread_type == "reply",
                ManagerThreadRecord.parent_thread_id == parent_thread_id,
                ManagerThreadRecord.root_message_id == root_message_id,
            )
        )
        return self._thread(row) if row is not None else None

    async def get_onboarding(self) -> ManagerDataOnboarding:
        row = await self.session.scalar(
            select(ManagerDataOnboardingRecord).where(
                ManagerDataOnboardingRecord.tenant_id == self.tenant_id
            )
        )
        if row is None:
            return ManagerDataOnboarding(tenant_id=self.tenant_id)
        return self._onboarding(row)

    async def save_onboarding(
        self, onboarding: ManagerDataOnboarding, *, now: datetime
    ) -> ManagerDataOnboarding:
        if onboarding.tenant_id != self.tenant_id:
            raise ValueError("manager onboarding tenant mismatch")
        row = await self.session.scalar(
            select(ManagerDataOnboardingRecord).where(
                ManagerDataOnboardingRecord.tenant_id == self.tenant_id
            )
        )
        state = onboarding.model_dump(
            mode="json", exclude={"tenant_id", "created_at", "updated_at"}
        )
        if row is None:
            row = ManagerDataOnboardingRecord(
                tenant_id=self.tenant_id,
                state=state,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self.session.add(row)
        else:
            row.state = state
            row.updated_at = now
            row.version += 1
        await self.session.flush()
        return self._onboarding(row)

    async def update_thread(
        self,
        *,
        thread_id: UUID,
        working_memory: ManagerWorkingMemory,
        user_turn_count: int,
        title: str,
        now: datetime,
    ) -> ManagerThread:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.id == thread_id,
            )
        )
        if row is None:
            raise ManagerThreadNotFoundError("Manager conversation was not found")
        row.working_memory = working_memory.model_dump(mode="json")
        row.user_turn_count = user_turn_count
        row.title = title
        row.updated_at = now
        row.version += 1
        await self.session.flush()
        return self._thread(row)

    async def update_thread_metadata(
        self,
        *,
        thread_id: UUID,
        title: str | None,
        description: str | None,
        status: ManagerThreadStatus | None,
        slug: str | None,
        now: datetime,
    ) -> ManagerThread:
        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.id == thread_id,
                ManagerThreadRecord.thread_type == "channel",
            )
        )
        if row is None:
            raise ManagerThreadNotFoundError("Manager channel was not found")
        if title is not None:
            row.title = title
        if description is not None:
            row.description = description
        if status is not None:
            row.status = status
        if slug is not None:
            row.slug = slug
        row.updated_at = now
        row.version += 1
        await self.session.flush()
        return self._thread(row)

    async def add_message(self, message: ManagerMessage) -> None:
        if message.tenant_id != self.tenant_id:
            raise ValueError("manager message tenant mismatch")
        self.session.add(
            ManagerMessageRecord(
                id=message.id,
                tenant_id=self.tenant_id,
                thread_id=message.thread_id,
                role=message.role,
                content=message.content,
                steps=[step.model_dump(mode="json") for step in message.steps],
                created_at=message.created_at,
            )
        )
        await self.session.flush()

    async def clear_channel_history(self, *, thread_id: UUID, now: datetime) -> tuple[int, int]:
        """Clear one channel branch while retaining tenant-level long-term memory."""

        row = await self.session.scalar(
            select(ManagerThreadRecord).where(
                ManagerThreadRecord.tenant_id == self.tenant_id,
                ManagerThreadRecord.id == thread_id,
                ManagerThreadRecord.thread_type == "channel",
            )
        )
        if row is None:
            raise ManagerThreadNotFoundError("Manager channel was not found")
        reply_ids = list(
            await self.session.scalars(
                select(ManagerThreadRecord.id).where(
                    ManagerThreadRecord.tenant_id == self.tenant_id,
                    ManagerThreadRecord.thread_type == "reply",
                    ManagerThreadRecord.parent_thread_id == thread_id,
                )
            )
        )
        branch_ids = [thread_id, *reply_ids]
        from open_commerce.manager_agent.runs import cancel_thread_runs

        await cancel_thread_runs(self.session, self.tenant_id, branch_ids)
        message_count = int(
            await self.session.scalar(
                select(func.count(ManagerMessageRecord.id)).where(
                    ManagerMessageRecord.tenant_id == self.tenant_id,
                    ManagerMessageRecord.thread_id.in_(branch_ids),
                )
            )
            or 0
        )
        await self.session.execute(
            delete(ManagerMemoryRecord).where(
                ManagerMemoryRecord.tenant_id == self.tenant_id,
                ManagerMemoryRecord.layer == "periodic",
                ManagerMemoryRecord.thread_id.in_(branch_ids),
            )
        )
        if reply_ids:
            await self.session.execute(
                delete(ManagerMessageRecord).where(
                    ManagerMessageRecord.tenant_id == self.tenant_id,
                    ManagerMessageRecord.thread_id.in_(reply_ids),
                )
            )
            await self.session.execute(
                delete(ManagerThreadRecord).where(
                    ManagerThreadRecord.tenant_id == self.tenant_id,
                    ManagerThreadRecord.id.in_(reply_ids),
                    ManagerThreadRecord.thread_type == "reply",
                )
            )
        await self.session.execute(
            delete(ManagerMessageRecord).where(
                ManagerMessageRecord.tenant_id == self.tenant_id,
                ManagerMessageRecord.thread_id == thread_id,
            )
        )
        row.working_memory = ManagerWorkingMemory().model_dump(mode="json")
        row.user_turn_count = 0
        row.updated_at = now
        row.version += 1
        await self.session.flush()
        return message_count, len(reply_ids)

    async def reset_workspace(self) -> tuple[int, int, int]:
        from open_commerce.manager_agent.runs import cancel_thread_runs

        await cancel_thread_runs(self.session, self.tenant_id)
        """Delete manager-only workspace state while retaining commerce and shopper data."""

        channel_count = int(
            await self.session.scalar(
                select(func.count(ManagerThreadRecord.id)).where(
                    ManagerThreadRecord.tenant_id == self.tenant_id,
                    ManagerThreadRecord.thread_type == "channel",
                )
            )
            or 0
        )
        message_count = int(
            await self.session.scalar(
                select(func.count(ManagerMessageRecord.id)).where(
                    ManagerMessageRecord.tenant_id == self.tenant_id
                )
            )
            or 0
        )
        memory_count = int(
            await self.session.scalar(
                select(func.count(ManagerMemoryRecord.id)).where(
                    ManagerMemoryRecord.tenant_id == self.tenant_id
                )
            )
            or 0
        )
        await self.session.execute(
            delete(ManagerMemoryRecord).where(ManagerMemoryRecord.tenant_id == self.tenant_id)
        )
        await self.session.execute(
            delete(ManagerMessageRecord).where(ManagerMessageRecord.tenant_id == self.tenant_id)
        )
        await self.session.execute(
            delete(ManagerThreadRecord).where(ManagerThreadRecord.tenant_id == self.tenant_id)
        )
        await self.session.execute(
            delete(ManagerDataOnboardingRecord).where(
                ManagerDataOnboardingRecord.tenant_id == self.tenant_id
            )
        )
        await self.session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == self.tenant_id,
                IdempotencyRecord.scope.like("manager:%"),
                # Post-reset snapshots contain no erased chat or memory content.
                IdempotencyRecord.scope != "manager:workspace:reset",
            )
        )
        await self.session.flush()
        return channel_count, message_count, memory_count

    async def list_messages(self, thread_id: UUID, *, limit: int = 100) -> list[ManagerMessage]:
        await self.get_thread(thread_id)
        rows = list(
            await self.session.scalars(
                select(ManagerMessageRecord)
                .where(
                    ManagerMessageRecord.tenant_id == self.tenant_id,
                    ManagerMessageRecord.thread_id == thread_id,
                )
                .order_by(
                    ManagerMessageRecord.created_at.desc(),
                    ManagerMessageRecord.role.asc(),
                    ManagerMessageRecord.id.desc(),
                )
                .limit(limit)
            )
        )
        rows.reverse()
        count_rows = (
            await self.session.execute(
                select(
                    ManagerThreadRecord.root_message_id,
                    func.count(ManagerMessageRecord.id),
                )
                .join(
                    ManagerMessageRecord,
                    ManagerMessageRecord.thread_id == ManagerThreadRecord.id,
                )
                .where(
                    ManagerThreadRecord.tenant_id == self.tenant_id,
                    ManagerThreadRecord.thread_type == "reply",
                    ManagerThreadRecord.parent_thread_id == thread_id,
                    ManagerMessageRecord.tenant_id == self.tenant_id,
                    ManagerMessageRecord.role == "user",
                )
                .group_by(ManagerThreadRecord.root_message_id)
            )
        ).all()
        counts: dict[UUID, int] = {
            root_id: int(count) for root_id, count in count_rows if root_id is not None
        }
        return [self._message(row, reply_count=int(counts.get(row.id, 0))) for row in rows]

    async def get_message(self, *, thread_id: UUID, message_id: UUID) -> ManagerMessage:
        row = await self.session.scalar(
            select(ManagerMessageRecord).where(
                ManagerMessageRecord.tenant_id == self.tenant_id,
                ManagerMessageRecord.thread_id == thread_id,
                ManagerMessageRecord.id == message_id,
            )
        )
        if row is None:
            raise ManagerThreadNotFoundError("The reply root was not found in this channel")
        return self._message(row)

    async def add_memory(self, memory: ManagerMemory, *, source_message_id: UUID | None) -> None:
        if memory.tenant_id != self.tenant_id:
            raise ValueError("manager memory tenant mismatch")
        existing = await self.session.scalar(
            select(ManagerMemoryRecord.id).where(
                ManagerMemoryRecord.tenant_id == self.tenant_id,
                ManagerMemoryRecord.id == memory.id,
            )
        )
        if existing is not None:
            return
        self.session.add(
            ManagerMemoryRecord(
                id=memory.id,
                tenant_id=self.tenant_id,
                thread_id=memory.thread_id,
                layer=memory.layer,
                title=memory.title,
                content=memory.content,
                source=memory.source,
                source_message_id=source_message_id,
                period_start=memory.period_start,
                period_end=memory.period_end,
                created_at=memory.created_at,
            )
        )
        await self.session.flush()

    async def list_memories(
        self, *, layer: MemoryLayer | None = None, thread_id: UUID | None = None
    ) -> list[ManagerMemory]:
        query = select(ManagerMemoryRecord).where(ManagerMemoryRecord.tenant_id == self.tenant_id)
        if layer is not None:
            query = query.where(ManagerMemoryRecord.layer == layer)
        if thread_id is not None:
            query = query.where(
                (ManagerMemoryRecord.thread_id == thread_id)
                | (ManagerMemoryRecord.thread_id.is_(None))
            )
        rows = await self.session.scalars(
            query.order_by(ManagerMemoryRecord.created_at.desc(), ManagerMemoryRecord.id)
        )
        return [self._memory(row) for row in rows]

    async def delete_long_term_memory(self, memory_id: UUID) -> ManagerMemoryDeleteResponse:
        row = await self.session.scalar(
            select(ManagerMemoryRecord).where(
                ManagerMemoryRecord.tenant_id == self.tenant_id,
                ManagerMemoryRecord.id == memory_id,
            )
        )
        if row is None:
            raise ManagerMemoryNotFoundError("Manager memory was not found")
        if row.layer != "long_term":
            raise ManagerMemoryImmutableError("Periodic memory is immutable")
        await self.session.execute(
            delete(ManagerMemoryRecord).where(
                ManagerMemoryRecord.tenant_id == self.tenant_id,
                ManagerMemoryRecord.id == memory_id,
            )
        )
        return ManagerMemoryDeleteResponse(memory_id=memory_id, deleted=True)

    def _thread(self, row: ManagerThreadRecord) -> ManagerThread:
        return ManagerThread(
            id=row.id,
            tenant_id=row.tenant_id,
            title=row.title,
            status=cast(ManagerThreadStatus, row.status),
            thread_type=cast(ManagerThreadType, row.thread_type),
            channel_kind=cast(ManagerChannelKind | None, row.channel_kind),
            slug=row.slug,
            description=row.description,
            position=row.position,
            parent_thread_id=row.parent_thread_id,
            root_message_id=row.root_message_id,
            working_memory=ManagerWorkingMemory.model_validate(row.working_memory),
            user_turn_count=row.user_turn_count,
            version=row.version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _message(self, row: ManagerMessageRecord, *, reply_count: int = 0) -> ManagerMessage:
        return ManagerMessage(
            id=row.id,
            tenant_id=row.tenant_id,
            thread_id=row.thread_id,
            role=cast(ManagerMessageRole, row.role),
            content=row.content,
            steps=[AgentStep.model_validate(step) for step in row.steps],
            reply_count=reply_count,
            created_at=row.created_at,
        )

    def _memory(self, row: ManagerMemoryRecord) -> ManagerMemory:
        return ManagerMemory(
            id=row.id,
            tenant_id=row.tenant_id,
            thread_id=row.thread_id,
            layer=cast(MemoryLayer, row.layer),
            title=row.title,
            content=row.content,
            source=cast(MemorySource, row.source),
            period_start=row.period_start,
            period_end=row.period_end,
            created_at=row.created_at,
        )

    def _onboarding(self, row: ManagerDataOnboardingRecord) -> ManagerDataOnboarding:
        return ManagerDataOnboarding.model_validate(
            {
                **row.state,
                "tenant_id": row.tenant_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
