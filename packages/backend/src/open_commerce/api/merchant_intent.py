"""Merchant view identity is a precondition, never authentication or tenant routing."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from open_commerce.stores.models import OwnerIdentity, StoreError

OWNER_HEADER = "X-Merchant-Owner-Id"
STORE_HEADER = "X-Merchant-Store-Id"


@dataclass(frozen=True)
class MerchantIntent:
    owner_id: UUID
    store_id: UUID


def get_merchant_intent(
    request: Request,
    expected_owner_id: Annotated[
        UUID | None,
        Header(alias=OWNER_HEADER, description="Expected owner; supply with X-Merchant-Store-Id."),
    ] = None,
    expected_store_id: Annotated[
        UUID | None,
        Header(alias=STORE_HEADER, description="Expected store; supply with X-Merchant-Owner-Id."),
    ] = None,
) -> MerchantIntent | None:
    """Validate optional, unambiguous headers without resolving any identity."""
    if any(len(request.headers.getlist(name)) > 1 for name in (OWNER_HEADER, STORE_HEADER)):
        raise StoreError("Supply each merchant identity header only once.", 422)
    if expected_owner_id is None and expected_store_id is None:
        return None
    if expected_owner_id is None or expected_store_id is None:
        raise StoreError("Supply both merchant identity headers together.", 422)
    return MerchantIntent(owner_id=expected_owner_id, store_id=expected_store_id)


MerchantIntentDependency = Annotated[MerchantIntent | None, Depends(get_merchant_intent)]


def verify_merchant_intent(owner: OwnerIdentity, intent: MerchantIntent | None) -> None:
    """Call only after cookie authentication and membership authorization succeed."""
    if intent is not None and (
        intent.owner_id != owner.user_id or intent.store_id != owner.tenant_id
    ):
        raise StoreError("Your workspace session changed. Check your session again.", 401)
