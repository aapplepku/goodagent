"""Tenant-scoped repository protocols for application services."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from open_commerce.core.actions import CompiledAction
from open_commerce.core.events import AuditEvent, ObservationSnapshot, Opportunity
from open_commerce.core.goals import GoalSpec
from open_commerce.core.policy_types import Approval, ApprovalRequest, PolicyDecision
from open_commerce.core.providers import CapabilitySet


class GoalRepository(Protocol):
    """Repository for tenant-scoped goals."""

    async def add(self, tenant_id: UUID, goal: GoalSpec) -> None: ...

    async def get(self, tenant_id: UUID, goal_id: UUID) -> GoalSpec | None: ...


class CatalogRepository(Protocol):
    """Repository for catalog facts."""

    async def count_products(self, tenant_id: UUID) -> int: ...


class ActionRepository(Protocol):
    """Repository for action intent and compiled-action state."""

    async def add_compiled(self, tenant_id: UUID, action: CompiledAction) -> None: ...

    async def get_compiled(self, tenant_id: UUID, action_id: UUID) -> CompiledAction | None: ...

    async def transition(self, tenant_id: UUID, action_id: UUID, status: str) -> None: ...


class ApprovalRepository(Protocol):
    """Repository for approval requests and decisions."""

    async def add_request(self, tenant_id: UUID, request: ApprovalRequest) -> None: ...

    async def add_approval(self, tenant_id: UUID, approval: Approval) -> None: ...


class BudgetRepository(Protocol):
    """Repository for budget accounts and ledger entries."""

    async def available_minor(self, tenant_id: UUID, account_id: UUID) -> int: ...

    async def reserve(
        self,
        tenant_id: UUID,
        account_id: UUID,
        amount_minor: int,
        operation_id: str,
        action_id: UUID | None = None,
    ) -> int: ...


class AuditRepository(Protocol):
    """Append-only audit repository."""

    async def append(self, tenant_id: UUID, event: AuditEvent) -> None: ...

    async def list_for_entity(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> list[AuditEvent]: ...


class IntegrationRepository(Protocol):
    """Repository for integration metadata and capabilities."""

    async def capabilities(self, tenant_id: UUID, integration_id: UUID) -> CapabilitySet | None: ...


class RunRepository(Protocol):
    """Repository for snapshots, opportunities, and run traces."""

    async def add_snapshot(self, tenant_id: UUID, snapshot: ObservationSnapshot) -> None: ...

    async def add_opportunity(self, tenant_id: UUID, opportunity: Opportunity) -> None: ...

    async def add_policy_decision(
        self,
        tenant_id: UUID,
        action_id: UUID,
        policy_version_id: UUID | None,
        action_version_hash: str,
        decision: PolicyDecision,
    ) -> None: ...
