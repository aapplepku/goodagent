from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from open_commerce.controller.models import (
    ControllerRunRecord,
    ControllerRunRequest,
    GoalCreateRequest,
    GoalRecord,
)
from open_commerce.controller.service import ControllerService
from open_commerce.core.enums import ActionType, AutonomyMode, GoalStatus
from open_commerce.simulator.service import SimulatorService

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def create_active_run(
    *,
    seed: int = 42,
    execute_bounded_auto: bool = False,
) -> tuple[ControllerService, GoalRecord, ControllerRunRecord]:
    service = ControllerService(simulator_service=SimulatorService())
    goal = service.create_goal(
        tenant_id=TENANT_ID,
        request=GoalCreateRequest(
            seed=seed,
            target_value=Decimal("10000"),
            per_action_modes={ActionType.SET_SEARCH_BOOST: AutonomyMode.BOUNDED_AUTO},
        ),
        idempotency_key=f"test-goal:{seed}:{execute_bounded_auto}",
    )
    service.set_goal_status(
        tenant_id=TENANT_ID,
        goal_id=goal.spec.id,
        status=GoalStatus.ACTIVE,
        idempotency_key=f"test-activate:{seed}:{execute_bounded_auto}",
    )
    run = await service.run_goal(
        tenant_id=TENANT_ID,
        goal_id=goal.spec.id,
        request=ControllerRunRequest(execute_bounded_auto=execute_bounded_auto),
        idempotency_key=f"test-run:{seed}:{execute_bounded_auto}",
    )
    return service, goal, run
