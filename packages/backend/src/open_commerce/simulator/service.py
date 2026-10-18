"""Simulator service and in-process store."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from open_commerce.simulator.engine import (
    advance_state,
    compare_to_baseline,
    create_initial_state,
    reset_state,
    run_until_state,
    summarize_state,
)
from open_commerce.simulator.exposure import DefaultExposurePolicy, ExposurePolicy
from open_commerce.simulator.models import (
    BaselineComparisonResponse,
    ScenarioListResponse,
    SimulatorMetricsResponse,
    SimulatorState,
    SimulatorStateResponse,
)
from open_commerce.simulator.provider import SimulatorProvider
from open_commerce.simulator.scenarios import get_scenario, list_scenarios


class SimulatorError(Exception):
    """Base simulator application error."""


class SimulatorBusyError(SimulatorError):
    """A consequential workflow prevents advancing or replacing simulator state."""


class ScenarioNotFoundError(SimulatorError):
    """Raised when a scenario id is unknown."""


class SimulatorInstanceNotFoundError(SimulatorError):
    """Raised when an instance is missing or belongs to another tenant."""


class SimulatorStore(Protocol):
    """Tenant-scoped simulator state storage."""

    def put(self, state: SimulatorState) -> None:
        """Persist a simulator state."""

    def get(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        """Load a simulator state for a tenant."""

    def list_for_tenant(self, tenant_id: UUID) -> list[SimulatorState]:
        """List simulator states for a tenant."""


class InMemorySimulatorStore:
    """Process-local simulator store for zero-credential local demo mode."""

    def __init__(self) -> None:
        self._states: dict[UUID, SimulatorState] = {}

    def put(self, state: SimulatorState) -> None:
        """Persist a simulator state."""

        self._states[state.id] = state

    def get(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        """Load a simulator state for a tenant."""

        state = self._states.get(instance_id)
        if state is None or state.tenant_id != tenant_id:
            raise SimulatorInstanceNotFoundError(str(instance_id))
        return state

    def list_for_tenant(self, tenant_id: UUID) -> list[SimulatorState]:
        """List simulator states for a tenant."""

        return sorted(
            [state for state in self._states.values() if state.tenant_id == tenant_id],
            key=lambda state: (state.scenario_id, state.current_time, str(state.id)),
        )


class FileSimulatorStore:
    """Durable local JSON simulator store for zero-credential demo mode."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put(self, state: SimulatorState) -> None:
        """Persist a simulator state to a tenant-scoped JSON file."""

        path = self._path_for(tenant_id=state.tenant_id, instance_id=state.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True)
        path.write_text(payload + "\n", encoding="utf-8")

    def get(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        """Load a simulator state from a tenant-scoped JSON file."""

        path = self._path_for(tenant_id=tenant_id, instance_id=instance_id)
        if not path.exists():
            raise SimulatorInstanceNotFoundError(str(instance_id))
        state = SimulatorState.model_validate_json(path.read_text(encoding="utf-8"))
        if state.tenant_id != tenant_id:
            raise SimulatorInstanceNotFoundError(str(instance_id))
        return state

    def list_for_tenant(self, tenant_id: UUID) -> list[SimulatorState]:
        """List simulator states for one tenant from local JSON files."""

        directory = self.root / str(tenant_id)
        if not directory.exists():
            return []
        states = [
            SimulatorState.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]
        return sorted(
            [state for state in states if state.tenant_id == tenant_id],
            key=lambda state: (state.scenario_id, state.current_time, str(state.id)),
        )

    def _path_for(self, *, tenant_id: UUID, instance_id: UUID) -> Path:
        return self.root / str(tenant_id) / f"{instance_id}.json"


class SimulatorService:
    """Application service for deterministic simulator instances."""

    def __init__(
        self,
        *,
        store: SimulatorStore | None = None,
        exposure_policy: ExposurePolicy | None = None,
    ) -> None:
        self.store = store or InMemorySimulatorStore()
        self.exposure_policy = exposure_policy or DefaultExposurePolicy()
        self._create_idempotency: dict[tuple[UUID, str, str], UUID] = {}
        self._operation_idempotency: dict[tuple[UUID, UUID, str, str], SimulatorStateResponse] = {}

    def list_scenarios(self) -> ScenarioListResponse:
        """Return all supported simulator scenarios."""

        return ScenarioListResponse(items=list_scenarios())

    def create_instance(
        self,
        *,
        tenant_id: UUID,
        scenario_id: str,
        seed: int | None,
        idempotency_key: str,
    ) -> SimulatorStateResponse:
        """Create or return an idempotent simulator instance."""

        try:
            definition = get_scenario(scenario_id)
        except KeyError as exc:
            raise ScenarioNotFoundError(scenario_id) from exc

        cache_key = (tenant_id, scenario_id, idempotency_key)
        existing_id = self._create_idempotency.get(cache_key)
        if existing_id is not None:
            return summarize_state(self.store.get(tenant_id=tenant_id, instance_id=existing_id))

        state = create_initial_state(definition=definition, tenant_id=tenant_id, seed=seed)
        self.store.put(state)
        self._create_idempotency[cache_key] = state.id
        return summarize_state(state)

    def get_state(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorStateResponse:
        """Return a simulator state summary."""

        return summarize_state(self.store.get(tenant_id=tenant_id, instance_id=instance_id))

    def get_full_state(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        """Return full simulator state for internal provider tests and workflows."""

        return self.store.get(tenant_id=tenant_id, instance_id=instance_id)

    def list_instances(self, *, tenant_id: UUID) -> list[SimulatorStateResponse]:
        """List simulator instances for a tenant."""

        return [summarize_state(state) for state in self.store.list_for_tenant(tenant_id)]

    def advance(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        hours: int,
        idempotency_key: str,
    ) -> SimulatorStateResponse:
        """Advance virtual time by hours idempotently."""

        return self._mutate_once(
            tenant_id=tenant_id,
            instance_id=instance_id,
            operation="advance",
            idempotency_key=idempotency_key,
            mutate=lambda state: advance_state(
                state=state,
                definition=get_scenario(state.scenario_id),
                hours=hours,
                exposure_policy=self.exposure_policy,
            ),
        )

    def run_until(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        timestamp: datetime,
        idempotency_key: str,
    ) -> SimulatorStateResponse:
        """Advance virtual time to a timestamp idempotently."""

        return self._mutate_once(
            tenant_id=tenant_id,
            instance_id=instance_id,
            operation="run_until",
            idempotency_key=idempotency_key,
            mutate=lambda state: run_until_state(
                state=state,
                definition=get_scenario(state.scenario_id),
                timestamp=timestamp,
                exposure_policy=self.exposure_policy,
            ),
        )

    def reset(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        seed: int | None,
        idempotency_key: str,
    ) -> SimulatorStateResponse:
        """Reset an instance idempotently."""

        return self._mutate_once(
            tenant_id=tenant_id,
            instance_id=instance_id,
            operation="reset",
            idempotency_key=idempotency_key,
            mutate=lambda state: reset_state(
                state=state,
                definition=get_scenario(state.scenario_id),
                seed=seed,
            ),
        )

    def metrics(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorMetricsResponse:
        """Return daily metrics for an instance."""

        state = self.store.get(tenant_id=tenant_id, instance_id=instance_id)
        return SimulatorMetricsResponse(instance_id=state.id, items=list(state.metrics))

    def compare_baseline(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
    ) -> BaselineComparisonResponse:
        """Compare current instance outcomes with no-intervention baseline."""

        state = self.store.get(tenant_id=tenant_id, instance_id=instance_id)
        return compare_to_baseline(
            state=state,
            definition=get_scenario(state.scenario_id),
            exposure_policy=self.exposure_policy,
        )

    def provider_for(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorProvider:
        """Return a provider facade for a tenant-owned instance."""

        return SimulatorProvider(self.store.get(tenant_id=tenant_id, instance_id=instance_id))

    def _mutate_once(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        operation: str,
        idempotency_key: str,
        mutate: _Mutation,
    ) -> SimulatorStateResponse:
        cache_key = (tenant_id, instance_id, operation, idempotency_key)
        existing = self._operation_idempotency.get(cache_key)
        if existing is not None:
            return existing.model_copy(deep=True)

        state = self.store.get(tenant_id=tenant_id, instance_id=instance_id)
        mutated = mutate(state)
        self.store.put(mutated)
        response = summarize_state(mutated)
        self._operation_idempotency[cache_key] = response.model_copy(deep=True)
        return response


class _Mutation(Protocol):
    def __call__(self, state: SimulatorState) -> SimulatorState:
        """Mutate and return a simulator state."""
