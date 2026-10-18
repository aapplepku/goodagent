"""Single controlled provider-write path for controller actions."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from open_commerce.controller.models import ControllerActionRecord, PolicyViolationError
from open_commerce.controller.policy import PolicyContext, PolicyEngine
from open_commerce.core.actions import (
    CreateDiscountIntent,
    DisableDiscountIntent,
    NoOpIntent,
    SetCampaignBudgetIntent,
    SetRecommendationPolicyIntent,
    SetSearchBoostIntent,
    SetVariantPriceIntent,
    transition_action,
)
from open_commerce.core.enums import ActionStatus, ExecutionStatus, PolicyOutcome
from open_commerce.core.providers import (
    CreateDiscountCommand,
    DisableDiscountCommand,
    ExecutionRef,
    ProviderResult,
    ReconciliationResult,
    SetCampaignBudgetCommand,
    SetRecommendationPolicyCommand,
    SetVariantPricesCommand,
)
from open_commerce.core.types import JsonObject, SafeError, canonical_hash
from open_commerce.simulator.models import SimulatorState
from open_commerce.simulator.provider import SetSearchBoostCommand, SimulatorProvider
from open_commerce.simulator.service import SimulatorService
from open_commerce.simulator.targets import target_state


class ControllerExecutor:
    """Execute simulator provider writes after final safety checks."""

    def __init__(
        self,
        *,
        simulator_service: SimulatorService,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.simulator_service = simulator_service
        self.policy_engine = policy_engine or PolicyEngine()

    async def execute(
        self,
        *,
        record: ControllerActionRecord,
        context: PolicyContext,
        has_matching_approval: bool,
    ) -> tuple[ProviderResult, ReconciliationResult | None]:
        """Execute one compiled action through the only provider-write path."""

        if record.execution_result is not None:
            return record.execution_result, record.reconciliation

        decision = self.policy_engine.decide(context)
        if decision.outcome == PolicyOutcome.DENY:
            record.policy_decision = decision
            record.action.status = ActionStatus.DENIED
            raise PolicyViolationError("policy denied action before execution")
        if decision.outcome == PolicyOutcome.REQUIRE_APPROVAL and not has_matching_approval:
            record.policy_decision = decision
            record.action.status = ActionStatus.AWAITING_APPROVAL
            raise PolicyViolationError("matching approval is required before execution")

        state = self.simulator_service.get_full_state(
            tenant_id=record.action.tenant_id,
            instance_id=UUID(record.action.target_provider.resource_id),
        )
        _assert_preconditions(record=record, state=state)
        provider = self.simulator_service.provider_for(
            tenant_id=record.action.tenant_id,
            instance_id=state.id,
        )

        if record.action.status == ActionStatus.AWAITING_APPROVAL and has_matching_approval:
            record.action.status = transition_action(record.action.status, ActionStatus.APPROVED)
        if record.action.status == ActionStatus.APPROVED:
            record.action.status = transition_action(record.action.status, ActionStatus.EXECUTABLE)
        if record.action.status == ActionStatus.COMPILED:
            record.action.status = transition_action(record.action.status, ActionStatus.EXECUTABLE)
        if record.action.status != ActionStatus.EXECUTABLE:
            raise PolicyViolationError(
                f"action is not executable from status {record.action.status}"
            )

        record.action.status = transition_action(record.action.status, ActionStatus.EXECUTING)
        result = await _dispatch(provider=provider, record=record)
        self.simulator_service.store.put(provider.state)
        record.execution_result = result
        if result.status == ExecutionStatus.SUCCEEDED:
            record.action.status = transition_action(record.action.status, ActionStatus.SUCCEEDED)
            reconciliation = await _reconcile(provider=provider, record=record, result=result)
            record.reconciliation = reconciliation
            return result, reconciliation
        if result.status == ExecutionStatus.UNCERTAIN:
            record.action.status = transition_action(record.action.status, ActionStatus.UNCERTAIN)
            return result, None
        record.action.status = transition_action(record.action.status, ActionStatus.FAILED)
        return result, None

    async def rollback(
        self,
        *,
        record: ControllerActionRecord,
        idempotency_key: str,
    ) -> ProviderResult:
        """Rollback a previous simulator execution through the controlled executor."""

        if record.execution_result is None or record.execution_result.provider_request_id is None:
            raise PolicyViolationError("action has no execution to roll back")
        if not record.action.rollback_plan.available:
            raise PolicyViolationError("rollback metadata is unavailable")
        execution_id = UUID(record.execution_result.provider_request_id)
        provider = self.simulator_service.provider_for(
            tenant_id=record.action.tenant_id,
            instance_id=UUID(record.action.target_provider.resource_id),
        )
        if record.action.status == ActionStatus.SUCCEEDED:
            record.action.status = transition_action(
                record.action.status,
                ActionStatus.ROLLBACK_PROPOSED,
            )
        if record.action.status == ActionStatus.ROLLBACK_PROPOSED:
            record.action.status = transition_action(
                record.action.status,
                ActionStatus.ROLLING_BACK,
            )
        result = await provider.rollback(execution_id=execution_id, idempotency_key=idempotency_key)
        self.simulator_service.store.put(provider.state)
        record.action.status = (
            ActionStatus.ROLLED_BACK
            if result.status == ExecutionStatus.SUCCEEDED
            else ActionStatus.ROLLBACK_FAILED
        )
        return result


def _assert_preconditions(*, record: ControllerActionRecord, state: SimulatorState) -> None:
    generation = next(
        (
            item.value
            for item in record.action.preconditions
            if item.field == "simulator.generation"
        ),
        None,
    )
    if generation is not None and generation != state.generation:
        raise PolicyViolationError("simulator was reset after action compilation")
    if (
        state.tenant_id != record.action.tenant_id
        or str(state.id) != record.action.target_provider.resource_id
    ):
        raise PolicyViolationError("action target is not owned by the tenant")
    expected_target = next(
        (
            item.value
            for item in record.action.preconditions
            if item.field == "simulator.target_hash"
        ),
        None,
    )
    if expected_target is not None and expected_target != canonical_hash(
        target_state(state, record.action.intent)
    ):
        raise PolicyViolationError("target state changed after action compilation")
    expected_hash = next(
        (
            str(precondition.value)
            for precondition in record.action.preconditions
            if precondition.field == "simulator.state_hash"
        ),
        None,
    )
    if expected_hash is not None and state.state_hash != expected_hash:
        raise PolicyViolationError("simulator state changed after action compilation")


async def _dispatch(
    *,
    provider: SimulatorProvider,
    record: ControllerActionRecord,
) -> ProviderResult:
    action = record.action
    intent = action.intent
    if isinstance(intent, CreateDiscountIntent):
        create_discount = CreateDiscountCommand(
            tenant_id=action.tenant_id,
            idempotency_key=action.idempotency_key,
            code=intent.code,
            discount_kind=intent.discount_kind,
            value=str(intent.value),
            starts_at=intent.starts_at,
            ends_at=intent.ends_at,
            product_scope=cast(JsonObject, intent.product_scope.model_dump(mode="json")),
            minimum_subtotal_minor=intent.minimum_subtotal_minor,
            maximum_cost_minor=intent.maximum_cost_minor,
            new_customers_only=intent.customer_scope.new_customers_only,
        )
        return await provider.create_discount(create_discount)
    if isinstance(intent, DisableDiscountIntent):
        disable_discount = DisableDiscountCommand(
            tenant_id=action.tenant_id,
            idempotency_key=action.idempotency_key,
            provider_discount_id=intent.provider_discount_id,
        )
        return await provider.disable_discount(disable_discount)
    if isinstance(intent, SetCampaignBudgetIntent):
        campaign_budget = SetCampaignBudgetCommand(
            tenant_id=action.tenant_id,
            idempotency_key=action.idempotency_key,
            campaign_id=intent.campaign_id,
            budget=intent.new_budget,
        )
        return await provider.set_campaign_budget(campaign_budget)
    if isinstance(intent, SetSearchBoostIntent):
        search_boost = SetSearchBoostCommand(
            tenant_id=action.tenant_id,
            idempotency_key=action.idempotency_key,
            query_text=str(action.normalized_parameters["query_text"]),
            category=str(action.normalized_parameters["category"]),
            product_ids=list(_string_sequence(action.normalized_parameters["product_ids"])),
            multiplier=intent.multiplier,
            starts_at=intent.starts_at,
            ends_at=intent.ends_at,
        )
        return await provider.set_search_boost(search_boost)
    if isinstance(intent, SetVariantPriceIntent):
        variant_prices = SetVariantPricesCommand(
            tenant_id=action.tenant_id,
            idempotency_key=action.idempotency_key,
            changes=[
                {
                    "product_id": change.product_id,
                    "variant_id": change.variant_id,
                    "new_price_minor": change.new_price.amount_minor,
                }
                for change in intent.changes
            ],
            window=intent.window,
            current_versions=intent.current_versions,
        )
        return await provider.set_variant_prices(variant_prices)
    if isinstance(intent, SetRecommendationPolicyIntent):
        return await provider.set_recommendation_policy(
            SetRecommendationPolicyCommand(
                tenant_id=action.tenant_id,
                idempotency_key=action.idempotency_key,
                expected_version=intent.expected_version,
                controls=intent.controls,
                window=intent.window,
            )
        )
    if isinstance(intent, NoOpIntent):
        return await provider.no_op(
            tenant_id=action.tenant_id, idempotency_key=action.idempotency_key
        )
    raise PolicyViolationError("unsupported provider action")


async def _reconcile(
    *,
    provider: SimulatorProvider,
    record: ControllerActionRecord,
    result: ProviderResult,
) -> ReconciliationResult | None:
    if result.provider_request_id is None:
        return None
    execution = ExecutionRef(
        tenant_id=record.action.tenant_id,
        execution_id=UUID(result.provider_request_id),
        action_id=record.action.id,
        provider=record.action.target_provider,
    )
    return await provider.reconcile(execution)


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def failed_execution_result(code: str, message: str) -> ProviderResult:
    """Build a redacted execution failure."""

    return ProviderResult(
        status=ExecutionStatus.FAILED,
        before_state={},
        after_state=None,
        error=SafeError(code=code, message=message),
    )
