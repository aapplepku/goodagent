"""Goal configuration review independent of storage and workflow state."""

from datetime import timedelta

from open_commerce.controller.models import GoalRecord, GoalUpdateRequest, PolicyViolationError
from open_commerce.core.enums import GoalStatus
from open_commerce.core.goals import BudgetSpec, GoalSpec, HorizonSpec
from open_commerce.core.types import JsonObject, canonical_hash, utc_now


def configuration_for(goal: GoalRecord) -> JsonObject:
    payload: JsonObject = goal.spec.model_dump(mode="json", exclude={"status", "created_at"})
    payload["planning_mode"] = goal.planning_mode
    payload["soft_preferences"] = goal.soft_preferences
    payload["allowed_action_types"] = sorted(
        action.value for action in goal.spec.allowed_action_types
    )
    payload["constraints"] = sorted(
        [item.model_dump(mode="json") for item in goal.spec.constraints], key=canonical_hash
    )
    payload["budgets"] = sorted(
        [item.model_dump(mode="json") for item in goal.spec.budgets], key=canonical_hash
    )
    return payload


def revise_goal(goal: GoalRecord, request: GoalUpdateRequest) -> GoalRecord:
    """Apply only explicitly reviewed changes; never reseed or reset business spend."""
    if request.expected_revision != goal.revision:
        raise PolicyViolationError("goal revision changed or review revision is missing")
    if goal.spec.status in {GoalStatus.COMPLETED, GoalStatus.ARCHIVED}:
        raise PolicyViolationError("terminal goals cannot be changed")
    payload = goal.spec.model_dump()
    result = goal.model_copy(deep=True)
    if request.replacement is not None:
        replacement = request.replacement
        if any(
            value is not None
            for value in (request.name, request.default_mode, request.allowed_action_types)
        ):
            raise PolicyViolationError("review either a replacement or a patch, not both")
        if replacement.review_hash != replacement.configuration_hash:
            raise PolicyViolationError(
                "replacement goal needs an exact reviewed configuration hash"
            )
        if replacement.scenario_id != goal.scenario_id or replacement.seed != goal.seed:
            raise PolicyViolationError("a goal revision cannot replace or reseed its simulator")
        horizon = HorizonSpec(
            start_at=goal.spec.horizon.start_at,
            end_at=goal.spec.horizon.start_at + timedelta(days=replacement.horizon_days),
        )
        payload.update(
            {
                "name": replacement.name,
                "objective": replacement.resolved_objective(),
                "horizon": horizon,
                "budgets": [
                    BudgetSpec(kind="goal", amount=replacement.budget, period=horizon),
                    BudgetSpec(kind="daily", amount=replacement.daily_budget, period=horizon),
                ],
                "constraints": replacement.resolved_constraints(),
                "autonomy": {
                    "default_mode": replacement.default_mode,
                    "per_action": replacement.per_action_modes,
                },
                "allowed_action_types": replacement.allowed_action_types,
                "merchandising": replacement.merchandising,
            }
        )
        result.planning_mode = replacement.planning_mode
        result.soft_preferences = replacement.soft_preferences
    else:
        if request.name is not None:
            payload["name"] = request.name
        if request.allowed_action_types is not None:
            payload["allowed_action_types"] = request.allowed_action_types
        if request.default_mode is not None:
            payload["autonomy"] = {
                **goal.spec.autonomy.model_dump(),
                "default_mode": request.default_mode,
            }
    payload["status"] = GoalStatus.DRAFT
    result.spec = GoalSpec.model_validate(payload)
    result.revision += 1
    result.updated_at = utc_now()
    return result
