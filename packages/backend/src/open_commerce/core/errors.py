"""Typed domain errors."""

from open_commerce.core.enums import ActionStatus


class DomainError(ValueError):
    """Base class for deterministic domain failures."""

    code = "DOMAIN_ERROR"


class InvalidTransitionError(DomainError):
    """Raised when an action transition is not allowed."""

    code = "INVALID_ACTION_TRANSITION"

    def __init__(self, current: ActionStatus, target: ActionStatus) -> None:
        super().__init__(f"Cannot transition action from {current.value} to {target.value}.")
        self.current = current
        self.target = target


class BudgetError(DomainError):
    """Raised when a budget operation would violate ledger invariants."""

    code = "BUDGET_ERROR"


class BudgetOverspendError(BudgetError):
    """Raised when a reservation or commit exceeds available budget."""

    code = "BUDGET_OVERSPEND"


class ApprovalHashMismatchError(DomainError):
    """Raised when an approval is replayed against a different action version."""

    code = "APPROVAL_HASH_MISMATCH"


class TenantScopeError(DomainError):
    """Raised when tenant scope is missing or inconsistent."""

    code = "TENANT_SCOPE_REQUIRED"


class MetricRegistryError(DomainError):
    """Raised when an unsupported metric/operator combination is requested."""

    code = "METRIC_REGISTRY_ERROR"
