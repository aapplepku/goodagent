"""Deterministic ReAct-style manager assistant over a finite discovery vocabulary."""

from __future__ import annotations

import re
from decimal import Decimal

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.types import canonical_hash
from open_commerce.manager_agent.data_onboarding import (
    onboarding_question,
    refresh_onboarding_status,
)
from open_commerce.manager_agent.models import (
    AgentStep,
    DataSourceDraft,
    DiscoveryObjectiveDraft,
    ManagerAgentCapabilities,
    ManagerAgentOutcome,
    ManagerDataOnboarding,
    ManagerMemory,
    ManagerMessage,
    ManagerWorkingMemory,
    PopularityStrength,
    RankingSignal,
)

POPULARITY_WEIGHTS: dict[PopularityStrength, Decimal] = {
    "light": Decimal("0.04"),
    "balanced": Decimal("0.08"),
    "strong": Decimal("0.12"),
}


class ManagerReActAgent:
    """Recall, inspect, validate and respond without granting execution authority."""

    def __init__(self, capabilities: ManagerAgentCapabilities) -> None:
        self.capabilities = capabilities

    def respond(
        self,
        *,
        content: str,
        working: ManagerWorkingMemory,
        long_term_memories: list[ManagerMemory],
        recent_messages: list[ManagerMessage],
        onboarding: ManagerDataOnboarding | None = None,
        catalog_index: CatalogIndexStatus | None = None,
    ) -> ManagerAgentOutcome:
        catalog_index = catalog_index or CatalogIndexStatus()
        text = content.strip()
        normalized = " ".join(text.lower().split())
        steps = [
            AgentStep(
                stage="recall",
                title="Recall manager context",
                detail=(
                    f"Loaded {len(long_term_memories)} explicit preferences and "
                    f"{min(len(recent_messages), 12)} recent messages."
                ),
            ),
            AgentStep(
                stage="understand",
                title="Interpret request",
                detail="Matched the message against the bounded discovery-objective vocabulary.",
            ),
        ]
        preference = explicit_preference(text)
        if preference is not None and not _contains_discovery_request(normalized):
            updated = working.model_copy(
                update={
                    "current_topic": "Manager preferences",
                    "recent_decisions": append_decision(
                        working.recent_decisions, f"Remember: {preference}"
                    ),
                }
            )
            steps.append(
                AgentStep(
                    stage="act",
                    title="Store explicit preference",
                    detail="Prepared a tenant-scoped long-term preference memory.",
                    tool="memory.store_preference",
                )
            )
            steps.append(
                AgentStep(
                    stage="respond",
                    title="Confirm memory",
                    detail="The preference will be recalled in future manager conversations.",
                )
            )
            return ManagerAgentOutcome(
                content=f"Got it. I'll remember that {preference}.",
                working_memory=updated,
                steps=steps,
                explicit_preference=preference,
            )

        if onboarding is not None and (
            _contains_onboarding_request(normalized)
            or (
                onboarding.status != "ready_for_review"
                and not _contains_discovery_request(normalized)
                and working.objective is None
            )
        ):
            updated_onboarding = _apply_onboarding_language(onboarding, normalized)
            onboarding_prompt = onboarding_question(updated_onboarding)
            reply = onboarding_prompt or (
                "The data onboarding draft is ready for review. Scheduled loads, indexing, "
                "and model activation remain inactive."
            )
            updated = working.model_copy(
                update={"current_topic": "Data onboarding", "open_question": onboarding_prompt}
            )
            steps.extend(
                [
                    AgentStep(
                        stage="act",
                        title="Update data onboarding",
                        detail=("Compiled explicit source and cadence choices into a typed draft."),
                        status="simulated",
                        tool="data.draft_onboarding",
                    ),
                    AgentStep(
                        stage="respond",
                        title="Continue onboarding",
                        detail=reply,
                        status="needs_input" if onboarding_prompt else "completed",
                    ),
                ]
            )
            return ManagerAgentOutcome(
                content=reply,
                working_memory=updated,
                steps=steps,
                explicit_preference=preference,
                onboarding=updated_onboarding,
            )

        if any(token in normalized for token in ("train a model", "online training", "personaliz")):
            reply = (
                "This conversation is using the offline interpreter. You can build a real "
                "popularity or logistic search model in the Model panel after uploading "
                "matching engagement. Model-backed chat can investigate the signals and queue "
                "that training too. Online training and individual personalization "
                "are not available."
            )
            updated = working.model_copy(
                update={
                    "current_topic": "Unsupported discovery request",
                    "open_question": "Which supported discovery surface should I configure?",
                }
            )
            steps.extend(
                [
                    AgentStep(
                        stage="observe",
                        title="Enforce capability boundary",
                        detail=(
                            "Offline chat does not queue training; use the explicit Model controls."
                        ),
                    ),
                    AgentStep(
                        stage="respond",
                        title="Offer supported path",
                        detail=reply,
                        status="needs_input",
                    ),
                ]
            )
            return ManagerAgentOutcome(
                content=reply,
                working_memory=updated,
                steps=steps,
                explicit_preference=preference,
            )

        draft = (working.objective or DiscoveryObjectiveDraft()).model_copy(deep=True)
        changed = _apply_objective_language(draft, normalized)
        if not changed and working.open_question:
            changed = _apply_follow_up(draft, normalized)

        if changed or _contains_discovery_request(normalized):
            steps.extend(
                [
                    AgentStep(
                        stage="act",
                        title="Inspect discovery capabilities",
                        detail=(
                            f"Semantic backend: {self.capabilities.semantic_backend}; "
                            f"{_catalog_index_detail(catalog_index)} The objective compiler "
                            "remains draft-only."
                        ),
                        status="simulated",
                        tool="discovery.inspect_capabilities",
                    ),
                    AgentStep(
                        stage="observe",
                        title="Validate objective",
                        detail=(
                            "Relevance remains a required gate. Popularity and quality are "
                            "bounded secondary signals."
                        ),
                    ),
                ]
            )
            apply_saved_strength(draft, long_term_memories)
            question = next_question(draft, self.capabilities)
            if question is not None:
                draft.status = "needs_clarification"
                draft.missing_fields = [question[0]]
                draft.review_hash = None
                updated = ManagerWorkingMemory(
                    current_topic="Discovery model objective",
                    open_question=question[1],
                    objective=draft,
                    recent_decisions=working.recent_decisions,
                )
                steps.append(
                    AgentStep(
                        stage="respond",
                        title="Ask one clarification",
                        detail=question[1],
                        status="needs_input",
                    )
                )
                return ManagerAgentOutcome(
                    content=question[1],
                    working_memory=updated,
                    steps=steps,
                    explicit_preference=preference,
                )

            draft.status = "ready_for_review"
            draft.missing_fields = []
            draft.review_hash = canonical_hash(
                draft.model_dump(mode="json", exclude={"review_hash"})
            )
            summary = objective_summary(draft, self.capabilities)
            updated = ManagerWorkingMemory(
                current_topic="Discovery model objective",
                open_question=None,
                objective=draft,
                recent_decisions=append_decision(working.recent_decisions, summary),
            )
            steps.append(
                AgentStep(
                    stage="respond",
                    title="Prepare model draft",
                    detail="Created a reviewable configuration; no model was trained or activated.",
                )
            )
            return ManagerAgentOutcome(
                content=(
                    f"I've prepared the model draft: {summary}. "
                    f"{_catalog_objective_notice(catalog_index)}"
                ),
                working_memory=updated,
                steps=steps,
                explicit_preference=preference,
            )

        reply = _merchant_reply(normalized, catalog_index)
        updated = working.model_copy(
            update={
                "current_topic": "Clarifying manager request",
                "open_question": reply,
            }
        )
        steps.append(
            AgentStep(
                stage="respond",
                title="Clarify workstream",
                detail=reply,
                status="needs_input",
            )
        )
        return ManagerAgentOutcome(
            content=reply,
            working_memory=updated,
            steps=steps,
            explicit_preference=preference,
        )


def _merchant_reply(normalized: str, catalog_index: CatalogIndexStatus) -> str:
    """Keep the local fallback useful and conversational when no model is configured."""

    if normalized in {"hi", "hello", "hey", "hello there"}:
        return (
            "Hey. I'm here and caught up on this channel. Tell me what's happening in the "
            "business, what feels off, or what you want to try next."
        )
    if any(token in normalized for token in ("what can you do", "help me", "how can you help")):
        return (
            "I can pressure-test a merchandising idea, shape search and recommendation "
            "strategy, inspect the catalog setup, remember how you like to work, and turn a "
            "clear request into a reviewable draft. Start with the messy version; I'll help "
            "make it precise."
        )
    if any(token in normalized for token in ("sales", "conversion", "revenue", "margin")):
        return (
            "Let's diagnose it before prescribing a change. I would split the problem into "
            "traffic quality, product discovery, offer strength, and checkout friction, then "
            "look for where the drop is concentrated. What changed most recently?"
        )
    if any(token in normalized for token in ("catalog", "product data", "csv", "index")):
        if catalog_index.status == "ready":
            return (
                f"Your search index is ready with {catalog_index.indexed_product_count} products "
                f"from {catalog_index.filename or 'the latest catalog'}. We can inspect search "
                "quality or shape a ranking objective next."
            )
        if catalog_index.status in {"queued", "running"}:
            verb = "is indexing" if catalog_index.status == "running" else "is queued"
            return (
                f"Your latest catalog {verb}: {catalog_index.indexed_product_count} of "
                f"{catalog_index.product_count} products are indexed. You can keep working here "
                "while the background job finishes."
            )
        if catalog_index.status == "failed":
            return (
                "The latest catalog index failed without replacing the last ready index. "
                f"The safe error code is {catalog_index.error_code or 'INDEX_FAILED'}. "
                "Re-upload the catalog to retry after checking its mapped fields."
            )
        return (
            "Catalog quality is the right place to start. Attach the CSV here and I'll validate "
            "the product keys, searchable text, prices, availability, and ranking signals before "
            "it is indexed."
        )
    return (
        "Got it. Say a little more about the outcome you want or the tradeoff you're weighing, "
        "and I'll help you turn it into a concrete next move."
    )


def _catalog_index_detail(status: CatalogIndexStatus) -> str:
    if status.status == "ready":
        return f"The tenant catalog index is ready with {status.indexed_product_count} products."
    if status.status in {"queued", "running"}:
        return (
            f"The tenant catalog index is {status.status} with "
            f"{status.indexed_product_count} of {status.product_count} products indexed."
        )
    if status.status == "failed":
        return "The latest catalog index failed and did not replace a previously active index."
    return "No uploaded tenant catalog is active; discovery uses the bundled simulator catalog."


def _catalog_objective_notice(status: CatalogIndexStatus) -> str:
    if status.status == "ready":
        return (
            f"The current {status.indexed_product_count}-product catalog index is live for local "
            "search, but this draft has not changed ranking behavior or activated a model."
        )
    if status.status in {"queued", "running"}:
        return (
            f"Catalog indexing is {status.status}; this strategy is ready for review but has not "
            "changed ranking behavior or activated a model."
        )
    return (
        "This strategy is ready for review, but there is no uploaded catalog index and the "
        "ranking change is not trained or active."
    )


def explicit_preference(text: str) -> str | None:
    for pattern in (
        r"^remember(?: that)?[,:]?\s+(.+)$",
        r"^(?:i|we) prefer\s+(.+)$",
    ):
        match = re.match(pattern, text.strip(), flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")[:500]
    return None


def _contains_discovery_request(text: str) -> bool:
    return any(
        token in text
        for token in (
            "search",
            "semantic",
            "retrieval",
            "rank",
            "recommend",
            "pdp",
            "related product",
        )
    )


def _contains_onboarding_request(text: str) -> bool:
    return any(
        token in text
        for token in (
            "catalog",
            "csv",
            "snowflake",
            "object storage",
            "engagement",
            "data warehouse",
            "hourly",
            "daily",
            "weekly",
            "every six hours",
        )
    )


def _apply_onboarding_language(
    onboarding: ManagerDataOnboarding, text: str
) -> ManagerDataOnboarding:
    updated = onboarding.model_copy(deep=True)
    dataset_kind = (
        "engagement"
        if any(token in text for token in ("engagement", "event", "click", "session"))
        else "catalog"
    )
    if "snowflake" in text:
        source = DataSourceDraft(dataset_kind=dataset_kind, source_kind="snowflake")
        if dataset_kind == "catalog":
            updated.catalog = source
        else:
            updated.engagement = source
            updated.engagement_decision = "provide"
    elif any(token in text for token in ("csv", "upload", "file")):
        source = DataSourceDraft(dataset_kind=dataset_kind, source_kind="csv_upload")
        if dataset_kind == "catalog":
            updated.catalog = source
        else:
            updated.engagement = source
            updated.engagement_decision = "provide"
    elif any(token in text for token in ("object storage", "s3", "gcs", "bucket")):
        source = DataSourceDraft(dataset_kind=dataset_kind, source_kind="object_storage")
        if dataset_kind == "catalog":
            updated.catalog = source
        else:
            updated.engagement = source
            updated.engagement_decision = "provide"
    if any(token in text for token in ("skip", "no engagement", "not now")):
        updated.engagement_decision = "skip"
        updated.engagement = None
    for cadence, tokens in (
        ("six_hourly", ("six hours", "6 hours", "six-hour")),
        ("hourly", ("hourly", "every hour")),
        ("daily", ("daily", "every day")),
        ("weekly", ("weekly", "every week")),
        ("manual", ("manual", "on demand")),
    ):
        if any(token in text for token in tokens):
            updated.cadence = cadence  # type: ignore[assignment]
            break
    if any(token in text for token in ("incremental", "watermark", "updated at")):
        updated.incremental_mode = "watermark"
    elif any(token in text for token in ("full refresh", "full load", "replace all")):
        updated.incremental_mode = "full_refresh"
    return refresh_onboarding_status(updated)


def _apply_objective_language(draft: DiscoveryObjectiveDraft, text: str) -> bool:
    changed = False
    search = any(token in text for token in ("search", "retrieval", "query", "semantic"))
    recommendations = any(token in text for token in ("recommend", "pdp", "related product"))
    if "both" in text or (search and recommendations):
        draft.surface = "both"
        changed = True
    elif search:
        draft.surface = "search"
        changed = True
    elif recommendations:
        draft.surface = "recommendations"
        changed = True
    for token, mode in (
        ("semantic", "semantic"),
        ("hybrid", "hybrid"),
        ("lexical", "lexical"),
        ("keyword", "lexical"),
    ):
        if token in text:
            draft.retrieval_mode = mode  # type: ignore[assignment]
            changed = True
            break
    signals: list[RankingSignal] = list(draft.ranking_signals)
    if (draft.surface is not None or "rank" in text) and "relevance" not in signals:
        signals.append("relevance")
    for token, signal in (("popular", "popularity"), ("quality", "quality")):
        if token in text and signal not in signals:
            signals.append(signal)  # type: ignore[arg-type]
            changed = True
    draft.ranking_signals = signals
    for strength in POPULARITY_WEIGHTS:
        if strength in text:
            draft.popularity_strength = strength
            changed = True
    if "complement" in text:
        draft.recommendation_strategy = "complements"
        changed = True
    elif "similar" in text:
        draft.recommendation_strategy = "similar"
        changed = True
    elif "popular recommendation" in text or "popular products" in text:
        draft.recommendation_strategy = "popular"
        changed = True
    return changed


def _apply_follow_up(draft: DiscoveryObjectiveDraft, text: str) -> bool:
    if text in POPULARITY_WEIGHTS:
        draft.popularity_strength = text  # type: ignore[assignment]
        return True
    if text in {"search", "recommendations", "both"}:
        draft.surface = text  # type: ignore[assignment]
        return True
    if text in {"semantic", "hybrid", "lexical"}:
        draft.retrieval_mode = text  # type: ignore[assignment]
        return True
    if text in {"similar", "popular", "complements"}:
        draft.recommendation_strategy = text  # type: ignore[assignment]
        return True
    return False


def reconcile_discovery_follow_up(
    working: ManagerWorkingMemory,
    content: str,
    capabilities: ManagerAgentCapabilities,
) -> ManagerWorkingMemory:
    """Ground a finite manager follow-up when a model returns prose without a tool call."""

    if working.objective is None:
        return working
    draft = working.objective.model_copy(deep=True)
    normalized = " ".join(content.lower().split())
    changed = _apply_objective_language(draft, normalized)
    if not changed and working.open_question:
        changed = _apply_follow_up(draft, normalized)
    if not changed:
        return working
    question = next_question(draft, capabilities)
    if question is not None:
        draft.status = "needs_clarification"
        draft.missing_fields = [question[0]]
        draft.review_hash = None
        return ManagerWorkingMemory(
            current_topic="Discovery model objective",
            open_question=question[1],
            objective=draft,
            recent_decisions=working.recent_decisions,
        )
    draft.status = "ready_for_review"
    draft.missing_fields = []
    draft.review_hash = canonical_hash(draft.model_dump(mode="json", exclude={"review_hash"}))
    summary = objective_summary(draft, capabilities)
    decisions = working.recent_decisions
    if not decisions or decisions[-1] != summary:
        decisions = append_decision(decisions, summary)
    return ManagerWorkingMemory(
        current_topic="Discovery model objective",
        open_question=None,
        objective=draft,
        recent_decisions=decisions,
    )


def apply_saved_strength(draft: DiscoveryObjectiveDraft, memories: list[ManagerMemory]) -> None:
    if "popularity" not in draft.ranking_signals or draft.popularity_strength is not None:
        return
    for memory in reversed(memories):
        text = memory.content.lower()
        for strength in POPULARITY_WEIGHTS:
            if strength in text and "popular" in text:
                draft.popularity_strength = strength
                return


def next_question(
    draft: DiscoveryObjectiveDraft, capabilities: ManagerAgentCapabilities
) -> tuple[str, str] | None:
    if draft.surface is None:
        return ("surface", "Should this apply to search, recommendations, or both?")
    if draft.surface in {"search", "both"} and draft.retrieval_mode is None:
        return (
            "retrieval_mode",
            "Should retrieval be lexical, semantic, or hybrid? I recommend hybrid "
            "for recall and exact matches.",
        )
    if draft.retrieval_mode == "semantic" and not capabilities.learned_semantics:
        return (
            "semantic_backend",
            "Learned semantic retrieval is not installed in this runtime. Should I "
            "draft a hybrid hash-baseline configuration instead?",
        )
    if "popularity" in draft.ranking_signals and draft.popularity_strength is None:
        return (
            "popularity_strength",
            "How strongly should popularity influence ranking: light, balanced, "
            "or strong? I recommend balanced.",
        )
    if draft.surface in {"recommendations", "both"} and draft.recommendation_strategy is None:
        return (
            "recommendation_strategy",
            "For recommendations, should we prioritize similar products, popular "
            "products, or explicit complements?",
        )
    return None


def objective_summary(
    draft: DiscoveryObjectiveDraft, capabilities: ManagerAgentCapabilities
) -> str:
    signals = ", then ".join(draft.ranking_signals) or "relevance"
    strength = (
        f" ({draft.popularity_strength}, weight {POPULARITY_WEIGHTS[draft.popularity_strength]})"
        if draft.popularity_strength
        else ""
    )
    retrieval = draft.retrieval_mode or "catalog-policy"
    return (
        f"{draft.surface} using {retrieval} retrieval on {capabilities.semantic_backend}, "
        f"ranked by {signals}{strength}, with relevance floor {draft.minimum_relevance}"
    )


def append_decision(items: list[str], value: str) -> list[str]:
    return [*items, value][-8:]
