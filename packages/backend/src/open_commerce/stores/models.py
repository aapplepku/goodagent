"""Validated store and identity transport contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr

from open_commerce.core.types import StrictDomainModel


class StoreError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class StoreUnavailableError(StoreError):
    """The shopper cannot currently access the store, not just one resource."""

    def __init__(self, message: str = "This store is not accepting shoppers yet.") -> None:
        super().__init__(message, 404)


class StoreProfile(StrictDomainModel):
    id: UUID
    slug: str
    name: str
    description: str = ""
    goal: str = "Help shoppers find suitable products"
    currency: str = "USD"
    sharing_enabled: bool = False
    published_catalog_id: UUID | None = None
    sample_data: bool = False
    readiness: dict[str, bool | str | int | None] = Field(default_factory=dict)


class StoreProfileUpdate(StrictDomainModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    goal: str = Field(default="Help shoppers find suitable products", max_length=300)
    currency: Literal["USD", "EUR", "GBP", "CAD", "AUD"] = "USD"


class OwnerSetupRequest(StoreProfileUpdate):
    bootstrap_token: SecretStr
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: SecretStr = Field(min_length=12, max_length=128)


class OwnerLoginRequest(StrictDomainModel):
    username: str = Field(min_length=3, max_length=80)
    password: SecretStr = Field(min_length=1, max_length=128)


class OwnerRecoveryRequest(StrictDomainModel):
    username: str = Field(min_length=3, max_length=80)
    recovery_code: SecretStr
    password: SecretStr = Field(min_length=12, max_length=128)


class OwnerIdentity(StrictDomainModel):
    user_id: UUID
    tenant_id: UUID
    role: Literal["owner"] = "owner"


class OwnerAuthResponse(StrictDomainModel):
    user_id: UUID
    store: StoreProfile
    recovery_code: str | None = None


class SetupStatus(StrictDomainModel):
    profile: Literal["legacy_demo", "self_hosted", "hosted"]
    setup_required: bool
    login_method: Literal["local", "oidc", "legacy"]


class SessionInfo(StrictDomainModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    current: bool


class SessionList(StrictDomainModel):
    items: list[SessionInfo]


class PublicationRequest(StrictDomainModel):
    catalog_id: UUID
    enabled: bool
    acknowledge_demo_checkout: bool = False
    acknowledge_image_issues: bool = False


class PreviewResponse(StrictDomainModel):
    token: str
    store_slug: str
    catalog_id: UUID
    expires_at: datetime
