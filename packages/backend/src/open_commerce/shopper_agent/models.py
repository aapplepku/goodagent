"""Typed public contracts for the shopper account and conversational agent."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, PrivateAttr, SecretStr, field_validator

from open_commerce.catalog.models import CatalogIndexState
from open_commerce.core.types import StrictDomainModel, ensure_utc

ShopperMessageRole = Literal["user", "assistant"]


class ShopperRegisterRequest(StrictDomainModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=80)
    password: SecretStr = Field(min_length=10, max_length=128)


class ShopperLoginRequest(StrictDomainModel):
    username: str = Field(min_length=3, max_length=40)
    password: SecretStr = Field(min_length=1, max_length=128)


class ShopperAccount(StrictDomainModel):
    _data_version: int | None = PrivateAttr(default=None)

    id: UUID
    username: str
    display_name: str
    created_at: datetime
    is_guest: bool = False
    memory_enabled: bool = True
    expires_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ShopperAuthResponse(StrictDomainModel):
    account: ShopperAccount
    recovery_code: str | None = None


class ShopperGuestResponse(ShopperAuthResponse):
    created: bool


class ShopperConversation(StrictDomainModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ShopperProductCard(StrictDomainModel):
    product_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    brand: str | None = Field(default=None, max_length=120)
    category: str = Field(default="", max_length=160)
    price_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    score: str = Field(max_length=80)
    highlights: list[str] = Field(default_factory=list, max_length=3)
    image_url: str | None = Field(default=None, max_length=1000)
    url: str | None = Field(default=None, max_length=1000)


class ShopperAgentStep(StrictDomainModel):
    stage: Literal["understand", "search", "observe", "respond", "remember"]
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=300)
    status: Literal["completed", "fallback", "needs_input"] = "completed"


class ShopperMessage(StrictDomainModel):
    id: UUID
    conversation_id: UUID
    role: ShopperMessageRole
    content: str = Field(min_length=1, max_length=4000)
    steps: list[ShopperAgentStep] = Field(default_factory=list, max_length=16)
    products: list[ShopperProductCard] = Field(default_factory=list, max_length=24)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ShopperMemory(StrictDomainModel):
    id: UUID
    content: str = Field(min_length=1, max_length=500)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ShopperConversationDetail(StrictDomainModel):
    conversation: ShopperConversation
    messages: list[ShopperMessage]


class ShopperConversationList(StrictDomainModel):
    items: list[ShopperConversation]


class ShopperMemoryList(StrictDomainModel):
    items: list[ShopperMemory]


class ShopperMemoryDeleteResponse(StrictDomainModel):
    memory_id: UUID
    deleted: bool


class ShopperDiscoverySuggestion(StrictDomainModel):
    """One catalog-grounded starter prompt for the shopper home view."""

    label: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=300)
    category: str | None = Field(default=None, max_length=160)
    image_url: str | None = Field(default=None, max_length=1000)


class ShopperDiscoveryResponse(StrictDomainModel):
    """Current manager-owned catalog state and bounded starter prompts."""

    conversation_mode: Literal["unknown", "basic", "model_configured"] = Field(
        default="unknown",
        description="Provider availability, not a connectivity check or answer-quality claim.",
    )
    catalog_status: CatalogIndexState = "not_configured"
    catalog_name: str | None = Field(default=None, max_length=255)
    product_count: int = Field(default=0, ge=0)
    suggestions: list[ShopperDiscoverySuggestion] = Field(default_factory=list, max_length=6)


class ShopperChatRequest(StrictDomainModel):
    _account_version: int | None = PrivateAttr(default=None)

    content: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    # Identity preconditions must not change existing chat receipt fingerprints.
    expected_account_id: UUID | None = Field(default=None, exclude=True)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class ShopperChatResponse(StrictDomainModel):
    conversation: ShopperConversation
    user_message: ShopperMessage
    assistant_message: ShopperMessage
    memory_created: ShopperMemory | None = None
    memories_saved: list[ShopperMemory] = Field(default_factory=list, max_length=3)


class ShopperAgentRuntime(Protocol):
    async def register(
        self, *, tenant_id: UUID, request: ShopperRegisterRequest
    ) -> tuple[ShopperAuthResponse, str]: ...

    async def login(
        self, *, tenant_id: UUID, request: ShopperLoginRequest
    ) -> tuple[ShopperAuthResponse, str]: ...

    async def authenticate(self, *, tenant_id: UUID, raw_token: str) -> ShopperAccount: ...

    async def logout(self, *, tenant_id: UUID, raw_token: str) -> None: ...

    async def list_conversations(
        self, *, tenant_id: UUID, account_id: UUID
    ) -> ShopperConversationList: ...

    async def get_conversation(
        self, *, tenant_id: UUID, account_id: UUID, conversation_id: UUID
    ) -> ShopperConversationDetail: ...

    async def list_memories(self, *, tenant_id: UUID, account_id: UUID) -> ShopperMemoryList: ...

    async def discovery(self, *, tenant_id: UUID, account_id: UUID) -> ShopperDiscoveryResponse: ...

    async def delete_memory(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        memory_id: UUID,
        idempotency_key: str,
    ) -> ShopperMemoryDeleteResponse: ...

    async def chat(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: ShopperChatRequest,
        idempotency_key: str,
    ) -> ShopperChatResponse: ...
