"""In-memory budget ledger primitives used by tests and service contracts."""

from dataclasses import dataclass, field
from uuid import UUID

from open_commerce.core.enums import BudgetEntryType
from open_commerce.core.errors import BudgetOverspendError


@dataclass(frozen=True)
class BudgetLedgerEntry:
    """One idempotent budget ledger operation."""

    tenant_id: UUID
    account_id: UUID
    operation_id: str
    entry_type: BudgetEntryType
    amount_minor: int
    action_id: UUID | None = None


@dataclass
class BudgetAccount:
    """Derived-balance budget account for deterministic service tests."""

    tenant_id: UUID
    account_id: UUID
    allocated_minor: int
    entries_by_operation: dict[str, BudgetLedgerEntry] = field(default_factory=dict)

    def available_minor(self) -> int:
        """Return derived available budget."""

        reserved = sum(
            entry.amount_minor
            for entry in self.entries_by_operation.values()
            if entry.entry_type == BudgetEntryType.RESERVED
        )
        committed = sum(
            entry.amount_minor
            for entry in self.entries_by_operation.values()
            if entry.entry_type == BudgetEntryType.COMMITTED
        )
        released = sum(
            entry.amount_minor
            for entry in self.entries_by_operation.values()
            if entry.entry_type == BudgetEntryType.RELEASED
        )
        adjusted = sum(
            entry.amount_minor
            for entry in self.entries_by_operation.values()
            if entry.entry_type == BudgetEntryType.ADJUSTED
        )
        return self.allocated_minor - reserved - committed + released + adjusted

    def apply(self, entry: BudgetLedgerEntry) -> int:
        """Apply an idempotent ledger entry and return available budget."""

        existing = self.entries_by_operation.get(entry.operation_id)
        if existing is not None:
            if existing != entry:
                raise BudgetOverspendError("operation_id already used for a different entry")
            return self.available_minor()
        if entry.entry_type in {BudgetEntryType.RESERVED, BudgetEntryType.COMMITTED}:
            if entry.amount_minor > self.available_minor():
                raise BudgetOverspendError("budget operation would overspend")
        self.entries_by_operation[entry.operation_id] = entry
        return self.available_minor()
