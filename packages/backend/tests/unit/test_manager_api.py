"""Manager-agent API route and local role contract tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from open_commerce.api.main import create_app
from open_commerce.config import Settings
from open_commerce.controller.service import ControllerService
from open_commerce.manager_agent.data_onboarding import attach_profile, profile_csv
from open_commerce.manager_agent.models import (
    ManagerAgentCapabilities,
    ManagerAgentReply,
    ManagerChannelClearResponse,
    ManagerDataOnboarding,
    ManagerDatasetProfileReply,
    ManagerDatasetProfileRequest,
    ManagerMemoryDeleteResponse,
    ManagerMemoryListResponse,
    ManagerMessage,
    ManagerMessageRequest,
    ManagerReplyThreadCreateRequest,
    ManagerRuntimeComponent,
    ManagerRuntimeStatus,
    ManagerThread,
    ManagerThreadCreateRequest,
    ManagerThreadDetail,
    ManagerThreadListResponse,
    ManagerThreadUpdateRequest,
    ManagerWorkingMemory,
    ManagerWorkspaceResetRequest,
    ManagerWorkspaceResetResponse,
    ManagerWorkspaceResponse,
    MemoryLayer,
)
from open_commerce.search.service import SearchService
from open_commerce.simulator.service import SimulatorService


class FakeManagerAgent:
    def __init__(self, tenant_id: UUID) -> None:
        now = datetime.now(UTC)
        self.thread = ManagerThread(
            id=uuid4(),
            tenant_id=tenant_id,
            title="Discovery strategy",
            working_memory=ManagerWorkingMemory(),
            created_at=now,
            updated_at=now,
        )
        self.capabilities = ManagerAgentCapabilities(
            semantic_backend="test", learned_semantics=True
        )
        self.onboarding = ManagerDataOnboarding(tenant_id=tenant_id)
        self.messages = [
            ManagerMessage(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=self.thread.id,
                role="assistant",
                content="What should we improve first?",
                created_at=now,
            )
        ]
        self.reply_thread = ManagerThread(
            id=uuid4(),
            tenant_id=tenant_id,
            title="Thread: What should we improve first?",
            thread_type="reply",
            channel_kind=None,
            slug=None,
            parent_thread_id=self.thread.id,
            root_message_id=self.messages[0].id,
            working_memory=ManagerWorkingMemory(),
            created_at=now,
            updated_at=now,
        )

    async def bootstrap_workspace(
        self, *, tenant_id: UUID, idempotency_key: str
    ) -> ManagerWorkspaceResponse:
        assert tenant_id == self.thread.tenant_id and idempotency_key
        return await self.get_workspace(tenant_id=tenant_id)

    async def get_workspace(self, *, tenant_id: UUID) -> ManagerWorkspaceResponse:
        assert tenant_id == self.thread.tenant_id
        return ManagerWorkspaceResponse(
            channels=[self.thread],
            onboarding=self.onboarding,
            capabilities=self.capabilities,
        )

    async def reset_workspace(
        self,
        *,
        tenant_id: UUID,
        request: ManagerWorkspaceResetRequest,
        idempotency_key: str,
    ) -> ManagerWorkspaceResetResponse:
        assert tenant_id == self.thread.tenant_id
        assert request.confirmation == "RESET" and idempotency_key
        return ManagerWorkspaceResetResponse(
            workspace=await self.get_workspace(tenant_id=tenant_id),
            deleted_channel_count=1,
            deleted_message_count=len(self.messages),
            deleted_memory_count=0,
        )

    async def get_runtime_status(self, *, tenant_id: UUID) -> ManagerRuntimeStatus:
        assert tenant_id == self.thread.tenant_id
        return ManagerRuntimeStatus(
            generated_at=datetime.now(UTC),
            components=[
                ManagerRuntimeComponent(key="api", label="API", state="green", detail="Responding")
            ],
        )

    async def create_thread(
        self,
        *,
        tenant_id: UUID,
        request: ManagerThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        assert tenant_id == self.thread.tenant_id
        assert idempotency_key
        self.thread.title = request.title
        return await self.get_thread(tenant_id=tenant_id, thread_id=self.thread.id)

    async def list_threads(self, *, tenant_id: UUID) -> ManagerThreadListResponse:
        assert tenant_id == self.thread.tenant_id
        return ManagerThreadListResponse(items=[self.thread])

    async def update_thread(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerThreadUpdateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        assert tenant_id == self.thread.tenant_id and thread_id == self.thread.id
        assert idempotency_key
        self.thread.title = request.title or self.thread.title
        self.thread.status = request.status or self.thread.status
        return await self.get_thread(tenant_id=tenant_id, thread_id=thread_id)

    async def clear_channel_history(
        self, *, tenant_id: UUID, thread_id: UUID, idempotency_key: str
    ) -> ManagerChannelClearResponse:
        assert tenant_id == self.thread.tenant_id and thread_id == self.thread.id
        assert idempotency_key
        deleted = len(self.messages)
        self.messages = [
            ManagerMessage(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="assistant",
                content="History cleared. Agent ready.",
                created_at=datetime.now(UTC),
            )
        ]
        return ManagerChannelClearResponse(
            detail=await self.get_thread(tenant_id=tenant_id, thread_id=thread_id),
            deleted_message_count=deleted,
            deleted_reply_thread_count=1,
        )

    async def create_reply_thread(
        self,
        *,
        tenant_id: UUID,
        channel_id: UUID,
        request: ManagerReplyThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail:
        assert tenant_id == self.thread.tenant_id and channel_id == self.thread.id
        assert request.root_message_id == self.messages[0].id and idempotency_key
        return await self.get_thread(tenant_id=tenant_id, thread_id=self.reply_thread.id)

    async def get_reply_thread(
        self, *, tenant_id: UUID, channel_id: UUID, root_message_id: UUID
    ) -> ManagerThreadDetail:
        assert tenant_id == self.thread.tenant_id and channel_id == self.thread.id
        assert root_message_id == self.messages[0].id
        return await self.get_thread(tenant_id=tenant_id, thread_id=self.reply_thread.id)

    async def get_thread(self, *, tenant_id: UUID, thread_id: UUID) -> ManagerThreadDetail:
        assert tenant_id == self.thread.tenant_id
        if thread_id == self.reply_thread.id:
            return ManagerThreadDetail(
                thread=self.reply_thread,
                messages=[],
                memories=[],
                capabilities=self.capabilities,
                onboarding=self.onboarding,
                root_message=self.messages[0],
            )
        assert thread_id == self.thread.id
        return ManagerThreadDetail(
            thread=self.thread,
            messages=self.messages,
            memories=[],
            capabilities=self.capabilities,
            onboarding=self.onboarding,
        )

    async def send_message(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
    ) -> ManagerAgentReply:
        assert tenant_id == self.thread.tenant_id and thread_id == self.thread.id
        assert idempotency_key
        now = datetime.now(UTC)
        user = ManagerMessage(
            id=uuid4(),
            tenant_id=tenant_id,
            thread_id=thread_id,
            role="user",
            content=request.content,
            created_at=now,
        )
        assistant = ManagerMessage(
            id=uuid4(),
            tenant_id=tenant_id,
            thread_id=thread_id,
            role="assistant",
            content="How strong: light, balanced, or strong?",
            created_at=now,
        )
        return ManagerAgentReply(
            thread=self.thread,
            user_message=user,
            assistant_message=assistant,
            memories=[],
            capabilities=self.capabilities,
            onboarding=self.onboarding,
        )

    async def profile_dataset(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerDatasetProfileRequest,
        idempotency_key: str,
    ) -> ManagerDatasetProfileReply:
        assert tenant_id == self.thread.tenant_id and thread_id == self.thread.id
        assert idempotency_key
        profile = profile_csv(
            dataset_kind=request.dataset_kind,
            filename=request.filename,
            csv_text=request.csv_text,
        )
        self.onboarding = attach_profile(self.onboarding, profile)
        now = datetime.now(UTC)
        return ManagerDatasetProfileReply(
            thread=self.thread,
            user_message=ManagerMessage(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="user",
                content=f"Attached {request.dataset_kind} CSV: {request.filename}",
                created_at=now,
            ),
            assistant_message=ManagerMessage(
                id=uuid4(),
                tenant_id=tenant_id,
                thread_id=thread_id,
                role="assistant",
                content="Catalog profile recorded.",
                created_at=now,
            ),
            memories=[],
            capabilities=self.capabilities,
            onboarding=self.onboarding,
            profile=profile,
        )

    async def list_memories(
        self, *, tenant_id: UUID, layer: MemoryLayer | None = None
    ) -> ManagerMemoryListResponse:
        assert tenant_id == self.thread.tenant_id
        _ = layer
        return ManagerMemoryListResponse(items=[])

    async def delete_memory(
        self, *, tenant_id: UUID, memory_id: UUID, idempotency_key: str
    ) -> ManagerMemoryDeleteResponse:
        assert tenant_id == self.thread.tenant_id and idempotency_key
        return ManagerMemoryDeleteResponse(memory_id=memory_id, deleted=True)


async def test_manager_conversation_routes_use_typed_service_and_idempotency() -> None:
    settings = Settings(environment="test")
    simulator = SimulatorService()
    manager = FakeManagerAgent(settings.local_tenant_id)
    app = create_app(
        settings=settings,
        simulator_service=simulator,
        search_service=SearchService(),
        controller_service=ControllerService(simulator_service=simulator),
        manager_agent_service=manager,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bootstrapped = await client.post(
            "/v1/manager/workspace/bootstrap",
            headers={"Idempotency-Key": "manager-workspace"},
        )
        workspace = await client.get("/v1/manager/workspace")
        runtime_status = await client.get("/v1/manager/status")
        listed = await client.get("/v1/manager/threads")
        updated = await client.patch(
            f"/v1/manager/threads/{manager.thread.id}",
            headers={"Idempotency-Key": "manager-update"},
            json={"title": "Search planning"},
        )
        reply = await client.post(
            f"/v1/manager/threads/{manager.thread.id}/replies",
            headers={"Idempotency-Key": "manager-reply"},
            json={"root_message_id": str(manager.messages[0].id)},
        )
        reply_history = await client.get(
            f"/v1/manager/threads/{manager.thread.id}/messages/{manager.messages[0].id}/replies"
        )
        replied = await client.post(
            f"/v1/manager/threads/{manager.thread.id}/messages",
            headers={"Idempotency-Key": "manager-turn"},
            json={"content": "Enable semantic search"},
        )
        profiled = await client.post(
            f"/v1/manager/threads/{manager.thread.id}/datasets/profile",
            headers={"Idempotency-Key": "manager-profile"},
            json={
                "dataset_kind": "catalog",
                "filename": "catalog.csv",
                "csv_text": "product_id,title\np-1,Trail Boot\n",
            },
        )
        cleared = await client.delete(
            f"/v1/manager/threads/{manager.thread.id}/messages",
            headers={"Idempotency-Key": "manager-clear"},
        )
        reset = await client.post(
            "/v1/manager/workspace/reset",
            headers={"Idempotency-Key": "manager-reset"},
            json={"confirmation": "RESET"},
        )
        invalid_reset = await client.post(
            "/v1/manager/workspace/reset",
            headers={"Idempotency-Key": "manager-reset-invalid"},
            json={"confirmation": "yes"},
        )

    assert bootstrapped.status_code == 200
    assert workspace.status_code == 200
    assert runtime_status.status_code == 200
    assert runtime_status.json()["components"][0]["state"] == "green"
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == str(manager.thread.id)
    assert updated.status_code == 200
    assert updated.json()["thread"]["title"] == "Search planning"
    assert reply.status_code == 200
    assert reply.json()["thread"]["thread_type"] == "reply"
    assert reply_history.status_code == 200
    assert reply_history.json()["root_message"]["id"] == str(manager.reply_thread.root_message_id)
    assert replied.status_code == 200
    assert replied.json()["assistant_message"]["content"].startswith("How strong")
    assert profiled.status_code == 200
    assert profiled.json()["profile"]["row_count"] == 1
    assert profiled.json()["onboarding"]["status"] == "needs_engagement_decision"
    assert cleared.status_code == 200
    assert cleared.json()["deleted_message_count"] == 1
    assert cleared.json()["deleted_reply_thread_count"] == 1
    assert reset.status_code == 200
    assert reset.json()["deleted_channel_count"] == 1
    assert invalid_reset.status_code == 422
