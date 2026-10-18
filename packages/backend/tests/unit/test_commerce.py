"""Commerce contracts and the no-money provider stay narrow and deterministic."""

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from open_commerce.commerce.models import (
    CheckoutConfirmRequest,
    PaymentConfirmationRequest,
    PaymentProvider,
)
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.core.money import Money
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider


def test_commerce_rejects_non_demo_payment_provider() -> None:
    with pytest.raises(ValueError, match="no-money"):
        DurableCommerceService(
            cast(RuntimeDatabase, object()),
            payment_provider=cast(PaymentProvider, SimpleNamespace(payment_mode="live")),
        )


async def test_local_payment_provider_supports_only_typed_test_outcomes() -> None:
    provider = LocalTestPaymentProvider()
    payment_id = uuid4()
    success = await provider.confirm(
        PaymentConfirmationRequest(
            payment_intent_id=payment_id,
            amount=Money(amount_minor=2599, currency="USD"),
            payment_method="test_success",
            idempotency_key="checkout-success",
        )
    )
    decline = await provider.confirm(
        PaymentConfirmationRequest(
            payment_intent_id=payment_id,
            amount=Money(amount_minor=2599, currency="USD"),
            payment_method="test_decline",
            idempotency_key="checkout-decline",
        )
    )

    assert success.status == "succeeded"
    assert decline.status == "requires_payment_method"
    assert decline.failure_code == "test_card_declined"
    assert success.provider_reference == decline.provider_reference


def test_checkout_contract_rejects_cardholder_data_and_unknown_payment_methods() -> None:
    with pytest.raises(ValidationError):
        CheckoutConfirmRequest.model_validate(
            {
                "checkout_id": str(uuid4()),
                "payment_method": "4242424242424242",
            }
        )
    with pytest.raises(ValidationError):
        CheckoutConfirmRequest.model_validate(
            {
                "checkout_id": str(uuid4()),
                "payment_method": "test_success",
                "card_number": "4242424242424242",
                "cvv": "123",
            }
        )
