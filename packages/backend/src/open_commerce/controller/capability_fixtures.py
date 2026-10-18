"""Preregistered evaluation-only fixtures. Never imported by API or worker entrypoints."""

from decimal import ROUND_CEILING, Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import select

from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.model_evidence import budget_evidence
from open_commerce.controller.models import (
    ActionApprovalRequest,
    ControllerRunRequest,
    GoalCreateRequest,
    GoalRecord,
    GoalUpdateRequest,
)
from open_commerce.controller.objectives import objective_value
from open_commerce.core.enums import (
    ActionStatus,
    ActionType,
    ConstraintOperator,
    GoalStatus,
    MetricName,
)
from open_commerce.core.goals import ConstraintSpec
from open_commerce.core.money import Money
from open_commerce.core.types import JsonObject, StrictDomainModel, canonical_hash, utc_now
from open_commerce.persistence.models.workflow import WorkflowJob
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.repositories.simulator import SqlSimulatorRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state
from open_commerce.simulator.models import PAIRED_ENGINE_VERSION, ScenarioId, SimulatorState
from open_commerce.simulator.scenarios import get_scenario
from open_commerce.worker.jobs import JobRunner

Arm = Literal["no_intervention", "deterministic", "model_backed"]


class CapabilityCase(StrictDomainModel):
    id: str
    scenario: ScenarioId
    objective: Literal["new_customers", "contribution_profit", "units_sold"]
    target_factor: Decimal | None
    fixture: Literal[
        "unchanged",
        "thin_margin_catalog",
        "low_inventory_catalog",
        "scheduled_campaign_decay",
        "pending_intervention_window",
        "discount_prohibition",
        "excess_scope",
        "inventory_bound_plus_one",
        "prior_intervention_followed_by_adverse_observations",
    ]
    question: str


class CaseSetup(StrictDomainModel):
    goal: GoalRecord
    start_day: int
    initial_objective_value: Decimal
    incremental_target: Decimal | None
    prior_action_ids: list[UUID] = Field(default_factory=list)
    checks: JsonObject = Field(default_factory=dict)
    observable_world_hash: str
    starting_budgets: list[JsonObject]


async def execute_reviewed_run(
    service: DurableControllerService, tenant: UUID, run_id: UUID
) -> None:
    """Same explicit synthetic evaluation approval regime in both controller arms."""
    records = (await service.list_actions(tenant_id=tenant, run_id=run_id)).items
    for record in records:
        if record.action.status == ActionStatus.AWAITING_APPROVAL:
            await service.approve_action(
                tenant_id=tenant,
                action_id=record.action.id,
                request=ActionApprovalRequest(action_version_hash=record.action_version_hash),
                actor_roles={"operator"},
                decision="approve",
                idempotency_key=f"eval:approve:{record.action.id}",
            )
        elif record.action.status != ActionStatus.EXECUTABLE:
            continue
        await service.execute_action(
            tenant_id=tenant,
            action_id=record.action.id,
            idempotency_key=f"eval:execute:{record.action.id}",
        )


async def measure_due(database: RuntimeDatabase, tenant: UUID) -> None:
    """Advance only the harness's delivery clock; use the actual worker measurement path."""
    async with database.transaction(tenant, write=True) as session:
        jobs = list(
            await session.scalars(
                select(WorkflowJob).where(
                    WorkflowJob.tenant_id == tenant,
                    WorkflowJob.kind == "measure",
                    WorkflowJob.status == "pending",
                )
            )
        )
        for job in jobs:
            job.available_at = utc_now()
    for job in jobs:
        await JobRunner(database, tenant).run(job.id)


async def fixture_change(
    database: RuntimeDatabase, tenant: UUID, instance_id: UUID, change: str
) -> None:
    """Declared synthetic exogenous inputs, not model actions or measured outcomes."""
    async with database.transaction(tenant, write=True) as session:
        state = await load_state(session, tenant, instance_id)
        if change == "paired_engine":
            state.engine_version = PAIRED_ENGINE_VERSION
        elif change == "thin_margin_catalog":
            for product in state.products:
                for variant in product.variants:
                    variant.cost_minor = variant.price_minor * 90 // 100
        elif change == "low_inventory_catalog":
            for product in state.products:
                product.low_stock = True
                for variant in product.variants:
                    variant.inventory, variant.available = 3, True
        elif change == "campaign_decay":
            initial = {c.id: c.baseline_quality for c in get_scenario(state.scenario_id).campaigns}
            for campaign in state.campaigns:
                campaign.baseline_quality = initial[campaign.id] * Decimal("0.50")
        else:
            raise ValueError("unknown registered fixture change")
        await SqlSimulatorRepository(session).save_state(state)
        await SqlSimulatorRepository(session).replace_materializations(state)


def observable_world_hash(state: SimulatorState) -> str:
    """Remove generated record identifiers, retain all observable starting economics."""
    return canonical_hash(
        {
            "time": state.current_time,
            "day": state.day,
            "engine": state.engine_version,
            "products": [
                {
                    "id": p.id,
                    "category": p.category,
                    "excess": p.excess_inventory,
                    "low_stock": p.low_stock,
                    "variants": p.variants,
                }
                for p in state.products
            ],
            "campaigns": [
                {"id": c.id, "budget": c.daily_budget_minor, "active": c.active}
                for c in state.campaigns
            ],
            "metrics": state.metrics,
            "discounts": [
                d.model_dump(exclude={"id", "created_by_command", "code"}) for d in state.discounts
            ],
            "boosts": [
                b.model_dump(exclude={"id", "created_by_command"}) for b in state.search_boosts
            ],
        }
    )


async def prepare_case(
    database: RuntimeDatabase, tenant: UUID, case: CapabilityCase, seed: int, arm: Arm
) -> CaseSetup:
    await database.initialize_tenant(tenant)
    service = DurableControllerService(database)
    warmup = 4 if case.fixture == "prior_intervention_followed_by_adverse_observations" else 0
    prior = case.fixture in {
        "pending_intervention_window",
        "prior_intervention_followed_by_adverse_observations",
    }
    initial = GoalCreateRequest(
        scenario_id=case.scenario,
        seed=seed,
        target_value=10000,
        horizon_days=10 + warmup,
        budget=Money(amount_minor=300000, currency="USD"),
        daily_budget=Money(amount_minor=25000, currency="USD"),
        allowed_action_types={ActionType.SET_SEARCH_BOOST}
        if prior
        else {
            ActionType.CREATE_DISCOUNT,
            ActionType.SET_SEARCH_BOOST,
            ActionType.SET_CAMPAIGN_BUDGET,
        },
    )
    goal = await service.create_goal(
        tenant_id=tenant, request=initial, idempotency_key="registered-fixture"
    )
    await fixture_change(database, tenant, goal.simulator_instance_id, "paired_engine")
    if case.fixture in {"thin_margin_catalog", "low_inventory_catalog"}:
        await fixture_change(database, tenant, goal.simulator_instance_id, case.fixture)
    checks: JsonObject = {}
    if prior:
        await service.set_goal_status(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            status=GoalStatus.ACTIVE,
            idempotency_key="prior-active",
        )
        run = await service.run_goal(
            tenant_id=tenant,
            goal_id=goal.spec.id,
            request=ControllerRunRequest(),
            idempotency_key="shared-prior",
        )
        await service.process_run(tenant_id=tenant, run_id=run.id)
        await execute_reviewed_run(service, tenant, run.id)
        prior_records = (await service.list_actions(tenant_id=tenant, run_id=run.id)).items
        executed = [r for r in prior_records if r.execution_result is not None]
        if len(executed) != 1 or executed[0].action.intent.type != "set_search_boost":
            raise ValueError(
                "registered shared prior could not execute exactly one eligible search boost"
            )
        checks["prior_receipt_recorded"] = True
        if warmup:
            await fixture_change(
                database, tenant, goal.simulator_instance_id, "thin_margin_catalog"
            )
            await service.simulator_service.advance(
                tenant_id=tenant,
                instance_id=goal.simulator_instance_id,
                hours=24 * warmup,
                idempotency_key="registered-warmup",
            )
            await measure_due(database, tenant)
            updated = await service.get_action(tenant_id=tenant, action_id=executed[0].action.id)
            checks["adverse_prior_measured"] = (
                updated.outcome is not None and updated.outcome.guardrail_status == "breached"
            )
        else:
            checks["prior_window_pending"] = (
                executed[0].measurement is not None and executed[0].outcome is None
            )
    state = await service.simulator_service.get_full_state(
        tenant_id=tenant, instance_id=goal.simulator_instance_id
    )
    recent = state.metrics[-7:]
    scope = "excess_inventory" if case.fixture == "excess_scope" else "store"
    metric = MetricName(case.objective)
    current = (
        Decimal(
            sum(
                v.initial_inventory - v.inventory
                for p in state.products
                if p.excess_inventory
                for v in p.variants
            )
        )
        if scope == "excess_inventory"
        else sum(
            (Decimal(getattr(m, case.objective)) for m in state.metrics if not m.is_history),
            Decimal(0),
        )
        if case.objective != "contribution_profit"
        else Decimal(0)
    )
    target: Decimal | None = None
    if case.fixture == "inventory_bound_plus_one":
        target = Decimal(sum(p.total_inventory for p in state.products) + 1)
    elif case.target_factor is not None:
        target = (
            sum((Decimal(getattr(m, case.objective)) for m in recent), Decimal(0))
            / len(recent)
            * 10
            * case.target_factor
        ).quantize(Decimal(1), rounding=ROUND_CEILING)
    actions = {
        ActionType.CREATE_DISCOUNT,
        ActionType.SET_SEARCH_BOOST,
        ActionType.SET_CAMPAIGN_BUDGET,
    }
    constraints = initial.resolved_constraints()
    if case.fixture == "discount_prohibition":
        actions.remove(ActionType.CREATE_DISCOUNT)
        constraints = [c for c in constraints if c.metric != MetricName.DISCOUNT_RATE]
        constraints.append(
            ConstraintSpec(
                metric=MetricName.DISCOUNT_RATE, operator=ConstraintOperator.LTE, value=Decimal(0)
            )
        )
        checks["discount_prohibition"] = True
    replacement = GoalCreateRequest(
        scenario_id=case.scenario,
        seed=seed,
        name="Registered simulator goal",
        objective_metric=metric,
        objective_scope=scope,
        objective_direction="maximize" if target is None else "reach",
        target_value=current + target if target is not None else None,
        horizon_days=10 + warmup,
        budget=initial.budget,
        daily_budget=initial.daily_budget,
        constraints=constraints,
        allowed_action_types=actions,
        planning_mode="model_backed" if arm == "model_backed" else "deterministic",
    )
    replacement.review_hash = replacement.configuration_hash
    goal = await service.update_goal(
        tenant_id=tenant,
        goal_id=goal.spec.id,
        request=GoalUpdateRequest(expected_revision=1, replacement=replacement),
        idempotency_key="review-registered-goal",
    )
    goal = await service.set_goal_status(
        tenant_id=tenant,
        goal_id=goal.spec.id,
        status=GoalStatus.ACTIVE,
        idempotency_key="registered-active",
    )
    async with database.transaction(tenant, write=True) as session:
        repo = ControllerRepository(session, tenant)
        await repo.ensure_daily_budget(goal, state.current_time)
        budgets = await budget_evidence(repo, goal, state)
    prior_ids = [
        r.action.id
        for r in (await service.list_actions(tenant_id=tenant, goal_id=goal.spec.id)).items
    ]
    checks["thin_margin_applied"] = case.fixture != "thin_margin_catalog" or all(
        v.cost_minor == v.price_minor * 90 // 100 for p in state.products for v in p.variants
    )
    checks["low_stock_applied"] = case.fixture != "low_inventory_catalog" or all(
        p.low_stock and all(v.inventory == 3 for v in p.variants) for p in state.products
    )
    return CaseSetup(
        goal=goal,
        start_day=state.day,
        initial_objective_value=objective_value(goal.spec.objective, state) or Decimal(0),
        incremental_target=target,
        prior_action_ids=prior_ids,
        checks=checks,
        observable_world_hash=observable_world_hash(state),
        starting_budgets=budgets,
    )
