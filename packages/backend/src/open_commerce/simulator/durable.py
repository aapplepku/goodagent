"""PostgreSQL-authoritative simulator operations for API and worker processes."""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.types import ensure_utc
from open_commerce.persistence.models.actions import ActionExecution, CompiledActionRecord
from open_commerce.persistence.models.goals import Goal
from open_commerce.persistence.models.simulator import SimulatorInstanceRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.engine import (
    compare_to_baseline,
    create_initial_state,
    reset_state,
    run_until_state,
    summarize_state,
)
from open_commerce.simulator.merchandising_models import PromotionRedemption
from open_commerce.simulator.models import (
    BaselineComparisonResponse,
    ScenarioListResponse,
    SimulatorMetricsResponse,
    SimulatorState,
    SimulatorStateResponse,
)
from open_commerce.simulator.scenarios import get_scenario, list_scenarios
from open_commerce.simulator.service import (
    ScenarioNotFoundError,
    SimulatorBusyError,
    SimulatorInstanceNotFoundError,
)


async def load_state(session: AsyncSession, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
    row = await session.scalar(
        select(SimulatorInstanceRecord).where(
            SimulatorInstanceRecord.tenant_id == tenant_id,
            SimulatorInstanceRecord.id == instance_id,
        )
    )
    if row is None:
        raise SimulatorInstanceNotFoundError(str(instance_id))
    return SimulatorState.model_validate(row.state)


class DurableSimulatorService:
    """All reads reload committed state; mutations and request receipts commit together."""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def list_scenarios(self) -> ScenarioListResponse:
        return ScenarioListResponse(items=list_scenarios())

    async def create_instance(
        self, *, tenant_id: UUID, scenario_id: str, seed: int | None, idempotency_key: str
    ) -> SimulatorStateResponse:
        async with self.database.transaction(tenant_id, write=True) as session:
            return await self.create_in_transaction(
                session,
                tenant_id=tenant_id,
                scenario_id=scenario_id,
                seed=seed,
                idempotency_key=idempotency_key,
            )

    async def create_in_transaction(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        scenario_id: str,
        seed: int | None,
        idempotency_key: str,
    ) -> SimulatorStateResponse:
        requests = RequestRepository(session, tenant_id)
        request = {"scenario_id": scenario_id, "seed": seed}
        cached = await requests.replay(
            scope="simulator:create", key=idempotency_key, request=request
        )
        if cached is not None:
            return SimulatorStateResponse.model_validate(cached)
        try:
            definition = get_scenario(scenario_id)
        except KeyError as exc:
            raise ScenarioNotFoundError(scenario_id) from exc
        state = create_initial_state(
            definition=definition,
            tenant_id=tenant_id,
            seed=seed,
            instance_id=uuid5(NAMESPACE_URL, f"{tenant_id}:simulator:{idempotency_key}"),
        )
        await SqlSimulatorRepository(session).save_state(state)
        await session.flush()
        response = summarize_state(state)
        requests.remember(
            scope="simulator:create", key=idempotency_key, request=request, response=response
        )
        return response

    async def get_full_state(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorState:
        async with self.database.transaction(tenant_id) as session:
            return await load_state(session, tenant_id, instance_id)

    async def redeem_merchandising_order(
        self,
        *,
        tenant_id: UUID,
        instance_id: UUID,
        order_key: str,
        product_id: str,
        variant_id: str,
        expected_price_version: int,
        discount_id: str | None,
        new_customer: bool = False,
    ) -> PromotionRedemption:
        """Simulator checkout, serialized with all effects and other redemptions."""
        from open_commerce.simulator.merchandising import redeem_order

        async with self.database.transaction(tenant_id, write=True) as session:
            await self._assert_idle(session, tenant_id, instance_id)
            state = await load_state(session, tenant_id, instance_id)
            result = redeem_order(
                state,
                tenant_id=tenant_id,
                order_key=order_key,
                product_id=product_id,
                variant_id=variant_id,
                expected_price_version=expected_price_version,
                discount_id=discount_id,
                new_customer=new_customer,
            )
            await SqlSimulatorRepository(session).save_state(state)
            return result

    async def get_state(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorStateResponse:
        return summarize_state(
            await self.get_full_state(tenant_id=tenant_id, instance_id=instance_id)
        )

    async def list_instances(self, *, tenant_id: UUID) -> list[SimulatorStateResponse]:
        async with self.database.transaction(tenant_id) as session:
            rows = await session.scalars(
                select(SimulatorInstanceRecord)
                .where(
                    SimulatorInstanceRecord.tenant_id == tenant_id,
                )
                .order_by(SimulatorInstanceRecord.created_at, SimulatorInstanceRecord.id)
            )
            return [summarize_state(SimulatorState.model_validate(row.state)) for row in rows]

    async def advance(
        self, *, tenant_id: UUID, instance_id: UUID, hours: int, idempotency_key: str
    ) -> SimulatorStateResponse:
        if hours <= 0 or hours > 24 * 366:
            raise ValueError("hours must be between 1 and 8784")
        return await self._advance(
            tenant_id,
            instance_id,
            "advance",
            idempotency_key,
            {"hours": hours},
            lambda state: state.current_time + timedelta(hours=hours),
        )

    async def run_until(
        self, *, tenant_id: UUID, instance_id: UUID, timestamp: datetime, idempotency_key: str
    ) -> SimulatorStateResponse:
        return await self._advance(
            tenant_id,
            instance_id,
            "run-until",
            idempotency_key,
            {"timestamp": timestamp},
            lambda state: ensure_utc(timestamp),
        )

    async def _advance(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        operation: str,
        key: str,
        request: object,
        target_for: Callable[[SimulatorState], datetime],
    ) -> SimulatorStateResponse:
        from open_commerce.persistence.repositories.controller import ControllerRepository
        from open_commerce.persistence.repositories.simulation_budget import SimulationBudget

        scope = f"simulator:{instance_id}:{operation}"
        async with self.database.transaction(tenant_id, write=True) as session:
            requests = RequestRepository(session, tenant_id)
            cached = await requests.replay(scope=scope, key=key, request=request)
            if cached is not None:
                return SimulatorStateResponse.model_validate(cached)
            await self._assert_idle(session, tenant_id, instance_id)
            state = await load_state(session, tenant_id, instance_id)
            target = target_for(state)
            if target < state.current_time or target > state.current_time + timedelta(days=366):
                raise ValueError("target must be within the next 366 simulated days")
            if state.merchandising is not None and (
                target.time() != time.min or state.current_time.time() != time.min
            ):
                raise ValueError("merchandising advances require whole UTC days")
            goal_id = await session.scalar(
                select(Goal.id).where(
                    Goal.tenant_id == tenant_id, Goal.simulator_instance_id == instance_id
                )
            )
            if goal_id is not None:
                goal = await ControllerRepository(session, tenant_id).get_goal(goal_id)
                if target > goal.spec.horizon.end_at:
                    raise ValueError("cannot advance a goal beyond its horizon")
                billing = SimulationBudget(session, tenant_id, goal)
                while True:
                    boundary = datetime.combine(
                        state.current_time.date() + timedelta(days=1), time.min, tzinfo=UTC
                    )
                    if boundary > target:
                        break
                    if goal.spec.merchandising is not None:
                        from open_commerce.search.durable import DurableSearchService
                        from open_commerce.simulator.merchandising_engine import (
                            simulate_merchandising_day,
                        )

                        search = DurableSearchService(self.database)
                        try:
                            index, _ = await search.prepare_state_index(session, state)
                            await simulate_merchandising_day(
                                state,
                                tenant_id=tenant_id,
                                index=index,
                                embedding_model=search.embedding_provider.model_id,
                            )
                        finally:
                            await search.close()
                        continue
                    before = {item.id: item.spent_minor for item in state.discounts}
                    await billing.prepare_day(state)
                    state = run_until_state(
                        state=state, definition=get_scenario(state.scenario_id), timestamp=boundary
                    )
                    await billing.settle_day(state, state.metrics[-1], before)
                state.current_time = target
            else:
                state = run_until_state(
                    state=state, definition=get_scenario(state.scenario_id), timestamp=target
                )
            await SqlSimulatorRepository(session).save_state(state)
            response = summarize_state(state)
            requests.remember(scope=scope, key=key, request=request, response=response)
            return response

    @staticmethod
    async def _assert_idle(session: AsyncSession, tenant_id: UUID, instance_id: UUID) -> None:
        attempt = await session.scalar(
            select(ActionExecution.id)
            .join(
                CompiledActionRecord,
                (CompiledActionRecord.id == ActionExecution.action_id)
                & (CompiledActionRecord.tenant_id == ActionExecution.tenant_id),
            )
            .where(
                ActionExecution.tenant_id == tenant_id,
                CompiledActionRecord.tenant_id == tenant_id,
                CompiledActionRecord.target_provider["resource_id"].astext == str(instance_id),
                ActionExecution.completed_at.is_(None),
            )
            .limit(1)
        )
        if attempt is not None:
            raise SimulatorBusyError(
                "reconcile the in-flight execution before advancing or resetting"
            )

    async def reset(
        self, *, tenant_id: UUID, instance_id: UUID, seed: int | None, idempotency_key: str
    ) -> SimulatorStateResponse:
        return await self._mutate(
            tenant_id,
            instance_id,
            "reset",
            idempotency_key,
            {"seed": seed},
            lambda state: reset_state(
                state=state, definition=get_scenario(state.scenario_id), seed=seed
            ),
        )

    async def _mutate(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        operation: str,
        key: str,
        request: object,
        mutate: Callable[[SimulatorState], SimulatorState],
    ) -> SimulatorStateResponse:
        scope = f"simulator:{instance_id}:{operation}"
        async with self.database.transaction(tenant_id, write=True) as session:
            requests = RequestRepository(session, tenant_id)
            cached = await requests.replay(scope=scope, key=key, request=request)
            if cached is not None:
                return SimulatorStateResponse.model_validate(cached)
            state = await load_state(session, tenant_id, instance_id)
            await self._assert_idle(session, tenant_id, instance_id)
            if operation == "reset":
                goal_id = await session.scalar(
                    select(Goal.id).where(
                        Goal.tenant_id == tenant_id, Goal.simulator_instance_id == instance_id
                    )
                )
                if goal_id is not None:
                    raise SimulatorBusyError(
                        "create a fresh goal to reset; historical goal-owned state is retained"
                    )
            state = mutate(state)
            await SqlSimulatorRepository(session).save_state(state)
            response = summarize_state(state)
            requests.remember(scope=scope, key=key, request=request, response=response)
            return response

    async def metrics(self, *, tenant_id: UUID, instance_id: UUID) -> SimulatorMetricsResponse:
        state = await self.get_full_state(tenant_id=tenant_id, instance_id=instance_id)
        return SimulatorMetricsResponse(instance_id=state.id, items=state.metrics)

    async def compare_baseline(
        self, *, tenant_id: UUID, instance_id: UUID
    ) -> BaselineComparisonResponse:
        state = await self.get_full_state(tenant_id=tenant_id, instance_id=instance_id)
        return compare_to_baseline(state=state, definition=get_scenario(state.scenario_id))
