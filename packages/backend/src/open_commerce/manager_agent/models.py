"""Typed contracts for the commerce-manager conversation and memory layers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.core.types import StrictDomainModel, ensure_utc
from open_commerce.manager_agent.runs_models import ManagerRun

ManagerThreadStatus = Literal["active", "archived"]
ManagerThreadType = Literal["channel", "reply"]
ManagerChannelKind = Literal[
    "onboarding", "status", "search", "recommendations", "buy_again", "custom"
]
StarterAgent = Literal["general", "status", "search", "recommendations", "buy_again", "analysis"]
ManagerMessageRole = Literal["user", "assistant"]
MemoryLayer = Literal["long_term", "working", "periodic"]
MemorySource = Literal["explicit_manager", "working_state", "periodic_summary"]
AgentStepStage = Literal["recall", "understand", "act", "observe", "respond"]
AgentStepStatus = Literal["completed", "simulated", "needs_input", "failed"]
DatasetKind = Literal["catalog", "engagement"]
DataSourceKind = Literal["csv_upload", "snowflake", "object_storage"]
EngagementDecision = Literal["pending", "provide", "skip"]
LoadCadence = Literal["manual", "hourly", "six_hourly", "daily", "weekly"]
IncrementalMode = Literal["full_refresh", "watermark"]
OnboardingStatus = Literal[
    "needs_catalog",
    "needs_engagement_decision",
    "needs_schedule",
    "ready_for_review",
]
WorkspaceOnboardingStatus = Literal["not_started", "in_progress", "review", "completed"]
OnboardingInputKind = Literal["text", "single_select", "multi_select", "dataset", "review"]
OnboardingField = Literal[
    "workspace_name",
    "business_summary",
    "manager_role",
    "primary_goal",
    "starter_agents",
    "priority_surfaces",
    "search_baseline",
    "recommendation_surfaces",
    "buy_again_strategy",
    "catalog_decision",
    "engagement_decision",
    "cadence",
    "success_metrics",
    "guardrails",
    "operating_mode",
    "response_style",
    "review",
]
DiscoverySurface = Literal["search", "recommendations", "both"]
RetrievalMode = Literal["lexical", "semantic", "hybrid"]
RankingSignal = Literal["relevance", "popularity", "quality"]
PopularityStrength = Literal["light", "balanced", "strong"]
ObjectiveStatus = Literal["collecting", "needs_clarification", "ready_for_review"]
RuntimeComponentState = Literal["green", "yellow", "red", "unknown"]


def _default_surfaces() -> list[DiscoverySurface]:
    return ["search", "recommendations", "both"]


def _default_signals() -> list[RankingSignal]:
    return ["relevance", "popularity", "quality"]


class AgentStep(StrictDomainModel):
    """A safe stage summary, never hidden model chain-of-thought."""

    stage: AgentStepStage
    title: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=500)
    status: AgentStepStatus = "completed"
    tool: str | None = Field(default=None, max_length=100)


class DiscoveryObjectiveDraft(StrictDomainModel):
    """Finite discovery-model objective assembled across conversation turns."""

    surface: DiscoverySurface | None = None
    retrieval_mode: RetrievalMode | None = None
    ranking_signals: list[RankingSignal] = Field(default_factory=list, max_length=3)
    popularity_strength: PopularityStrength | None = None
    recommendation_strategy: Literal["similar", "popular", "complements"] | None = None
    minimum_relevance: Decimal = Field(default=Decimal("0.45"), ge=0, le=1)
    status: ObjectiveStatus = "collecting"
    missing_fields: list[str] = Field(default_factory=list, max_length=5)
    review_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("ranking_signals")
    @classmethod
    def unique_signals(cls, value: list[RankingSignal]) -> list[RankingSignal]:
        return list(dict.fromkeys(value))


class ManagerWorkingMemory(StrictDomainModel):
    """Bounded, replaceable context for one active conversation."""

    current_topic: str | None = Field(default=None, max_length=200)
    open_question: str | None = Field(default=None, max_length=500)
    objective: DiscoveryObjectiveDraft | None = None
    recent_decisions: list[str] = Field(default_factory=list, max_length=8)


class DatasetProfile(StrictDomainModel):
    """Safe structural facts retained after transient CSV validation."""

    dataset_kind: DatasetKind
    filename: str = Field(min_length=1, max_length=255)
    content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(gt=0, le=20_971_520)
    row_count: int = Field(gt=0, le=10_000)
    columns: list[str] = Field(min_length=1, max_length=64)
    detected_mappings: dict[str, str] = Field(default_factory=dict, max_length=24)
    missing_required: list[str] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=12)
    profiled_at: datetime

    @field_validator("profiled_at")
    @classmethod
    def normalize_profiled_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class DataSourceDraft(StrictDomainModel):
    """Non-secret source configuration collected during onboarding."""

    dataset_kind: DatasetKind
    source_kind: DataSourceKind
    display_name: str | None = Field(default=None, max_length=120)
    account_identifier: str | None = Field(default=None, max_length=160)
    warehouse: str | None = Field(default=None, max_length=160)
    database: str | None = Field(default=None, max_length=160)
    schema_name: str | None = Field(default=None, max_length=160)
    relation: str | None = Field(default=None, max_length=240)
    role: str | None = Field(default=None, max_length=160)
    object_uri: str | None = Field(default=None, max_length=500)
    mapping_document_name: str | None = Field(default=None, max_length=255)
    profile: DatasetProfile | None = None
    credential_status: Literal["not_configured"] = "not_configured"
    connection_test_status: Literal["not_run"] = "not_run"


class OnboardingChoice(StrictDomainModel):
    value: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=240)


class OnboardingPrompt(StrictDomainModel):
    field: OnboardingField
    section: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=500)
    intro: str | None = Field(default=None, max_length=500)
    input_kind: OnboardingInputKind
    choices: list[OnboardingChoice] = Field(default_factory=list, max_length=8)
    required: bool = True
    ordinal: int = Field(ge=1, le=16)
    total: int = Field(default=8, ge=1, le=16)


class ManagerWorkspaceProfile(StrictDomainModel):
    """Bounded, non-secret context collected during the first-run interview."""

    workspace_name: str | None = Field(default=None, max_length=120)
    business_summary: str | None = Field(default=None, max_length=500)
    manager_role: Literal["merchandising", "search", "growth", "operations", "mixed"] | None = None
    primary_goal: str | None = Field(default=None, max_length=500)
    starter_agents: list[StarterAgent] = Field(default_factory=list, max_length=6)
    priority_surfaces: list[
        Literal["search", "pdp_recommendations", "home_recommendations", "cart", "buy_again"]
    ] = Field(default_factory=list, max_length=5)
    search_baseline: Literal["none", "keyword", "semantic", "hybrid", "unknown"] | None = None
    recommendation_surfaces: list[
        Literal["none", "pdp", "home", "cart", "post_purchase", "email"]
    ] = Field(default_factory=list, max_length=6)
    buy_again_strategy: Literal["important", "later", "not_applicable", "unknown"] | None = None
    success_metrics: list[
        Literal[
            "conversion",
            "revenue_per_session",
            "search_success",
            "recommendation_ctr",
            "repeat_purchase",
            "margin",
        ]
    ] = Field(default_factory=list, max_length=6)
    guardrails: list[
        Literal["relevance", "availability", "margin", "brand", "diversity", "privacy"]
    ] = Field(default_factory=list, max_length=6)
    operating_mode: Literal["draft_only", "approval_required"] | None = None
    response_style: Literal["concise", "balanced", "detailed"] | None = None


class ManagerDataOnboarding(StrictDomainModel):
    """Tenant-level data intake draft shared by every manager conversation."""

    tenant_id: UUID
    catalog: DataSourceDraft | None = None
    engagement: DataSourceDraft | None = None
    engagement_decision: EngagementDecision = "pending"
    cadence: LoadCadence | None = None
    incremental_mode: IncrementalMode | None = None
    watermark_column: str | None = Field(default=None, max_length=160)
    timezone: Literal["UTC"] = "UTC"
    status: OnboardingStatus = "needs_catalog"
    scheduled_loads_active: Literal[False] = False
    workspace_status: WorkspaceOnboardingStatus = "not_started"
    current_prompt: OnboardingPrompt | None = None
    completed_fields: list[OnboardingField] = Field(default_factory=list, max_length=16)
    workspace_profile: ManagerWorkspaceProfile = Field(default_factory=ManagerWorkspaceProfile)
    catalog_decision: Literal["pending", "provide", "defer"] = "pending"
    limited_mode: bool = False
    status_refresh_minutes: int = Field(default=5, ge=0, le=60)
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("completed_at", "created_at", "updated_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class ManagerThread(StrictDomainModel):
    id: UUID
    tenant_id: UUID
    title: str = Field(min_length=1, max_length=120)
    status: ManagerThreadStatus = "active"
    thread_type: ManagerThreadType = "channel"
    channel_kind: ManagerChannelKind | None = "custom"
    slug: str | None = Field(default=None, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = Field(default=None, max_length=240)
    position: int = Field(default=100, ge=0)
    parent_thread_id: UUID | None = None
    root_message_id: UUID | None = None
    working_memory: ManagerWorkingMemory = Field(default_factory=ManagerWorkingMemory)
    user_turn_count: int = Field(default=0, ge=0)
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ManagerMessage(StrictDomainModel):
    id: UUID
    tenant_id: UUID
    thread_id: UUID
    role: ManagerMessageRole
    content: str = Field(min_length=1, max_length=4000)
    steps: list[AgentStep] = Field(default_factory=list, max_length=12)
    reply_count: int = Field(default=0, ge=0)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ManagerMemory(StrictDomainModel):
    id: UUID
    tenant_id: UUID
    thread_id: UUID | None = None
    layer: MemoryLayer
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    source: MemorySource
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime

    @field_validator("period_start", "period_end", "created_at")
    @classmethod
    def normalize_optional_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class ManagerAgentCapabilities(StrictDomainModel):
    semantic_backend: str = Field(min_length=1, max_length=160)
    learned_semantics: bool
    conversation_provider: str = Field(default="deterministic", min_length=1, max_length=50)
    conversation_model: str = Field(
        default="bounded-rule-interpreter", min_length=1, max_length=100
    )
    model_backed: bool = False
    supported_surfaces: list[DiscoverySurface] = Field(default_factory=_default_surfaces)
    supported_ranking_signals: list[RankingSignal] = Field(default_factory=_default_signals)
    complex_tools_simulated: bool = True
    search_testing: bool = True
    service_status: bool = True
    code_context: bool = True


class ManagerRuntimeComponent(StrictDomainModel):
    """One dynamic operational status displayed in the manager workspace."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    state: RuntimeComponentState
    detail: str = Field(min_length=1, max_length=240)
    latency_ms: float | None = Field(default=None, ge=0)
    observed_at: datetime | None = None
    evidence_kind: Literal["probe", "derived", "configuration", "model_call"] = "derived"
    repair_available: bool = False


class ManagerRuntimeStatus(StrictDomainModel):
    """Dynamic service and commerce-surface health for the local workspace."""

    generated_at: datetime
    components: list[ManagerRuntimeComponent] = Field(max_length=16)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ManagerAgentOutcome(StrictDomainModel):
    content: str
    working_memory: ManagerWorkingMemory
    steps: list[AgentStep]
    explicit_preference: str | None = None
    onboarding: ManagerDataOnboarding | None = None


class ManagerThreadCreateRequest(StrictDomainModel):
    title: str = Field(default="Discovery strategy", min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=240)


class ManagerThreadUpdateRequest(StrictDomainModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=240)
    status: ManagerThreadStatus | None = None


class ManagerReplyThreadCreateRequest(StrictDomainModel):
    root_message_id: UUID


class ManagerMessageRequest(StrictDomainModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class ManagerDatasetProfileRequest(StrictDomainModel):
    dataset_kind: DatasetKind
    filename: str = Field(min_length=1, max_length=255)
    csv_text: str = Field(min_length=1, max_length=524_288)
    catalog_currency: Literal["USD", "EUR", "GBP", "CAD", "AUD"] | None = None

    @field_validator("filename")
    @classmethod
    def clean_filename(cls, value: str) -> str:
        cleaned = value.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
        if not cleaned.lower().endswith(".csv"):
            raise ValueError("filename must end in .csv")
        return cleaned


class ManagerThreadListResponse(StrictDomainModel):
    items: list[ManagerThread]


class ManagerMemoryListResponse(StrictDomainModel):
    items: list[ManagerMemory]


class ManagerThreadDetail(StrictDomainModel):
    thread: ManagerThread
    messages: list[ManagerMessage]
    memories: list[ManagerMemory]
    capabilities: ManagerAgentCapabilities
    onboarding: ManagerDataOnboarding
    root_message: ManagerMessage | None = None
    active_run: ManagerRun | None = None


class ManagerChannelClearResponse(StrictDomainModel):
    detail: ManagerThreadDetail
    deleted_message_count: int = Field(ge=0)
    deleted_reply_thread_count: int = Field(ge=0)


class ManagerWorkspaceResponse(StrictDomainModel):
    channels: list[ManagerThread]
    onboarding: ManagerDataOnboarding
    capabilities: ManagerAgentCapabilities
    catalog_index: CatalogIndexStatus = Field(default_factory=CatalogIndexStatus)


class ManagerWorkspaceResetRequest(StrictDomainModel):
    confirmation: Literal["RESET"]


class ManagerWorkspaceResetResponse(StrictDomainModel):
    workspace: ManagerWorkspaceResponse
    deleted_channel_count: int = Field(ge=0)
    deleted_message_count: int = Field(ge=0)
    deleted_memory_count: int = Field(ge=0)


class ManagerAgentReply(StrictDomainModel):
    thread: ManagerThread
    user_message: ManagerMessage
    assistant_message: ManagerMessage
    memories: list[ManagerMemory]
    periodic_memory_created: ManagerMemory | None = None
    capabilities: ManagerAgentCapabilities
    onboarding: ManagerDataOnboarding
    workspace_changed: bool = False


class ManagerDatasetProfileReply(StrictDomainModel):
    thread: ManagerThread
    user_message: ManagerMessage
    assistant_message: ManagerMessage
    memories: list[ManagerMemory]
    capabilities: ManagerAgentCapabilities
    onboarding: ManagerDataOnboarding
    profile: DatasetProfile
    catalog_index: CatalogIndexStatus = Field(default_factory=CatalogIndexStatus)


class ManagerMemoryDeleteResponse(StrictDomainModel):
    memory_id: UUID
    deleted: bool


class ManagerAgentRuntime(Protocol):
    async def bootstrap_workspace(
        self, *, tenant_id: UUID, idempotency_key: str
    ) -> ManagerWorkspaceResponse: ...

    async def get_workspace(self, *, tenant_id: UUID) -> ManagerWorkspaceResponse: ...

    async def reset_workspace(
        self,
        *,
        tenant_id: UUID,
        request: ManagerWorkspaceResetRequest,
        idempotency_key: str,
    ) -> ManagerWorkspaceResetResponse: ...

    async def get_runtime_status(self, *, tenant_id: UUID) -> ManagerRuntimeStatus: ...

    async def create_thread(
        self,
        *,
        tenant_id: UUID,
        request: ManagerThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail: ...

    async def list_threads(self, *, tenant_id: UUID) -> ManagerThreadListResponse: ...

    async def update_thread(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerThreadUpdateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail: ...

    async def clear_channel_history(
        self, *, tenant_id: UUID, thread_id: UUID, idempotency_key: str
    ) -> ManagerChannelClearResponse: ...

    async def create_reply_thread(
        self,
        *,
        tenant_id: UUID,
        channel_id: UUID,
        request: ManagerReplyThreadCreateRequest,
        idempotency_key: str,
    ) -> ManagerThreadDetail: ...

    async def get_reply_thread(
        self, *, tenant_id: UUID, channel_id: UUID, root_message_id: UUID
    ) -> ManagerThreadDetail: ...

    async def get_thread(self, *, tenant_id: UUID, thread_id: UUID) -> ManagerThreadDetail: ...

    async def send_message(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerMessageRequest,
        idempotency_key: str,
    ) -> ManagerAgentReply: ...

    async def profile_dataset(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        request: ManagerDatasetProfileRequest,
        idempotency_key: str,
    ) -> ManagerDatasetProfileReply: ...

    async def list_memories(
        self, *, tenant_id: UUID, layer: MemoryLayer | None = None
    ) -> ManagerMemoryListResponse: ...

    async def delete_memory(
        self, *, tenant_id: UUID, memory_id: UUID, idempotency_key: str
    ) -> ManagerMemoryDeleteResponse: ...
