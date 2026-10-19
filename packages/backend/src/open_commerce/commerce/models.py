"""Strict transport-neutral commerce contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from open_commerce.core.money import Money
from open_commerce.core.types import StrictDomainModel, ensure_utc

CartStatus = Literal["open", "converted", "abandoned"]
ReservationStatus = Literal["active", "released", "consumed", "expired"]
PaymentStatus = Literal[
    "requires_confirmation",
    "processing",
    "requires_payment_method",
    "succeeded",
    "cancelled",
]
TestPaymentMethod = Literal["test_success", "test_decline"]
InventoryState = Literal["healthy", "low", "out", "unknown"]


class CartLine(StrictDomainModel):
    id: UUID
    product_id: str = Field(min_length=1, max_length=240)
    variant_id: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=500)
    variant_title: str = Field(min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2000)
    quantity: int = Field(ge=1, le=20)
    unit_price: Money
    line_total: Money
    available_quantity: int | None = Field(default=None, ge=0)
    sellable_quantity: int | None = Field(default=None, ge=0)


class Cart(StrictDomainModel):
    id: UUID | None = None
    status: CartStatus = "open"
    lines: list[CartLine] = Field(default_factory=list, max_length=100)
    subtotal: Money = Field(default_factory=lambda: Money(amount_minor=0, currency="USD"))
    total: Money = Field(default_factory=lambda: Money(amount_minor=0, currency="USD"))
    item_count: int = Field(default=0, ge=0)
    version: int = Field(default=0, ge=0)
    updated_at: datetime | None = None

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class CartItemAddRequest(StrictDomainModel):
    variant_id: str | None = Field(default=None, min_length=1, max_length=240)
    product_id: str = Field(min_length=1, max_length=240)
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdateRequest(StrictDomainModel):
    quantity: int = Field(ge=1, le=20)


class CheckoutPreviewRequest(StrictDomainModel):
    cart_version: int = Field(ge=1)


class CheckoutLine(StrictDomainModel):
    product_id: str
    variant_id: str
    title: str
    quantity: int = Field(ge=1)
    unit_price: Money
    line_total: Money


class CommercePolicyDecision(StrictDomainModel):
    allowed: bool
    code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=300)
    preconditions: list[str] = Field(default_factory=list, max_length=20)
    rollback_strategy: str = Field(min_length=1, max_length=300)


class CheckoutPreview(StrictDomainModel):
    checkout_id: UUID
    cart_id: UUID
    cart_version: int = Field(ge=1)
    status: PaymentStatus
    lines: list[CheckoutLine] = Field(min_length=1, max_length=100)
    subtotal: Money
    total: Money
    reservation_expires_at: datetime
    payment_mode: Literal["local_test"] = "local_test"
    policy: CommercePolicyDecision

    @field_validator("reservation_expires_at")
    @classmethod
    def normalize_expiry(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class CheckoutConfirmRequest(StrictDomainModel):
    checkout_id: UUID
    payment_method: TestPaymentMethod


class OrderSummary(StrictDomainModel):
    id: UUID
    order_number: str
    status: Literal["paid", "cancelled"]
    lines: list[CheckoutLine]
    total: Money
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ShopperOrderQuery(StrictDomainModel):
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ShopperOrderList(StrictDomainModel):
    items: list[OrderSummary]
    next_offset: int | None = Field(default=None, ge=0)
    payment_mode: Literal["local_test"] = "local_test"


class CheckoutConfirmation(StrictDomainModel):
    checkout_id: UUID
    status: PaymentStatus
    order: OrderSummary | None = None
    failure_code: str | None = Field(default=None, max_length=80)
    message: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def successful_checkout_has_order(self) -> CheckoutConfirmation:
        if self.status == "succeeded" and self.order is None:
            raise ValueError("successful checkout requires an order")
        if self.status != "succeeded" and self.order is not None:
            raise ValueError("unsuccessful checkout cannot include an order")
        return self


class CheckoutRecovery(StrictDomainModel):
    checkout_id: UUID
    status: Literal[
        "requires_confirmation",
        "processing",
        "requires_payment_method",
        "succeeded",
        "cancelled",
        "expired",
    ]
    preview: CheckoutPreview | None = None
    confirmation: CheckoutConfirmation | None = None
    message: str = Field(max_length=300)


class CommerceInventoryItem(StrictDomainModel):
    product_id: str
    variant_id: str
    sku: str | None = None
    title: str
    variant_title: str
    image_url: str | None = None
    observed_quantity: int | None = Field(default=None, ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    sellable_quantity: int | None = Field(default=None, ge=0)
    state: InventoryState
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None


class ReservationSummary(StrictDomainModel):
    id: UUID
    checkout_id: UUID
    product_id: str
    variant_id: str
    quantity: int = Field(ge=1)
    status: ReservationStatus
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PaymentAttemptSummary(StrictDomainModel):
    id: UUID
    provider: Literal["local_test"] = "local_test"
    provider_reference: str
    status: PaymentStatus
    total: Money
    failure_code: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class CommerceOverview(StrictDomainModel):
    inventory: list[CommerceInventoryItem]
    reservations: list[ReservationSummary]
    orders: list[OrderSummary]
    payments: list[PaymentAttemptSummary]
    inventory_writes_enabled: Literal[False] = False
    payment_mode: Literal["local_test"] = "local_test"
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PaymentConfirmationRequest(StrictDomainModel):
    payment_intent_id: UUID
    amount: Money
    payment_method: TestPaymentMethod
    idempotency_key: str = Field(min_length=1, max_length=200)


class PaymentConfirmationResult(StrictDomainModel):
    provider_reference: str
    status: Literal["succeeded", "requires_payment_method"]
    failure_code: str | None = None


class PaymentProvider(Protocol):
    @property
    def payment_mode(self) -> Literal["local_test"]: ...

    async def confirm(self, request: PaymentConfirmationRequest) -> PaymentConfirmationResult: ...


class CommerceRuntime(Protocol):
    async def checkout_status(
        self, *, tenant_id: UUID, account_id: UUID, checkout_id: UUID | None = None
    ) -> CheckoutRecovery | None: ...

    async def orders(
        self, *, tenant_id: UUID, account_id: UUID, limit: int, offset: int
    ) -> ShopperOrderList: ...

    async def get_cart(self, *, tenant_id: UUID, account_id: UUID) -> Cart: ...

    async def add_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CartItemAddRequest,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart: ...

    async def update_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        line_id: UUID,
        request: CartItemUpdateRequest,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart: ...

    async def delete_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        line_id: UUID,
        idempotency_key: str,
        request_id: str,
        account_version: int | None = None,
    ) -> Cart: ...

    async def preview_checkout(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CheckoutPreviewRequest,
        idempotency_key: str,
        request_id: str,
    ) -> CheckoutPreview: ...

    async def confirm_checkout(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        request: CheckoutConfirmRequest,
        idempotency_key: str,
        request_id: str,
    ) -> CheckoutConfirmation: ...

    async def overview(self, *, tenant_id: UUID) -> CommerceOverview: ...
