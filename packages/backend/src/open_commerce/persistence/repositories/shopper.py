"""Tenant and account scoped persistence for shopper identity and memory."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.persistence.models.shopper import (
    ShopperAccountRecord,
    ShopperConversationRecord,
    ShopperMemoryRecord,
    ShopperMessageRecord,
    ShopperSessionRecord,
)
from open_commerce.shopper_agent.errors import (
    ShopperConversationNotFoundError,
    ShopperMemoryNotFoundError,
)
from open_commerce.shopper_agent.models import (
    ShopperAccount,
    ShopperConversation,
    ShopperMemory,
    ShopperMessage,
)


class ShopperRepository:
    """All shopper records are constrained by tenant and, after login, account."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def get_account_credentials(self, username: str) -> tuple[ShopperAccount, str] | None:
        row = await self.session.scalar(
            select(ShopperAccountRecord).where(
                ShopperAccountRecord.tenant_id == self.tenant_id,
                ShopperAccountRecord.username == username,
                ShopperAccountRecord.status == "active",
                ShopperAccountRecord.is_guest.is_(False),
            )
        )
        if row is None:
            return None
        return self._account(row), row.password_hash

    async def create_account(
        self,
        *,
        account_id: UUID,
        username: str,
        display_name: str,
        password_hash: str,
        now: datetime,
    ) -> ShopperAccount:
        row = ShopperAccountRecord(
            id=account_id,
            tenant_id=self.tenant_id,
            username=username,
            display_name=display_name,
            password_hash=password_hash,
            status="active",
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.session.add(row)
        await self.session.flush()
        return self._account(row)

    async def create_session(
        self,
        *,
        session_id: UUID,
        account_id: UUID,
        token_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> None:
        self.session.add(
            ShopperSessionRecord(
                id=session_id,
                tenant_id=self.tenant_id,
                account_id=account_id,
                token_hash=token_hash,
                expires_at=expires_at,
                revoked_at=None,
                created_at=now,
            )
        )
        await self.session.flush()

    async def account_for_session(self, *, token_hash: str, now: datetime) -> ShopperAccount | None:
        result = await self.session.execute(
            select(ShopperAccountRecord)
            .join(
                ShopperSessionRecord,
                ShopperSessionRecord.account_id == ShopperAccountRecord.id,
            )
            .where(
                ShopperSessionRecord.tenant_id == self.tenant_id,
                ShopperAccountRecord.tenant_id == self.tenant_id,
                ShopperSessionRecord.token_hash == token_hash,
                ShopperSessionRecord.revoked_at.is_(None),
                ShopperSessionRecord.expires_at > now,
                ShopperAccountRecord.status == "active",
                or_(
                    ShopperAccountRecord.expires_at.is_(None), ShopperAccountRecord.expires_at > now
                ),
            )
        )
        row = result.scalar_one_or_none()
        return self._account(row) if row is not None else None

    async def revoke_session(self, *, token_hash: str, now: datetime) -> None:
        await self.session.execute(
            update(ShopperSessionRecord)
            .where(
                ShopperSessionRecord.tenant_id == self.tenant_id,
                ShopperSessionRecord.token_hash == token_hash,
                ShopperSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def create_conversation(
        self,
        *,
        conversation_id: UUID,
        account_id: UUID,
        title: str,
        now: datetime,
    ) -> ShopperConversation:
        row = ShopperConversationRecord(
            id=conversation_id,
            tenant_id=self.tenant_id,
            account_id=account_id,
            title=title,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.session.add(row)
        await self.session.flush()
        return self._conversation(row)

    async def get_conversation(
        self, *, account_id: UUID, conversation_id: UUID
    ) -> ShopperConversation:
        row = await self.session.scalar(
            select(ShopperConversationRecord).where(
                ShopperConversationRecord.tenant_id == self.tenant_id,
                ShopperConversationRecord.account_id == account_id,
                ShopperConversationRecord.id == conversation_id,
            )
        )
        if row is None:
            raise ShopperConversationNotFoundError("Shopper conversation was not found")
        return self._conversation(row)

    async def list_conversations(self, *, account_id: UUID) -> list[ShopperConversation]:
        rows = await self.session.scalars(
            select(ShopperConversationRecord)
            .where(
                ShopperConversationRecord.tenant_id == self.tenant_id,
                ShopperConversationRecord.account_id == account_id,
            )
            .order_by(
                ShopperConversationRecord.updated_at.desc(),
                ShopperConversationRecord.id.desc(),
            )
            .limit(50)
        )
        return [self._conversation(row) for row in rows]

    async def touch_conversation(
        self, *, account_id: UUID, conversation_id: UUID, now: datetime
    ) -> ShopperConversation:
        row = await self.session.scalar(
            select(ShopperConversationRecord).where(
                ShopperConversationRecord.tenant_id == self.tenant_id,
                ShopperConversationRecord.account_id == account_id,
                ShopperConversationRecord.id == conversation_id,
            )
        )
        if row is None:
            raise ShopperConversationNotFoundError("Shopper conversation was not found")
        row.updated_at = now
        row.version += 1
        await self.session.flush()
        return self._conversation(row)

    async def add_message(self, *, account_id: UUID, message: ShopperMessage) -> None:
        self.session.add(
            ShopperMessageRecord(
                id=message.id,
                tenant_id=self.tenant_id,
                account_id=account_id,
                conversation_id=message.conversation_id,
                role=message.role,
                content=message.content,
                steps=[item.model_dump(mode="json") for item in message.steps],
                products=[item.model_dump(mode="json") for item in message.products],
                created_at=message.created_at,
            )
        )
        await self.session.flush()

    async def list_messages(
        self, *, account_id: UUID, conversation_id: UUID, limit: int = 100
    ) -> list[ShopperMessage]:
        await self.get_conversation(account_id=account_id, conversation_id=conversation_id)
        rows = list(
            await self.session.scalars(
                select(ShopperMessageRecord)
                .where(
                    ShopperMessageRecord.tenant_id == self.tenant_id,
                    ShopperMessageRecord.account_id == account_id,
                    ShopperMessageRecord.conversation_id == conversation_id,
                )
                .order_by(
                    ShopperMessageRecord.created_at.desc(),
                    ShopperMessageRecord.id.desc(),
                )
                .limit(limit)
            )
        )
        rows.reverse()
        return [self._message(row) for row in rows]

    async def get_message(
        self, *, account_id: UUID, conversation_id: UUID, message_id: UUID
    ) -> ShopperMessage | None:
        row = await self.session.scalar(
            select(ShopperMessageRecord).where(
                ShopperMessageRecord.tenant_id == self.tenant_id,
                ShopperMessageRecord.account_id == account_id,
                ShopperMessageRecord.conversation_id == conversation_id,
                ShopperMessageRecord.id == message_id,
            )
        )
        return self._message(row) if row is not None else None

    async def get_memory(self, *, account_id: UUID, memory_id: UUID) -> ShopperMemory | None:
        row = await self.session.scalar(
            select(ShopperMemoryRecord).where(
                ShopperMemoryRecord.tenant_id == self.tenant_id,
                ShopperMemoryRecord.account_id == account_id,
                ShopperMemoryRecord.id == memory_id,
            )
        )
        return self._memory(row) if row is not None else None

    async def add_memory(
        self,
        *,
        memory_id: UUID,
        account_id: UUID,
        content: str,
        source_message_id: UUID,
        now: datetime,
    ) -> ShopperMemory:
        from sqlalchemy import func

        prior = await self.session.scalar(
            select(ShopperMemoryRecord)
            .where(
                ShopperMemoryRecord.tenant_id == self.tenant_id,
                ShopperMemoryRecord.account_id == account_id,
                func.lower(ShopperMemoryRecord.content) == content.lower(),
            )
            .limit(1)
        )
        if prior:
            return self._memory(prior)
        row = ShopperMemoryRecord(
            id=memory_id,
            tenant_id=self.tenant_id,
            account_id=account_id,
            content=content,
            source_message_id=source_message_id,
            created_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return self._memory(row)

    async def list_memories(self, *, account_id: UUID, limit: int = 20) -> list[ShopperMemory]:
        """Recall remains opt-in, including for callers using the default method."""
        if not await self.session.scalar(
            select(ShopperAccountRecord.memory_enabled).where(
                ShopperAccountRecord.tenant_id == self.tenant_id,
                ShopperAccountRecord.id == account_id,
            )
        ):
            return []
        return await self.list_memories_for_management(account_id=account_id, limit=limit)

    async def list_memories_for_management(
        self, *, account_id: UUID, limit: int = 20
    ) -> list[ShopperMemory]:
        """Inspect retained preferences for the authenticated account, even when recall is off."""
        rows = list(
            await self.session.scalars(
                select(ShopperMemoryRecord)
                .where(
                    ShopperMemoryRecord.tenant_id == self.tenant_id,
                    ShopperMemoryRecord.account_id == account_id,
                )
                .order_by(ShopperMemoryRecord.created_at.desc(), ShopperMemoryRecord.id.desc())
                .limit(limit)
            )
        )
        rows.reverse()
        return [self._memory(row) for row in rows]

    async def delete_memory(self, *, account_id: UUID, memory_id: UUID) -> None:
        row = await self.session.scalar(
            select(ShopperMemoryRecord).where(
                ShopperMemoryRecord.tenant_id == self.tenant_id,
                ShopperMemoryRecord.account_id == account_id,
                ShopperMemoryRecord.id == memory_id,
            )
        )
        if row is None:
            raise ShopperMemoryNotFoundError("Shopping memory was not found")
        await self.session.execute(
            delete(ShopperMemoryRecord).where(
                ShopperMemoryRecord.tenant_id == self.tenant_id,
                ShopperMemoryRecord.account_id == account_id,
                ShopperMemoryRecord.id == memory_id,
            )
        )

    @staticmethod
    def _account(row: ShopperAccountRecord) -> ShopperAccount:
        account = ShopperAccount(
            is_guest=row.is_guest,
            memory_enabled=row.memory_enabled,
            expires_at=row.expires_at,
            id=row.id,
            username=row.username,
            display_name=row.display_name,
            created_at=row.created_at,
        )
        account._data_version = row.version
        return account

    @staticmethod
    def _conversation(row: ShopperConversationRecord) -> ShopperConversation:
        return ShopperConversation(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )

    @staticmethod
    def _message(row: ShopperMessageRecord) -> ShopperMessage:
        return ShopperMessage(
            id=row.id,
            conversation_id=row.conversation_id,
            role=row.role,
            content=row.content,
            steps=row.steps,
            products=row.products,
            created_at=row.created_at,
        )

    @staticmethod
    def _memory(row: ShopperMemoryRecord) -> ShopperMemory:
        return ShopperMemory(id=row.id, content=row.content, created_at=row.created_at)
