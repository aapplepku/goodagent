"""Ad-hoc monitoring is bounded numeric configuration, never dynamic code."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from open_commerce.core.types import utc_now
from open_commerce.telemetry.activity import evaluate_metric
from open_commerce.telemetry.activity_models import ActivityEvent, ActivityRuleInput
from open_commerce.telemetry.activity_tools import ACTIVITY_TOOLS


def test_empty_result_monitor_distinguishes_insufficient_data_alert_and_healthy() -> None:
    now = utc_now()
    rule = ActivityRuleInput.model_validate(
        {
            "name": "Empty searches",
            "query": {"kind": "search"},
            "metric": "empty_result_rate",
            "threshold": 25,
            "minimum_samples": 2,
        }
    )
    events = [
        ActivityEvent.model_validate(
            {
                "id": uuid4(),
                "kind": "search",
                "status": "ok",
                "duration_ms": 12,
                "result_count": result,
                "occurred_at": now,
            }
        )
        for result in (0, 4)
    ]
    assert evaluate_metric(rule, [], now=now).state == "insufficient_data"
    result = evaluate_metric(rule, events, now=now)
    assert result.state == "alert" and result.value == 50
    assert evaluate_metric(rule, events, now=now, truncated=True).state == "insufficient_data"
    events[0].result_count = 2
    assert evaluate_metric(rule, events, now=now).state == "ok"
    rule.enabled = False
    assert evaluate_metric(rule, events, now=now).state == "paused"


@pytest.mark.parametrize(
    "extra",
    [
        {"account_id": str(uuid4())},
        {"sql": "select * from users"},
        {"metric": "raw_query"},
        {"query": {"email": "person@example.com"}},
        {"metric": "error_rate", "query": {"status": "error"}},
        {"metric": "empty_result_rate", "query": {"kind": "search", "empty_results_only": True}},
        {"interval_minutes": 0},
        {"name": "token sk-" + "proj-synthetic-test-secret-123456789"},
    ],
)
def test_invalid_authority_fields_code_and_misleading_denominators_are_rejected(
    extra: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ActivityRuleInput.model_validate({"name": "Search quality", **extra})


def test_tool_schemas_are_strict_including_nested_definitions() -> None:
    def visit(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    for tool in ACTIVITY_TOOLS:
        visit(tool.parameters)
