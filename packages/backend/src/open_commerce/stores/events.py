"""Finite setup milestones with no raw rows, personal text, or credential payloads."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.core.types import StrictDomainModel, utc_now
from open_commerce.persistence.models.store_setup import SetupEventRecord


class ImportMilestone(StrictDomainModel):
    kind: Literal["products_uploaded", "products_reviewed", "products_confirmed"]
    import_id: UUID
    product_count: int | None = Field(default=None, ge=0, le=10000)


async def record_import_milestone(
    session: AsyncSession, tenant: UUID, event: ImportMilestone
) -> None:
    await session.execute(
        insert(SetupEventRecord)
        .values(
            id=uuid4(),
            tenant_id=tenant,
            kind=event.kind,
            event_key=f"{event.kind}:{event.import_id}",
            details=event.model_dump(mode="json", exclude={"kind"}, exclude_none=True),
            occurred_at=utc_now(),
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "event_key"])
    )
