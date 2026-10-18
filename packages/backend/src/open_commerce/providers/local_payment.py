"""Deterministic no-money payment provider for the local commerce MVP."""

from typing import Literal

from open_commerce.commerce.models import (
    PaymentConfirmationRequest,
    PaymentConfirmationResult,
)


class LocalTestPaymentProvider:
    """Accept only typed synthetic payment methods; never cardholder data."""

    payment_mode: Literal["local_test"] = "local_test"

    async def confirm(self, request: PaymentConfirmationRequest) -> PaymentConfirmationResult:
        provider_reference = f"local_pi_{request.payment_intent_id.hex}"
        if request.payment_method == "test_decline":
            return PaymentConfirmationResult(
                provider_reference=provider_reference,
                status="requires_payment_method",
                failure_code="test_card_declined",
            )
        return PaymentConfirmationResult(
            provider_reference=provider_reference,
            status="succeeded",
        )
