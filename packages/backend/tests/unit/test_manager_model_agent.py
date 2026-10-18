"""Model-backed manager loop tests using a deterministic fake provider."""

from datetime import UTC, datetime
from unittest.mock import create_autospec
from uuid import UUID, uuid4

import pytest

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.manager_agent.model_agent import ModelBackedManagerAgent
from open_commerce.manager_agent.model_provider import (
    ManagerModelMessage,
    ManagerModelSession,
    ManagerModelTurn,
    ManagerToolCall,
    ManagerToolDefinition,
    ManagerToolResult,
)
from open_commerce.manager_agent.models import (
    DiscoveryObjectiveDraft,
    ManagerAgentCapabilities,
    ManagerDataOnboarding,
    ManagerMemory,
    ManagerMessage,
    ManagerWorkingMemory,
)
from open_commerce.manager_agent.run_hooks import RunJournal


async def test_repeated_identical_failures_stop_with_observed_blocker() -> None:
    bad_call = ManagerToolCall(call_id="bad", name="delete_catalog", arguments={})
    agent, provider = _agent(
        [ManagerModelTurn(tool_calls=[bad_call]) for _ in range(4)],
        max_iterations=5,
        max_tool_calls=5,
    )
    result = await agent.respond(
        content="Investigate", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
    )
    assert "repeated failure" in result.content
    assert "UNKNOWN_TOOL" in result.content
    assert all(step.status == "failed" for step in result.steps if step.tool == "delete_catalog")
    assert len(provider.session.results) == 3


async def test_recovery_rejects_commands_and_non_application_service_ids() -> None:
    turns = [
        ManagerModelTurn(
            tool_calls=[
                ManagerToolCall(
                    call_id="bad",
                    name="repair_local_service",
                    arguments={"service": "shopper_web", "command": "arbitrary command"},
                )
            ]
        ),
        ManagerModelTurn(content="Only known application services can be recovered."),
    ]
    agent, model = _agent(turns)
    await agent.respond(
        content="Repair", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
    )
    assert model.session.results[1][0].output["error"] == "INVALID_TOOL_ARGUMENTS"


async def test_initial_setup_correction_is_retained_in_conversation_context() -> None:
    agent, model = _agent([ManagerModelTurn(content="Let's start with one useful setup step.")])
    recent = [
        ManagerMessage(
            id=uuid4(),
            tenant_id=uuid4(),
            thread_id=uuid4(),
            role="user",
            content="It is initial setup, not a change",
            steps=[],
            created_at=datetime.now(UTC),
        )
    ]
    await agent.respond(
        content="ok", working=ManagerWorkingMemory(), memories=[], recent_messages=recent
    )
    assert model.messages[-2].content == recent[0].content
    assert model.messages[-1].content == "ok"
    assert "Never\nassume falling sales" in model.instructions


class FakeSession:
    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.turns = list(turns)
        self.results: list[list[ManagerToolResult]] = []

    async def next(self, tool_results: list[ManagerToolResult]) -> ManagerModelTurn:
        self.results.append(tool_results)
        return self.turns.pop(0)


async def test_commentary_is_not_a_final_manager_answer() -> None:
    agent, provider = _agent(
        [
            ManagerModelTurn(content="I will check.", phase="commentary"),
            ManagerModelTurn(content="What would you like to change?", phase="final_answer"),
        ]
    )
    result = await agent.respond(
        content="Hello", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
    )
    assert result.content == "What would you like to change?"
    assert provider.session.results == [[], []]


async def test_repeated_manager_commentary_consumes_iteration_budget() -> None:
    agent, provider = _agent(
        [ManagerModelTurn(content="Still checking", phase="commentary") for _ in range(3)],
        max_iterations=2,
    )
    result = await agent.respond(
        content="Check", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
    )
    assert "iteration limit" in result.content
    assert len(provider.session.results) == 2
    assert "Still checking" not in result.content


async def test_manager_does_not_claim_incomplete_provider_reply_is_final() -> None:
    agent, provider = _agent(
        [ManagerModelTurn(content="Unfinished", phase="final_answer", stop_reason="incomplete")]
    )
    result = await agent.respond(
        content="Check", working=ManagerWorkingMemory(), memories=[], recent_messages=[]
    )
    assert "incomplete model response" in result.content
    assert "Unfinished" not in result.content
    assert len(provider.session.results) == 1


@pytest.mark.parametrize(
    "stop_reason", ["incomplete", "failed", "cancelled", "in_progress", "queued", "unknown"]
)
async def test_manager_does_not_execute_tools_from_unfinished_turns(stop_reason: str) -> None:
    call = ManagerToolCall(
        call_id="unfinished-draft",
        name="draft_discovery_objective",
        arguments={
            "surface": "search",
            "retrieval_mode": "semantic",
            "ranking_signals": ["relevance", "popularity"],
            "popularity_strength": "balanced",
            "recommendation_strategy": None,
            "minimum_relevance": 0.5,
        },
    )
    agent, provider = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason=stop_reason),
            ManagerModelTurn(content="Should not reach this response"),
        ]
    )
    journal = create_autospec(RunJournal, instance=True)
    journal.checkpoint = {}
    result = await agent.respond(
        content="Draft semantic search",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        journal=journal,
    )
    assert result.working_memory.objective is None
    assert all(step.tool != call.name for step in result.steps)
    assert "incomplete model response" in result.content
    assert provider.session.results == [[]]
    journal.save.assert_awaited_once()
    saved = journal.save.await_args.args[0]
    assert saved["iteration"] == 1
    assert saved["call"] is None and saved["call_admission"] is None
    assert saved["tool_calls"] == 0 and saved["results"] == []
    assert saved["provider"] == {}
    assert all(call.args[0] != "tool_started" for call in journal.event.await_args_list)


class FakeProvider:
    provider_name = "fake"
    model_id = "useful-chat-model"

    def __init__(self, turns: list[ManagerModelTurn]) -> None:
        self.session = FakeSession(turns)
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
        assert max_output_tokens == 800
        self.instructions = instructions
        self.messages = messages
        self.tools = tools
        return self.session


def _agent(
    turns: list[ManagerModelTurn], *, max_iterations: int = 4, max_tool_calls: int = 3
) -> tuple[ModelBackedManagerAgent, FakeProvider]:
    provider = FakeProvider(turns)
    capabilities = ManagerAgentCapabilities(
        semantic_backend="all-MiniLM-L6-v2",
        learned_semantics=True,
        conversation_provider=provider.provider_name,
        conversation_model=provider.model_id,
        model_backed=True,
    )
    return (
        ModelBackedManagerAgent(
            provider=provider,
            capabilities=capabilities,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            max_output_tokens=800,
        ),
        provider,
    )


async def test_natural_model_response_is_returned_without_forcing_a_workflow() -> None:
    agent, provider = _agent(
        [
            ManagerModelTurn(
                content=(
                    "Yes. A good first experiment is to compare hybrid retrieval with your "
                    "current keyword baseline."
                )
            )
        ]
    )

    result = await agent.respond(
        content="What would be a sensible first experiment?",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
    )

    assert result.content.startswith("Yes. A good first experiment")
    assert result.working_memory.current_topic == "Manager conversation"
    assert provider.messages[-1].content == "What would be a sensible first experiment?"
    assert "include them only when the manager explicitly" in provider.instructions
    assert result.steps[-1].title == "Respond to manager"


async def test_prose_does_not_silently_mutate_a_typed_draft_without_a_tool() -> None:
    agent, _ = _agent([ManagerModelTurn(content="Balanced is a sensible default.")])
    working = ManagerWorkingMemory(
        current_topic="Discovery model objective",
        open_question="How strongly should popularity influence ranking?",
        objective=DiscoveryObjectiveDraft(
            surface="search",
            retrieval_mode="semantic",
            ranking_signals=["relevance", "popularity"],
            status="needs_clarification",
            missing_fields=["popularity_strength"],
        ),
    )

    result = await agent.respond(
        content="balanced",
        working=working,
        memories=[],
        recent_messages=[],
    )

    objective = result.working_memory.objective
    assert objective is not None
    assert objective == working.objective
    assert objective.popularity_strength is None
    assert not any(step.title == "Reconcile typed objective" for step in result.steps)


async def test_model_can_call_typed_draft_tool_then_observe_and_respond() -> None:
    call = ManagerToolCall(
        call_id="call-draft",
        name="draft_discovery_objective",
        arguments={
            "surface": "search",
            "retrieval_mode": "semantic",
            "ranking_signals": ["relevance", "popularity", "quality"],
            "popularity_strength": "balanced",
            "recommendation_strategy": None,
            "minimum_relevance": 0.5,
        },
    )
    agent, provider = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason="tool_call"),
            ManagerModelTurn(
                content=(
                    "How strongly should popularity influence ranking: light, balanced, or strong?"
                )
            ),
        ]
    )

    result = await agent.respond(
        content="Enable semantic search and rank products by popularity",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
    )

    objective = result.working_memory.objective
    assert objective is not None
    assert objective.surface == "search"
    assert objective.ranking_signals == ["relevance", "popularity"]
    assert objective.status == "needs_clarification"
    assert objective.popularity_strength is None
    assert objective.missing_fields == ["popularity_strength"]
    assert provider.session.results[1][0].output["simulated"] is True
    assert any(step.tool == "draft_discovery_objective" for step in result.steps)


async def test_model_receives_bounded_catalog_index_status() -> None:
    call = ManagerToolCall(call_id="inspect-data", name="inspect_data_onboarding", arguments={})
    agent, provider = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason="tool_call"),
            ManagerModelTurn(content="Your 42-product catalog index is ready."),
        ]
    )

    await agent.respond(
        content="Is indexing done?",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        catalog_index=CatalogIndexStatus(
            status="ready",
            filename="products.csv",
            product_count=42,
            indexed_product_count=42,
        ),
    )

    tool_output = provider.session.results[1][0].output["catalog_index"]
    assert isinstance(tool_output, dict)
    assert tool_output["status"] == "ready"
    assert tool_output["indexed_product_count"] == 42
    assert "'product_count': 42" in provider.instructions


async def test_unknown_tool_is_rejected_and_returned_to_model() -> None:
    call = ManagerToolCall(call_id="bad-call", name="delete_catalog", arguments={})
    agent, provider = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason="tool_call"),
            ManagerModelTurn(content="I can't perform catalog writes from this workspace."),
        ]
    )

    result = await agent.respond(
        content="Delete the catalog",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
    )

    tool_result = provider.session.results[1][0]
    assert tool_result.is_error is True
    assert tool_result.output == {"ok": False, "error": "UNKNOWN_TOOL"}
    assert result.working_memory.objective is None


async def test_iteration_limit_stops_without_claiming_execution() -> None:
    call = ManagerToolCall(
        call_id="inspect",
        name="inspect_discovery_capabilities",
        arguments={},
    )
    agent, _ = _agent(
        [ManagerModelTurn(tool_calls=[call], stop_reason="tool_call")],
        max_iterations=1,
    )

    result = await agent.respond(
        content="Inspect search",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
    )

    assert "iteration limit" in result.content
    assert result.steps[-1].title == "Stop bounded run"


async def test_cloud_context_redacts_direct_contact_data_and_credentials() -> None:
    agent, provider = _agent([ManagerModelTurn(content="I can help with the safe parts.")])
    credential = "sk-" + "test_abcdefghijklmnopqrstuvwxyz"
    now = datetime.now(UTC)
    prior = ManagerMessage(
        id=uuid4(),
        tenant_id=UUID(int=1),
        thread_id=uuid4(),
        role="user",
        content="Email me at manager@example.com",
        created_at=now,
    )
    memory = ManagerMemory(
        id=uuid4(),
        tenant_id=UUID(int=1),
        layer="long_term",
        title="Contact",
        content="Call 212-555-0199 or visit 123 Market Street,",
        source="explicit_manager",
        created_at=now,
    )

    await agent.respond(
        content=f"api_key={credential}",
        working=ManagerWorkingMemory(),
        memories=[memory],
        recent_messages=[prior],
    )

    serialized = " ".join(item.content for item in provider.messages) + provider.instructions
    assert "manager@example.com" not in serialized
    assert "212-555-0199" not in serialized
    assert "123 Market Street" not in serialized
    assert credential not in serialized
    assert "[redacted" in serialized


async def test_model_can_draft_grounded_snowflake_onboarding_without_connecting() -> None:
    call = ManagerToolCall(
        call_id="data-draft",
        name="draft_data_onboarding",
        arguments={
            "dataset_kind": "catalog",
            "source_kind": "snowflake",
            "engagement_decision": None,
            "account_identifier": "acme-org",
            "warehouse": "INGEST_WH",
            "database": "COMMERCE",
            "schema_name": "PUBLIC",
            "relation": "PRODUCTS",
            "role": "OCA_READER",
            "object_uri": None,
            "mapping_document_name": None,
            "cadence": "hourly",
            "incremental_mode": "watermark",
            "watermark_column": "updated_at",
        },
    )
    agent, provider = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason="tool_call"),
            ManagerModelTurn(
                content="Would you like to provide optional pseudonymous engagement events?"
            ),
        ]
    )

    result = await agent.respond(
        content=(
            "My catalog is in Snowflake account acme-org, warehouse INGEST_WH, database "
            "COMMERCE, schema PUBLIC, table PRODUCTS, role OCA_READER. Refresh hourly using "
            "updated_at as the incremental watermark."
        ),
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        onboarding=ManagerDataOnboarding(tenant_id=UUID(int=1)),
    )

    assert result.onboarding is not None
    assert result.onboarding.catalog is not None
    assert result.onboarding.catalog.relation == "PRODUCTS"
    assert result.onboarding.cadence == "hourly"
    assert result.onboarding.incremental_mode == "watermark"
    assert result.onboarding.scheduled_loads_active is False
    assert result.onboarding.status == "needs_engagement_decision"
    assert provider.session.results[1][0].output["simulated"] is True


async def test_model_cannot_invent_warehouse_identifiers() -> None:
    call = ManagerToolCall(
        call_id="invented-data",
        name="draft_data_onboarding",
        arguments={
            "dataset_kind": "catalog",
            "source_kind": "snowflake",
            "engagement_decision": None,
            "account_identifier": "invented-account",
            "warehouse": "INVENTED_WH",
            "database": "INVENTED_DB",
            "schema_name": "PUBLIC",
            "relation": "PRODUCTS",
            "role": "INVENTED_ROLE",
            "object_uri": None,
            "mapping_document_name": None,
            "cadence": None,
            "incremental_mode": None,
            "watermark_column": None,
        },
    )
    agent, _ = _agent(
        [
            ManagerModelTurn(tool_calls=[call], stop_reason="tool_call"),
            ManagerModelTurn(content="What Snowflake identifiers should I use?"),
        ]
    )

    result = await agent.respond(
        content="The catalog is in Snowflake.",
        working=ManagerWorkingMemory(),
        memories=[],
        recent_messages=[],
        onboarding=ManagerDataOnboarding(tenant_id=UUID(int=1)),
    )

    assert result.onboarding is not None
    assert result.onboarding.catalog is not None
    assert result.onboarding.catalog.account_identifier is None
    assert result.onboarding.catalog.relation is None
    assert result.onboarding.status == "needs_catalog"
