"""Model tools expose instrumented facts and scoped configuration, never arbitrary logging."""

from uuid import UUID

from open_commerce.core.tool_schema import strict_tool_schema
from open_commerce.core.types import JsonObject, canonical_hash
from open_commerce.manager_agent.model_provider import ManagerToolCall, ManagerToolDefinition
from open_commerce.telemetry.activity import ActivityRuleError, ActivityService
from open_commerce.telemetry.activity_models import ActivityQuery, ActivityRuleInput


def activity_tool_schema(model: type[ActivityQuery] | type[ActivityRuleInput]) -> JsonObject:
    return strict_tool_schema(model)


ACTIVITY_TOOLS = [
    ManagerToolDefinition(
        name="inspect_shopping_activity",
        description=(
            "Inspect redacted operational logs, observed event counts, available fields, saved "
            "views and monitors. Use the returned data dictionary before proposing tracking. "
            "Shopper context sees only its own events; operator context sees store aggregates "
            "and redacted events. No private text or identities. Latest 100 events, "
            "30-day retention."
        ),
        parameters=activity_tool_schema(ActivityQuery),
    ),
    ManagerToolDefinition(
        name="configure_activity_monitor",
        description=(
            "On explicit request, create or update a named log view or threshold monitor. "
            "Inspect available activity first. Same name updates; enabled=false pauses. "
            "threshold=null creates a log-only view. Threshold alerts when value >= threshold. "
            "Rates are percent, latency is milliseconds. Use unfiltered search outcomes for "
            "empty_result_rate: query.kind=search, query.status=null, empty_results_only=false. "
            "Use query.status=null for error_rate. No data is insufficient, "
            "not healthy. Shopper rules affect only their own account, never store tracking. "
            "Checks run in the worker with in-app results; no external notifications. "
            "Unsupported fields require new instrumentation; do not claim to collect them."
        ),
        parameters=activity_tool_schema(ActivityRuleInput),
    ),
]


class ActivityTools:
    def __init__(
        self,
        service: ActivityService,
        *,
        tenant_id: UUID,
        account_id: UUID | None,
        turn_key: str,
        account_version: int | None = None,
    ) -> None:
        self.service = service
        self.tenant_id = tenant_id
        self.account_id = account_id
        self.turn_key = turn_key
        self.account_version = account_version
        self.configured = False

    async def execute(self, call: ManagerToolCall) -> JsonObject:
        if call.name == "inspect_shopping_activity":
            return (
                await self.service.overview(
                    tenant_id=self.tenant_id,
                    account_id=self.account_id,
                    query=ActivityQuery.model_validate(call.arguments),
                )
            ).model_dump(mode="json")
        if call.name != "configure_activity_monitor":
            return {"error": "UNKNOWN_TOOL"}
        try:
            result = await self.service.configure(
                tenant_id=self.tenant_id,
                account_id=self.account_id,
                definition=ActivityRuleInput.model_validate(call.arguments),
                key=canonical_hash({"turn": self.turn_key, "call": call.call_id}),
                account_version=self.account_version,
            )
        except ActivityRuleError as exc:
            return {"error": "ACTIVITY_RULE_BLOCKED", "message": str(exc)}
        self.configured = True
        return {"ok": True, "verified": True, "rule": result.model_dump(mode="json")}
