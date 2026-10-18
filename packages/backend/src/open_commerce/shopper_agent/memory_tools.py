"""Ground model-selected memory in shopper messages and commit before acknowledging it."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from open_commerce.core.redaction import contains_direct_pii_or_secret
from open_commerce.core.types import StrictDomainModel, canonical_hash, utc_now
from open_commerce.manager_agent.model_provider import ManagerToolDefinition
from open_commerce.persistence.models.shopper import ShopperAccountRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.repositories.shopper import ShopperRepository
from open_commerce.persistence.runtime_db import DatabaseUnavailableError, RuntimeDatabase
from open_commerce.shopper_agent.models import ShopperMemory, ShopperMessage


class SaveShoppingMemoryInput(StrictDomainModel):
    source_message_id: UUID
    preference: str = Field(min_length=3, max_length=500)


SAVE_SHOPPING_MEMORY = ManagerToolDefinition(
    name="save_shopping_memory",
    description=(
        "Save a durable shopping preference to this authenticated shopper's account. "
        "Select an exact, self-contained quote from an eligible user message, with its "
        "source_message_id. Use for clearly stated ongoing preferences, even without 'remember'. "
        "Never infer preferences from products, assistant text, third parties, or temporary "
        "requests. Do not save when the shopper opts out. Only report success after ok=true. "
        "At most three distinct preferences per turn. Existing identical preferences are reused."
    ),
    parameters=SaveShoppingMemoryInput.model_json_schema(),
)


class ShopperMemoryToolError(ValueError):
    """Safe error code suitable for the model; never include database or user details."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def memory_opt_out(content: str) -> bool:
    return bool(
        re.search(
            r"\b(?:do not|don't|dont|never|stop|must not|should not|shouldn't|cannot|can't)\s+"
            r"(?:(?:automatically|ever|auto)\s+)?(?:save|saving|remember|remembering|store|storing)\b"
            r"|\b(?:no memory|without (?:saving|storing)|"
            r"(?:this|current) (?:chat|conversation) only)\b",
            content.casefold().replace("\u2019", "'"),
        )
    )


def grounded_preference(
    arguments: SaveShoppingMemoryInput,
    *,
    messages: list[ShopperMessage],
    current_message: ShopperMessage,
) -> str:
    source = next(
        (
            item
            for item in messages
            if item.id == arguments.source_message_id and item.role == "user"
        ),
        None,
    )
    if source is None or source.conversation_id != current_message.conversation_id:
        raise ShopperMemoryToolError("INVALID_MEMORY_SOURCE")
    if memory_opt_out(current_message.content) or memory_opt_out(source.content):
        raise ShopperMemoryToolError("MEMORY_OPTED_OUT")
    quote = " ".join(arguments.preference.split())
    source_text = " ".join(source.content.split())
    match = re.search(re.escape(quote.strip('"').rstrip(".!?")), source_text, re.IGNORECASE)
    if len(quote) < 3 or match is None or len(match.group()) < 3:
        raise ShopperMemoryToolError("MEMORY_QUOTE_NOT_GROUNDED")
    quote = match.group()
    if contains_direct_pii_or_secret(source.content) or contains_direct_pii_or_secret(quote):
        raise ShopperMemoryToolError("UNSAFE_MEMORY")
    return quote


class ShopperMemoryTool:
    """Authority comes from the authenticated application, never model-selected IDs."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        tenant_id: UUID,
        account_id: UUID,
        current_message: ShopperMessage,
        history: list[ShopperMessage],
    ) -> None:
        self.database = database
        self.tenant_id = tenant_id
        self.account_id = account_id
        self.current_message = current_message
        self.messages = [*history[-12:], current_message]
        self.saved: dict[UUID, ShopperMemory] = {}

    async def save(self, arguments: SaveShoppingMemoryInput) -> ShopperMemory:
        quote = grounded_preference(
            arguments, messages=self.messages, current_message=self.current_message
        )
        if len(self.saved) >= 3 and quote not in {item.content for item in self.saved.values()}:
            raise ShopperMemoryToolError("MEMORY_TURN_LIMIT")
        scope = f"shopper:memory:save:{self.account_id}"
        request = {
            "turn_message_id": str(self.current_message.id),
            "source_message_id": str(arguments.source_message_id),
            "preference": quote,
        }
        key = canonical_hash(request)
        try:
            async with self.database.transaction(self.tenant_id, write=True) as session:
                enabled = await session.scalar(
                    select(ShopperAccountRecord.memory_enabled).where(
                        ShopperAccountRecord.tenant_id == self.tenant_id,
                        ShopperAccountRecord.id == self.account_id,
                        ShopperAccountRecord.status == "active",
                        or_(
                            ShopperAccountRecord.expires_at.is_(None),
                            ShopperAccountRecord.expires_at > utc_now(),
                        ),
                    )
                )
                if enabled is None:
                    raise ShopperMemoryToolError("INVALID_MEMORY_SOURCE")
                if not enabled:
                    raise ShopperMemoryToolError("MEMORY_OPTED_OUT")
                repo = ShopperRepository(session, self.tenant_id)
                # Revalidate ownership against persistence even when a caller supplies context.
                for message_id in {self.current_message.id, arguments.source_message_id}:
                    stored = await repo.get_message(
                        account_id=self.account_id,
                        conversation_id=self.current_message.conversation_id,
                        message_id=message_id,
                    )
                    expected = next(item for item in self.messages if item.id == message_id)
                    if (
                        stored is None
                        or stored.role != "user"
                        or stored.content != expected.content
                    ):
                        raise ShopperMemoryToolError("INVALID_MEMORY_SOURCE")
                receipts = RequestRepository(session, self.tenant_id)
                cached = await receipts.replay(scope=scope, key=key, request=request)
                if cached is not None:
                    receipt = ShopperMemory.model_validate(cached)
                    memory = await repo.get_memory(account_id=self.account_id, memory_id=receipt.id)
                    if memory is None:
                        raise ShopperMemoryToolError("MEMORY_PREVIOUSLY_REMOVED")
                else:
                    memory = await repo.add_memory(
                        memory_id=uuid4(),
                        account_id=self.account_id,
                        content=quote,
                        source_message_id=arguments.source_message_id,
                        now=utc_now(),
                    )
                    receipts.remember(scope=scope, key=key, request=request, response=memory)
        except (SQLAlchemyError, DatabaseUnavailableError) as exc:
            raise ShopperMemoryToolError("MEMORY_STORAGE_UNAVAILABLE") from exc
        self.saved[memory.id] = memory
        return memory
