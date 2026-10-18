"""Durable ranking jobs, safe summaries, exact approval and reversible serving."""

import asyncio
from collections import Counter
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import active_catalog_integration, catalog_records
from open_commerce.core.redaction import redact_model_text
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.persistence.models.ranking import EngagementSnapshot, RankingModelRecord
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.ranking.engagement import normalize_engagement
from open_commerce.ranking.models import (
    EngagementEvent,
    EngagementSummary,
    RankingApproval,
    RankingArtifact,
    RankingDataError,
    RankingModel,
    RankingOverview,
    TrainRankingInput,
)
from open_commerce.ranking.training import train, validate_goal


async def import_engagement(
    session: AsyncSession, tenant_id: UUID, csv_text: str
) -> EngagementSummary:
    events = normalize_engagement(tenant_id, csv_text)
    fingerprint = canonical_hash(events)
    prior = await session.scalar(
        select(EngagementSnapshot).where(
            EngagementSnapshot.tenant_id == tenant_id,
            EngagementSnapshot.fingerprint == fingerprint,
        )
    )
    if prior:
        return EngagementSummary.model_validate(prior.summary)
    summary = EngagementSummary(
        id=uuid4(),
        fingerprint=fingerprint,
        event_count=len(events),
        product_count=len({event.product_id for event in events}),
        event_counts=dict(Counter(event.kind for event in events)),
        session_count=len({event.session for event in events if event.session}),
        start_at=events[0].at,
        end_at=events[-1].at,
    )
    session.add(
        EngagementSnapshot(
            id=summary.id,
            tenant_id=tenant_id,
            fingerprint=fingerprint,
            events=[event.model_dump(mode="json") for event in events],
            summary=summary.model_dump(mode="json"),
            created_at=utc_now(),
        )
    )
    return summary


def public_model(row: RankingModelRecord) -> RankingModel:
    return RankingModel.model_validate(
        {name: getattr(row, name) for name in RankingModel.model_fields}
    )


async def get_model(session: AsyncSession, tenant_id: UUID, model_id: UUID) -> RankingModelRecord:
    row = await session.scalar(
        select(RankingModelRecord).where(
            RankingModelRecord.tenant_id == tenant_id,
            RankingModelRecord.id == model_id,
        )
    )
    if row is None:
        raise RankingDataError("Ranking model not found in this workspace.")
    return row


async def serving_artifact(
    session: AsyncSession, tenant_id: UUID, catalog_id: UUID
) -> tuple[UUID, RankingArtifact] | None:
    row = await session.scalar(
        select(RankingModelRecord).where(
            RankingModelRecord.tenant_id == tenant_id,
            RankingModelRecord.catalog_id == catalog_id,
            RankingModelRecord.active.is_(True),
            RankingModelRecord.status == "ready",
        )
    )
    if row is None:
        return None
    return row.id, checked_artifact(row)


def checked_artifact(row: RankingModelRecord) -> RankingArtifact:
    if row.artifact is None or canonical_hash(row.artifact) != row.artifact_hash:
        raise RankingDataError("Ranking artifact checksum mismatch; disable it and retrain.")
    return RankingArtifact.model_validate(row.artifact)


class RankingService:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def overview(self, tenant_id: UUID) -> RankingOverview:
        async with self.database.transaction(tenant_id) as session:
            catalog = await active_catalog_integration(session, tenant_id=tenant_id)
            snapshot = await session.scalar(
                select(EngagementSnapshot)
                .where(
                    EngagementSnapshot.tenant_id == tenant_id,
                )
                .order_by(EngagementSnapshot.created_at.desc())
                .limit(1)
            )
            rows = await session.scalars(
                select(RankingModelRecord)
                .where(
                    RankingModelRecord.tenant_id == tenant_id,
                )
                .order_by(RankingModelRecord.active.desc(), RankingModelRecord.created_at.desc())
                .limit(30)
            )
            return RankingOverview(
                catalog_id=catalog.id if catalog else None,
                dataset=EngagementSummary.model_validate(snapshot.summary) if snapshot else None,
                models=[public_model(row) for row in rows],
            )

    async def submit(self, tenant_id: UUID, request: TrainRankingInput, key: str) -> RankingModel:
        validate_goal(request)
        if redact_model_text(request.goal) != request.goal:
            raise RankingDataError("Remove sensitive text from the training goal.")
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            cached = await receipts.replay(scope="ranking:train", key=key, request=request)
            if cached:
                return public_model(await get_model(session, tenant_id, UUID(str(cached["id"]))))
            catalog = await active_catalog_integration(session, tenant_id=tenant_id)
            snapshot = await session.scalar(
                select(EngagementSnapshot)
                .where(
                    EngagementSnapshot.tenant_id == tenant_id,
                )
                .order_by(EngagementSnapshot.created_at.desc())
                .limit(1)
            )
            if catalog is None or snapshot is None:
                raise RankingDataError(
                    "Publish a catalog and upload engagement first. "
                    "Older profile-only uploads must be uploaded again."
                )
            active_job = await session.scalar(
                select(RankingModelRecord.id)
                .where(
                    RankingModelRecord.tenant_id == tenant_id,
                    RankingModelRecord.status.in_(["queued", "running"]),
                )
                .limit(1)
            )
            if active_job:
                raise RankingDataError(
                    "A ranking build is already running. Inspect it before queuing another."
                )
            now = utc_now()
            row = RankingModelRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                catalog_id=catalog.id,
                dataset_id=snapshot.id,
                goal=request.goal,
                target=request.target,
                method=request.method,
                status="queued",
                active=False,
                metrics={},
                attempts=0,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            response = public_model(row)
            receipts.remember(scope="ranking:train", key=key, request=request, response=response)
            return response

    async def run(self, tenant_id: UUID, model_id: UUID) -> bool:
        async with self.database.transaction(tenant_id, write=True) as session:
            row = await get_model(session, tenant_id, model_id)
            if row.status in {"ready", "failed"} or (
                row.lease_until and row.lease_until > utc_now()
            ):
                return False
            if row.attempts >= 3:
                row.status, row.error = (
                    "failed",
                    "Training interrupted repeatedly; submit a new build.",
                )
                return False
            token = uuid4()
            row.status, row.lease_token = "running", token
            row.lease_until = utc_now() + timedelta(minutes=3)
            row.attempts += 1
            row.updated_at = utc_now()
            snapshot = await session.scalar(
                select(EngagementSnapshot).where(
                    EngagementSnapshot.tenant_id == tenant_id,
                    EngagementSnapshot.id == row.dataset_id,
                )
            )
            if snapshot is None:
                raise RankingDataError("Engagement snapshot unavailable.")
            events = [EngagementEvent.model_validate(event) for event in snapshot.events]
            records = await catalog_records(
                session, tenant_id=tenant_id, integration_id=row.catalog_id
            )
            products = [product.source_product_id for product, _, _ in records]
            request = TrainRankingInput.model_validate(
                {"goal": row.goal, "target": row.target, "method": row.method}
            )
            fingerprint = snapshot.fingerprint
        artifact: RankingArtifact | None = None
        metrics: dict[str, float | int | str | bool | None] = {}
        error = None
        try:
            artifact, metrics = await asyncio.wait_for(
                asyncio.to_thread(train, events, products, request), timeout=120
            )
            metrics["dataset_fingerprint"] = fingerprint
        except RankingDataError as exc:
            error = str(exc)
        except Exception:
            error = (
                "Training failed without publishing a model. Check worker dependencies or retry."
            )
        async with self.database.transaction(tenant_id, write=True) as session:
            row = await get_model(session, tenant_id, model_id)
            if row.lease_token != token:
                return False
            row.artifact = artifact.model_dump(mode="json") if artifact else None
            row.artifact_hash = canonical_hash(row.artifact) if artifact else None
            row.metrics = dict(metrics)
            row.status, row.error = ("ready", None) if artifact else ("failed", error)
            row.updated_at, row.lease_token, row.lease_until = utc_now(), None, None
        return artifact is not None

    async def approve(self, tenant_id: UUID, request: RankingApproval, key: str) -> RankingOverview:
        async with self.database.transaction(tenant_id, write=True) as session:
            receipts = RequestRepository(session, tenant_id)
            if await receipts.replay(scope="ranking:approve", key=key, request=request) is None:
                active = await session.scalar(
                    select(RankingModelRecord).where(
                        RankingModelRecord.tenant_id == tenant_id,
                        RankingModelRecord.active.is_(True),
                    )
                )
                if (active.id if active else None) != request.expected_active_id:
                    raise RankingDataError("The active model changed. Refresh before approving.")
                catalog = await active_catalog_integration(session, tenant_id=tenant_id)
                row = None
                if request.model_id:
                    if request.confirm != "APPLY_LOCAL_RANKING":
                        raise RankingDataError("Explicit local ranking approval is required.")
                    row = await get_model(session, tenant_id, request.model_id)
                    if not catalog or row.catalog_id != catalog.id or row.status != "ready":
                        raise RankingDataError(
                            "Only a ready model for the current catalog can be applied."
                        )
                    checked_artifact(row)
                    if request.artifact_hash != row.artifact_hash or not row.metrics.get(
                        "eligible_for_activation"
                    ):
                        raise RankingDataError(
                            "Exact artifact approval and a passing baseline evaluation "
                            "are required."
                        )
                elif request.confirm != "DISABLE_LOCAL_RANKING":
                    raise RankingDataError("Explicit disable confirmation is required.")
                if active:
                    active.active = False
                    await session.flush()
                if row:
                    row.active, row.updated_at = True, utc_now()
                from pydantic import RootModel

                receipts.remember(
                    scope="ranking:approve",
                    key=key,
                    request=request,
                    response=RootModel[dict[str, object]](
                        {
                            "policy": "EXPLICIT_OPERATOR_LOCAL_RANKING_APPROVAL",
                            "previous_model_id": str(active.id) if active else None,
                            "model_id": str(row.id) if row else None,
                            "artifact_hash": row.artifact_hash if row else None,
                            "rollback": "Reapprove prior compatible artifact or disable ranking",
                            "at": utc_now().isoformat(),
                        }
                    ),
                )
        return await self.overview(tenant_id)
