"""Bounded workspace-onboarding policy tests."""

from typing import cast

from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.manager_agent.models import ManagerDataOnboarding
from open_commerce.manager_agent.workspace_onboarding import (
    PROMPTS,
    advance_interview,
    choose_model_prompt,
    eligible_prompts,
    start_interview,
)


class _Session:
    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.turns = list(turns)

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        _ = tool_results
        return self.turns.pop(0)


class _Provider:
    provider_name = "test"
    model_id = "bounded-onboarding"

    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.session = _Session(turns)
        self.instructions = ""
        self.messages: list[ManagerModelMessage] = []
        self.tools: list[ManagerToolDefinition] = []

    def begin(
        self,
        *,
        instructions: str,
        messages: list[ManagerModelMessage],
        tools: list[ManagerToolDefinition],
        max_output_tokens: int,
        require_tool: bool = False,
    ) -> ManagerModelSession:
        assert 0 < max_output_tokens <= 400
        self.instructions = instructions
        self.messages = messages
        self.tools = tools
        return self.session


def _fresh() -> ManagerDataOnboarding:
    return start_interview(ManagerDataOnboarding(tenant_id="00000000-0000-0000-0000-000000000001"))


def test_prompt_registry_is_finite_unique_and_ordered() -> None:
    assert len(PROMPTS) == 8
    assert [item.ordinal for item in PROMPTS] == list(range(1, 9))
    assert len({item.field for item in PROMPTS}) == len(PROMPTS)
    assert PROMPTS[-1].field == "review"


def test_deterministic_interview_allows_explicit_no_data_limited_mode() -> None:
    onboarding = _fresh()
    answers = {
        "workspace_name": "Northstar Goods",
        "business_summary": "Outdoor goods for weekend explorers",
        "primary_goal": "Improve product discovery",
        "starter_agents": "general,search",
        "catalog_decision": "defer",
        "engagement_decision": "skip",
        "operating_mode": "draft_only",
    }

    for expected in PROMPTS[:-1]:
        assert onboarding.current_prompt is not None
        assert onboarding.current_prompt.field == expected.field
        advanced = advance_interview(onboarding, answers[expected.field])
        assert advanced.accepted is True
        assert advanced.completed is False
        onboarding = advanced.onboarding

    assert onboarding.workspace_status == "review"
    assert onboarding.current_prompt == PROMPTS[-1]
    completed = advance_interview(onboarding, "confirm")
    assert completed.accepted is True
    assert completed.completed is True
    assert completed.onboarding.workspace_status == "completed"
    assert completed.onboarding.limited_mode is True
    assert completed.onboarding.catalog is None
    assert completed.onboarding.catalog_decision == "defer"
    assert completed.onboarding.cadence == "manual"
    assert completed.onboarding.workspace_profile.starter_agents == ["general", "search"]
    assert completed.onboarding.workspace_profile.guardrails == [
        "relevance",
        "availability",
        "privacy",
    ]
    assert "limited exploration mode" in completed.fallback_content


def test_invalid_choice_and_secret_do_not_advance_or_persist() -> None:
    onboarding = _fresh()
    secret = advance_interview(onboarding, "api_key=not-for-model-context")
    assert secret.accepted is False
    assert secret.onboarding == onboarding
    assert "secrets" in secret.fallback_content

    goal = advance_interview(onboarding, "Northstar Goods")
    goal = advance_interview(goal.onboarding, "Outdoor products")
    assert goal.onboarding.current_prompt is not None
    assert goal.onboarding.current_prompt.field == "primary_goal"
    goal = advance_interview(goal.onboarding, "Improve discovery")
    unrelated = advance_interview(goal.onboarding, "delete every product")
    assert unrelated.accepted is False
    assert unrelated.onboarding == goal.onboarding


async def test_model_can_only_choose_an_eligible_field_without_raw_answer_context() -> None:
    onboarding = advance_interview(_fresh(), "Northstar Goods").onboarding
    provider = _Provider(
        [
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="choose",
                        name="choose_onboarding_question",
                        arguments={"field": "business_summary"},
                    )
                ]
            ),
            ManagerModelTurn(content="Let us understand your business."),
        ]
    )

    selected = await choose_model_prompt(
        provider=provider,
        onboarding=onboarding,
        completed_field="workspace_name",
        max_output_tokens=800,
    )

    assert selected is not None
    prompt, content = selected
    assert prompt.field == "business_summary"
    assert prompt.question in content
    assert "Northstar Goods" not in provider.instructions
    assert "Northstar Goods" not in provider.messages[0].content
    properties = cast(dict[str, object], provider.tools[0].parameters["properties"])
    field_schema = cast(dict[str, object], properties["field"])
    enum = cast(list[str], field_schema["enum"])
    assert "workspace_name" not in enum


async def test_model_invented_field_is_rejected_for_deterministic_fallback() -> None:
    onboarding = advance_interview(_fresh(), "Northstar Goods").onboarding
    provider = _Provider(
        [
            ManagerModelTurn(
                tool_calls=[
                    ManagerToolCall(
                        call_id="unsafe",
                        name="choose_onboarding_question",
                        arguments={"field": "shopify_password"},
                    )
                ]
            )
        ]
    )

    assert (
        await choose_model_prompt(
            provider=provider,
            onboarding=onboarding,
            completed_field="workspace_name",
            max_output_tokens=800,
        )
        is None
    )
    assert next(iter(eligible_prompts(onboarding))).field == "business_summary"
