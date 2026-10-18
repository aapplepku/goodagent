"""Budget repository implementation."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.enums import BudgetEntryType
from open_commerce.core.errors import BudgetOverspendError
from open_commerce.persistence.models.budgets import BudgetAccountRecord, BudgetLedgerEntryRecord


class SqlBudgetRepository:
    """Tenant-scoped transactional budget ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def outstanding_minor(self, tenant_id: UUID, account_id: UUID, action_id: UUID) -> int:
        entries = [
            entry
            for entry in await self._entries(tenant_id, account_id)
            if entry.action_id == action_id
        ]
        reserved = sum(
            entry.amount_minor
            for entry in entries
            if entry.entry_type == BudgetEntryType.RESERVED.value
        )
        released = sum(
            entry.amount_minor
            for entry in entries
            if entry.entry_type == BudgetEntryType.RELEASED.value
        )
        return reserved - released

    async def available_minor(self, tenant_id: UUID, account_id: UUID) -> int:
        """Return the derived available balance."""

        account = await self._load_account(tenant_id, account_id, lock=False)
        entries = await self._entries(tenant_id, account.id)
        reserved = sum(
            e.amount_minor for e in entries if e.entry_type == BudgetEntryType.RESERVED.value
        )
        committed = sum(
            e.amount_minor for e in entries if e.entry_type == BudgetEntryType.COMMITTED.value
        )
        released = sum(
            e.amount_minor for e in entries if e.entry_type == BudgetEntryType.RELEASED.value
        )
        adjusted = sum(
            e.amount_minor for e in entries if e.entry_type == BudgetEntryType.ADJUSTED.value
        )
        return account.allocated_minor - reserved - committed + released + adjusted

    async def reserve(
        self,
        tenant_id: UUID,
        account_id: UUID,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None = None,
    ) -> int:
        """Reserve budget idempotently under a row lock."""

        return await self._apply(
            tenant_id=tenant_id,
            account_id=account_id,
            entry_type=BudgetEntryType.RESERVED,
            amount_minor=amount_minor,
            operation_id=operation_id,
            action_id=action_id,
        )

    async def commit(
        self,
        tenant_id: UUID,
        account_id: UUID,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None = None,
    ) -> int:
        """Commit budget idempotently."""

        return await self._apply(
            tenant_id=tenant_id,
            account_id=account_id,
            entry_type=BudgetEntryType.COMMITTED,
            amount_minor=amount_minor,
            operation_id=operation_id,
            action_id=action_id,
        )

    async def release(
        self,
        tenant_id: UUID,
        account_id: UUID,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None = None,
    ) -> int:
        """Release budget idempotently."""

        return await self._apply(
            tenant_id=tenant_id,
            account_id=account_id,
            entry_type=BudgetEntryType.RELEASED,
            amount_minor=amount_minor,
            operation_id=operation_id,
            action_id=action_id,
        )

    async def adjust(
        self,
        tenant_id: UUID,
        account_id: UUID,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None = None,
    ) -> int:
        """Adjust observed budget idempotently."""

        return await self._apply(
            tenant_id=tenant_id,
            account_id=account_id,
            entry_type=BudgetEntryType.ADJUSTED,
            amount_minor=amount_minor,
            operation_id=operation_id,
            action_id=action_id,
        )

    async def _apply(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        entry_type: BudgetEntryType,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None,
    ) -> int:
        account = await self._load_account(tenant_id, account_id, lock=True)
        if entry_type != BudgetEntryType.ADJUSTED and amount_minor < 0:
            raise BudgetOverspendError("budget amounts must not be negative")
        existing = await self._load_entry(tenant_id, account.id, operation_id)
        if existing is not None:
            if (
                existing.entry_type != entry_type.value
                or existing.amount_minor != amount_minor
                or existing.action_id != action_id
            ):
                raise BudgetOverspendError("operation_id already used for a different entry")
            return await self.available_minor(tenant_id, account_id)
        available = await self.available_minor(tenant_id, account_id)
        if entry_type == BudgetEntryType.RELEASED:
            entries = [
                entry
                for entry in await self._entries(tenant_id, account_id)
                if entry.action_id == action_id
            ]
            outstanding = sum(
                entry.amount_minor
                for entry in entries
                if entry.entry_type == BudgetEntryType.RESERVED.value
            )
            outstanding -= sum(
                entry.amount_minor
                for entry in entries
                if entry.entry_type == BudgetEntryType.RELEASED.value
            )
            if amount_minor > outstanding:
                raise BudgetOverspendError("release exceeds outstanding reservation")
        if (
            entry_type == BudgetEntryType.ADJUSTED
            and not 0 <= available + amount_minor <= account.allocated_minor
        ):
            raise BudgetOverspendError("adjustment exceeds account capacity")
        if entry_type in {BudgetEntryType.RESERVED, BudgetEntryType.COMMITTED}:
            if amount_minor > available:
                raise BudgetOverspendError("budget operation would overspend")
        self._session.add(
            BudgetLedgerEntryRecord(
                tenant_id=tenant_id,
                account_id=account.id,
                action_id=action_id,
                operation_id=operation_id,
                entry_type=entry_type.value,
                amount_minor=amount_minor,
                entry_metadata={},
                created_at=datetime.now(UTC),
            ),
        )
        return await self.available_minor(tenant_id, account_id)

    async def _load_account(
        self,
        tenant_id: UUID,
        account_id: UUID,
        *,
        lock: bool,
    ) -> BudgetAccountRecord:
        query = select(BudgetAccountRecord).where(
            BudgetAccountRecord.tenant_id == tenant_id,
            BudgetAccountRecord.id == account_id,
        )
        if lock:
            query = query.with_for_update()
        account = await self._session.scalar(query)
        if account is None:
            raise BudgetOverspendError("budget account not found")
        return account

    async def _entries(self, tenant_id: UUID, account_id: UUID) -> list[BudgetLedgerEntryRecord]:
        entries = await self._session.scalars(
            select(BudgetLedgerEntryRecord).where(
                BudgetLedgerEntryRecord.tenant_id == tenant_id,
                BudgetLedgerEntryRecord.account_id == account_id,
            ),
        )
        return list(entries)

    async def _load_entry(
        self,
        tenant_id: UUID,
        account_id: UUID,
        operation_id: str,
    ) -> BudgetLedgerEntryRecord | None:
        entry: BudgetLedgerEntryRecord | None = await self._session.scalar(
            select(BudgetLedgerEntryRecord).where(
                BudgetLedgerEntryRecord.tenant_id == tenant_id,
                BudgetLedgerEntryRecord.account_id == account_id,
                BudgetLedgerEntryRecord.operation_id == operation_id,
            ),
        )
        return entry
