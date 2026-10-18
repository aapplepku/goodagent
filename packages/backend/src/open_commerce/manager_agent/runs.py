"""Tenant-scoped run delivery, leases, checkpoints and cancellation."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from time import monotonic
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import JsonObject, utc_now
from open_commerce.manager_agent.errors import ManagerThreadBusyError, ManagerThreadNotFoundError
from open_commerce.manager_agent.models import (
    ManagerAgentReply,
    ManagerMessage,
    ManagerMessageRequest,
)
from open_commerce.manager_agent.run_hooks import RunCancelled, RunSuspended
from open_commerce.manager_agent.runs_models import (
    ACTIVE_RUN_STATES,
    ManagerRun,
    ManagerRunEvent,
    ManagerRunEvents,
)
from open_commerce.persistence.models.manager_runs import (
    ManagerRunEventRecord,
    ManagerRunRecord,
    RuntimeOperationRecord,
)
from open_commerce.persistence.repositories.manager_agent import ManagerAgentRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase

if TYPE_CHECKING:
    from open_commerce.manager_agent.service import DurableManagerAgentService


def public_run(row: ManagerRunRecord) -> ManagerRun:
    return ManagerRun.model_validate({name: getattr(row, name) for name in ManagerRun.model_fields})


async def run_row(session: AsyncSession, tenant_id: UUID, run_id: UUID) -> ManagerRunRecord:
    row = await session.scalar(
        select(ManagerRunRecord).where(
            ManagerRunRecord.tenant_id == tenant_id, ManagerRunRecord.id == run_id
        )
    )
    if row is None:
        raise ManagerThreadNotFoundError("Agent run was not found")
    return row


async def active_run(session: AsyncSession, tenant_id: UUID, thread_id: UUID) -> ManagerRun | None:
    row = await session.scalar(
        select(ManagerRunRecord).where(
            ManagerRunRecord.tenant_id == tenant_id,
            ManagerRunRecord.thread_id == thread_id,
            ManagerRunRecord.status.in_(ACTIVE_RUN_STATES),
        )
    )
    return public_run(row) if row else None


async def append_event(
    session: AsyncSession,
    row: ManagerRunRecord,
    kind: str,
    title: str,
    detail: str,
    tool: str | None = None,
) -> None:
    sequence = await session.scalar(
        select(func.coalesce(func.max(ManagerRunEventRecord.sequence), 0)).where(
            ManagerRunEventRecord.tenant_id == row.tenant_id, ManagerRunEventRecord.run_id == row.id
        )
    )
    session.add(
        ManagerRunEventRecord(
            id=uuid4(),
            tenant_id=row.tenant_id,
            run_id=row.id,
            sequence=int(sequence or 0) + 1,
            kind=kind,
            title=title[:240],
            detail=redact_model_text(detail)[:2000],
            tool=tool,
            created_at=utc_now(),
        )
    )
    row.phase = title[:240]
    row.updated_at = utc_now()
    await session.flush()


async def cancel_thread_runs(
    session: AsyncSession, tenant_id: UUID, thread_ids: list[UUID] | None = None
) -> None:
    query = select(ManagerRunRecord).where(
        ManagerRunRecord.tenant_id == tenant_id, ManagerRunRecord.status.in_(ACTIVE_RUN_STATES)
    )
    if thread_ids is not None:
        query = query.where(ManagerRunRecord.thread_id.in_(thread_ids))
    for row in await session.scalars(query):
        row.status = "cancelled"
        row.lease_token = None
        await append_event(
            session, row, "cancelled", "Stopped", "This conversation was cleared or reset."
        )
        await cancel_queued_operations(session, tenant_id, row.id)


async def cancel_queued_operations(session: AsyncSession, tenant_id: UUID, run_id: UUID) -> None:
    for operation in await session.scalars(
        select(RuntimeOperationRecord).where(
            RuntimeOperationRecord.tenant_id == tenant_id,
            RuntimeOperationRecord.run_id == run_id,
            RuntimeOperationRecord.status == "queued",
        )
    ):
        operation.status = "cancelled"
        operation.updated_at = utc_now()


async def record_stopped_reply(session: AsyncSession, row: ManagerRunRecord, detail: str) -> None:
    repo = ManagerAgentRepository(session, row.tenant_id)
    try:
        thread = await repo.get_thread(row.thread_id)
    except ManagerThreadNotFoundError:
        return
    if thread.version != row.thread_version or row.assistant_message_id is not None:
        return
    from open_commerce.manager_agent.models import AgentStep

    observations = list(
        await session.scalars(
            select(ManagerRunEventRecord)
            .where(
                ManagerRunEventRecord.tenant_id == row.tenant_id,
                ManagerRunEventRecord.run_id == row.id,
                ManagerRunEventRecord.kind == "tool_result",
            )
            .order_by(ManagerRunEventRecord.sequence)
            .limit(10)
        )
    )
    message = ManagerMessage(
        id=uuid4(),
        tenant_id=row.tenant_id,
        thread_id=row.thread_id,
        role="assistant",
        content=detail + " Send a follow-up when you are ready to continue.",
        steps=[
            AgentStep(
                stage="observe",
                title=item.title,
                detail=item.detail[:500],
                tool=item.tool,
                status="failed" if item.title == "Tool failed" else "completed",
            )
            for item in observations
        ],
        created_at=utc_now(),
    )
    await repo.add_message(message)
    row.assistant_message_id = message.id
    row.updated_at = utc_now()


class PersistentRunJournal:
    def __init__(
        self, database: RuntimeDatabase, tenant_id: UUID, row: ManagerRunRecord, token: UUID
    ):
        self.database = database
        self.tenant_id = tenant_id
        self.run_id = row.id
        self.token = token
        self.checkpoint = cast(JsonObject, dict(row.checkpoint))
        self.started = monotonic()
        self.active_before = row.active_seconds

    async def checked_row(self, session: AsyncSession) -> ManagerRunRecord:
        row = await run_row(session, self.tenant_id, self.run_id)
        if row.status != "running" or row.lease_token != self.token:
            raise RunCancelled()
        thread = await ManagerAgentRepository(session, self.tenant_id).get_thread(row.thread_id)
        if thread.version != row.thread_version:
            raise RunCancelled()
        return row

    async def check(self) -> None:
        async with self.database.transaction(self.tenant_id) as session:
            await self.checked_row(session)

    async def save(self, checkpoint: JsonObject) -> None:
        async with self.database.transaction(self.tenant_id, write=True) as session:
            row = await self.checked_row(session)
            row.checkpoint = dict(checkpoint)
            row.active_seconds = self.active_before + int(monotonic() - self.started)
            row.updated_at = utc_now()
            row.lease_until = utc_now() + timedelta(
                seconds=self.database.settings.manager_run_active_seconds + 30
            )
        self.checkpoint = dict(checkpoint)

    async def event(self, kind: str, title: str, detail: str, tool: str | None = None) -> None:
        async with self.database.transaction(self.tenant_id, write=True) as session:
            row = await self.checked_row(session)
            await append_event(session, row, kind, title, detail, tool)


class ManagerRunService:
    def __init__(self, database: RuntimeDatabase):
        self.database = database

    async def submit(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
    ) -> ManagerRun:
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            scope = f"manager:run:{thread_id}"
            prior = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            if prior is not None:
                return public_run(await run_row(session, tenant_id, UUID(str(prior["id"]))))
            repo = ManagerAgentRepository(session, tenant_id)
            thread = await repo.get_thread(thread_id)
            if await active_run(session, tenant_id, thread_id):
                raise ManagerThreadBusyError(
                    "This agent is still working. Stop it or wait for its reply."
                )
            now = utc_now()
            message = ManagerMessage(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="user",
                content=request.content,
                steps=[],
                created_at=now,
            )
            await repo.add_message(message)
            row = ManagerRunRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                user_message_id=message.id,
                thread_version=thread.version,
                content=request.content,
                status="queued",
                phase="Waiting for agent",
                checkpoint={},
                active_seconds=0,
                available_at=now,
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(row)
            await session.flush()
            await append_event(
                session,
                row,
                "queued",
                "Message received",
                "Your request is saved. The agent will pick it up shortly.",
            )
            response = public_run(row)
            receipts.remember(scope=scope, key=idempotency_key, request=request, response=response)
            return response

    async def get(self, *, tenant_id: UUID, run_id: UUID) -> ManagerRun:
        async with self.database.transaction(tenant_id) as session:
            return public_run(await run_row(session, tenant_id, run_id))

    async def events(self, *, tenant_id: UUID, run_id: UUID, after: int = 0) -> ManagerRunEvents:
        async with self.database.transaction(tenant_id) as session:
            run = public_run(await run_row(session, tenant_id, run_id))
            rows = await session.scalars(
                select(ManagerRunEventRecord)
                .where(
                    ManagerRunEventRecord.tenant_id == tenant_id,
                    ManagerRunEventRecord.run_id == run_id,
                    ManagerRunEventRecord.sequence > after,
                )
                .order_by(ManagerRunEventRecord.sequence)
                .limit(100)
            )
            items = [
                ManagerRunEvent.model_validate(
                    {name: getattr(row, name) for name in ManagerRunEvent.model_fields}
                )
                for row in rows
            ]
            return ManagerRunEvents(
                run=run, items=items, next_cursor=items[-1].sequence if items else after
            )

    async def cancel(self, *, tenant_id: UUID, run_id: UUID, idempotency_key: str) -> ManagerRun:
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            scope = f"manager:run:{run_id}:cancel"
            request = {"run_id": str(run_id)}
            prior = await receipts.replay(scope=scope, key=idempotency_key, request=request)
            row = await run_row(session, tenant_id, run_id)
            if prior is None and row.status in ACTIVE_RUN_STATES:
                row.status = "cancelled"
                row.lease_token = None
                await cancel_queued_operations(session, tenant_id, run_id)
                await append_event(
                    session,
                    row,
                    "cancelled",
                    "Stopped",
                    "No further tools will run. Already completed actions remain recorded.",
                )
                await record_stopped_reply(
                    session,
                    row,
                    "Stopped this run. No further tools will run; "
                    "completed actions remain recorded.",
                )
            await session.flush()
            response = public_run(row)
            if prior is None:
                receipts.remember(
                    scope=scope, key=idempotency_key, request=request, response=response
                )
            return response

    async def process(
        self, *, tenant_id: UUID, run_id: UUID, service: DurableManagerAgentService
    ) -> bool:
        async with self.database.transaction(tenant_id, write=True) as session:
            row = await run_row(session, tenant_id, run_id)
            if row.status not in ACTIVE_RUN_STATES:
                return True
            if row.available_at > utc_now() or (
                row.status == "running" and row.lease_until and row.lease_until > utc_now()
            ):
                return False
            token = uuid4()
            row.status = "running"
            row.lease_token = token
            row.lease_until = utc_now() + timedelta(
                seconds=self.database.settings.manager_run_active_seconds + 30
            )
            journal = PersistentRunJournal(self.database, tenant_id, row, token)
            thread_id, content, message_id = row.thread_id, row.content, row.user_message_id
            remaining = self.database.settings.manager_run_active_seconds - row.active_seconds
            if row.created_at < utc_now() - timedelta(minutes=15):
                remaining = 0
        deadline = asyncio.timeout(max(0, remaining))
        try:
            if remaining <= 0:
                raise TimeoutError
            async with deadline:
                await service._execute_message(
                    tenant_id=tenant_id,
                    thread_id=thread_id,
                    request=ManagerMessageRequest(content=content),
                    idempotency_key=f"run:{run_id}",
                    journal=journal,
                    persisted_user_id=message_id,
                )
            return True
        except RunSuspended:
            state, title, code = "waiting", "Waiting for background work", None
        except RunCancelled:
            state, title, code = "cancelled", "Stopped", "CONVERSATION_CHANGED"
        except TimeoutError:
            if remaining <= 0 or deadline.expired():
                state, title, code = "failed", "Time limit reached", "RUN_TIME_BUDGET_EXCEEDED"
            else:
                state, title, code = "failed", "Agent needs attention", "TimeoutError"
        except Exception as exc:
            state, title, code = "failed", "Agent needs attention", type(exc).__name__[:100]
            if code == "ManagerModelUnavailableError":
                title = "Model unavailable"
        async with self.database.transaction(tenant_id, write=True) as session:
            try:
                row = await run_row(session, tenant_id, run_id)
            except ManagerThreadNotFoundError:
                return True
            if row.status not in ACTIVE_RUN_STATES or row.lease_token != token:
                return True
            row.status = state
            row.error_code = code
            row.lease_token = None
            row.lease_until = None
            row.available_at = utc_now() + timedelta(seconds=2)
            row.active_seconds = journal.active_before + int(monotonic() - journal.started)
            detail = (
                "The job is still running. You can use another channel while it finishes."
                if state == "waiting"
                else "The conversation changed. No further tools will run."
                if state == "cancelled"
                else "The model connection is unavailable. Check the Model panel and retry; "
                "your message and completed tool results are saved."
                if code == "ManagerModelUnavailableError"
                else "This run reached its time limit. Your message and completed results "
                "are saved. Send a follow-up with a smaller next step to continue in a new run."
                if code == "RUN_TIME_BUDGET_EXCEEDED"
                else "The run stopped before completion. Its message and results are saved; "
                "retry when the underlying service is available."
            )
            await append_event(session, row, state, title, detail)
            if state == "failed":
                await record_stopped_reply(session, row, detail)
            return state != "waiting"

    async def compatibility_reply(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
        service: DurableManagerAgentService,
    ) -> ManagerAgentReply:
        run = await self.submit(
            tenant_id=tenant_id,
            thread_id=thread_id,
            request=request,
            idempotency_key=idempotency_key,
        )
        await self.process(tenant_id=tenant_id, run_id=run.id, service=service)
        async with self.database.transaction(tenant_id) as session:
            row = await run_row(session, tenant_id, run.id)
            if row.result is not None:
                return ManagerAgentReply.model_validate(row.result)
            if row.status == "failed":
                from open_commerce.manager_agent.errors import ManagerModelUnavailableError

                raise ManagerModelUnavailableError(row.phase)
        raise ManagerThreadBusyError("The saved agent run is continuing in the background.")
