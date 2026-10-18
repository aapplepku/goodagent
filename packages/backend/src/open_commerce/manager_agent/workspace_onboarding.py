"""Finite, model-assisted manager workspace onboarding."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from open_commerce.core.types import utc_now
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelProvider,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.manager_agent.models import (
    DataSourceDraft,
    DataSourceKind,
    LoadCadence,
    ManagerDataOnboarding,
    OnboardingChoice,
    OnboardingField,
    OnboardingPrompt,
)

_SECRET_RE = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{12,}\b|\b(?:password|secret|api[_ -]?key|access[_ -]?token)\s*[:=])",
    re.IGNORECASE,
)


def _choice(value: str, label: str, description: str | None = None) -> OnboardingChoice:
    return OnboardingChoice(value=value, label=label, description=description)


PROMPTS: tuple[OnboardingPrompt, ...] = (
    OnboardingPrompt(
        field="workspace_name",
        section="Your business",
        intro="First, give this workspace a useful identity.",
        question="What should I call this commerce workspace?",
        input_kind="text",
        ordinal=1,
    ),
    OnboardingPrompt(
        field="business_summary",
        section="Your business",
        question="In a sentence or two, what do you sell and who shops with you?",
        input_kind="text",
        ordinal=2,
    ),
    OnboardingPrompt(
        field="primary_goal",
        section="Your goals",
        intro="Give me one outcome to orient the workspace. We can unpack the strategy later.",
        question="What is the most important shopper or business outcome you want to improve?",
        input_kind="text",
        ordinal=3,
    ),
    OnboardingPrompt(
        field="starter_agents",
        section="Your agents",
        intro=(
            "Choose only the specialists that are useful now. You can create, rename, or "
            "archive agents later."
        ),
        question="Which agents should I set up first? Choose one or more.",
        input_kind="multi_select",
        choices=[
            _choice("general", "General commerce", "An open-ended operator copilot."),
            _choice("status", "Operations & status", "Service and data readiness."),
            _choice("search", "Search", "Retrieval, ranking, and query testing."),
            _choice("recommendations", "Recommendations", "Discovery surfaces and strategy."),
            _choice("buy_again", "Buy it again", "Repeat-purchase strategy."),
            _choice("analysis", "Analysis", "Questions, diagnostics, and briefs."),
        ],
        ordinal=4,
    ),
    OnboardingPrompt(
        field="catalog_decision",
        section="Your data",
        intro=(
            "The agent can plan without data, but it cannot honestly index, train, or measure "
            "anything until a catalog is connected."
        ),
        question="How should we handle the product catalog for now?",
        input_kind="dataset",
        choices=[
            _choice("defer", "No data yet", "Enter limited exploration mode."),
            _choice("csv_upload", "Attach a CSV"),
            _choice("snowflake", "Configure Snowflake identifiers"),
            _choice("object_storage", "Use an object-storage export"),
        ],
        ordinal=5,
    ),
    OnboardingPrompt(
        field="engagement_decision",
        section="Your data",
        question="Do you want to provide pseudonymous engagement events now?",
        input_kind="dataset",
        choices=[
            _choice("skip", "Skip for now"),
            _choice("csv_upload", "Attach a CSV"),
            _choice("snowflake", "Configure Snowflake identifiers"),
            _choice("object_storage", "Use an object-storage export"),
        ],
        ordinal=6,
    ),
    OnboardingPrompt(
        field="operating_mode",
        section="How we work",
        intro="One last operating choice, then I will open the workspace.",
        question="How should the agent handle proposed changes?",
        input_kind="single_select",
        choices=[
            _choice("draft_only", "Draft only", "Prepare ideas without seeking execution."),
            _choice(
                "approval_required",
                "Approval required",
                "Prepare reviewable actions that still require explicit approval.",
            ),
        ],
        ordinal=7,
    ),
    OnboardingPrompt(
        field="review",
        section="Review",
        intro="That gives me enough context to organize the workspace.",
        question="Review the setup summary. Is it ready to use?",
        input_kind="review",
        choices=[_choice("confirm", "Open workspace")],
        ordinal=8,
    ),
)

_PROMPT_BY_FIELD = {prompt.field: prompt for prompt in PROMPTS}


@dataclass(frozen=True)
class InterviewAdvance:
    onboarding: ManagerDataOnboarding
    accepted: bool
    completed: bool
    fallback_content: str


def start_interview(onboarding: ManagerDataOnboarding) -> ManagerDataOnboarding:
    if onboarding.workspace_status == "completed":
        return onboarding
    updated = _with_essential_defaults(onboarding)
    if onboarding.workspace_status != "not_started":
        current = onboarding.current_prompt
        if current is not None and current.field in _PROMPT_BY_FIELD:
            return updated.model_copy(update={"current_prompt": _PROMPT_BY_FIELD[current.field]})
        remaining = eligible_prompts(updated)
        return set_current_prompt(updated, (remaining[0] if remaining else PROMPTS[-1]).field)
    return updated.model_copy(
        update={
            "workspace_status": "in_progress",
            "current_prompt": PROMPTS[0],
            "completed_fields": [],
        },
        deep=True,
    )


def set_current_prompt(
    onboarding: ManagerDataOnboarding, field: OnboardingField
) -> ManagerDataOnboarding:
    status = "review" if field == "review" else "in_progress"
    return onboarding.model_copy(
        update={"workspace_status": status, "current_prompt": _PROMPT_BY_FIELD[field]},
        deep=True,
    )


def eligible_prompts(onboarding: ManagerDataOnboarding) -> list[OnboardingPrompt]:
    completed = set(onboarding.completed_fields)
    return [prompt for prompt in PROMPTS[:-1] if prompt.field not in completed]


def advance_interview(onboarding: ManagerDataOnboarding, answer: str) -> InterviewAdvance:
    current = onboarding.current_prompt or PROMPTS[0]
    cleaned = " ".join(answer.strip().split())[:500]
    if _SECRET_RE.search(cleaned):
        return InterviewAdvance(
            onboarding,
            False,
            False,
            "Please remove credentials or secrets from that answer and try again.",
        )
    if current.field == "review":
        edit = re.fullmatch(r"edit:([a-z_]+)", cleaned.lower())
        if edit and edit.group(1) in _PROMPT_BY_FIELD:
            field = cast(OnboardingField, edit.group(1))
            if field != "review":
                updated = set_current_prompt(onboarding, field)
                return InterviewAdvance(
                    updated, True, False, _prompt_content(updated.current_prompt)
                )
        if _selected_values(current, cleaned) != ["confirm"]:
            return InterviewAdvance(
                onboarding,
                False,
                False,
                "Please confirm the review or choose a field to edit.",
            )
        limited = not _catalog_ready(onboarding)
        completed = onboarding.model_copy(
            update={
                "workspace_status": "completed",
                "current_prompt": None,
                "limited_mode": limited,
                "completed_at": utc_now(),
            },
            deep=True,
        )
        mode = "limited exploration mode" if limited else "the connected-data workspace"
        agents = onboarding.workspace_profile.starter_agents or ["general"]
        agent_names = ", ".join(item.replace("_", " ") for item in agents)
        return InterviewAdvance(
            completed,
            True,
            True,
            f"Your workspace is ready in {mode}. I set up these agents: {agent_names}.",
        )

    updated = onboarding.model_copy(deep=True)
    accepted = _apply_answer(updated, current, cleaned)
    if not accepted:
        return InterviewAdvance(
            onboarding,
            False,
            False,
            f"I could not map that answer safely. {current.question}",
        )
    completed_fields = list(dict.fromkeys([*updated.completed_fields, current.field]))
    updated.completed_fields = completed_fields
    remaining = eligible_prompts(updated)
    next_prompt = remaining[0] if remaining else PROMPTS[-1]
    updated = set_current_prompt(updated, next_prompt.field)
    return InterviewAdvance(updated, True, False, _prompt_content(next_prompt))


def apply_profile_progress(
    onboarding: ManagerDataOnboarding, dataset_kind: str
) -> ManagerDataOnboarding:
    field: OnboardingField = (
        "catalog_decision" if dataset_kind == "catalog" else "engagement_decision"
    )
    completed = list(dict.fromkeys([*onboarding.completed_fields, field]))
    updated = onboarding.model_copy(update={"completed_fields": completed}, deep=True)
    if onboarding.current_prompt and onboarding.current_prompt.field == field:
        remaining = eligible_prompts(updated)
        updated = set_current_prompt(updated, (remaining[0] if remaining else PROMPTS[-1]).field)
    return updated


async def choose_model_prompt(
    *,
    provider: ManagerModelProvider,
    onboarding: ManagerDataOnboarding,
    completed_field: OnboardingField,
    max_output_tokens: int,
) -> tuple[OnboardingPrompt, str] | None:
    candidates = eligible_prompts(onboarding)
    if not candidates:
        candidates = [PROMPTS[-1]]
    allowed = [item.field for item in candidates]
    tool = ManagerToolDefinition(
        name="choose_onboarding_question",
        description=(
            "Choose exactly one next question from the finite eligible list. Do not invent a "
            "field or ask for credentials, secrets, customer data, or raw records."
        ),
        parameters={
            "type": "object",
            "properties": {"field": {"type": "string", "enum": allowed}},
            "required": ["field"],
            "additionalProperties": False,
        },
    )
    candidate_text = "; ".join(f"{item.field}: {item.question}" for item in candidates)
    session = provider.begin(
        instructions=(
            "You guide a store operator through a bounded onboarding interview. First call "
            "choose_onboarding_question. After the tool result, acknowledge progress in one short "
            "sentence and ask the required question exactly once. Never request secrets or PII. "
            f"Eligible questions: {candidate_text}"
        ),
        messages=[
            ManagerModelMessage(
                role="user",
                content=f"The store operator completed onboarding field {completed_field}.",
            )
        ],
        tools=[tool],
        max_output_tokens=min(max_output_tokens, 400),
    )
    first = await session.next([])
    if not first.tool_calls:
        return None
    call = first.tool_calls[0]
    selected = call.arguments.get("field")
    if call.name != tool.name or selected not in allowed:
        return None
    prompt = _PROMPT_BY_FIELD[cast(OnboardingField, selected)]
    result = ManagerToolResult(
        call_id=call.call_id,
        name=call.name,
        output={"field": prompt.field, "required_question": prompt.question},
    )
    final = await session.next([result])
    content = (final.content or "").strip()
    if not content:
        content = _prompt_content(prompt)
    elif prompt.question not in content:
        content = f"{content[:350]}\n\n{prompt.question}"
    return prompt, content[:900]


def _apply_answer(onboarding: ManagerDataOnboarding, prompt: OnboardingPrompt, answer: str) -> bool:
    profile = onboarding.workspace_profile.model_copy(deep=True)
    if prompt.input_kind == "text":
        if len(answer) < 2:
            return False
        setattr(profile, prompt.field, answer)
        onboarding.workspace_profile = profile
        return True
    values = _selected_values(prompt, answer)
    if not values:
        return False
    if prompt.field in {
        "starter_agents",
        "priority_surfaces",
        "recommendation_surfaces",
        "success_metrics",
        "guardrails",
    }:
        if prompt.field == "success_metrics":
            values = values[:3]
        setattr(profile, prompt.field, values)
        onboarding.workspace_profile = profile
        return True
    value = values[0]
    if prompt.field == "catalog_decision":
        if value == "defer":
            onboarding.catalog_decision = "defer"
            onboarding.catalog = None
        else:
            onboarding.catalog_decision = "provide"
            onboarding.catalog = DataSourceDraft(
                dataset_kind="catalog", source_kind=cast(DataSourceKind, value)
            )
        return True
    if prompt.field == "engagement_decision":
        if value == "skip":
            onboarding.engagement_decision = "skip"
            onboarding.engagement = None
        else:
            onboarding.engagement_decision = "provide"
            onboarding.engagement = DataSourceDraft(
                dataset_kind="engagement", source_kind=cast(DataSourceKind, value)
            )
        return True
    if prompt.field == "cadence":
        onboarding.cadence = cast(LoadCadence, value)
        onboarding.incremental_mode = "watermark" if _has_watermark(onboarding) else "full_refresh"
        return True
    setattr(profile, prompt.field, value)
    onboarding.workspace_profile = profile
    return True


def _selected_values(prompt: OnboardingPrompt, answer: str) -> list[str]:
    normalized = answer.lower().strip()
    selected: list[str] = []
    for choice in prompt.choices:
        label = choice.label.lower()
        if (
            normalized == choice.value
            or normalized == label
            or choice.value in {part.strip() for part in normalized.split(",")}
            or label in {part.strip() for part in normalized.split(",")}
        ):
            selected.append(choice.value)
    return selected


def _prompt_content(prompt: OnboardingPrompt | None) -> str:
    if prompt is None:
        return "Your onboarding answers are ready for review."
    return f"{prompt.intro}\n\n{prompt.question}" if prompt.intro else prompt.question


def _has_watermark(onboarding: ManagerDataOnboarding) -> bool:
    profile = onboarding.catalog.profile if onboarding.catalog else None
    return bool(profile and "updated_at" in profile.detected_mappings)


def _catalog_ready(onboarding: ManagerDataOnboarding) -> bool:
    source = onboarding.catalog
    if source is None:
        return False
    if source.source_kind == "csv_upload":
        return source.profile is not None and not source.profile.missing_required
    if source.source_kind == "snowflake":
        return all(
            (
                source.account_identifier,
                source.warehouse,
                source.database,
                source.schema_name,
                source.relation,
            )
        )
    return source.object_uri is not None


def onboarding_welcome(onboarding: ManagerDataOnboarding) -> str:
    prompt = onboarding.current_prompt or PROMPTS[0]
    return (
        "Welcome to Open Commerce. I only need a few essentials to set up your operator workspace. "
        "We can work through strategy, metrics, and merchandising details naturally in the "
        "channels afterward. Nothing will be written to a store during setup.\n\n"
        f"{_prompt_content(prompt)}"
    )


def _with_essential_defaults(onboarding: ManagerDataOnboarding) -> ManagerDataOnboarding:
    """Apply safe, editable defaults for detail that no longer blocks first use."""

    profile = onboarding.workspace_profile.model_copy(deep=True)
    profile.manager_role = profile.manager_role or "mixed"
    profile.search_baseline = profile.search_baseline or "unknown"
    profile.recommendation_surfaces = profile.recommendation_surfaces or ["none"]
    profile.buy_again_strategy = profile.buy_again_strategy or "unknown"
    profile.success_metrics = profile.success_metrics or ["conversion", "search_success"]
    profile.guardrails = profile.guardrails or ["relevance", "availability", "privacy"]
    profile.response_style = profile.response_style or "balanced"
    return onboarding.model_copy(
        update={
            "workspace_profile": profile,
            "cadence": onboarding.cadence or "manual",
            "incremental_mode": onboarding.incremental_mode or "full_refresh",
        },
        deep=True,
    )
