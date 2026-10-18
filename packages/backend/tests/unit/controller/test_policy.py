from dataclasses import replace

from open_commerce.controller.models import ControllerPolicyConfig
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.core.enums import ActionStatus, Capability, PolicyOutcome
from open_commerce.core.money import Money

from .helpers import TENANT_ID, create_active_run


async def test_controller_run_proposes_goal_conditioned_approval_and_allow() -> None:
    service, _goal, run = await create_active_run()
    records = service.list_actions(tenant_id=TENANT_ID, run_id=run.id).items

    statuses = {record.action.intent.type: record.action.status for record in records}
    assert {
        key: run.summary[key]
        for key in (
            "awaiting_approval_actions",
            "denied_actions",
            "executable_actions",
            "proposed_actions",
        )
    } == {
        "awaiting_approval_actions": 1,
        "denied_actions": 0,
        "executable_actions": 1,
        "proposed_actions": 2,
    }
    assert statuses["set_search_boost"] == ActionStatus.EXECUTABLE
    assert statuses["create_discount"] == ActionStatus.AWAITING_APPROVAL
    trace_nodes = [event.node for event in run.trace]
    assert trace_nodes[0] == "load_goal_and_policy"
    assert trace_nodes[-1] == "summarize"


async def test_policy_boundaries_cover_relevance_inventory_freshness_and_capability() -> None:
    service, goal, run = await create_active_run()
    boost = next(
        record
        for record in service.list_actions(tenant_id=TENANT_ID, run_id=run.id).items
        if record.action.intent.type == "set_search_boost"
    )
    state = service.simulator_service.get_full_state(
        tenant_id=TENANT_ID,
        instance_id=goal.simulator_instance_id,
    )
    policy = ControllerPolicyConfig(tenant_id=TENANT_ID, updated_at=state.current_time)
    base_context = PolicyContext(
        goal=goal.spec,
        policy=policy,
        action=boost.action,
        capabilities={Capability.WRITE_MERCHANDISING},
        sample_size=1_000,
        data_age_minutes={"catalog": 0, "inventory": 0, "orders": 0},
        budget_remaining=Money(amount_minor=100_000, currency="USD"),
        actions_in_run=1,
        active_target_keys=set(),
        recent_target_keys=set(),
    )
    engine = PolicyEngine()

    low_relevance = boost.action.model_copy(
        update={
            "normalized_parameters": {
                **boost.action.normalized_parameters,
                "min_relevance_score": "0.10",
            }
        },
        deep=True,
    )
    inventory_write = boost.action.model_copy(
        update={
            "normalized_parameters": {
                **boost.action.normalized_parameters,
                "inventory_write_requested": True,
            }
        },
        deep=True,
    )

    assert engine.decide(replace(base_context, action=low_relevance)).outcome == PolicyOutcome.DENY
    assert (
        engine.decide(replace(base_context, action=inventory_write)).outcome == PolicyOutcome.DENY
    )
    assert (
        engine.decide(replace(base_context, data_age_minutes={"catalog": 999})).outcome
        == PolicyOutcome.DENY
    )
    assert engine.decide(replace(base_context, capabilities=set())).outcome == PolicyOutcome.DENY
