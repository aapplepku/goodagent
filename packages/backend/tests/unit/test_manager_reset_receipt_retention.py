"""Reset receipts survive cleanup without retaining erased conversational payloads."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.types import canonical_hash
from open_commerce.manager_agent import service as manager_service
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerDataOnboarding,
    ManagerThread,
    ManagerWorkspaceResetRequest,
    ManagerWorkspaceResetResponse,
    ManagerWorkspaceResponse,
)
from open_commerce.manager_agent.workspace_onboarding import start_interview
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.manager_agent import ManagerAgentRepository
from open_commerce.persistence.repositories.requests import IdempotencyConflictError
from open_commerce.persistence.runtime_db import RuntimeDatabase

TENANT = UUID(int=13501)
THREAD = UUID(int=13502)
NOW = datetime(2026, 10, 18, tzinfo=UTC)
SCOPE = "manager:workspace:reset"
REQUEST = ManagerWorkspaceResetRequest(confirmation="RESET")
CAPABILITIES = ManagerAgentCapabilities(semantic_backend="synthetic", learned_semantics=False)


def reset_response() -> ManagerWorkspaceResetResponse:
    return ManagerWorkspaceResetResponse(
        workspace=ManagerWorkspaceResponse(
            channels=[],
            onboarding=ManagerDataOnboarding(tenant_id=TENANT),
            capabilities=CAPABILITIES,
        ),
        deleted_channel_count=2,
        deleted_message_count=4,
        deleted_memory_count=3,
    )


@pytest.fixture
def session() -> MagicMock:
    return cast(MagicMock, create_autospec(AsyncSession, instance=True))


@pytest.fixture
def service(session: MagicMock) -> manager_service.DurableManagerAgentService:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    instance = object.__new__(manager_service.DurableManagerAgentService)
    instance.database = database
    instance.capabilities = CAPABILITIES
    return instance


async def test_cleanup_excludes_only_exact_reset_scope_under_tenant_predicate(
    session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    cancel_runs = AsyncMock()
    monkeypatch.setattr("open_commerce.manager_agent.runs.cancel_thread_runs", cancel_runs)
    session.scalar.side_effect = [2, 4, 3]

    counts = await ManagerAgentRepository(session, TENANT).reset_workspace()

    assert counts == (2, 4, 3)
    cancel_runs.assert_awaited_once_with(session, TENANT)
    statements = [call.args[0].compile() for call in session.execute.call_args_list]
    assert len(statements) == 5
    receipt_delete = statements[-1]
    assert receipt_delete.params == {
        "tenant_id_1": TENANT,
        "scope_1": "manager:%",
        "scope_2": SCOPE,
    }
    assert str(receipt_delete) == (
        "DELETE FROM idempotency_records WHERE idempotency_records.tenant_id = :tenant_id_1 "
        "AND idempotency_records.scope LIKE :scope_1 AND idempotency_records.scope != :scope_2"
    )
    for table, statement in zip(
        ("manager_memories", "manager_messages", "manager_threads", "manager_data_onboarding"),
        statements[:-1],
        strict=True,
    ):
        assert str(statement).startswith(f"DELETE FROM {table} WHERE")
        assert statement.params == {"tenant_id_1": TENANT}
    session.flush.assert_awaited_once()


async def test_cleanup_failure_propagates_without_flush(
    session: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("open_commerce.manager_agent.runs.cancel_thread_runs", AsyncMock())
    session.scalar.return_value = 0
    session.execute.side_effect = [None, None, None, None, RuntimeError("synthetic delete error")]

    with pytest.raises(RuntimeError, match="synthetic delete error"):
        await ManagerAgentRepository(session, TENANT).reset_workspace()

    session.flush.assert_not_called()


@pytest.mark.parametrize("key", ["first-reset", "second-reset"])
async def test_retained_reset_receipt_replay_never_enters_mutation_repository(
    service: manager_service.DurableManagerAgentService,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
) -> None:
    response = reset_response()
    session.scalar.return_value = IdempotencyRecord(
        tenant_id=TENANT,
        scope=SCOPE,
        key=key,
        fingerprint=canonical_hash(REQUEST),
        response=response.model_dump(mode="json"),
    )
    factory = MagicMock(side_effect=AssertionError("Replay must not enter reset mutation"))
    monkeypatch.setattr(manager_service, "ManagerAgentRepository", factory)

    for _ in range(2):
        replay = await service.reset_workspace(
            tenant_id=TENANT, request=REQUEST, idempotency_key=key
        )
        assert replay == response

    factory.assert_not_called()
    session.execute.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    database = cast(MagicMock, service.database)
    assert database.transaction.call_count == 2
    database.transaction.assert_called_with(TENANT, write=True)
    query = session.scalar.call_args.args[0].compile()
    assert query.params == {"tenant_id_1": TENANT, "scope_1": SCOPE, "key_1": key}


async def test_retained_receipt_keeps_request_fingerprint_conflict_check(
    service: manager_service.DurableManagerAgentService,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.scalar.return_value = IdempotencyRecord(
        tenant_id=TENANT,
        scope=SCOPE,
        key="conflict",
        fingerprint=canonical_hash({"confirmation": "different input"}),
        response=reset_response().model_dump(mode="json"),
    )
    factory = MagicMock()
    monkeypatch.setattr(manager_service, "ManagerAgentRepository", factory)

    with pytest.raises(IdempotencyConflictError):
        await service.reset_workspace(tenant_id=TENANT, request=REQUEST, idempotency_key="conflict")

    factory.assert_not_called()
    session.execute.assert_not_called()
    session.add.assert_not_called()


async def test_new_reset_receipt_contains_fresh_defaults_and_retained_catalog_only(
    service: manager_service.DurableManagerAgentService,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.scalar.return_value = None
    repo = create_autospec(ManagerAgentRepository, instance=True)
    repo.reset_workspace.return_value = (2, 4, 3)
    repo.get_channel_by_slug.return_value = None
    repo.get_onboarding.side_effect = AssertionError("Old onboarding must not be read")
    thread = ManagerThread(
        id=THREAD,
        tenant_id=TENANT,
        title="Onboarding",
        slug="onboarding",
        channel_kind="onboarding",
        created_at=NOW,
        updated_at=NOW,
    )
    repo.create_thread.return_value = thread
    repo.list_threads.return_value = [thread]

    async def save_onboarding(
        value: ManagerDataOnboarding, *, now: datetime
    ) -> ManagerDataOnboarding:
        assert now == NOW
        return value

    repo.save_onboarding.side_effect = save_onboarding
    monkeypatch.setattr(manager_service, "ManagerAgentRepository", MagicMock(return_value=repo))
    monkeypatch.setattr(manager_service, "utc_now", lambda: NOW)
    catalog = CatalogIndexStatus(filename="retained-catalog.csv", product_count=7)
    index_status = AsyncMock(return_value=catalog)
    monkeypatch.setattr(manager_service, "catalog_index_status", index_status)

    response = await service.reset_workspace(
        tenant_id=TENANT, request=REQUEST, idempotency_key="fresh"
    )

    repo.reset_workspace.assert_awaited_once()
    repo.create_thread.assert_awaited_once()
    assert repo.create_thread.call_args.kwargs["title"] == "Onboarding"
    assert repo.create_thread.call_args.kwargs["channel_kind"] == "onboarding"
    assert repo.create_thread.call_args.kwargs["slug"] == "onboarding"
    defaults = start_interview(ManagerDataOnboarding(tenant_id=TENANT))
    assert response.workspace.onboarding.workspace_profile == defaults.workspace_profile
    assert response.workspace.onboarding.workspace_status == "in_progress"
    assert response.workspace.onboarding.catalog is None
    assert response.workspace.onboarding.engagement is None
    assert response.workspace.onboarding.completed_fields == []
    assert response.workspace.channels[0].working_memory.model_dump() == {
        "current_topic": None,
        "open_question": None,
        "objective": None,
        "recent_decisions": [],
    }
    assert response.workspace.catalog_index == catalog
    index_status.assert_awaited_once_with(session, tenant_id=TENANT)
    record = session.add.call_args.args[0]
    assert isinstance(record, IdempotencyRecord)
    assert record.scope == SCOPE
    assert record.tenant_id == TENANT
    assert record.response == response.model_dump(mode="json")
    workspace = record.response["workspace"]
    assert isinstance(workspace, dict)
    assert "messages" not in workspace
    assert "memories" not in workspace
    assert record.response["deleted_message_count"] == 4
    assert record.response["deleted_memory_count"] == 3
