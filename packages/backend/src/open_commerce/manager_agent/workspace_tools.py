"""Finite workspace investigation and owner-authorized local recovery tools."""

from collections import Counter
from datetime import timedelta
from typing import cast
from uuid import UUID, uuid4

from pydantic import RootModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.catalog.persistence import active_catalog_integration, catalog_index_status
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.core.types import JsonObject, canonical_hash, utc_now
from open_commerce.manager_agent.model_provider import ManagerToolCall
from open_commerce.manager_agent.models import ManagerRuntimeComponent
from open_commerce.manager_agent.operations import OPERATIONS_DESCRIPTIONS, StoreOperations
from open_commerce.manager_agent.run_hooks import RunCancelled, RunJournal
from open_commerce.manager_agent.runs import run_row
from open_commerce.manager_agent.runs_models import (
    IndexRecoveryInput,
    RecommendationTestInput,
    RuntimeRepairInput,
)
from open_commerce.persistence.models.manager_runs import RuntimeOperationRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.repositories.manager_agent import ManagerAgentRepository
from open_commerce.persistence.repositories.requests import RequestRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.ranking.models import RankingDataError, RankingPreviewInput, TrainRankingInput
from open_commerce.ranking.service import RankingService
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.models import RecommendationRequest


class WorkspaceTools:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def model_connection(self, tenant_id: UUID) -> ManagerRuntimeComponent | None:
        from open_commerce.runtime_services import model_connection

        return await model_connection(self.database, tenant_id)

    async def guard(self, session: AsyncSession, tenant_id: UUID, journal: RunJournal) -> None:
        row = await run_row(session, tenant_id, journal.run_id)
        thread = await ManagerAgentRepository(session, tenant_id).get_thread(row.thread_id)
        if (
            row.status != "running"
            or row.lease_token != journal.token
            or thread.version != row.thread_version
        ):
            raise RunCancelled()

    async def execute(
        self, call: ManagerToolCall, tenant_id: UUID, journal: RunJournal | None
    ) -> JsonObject:
        if call.name in OPERATIONS_DESCRIPTIONS:
            return await StoreOperations(self.database).execute(call, tenant_id)
        if call.name in {"inspect_shopping_activity", "configure_activity_monitor"}:
            from open_commerce.telemetry.activity import ActivityService
            from open_commerce.telemetry.activity_tools import ActivityTools

            if call.name == "configure_activity_monitor":
                if journal is None:
                    return {"error": "DURABLE_RUN_REQUIRED"}
                await journal.check()
            return await ActivityTools(
                ActivityService(self.database),
                tenant_id=tenant_id,
                account_id=None,
                turn_key=str(journal.run_id) if journal else "read",
            ).execute(call)
        if call.name in {"inspect_shopify_connection", "import_shopify_catalog"}:
            from open_commerce.catalog.intake import CatalogIntake
            from open_commerce.catalog.sources import CatalogSourceError

            intake = CatalogIntake(self.database)
            try:
                if call.name == "inspect_shopify_connection":
                    return (await intake.check(tenant_id)).model_dump(mode="json")
                if journal is None:
                    return {"error": "DURABLE_RUN_REQUIRED"}
                await journal.check()
                result = await intake.load(
                    tenant_id, canonical_hash({"run": str(journal.run_id), "call": call.call_id})
                )
                return {
                    **result.model_dump(mode="json"),
                    "indexed": False,
                    "next": "Inspect index jobs to verify publication; Shopify was not modified.",
                }
            except CatalogSourceError as exc:
                return {"error": "SHOPIFY_IMPORT_BLOCKED", "message": str(exc)}
        if call.name in {"inspect_ranking_signals", "train_search_ranker", "preview_search_ranker"}:
            try:
                return await self.ranking(call, tenant_id, journal)
            except RankingDataError as exc:
                return {"error": "RANKING_BLOCKED", "message": str(exc), "verified": False}
        if call.name == "inspect_commerce":
            overview = await DurableCommerceService(
                self.database, payment_provider=LocalTestPaymentProvider()
            ).overview(tenant_id=tenant_id)
            return {
                "inventory_products": len(overview.inventory),
                "orders_by_status": dict(Counter(item.status for item in overview.orders)),
                "payments_by_status": dict(Counter(item.status for item in overview.payments)),
                "reservation_count": len(overview.reservations),
                "payment_mode": overview.payment_mode,
                "inventory_writes_enabled": False,
                "scope": "Current local demo records, not historical sales analytics",
            }
        if call.name == "test_recommendations":
            args = RecommendationTestInput.model_validate(call.arguments)
            if args.strategy == "similar" and not args.product_id:
                return {"error": "PRODUCT_REQUIRED_FOR_SIMILAR"}
            search = DurableSearchService(self.database)
            try:
                response = await search.recommendations(
                    tenant_id=tenant_id,
                    request=RecommendationRequest(
                        anchor_product_ids=[args.product_id] if args.product_id else [],
                        top_k=args.top_k,
                    ),
                )
                return {
                    "strategy": response.strategy,
                    "results": [
                        item.model_dump(
                            mode="json", include={"product_id", "title", "price", "score"}
                        )
                        for item in response.results
                    ],
                    "quality_verified": False,
                }
            finally:
                await search.close()
        if call.name in {"inspect_catalog", "inspect_index_jobs"}:
            async with self.database.transaction(tenant_id) as session:
                current = await catalog_index_status(session, tenant_id=tenant_id)
                active = await active_catalog_integration(session, tenant_id=tenant_id)
                rows = await session.scalars(
                    select(CatalogIndexJob)
                    .where(CatalogIndexJob.tenant_id == tenant_id)
                    .order_by(CatalogIndexJob.updated_at.desc())
                    .limit(10)
                )
                return {
                    "latest": current.model_dump(mode="json"),
                    "active_catalog_id": str(active.id) if active else None,
                    "jobs": [
                        {
                            "id": str(row.id),
                            "status": row.status,
                            "product_count": row.product_count,
                            "indexed_count": row.indexed_product_count,
                            "failures": row.failures,
                        }
                        for row in rows
                    ],
                }
        if journal is None:
            return {"error": "DURABLE_RUN_REQUIRED"}
        await journal.check()
        if call.name == "recover_catalog_index":
            return await self.recover_index(tenant_id, call, journal)
        if call.name == "repair_local_service":
            return await self.repair_service(tenant_id, call, journal)
        return {"error": "UNKNOWN_TOOL"}

    async def ranking(
        self, call: ManagerToolCall, tenant_id: UUID, journal: RunJournal | None
    ) -> JsonObject:
        service = RankingService(self.database)
        if call.name == "inspect_ranking_signals":
            overview = await service.overview(tenant_id)
            return {
                **overview.model_dump(mode="json"),
                "activation": "Explicit operator approval in the Model panel",
                "limitations": "Offline product propensity, not personalization or causal lift",
            }
        if call.name == "preview_search_ranker":
            from open_commerce.ranking.preview import preview

            return (
                await preview(
                    self.database, tenant_id, RankingPreviewInput.model_validate(call.arguments)
                )
            ).model_dump(mode="json")
        if journal is None:
            return {"error": "DURABLE_RUN_REQUIRED"}
        args = TrainRankingInput.model_validate(call.arguments)
        async with self.database.transaction(tenant_id) as session:
            await self.guard(session, tenant_id, journal)
            row = await run_row(session, tenant_id, journal.run_id)
            from open_commerce.persistence.models.manager_agent import ManagerMessageRecord

            messages = await session.scalars(
                select(ManagerMessageRecord.content)
                .where(
                    ManagerMessageRecord.tenant_id == tenant_id,
                    ManagerMessageRecord.thread_id == row.thread_id,
                    ManagerMessageRecord.role == "user",
                )
                .order_by(ManagerMessageRecord.created_at.desc())
                .limit(20)
            )
            if not any(args.goal.casefold() in message.casefold() for message in messages):
                raise RankingDataError(
                    "The target goal must quote the merchant's recent request, "
                    "not a model-invented objective."
                )
        model = await service.submit(
            tenant_id, args, canonical_hash({"run": str(journal.run_id), "call": call.call_id})
        )
        return {
            **model.model_dump(mode="json"),
            "_wait": model.status in {"queued", "running"},
            "verified": model.status == "ready",
            "error": model.error,
            "activation": "Not activated; review the exact artifact in the Model panel",
        }

    async def recover_index(
        self, tenant_id: UUID, call: ManagerToolCall, journal: RunJournal
    ) -> JsonObject:
        args = IndexRecoveryInput.model_validate(call.arguments)
        key = canonical_hash({"run": str(journal.run_id), "call": call.call_id})
        async with self.database.transaction(tenant_id, write=True) as session:
            await self.guard(session, tenant_id, journal)
            receipts = RequestRepository(session, tenant_id)
            prior = await receipts.replay(
                scope="manager:index-recovery", key=key, request=call.arguments
            )
            if prior is None:
                query = select(CatalogIndexJob).where(CatalogIndexJob.tenant_id == tenant_id)
                active = await active_catalog_integration(session, tenant_id=tenant_id)
                if args.action == "retry_failed":
                    query = query.where(CatalogIndexJob.status == "failed")
                elif active is not None:
                    query = query.where(
                        CatalogIndexJob.integration_id == active.id,
                        CatalogIndexJob.status == "ready",
                    )
                else:
                    return {"error": "NO_ACTIVE_CATALOG"}
                row = await session.scalar(
                    query.order_by(CatalogIndexJob.updated_at.desc()).limit(1)
                )
                if row is None:
                    return {"error": "NO_ELIGIBLE_INDEX_JOB"}
                prior = {
                    "job_id": str(row.id),
                    "previous_version": row.source_version,
                    "policy": "OWNER_AUTHORIZED_LOCAL_PROJECTION_RECOVERY",
                    "run_id": str(journal.run_id),
                    "precondition": row.status,
                    "rollback": "Previous active projection retained until count verification",
                }
                if args.action == "rebuild_active":
                    row.source_version = canonical_hash(
                        {"previous": row.source_version, "receipt": key}
                    )
                row.status, row.failures, row.safe_error = "queued", 0, None
                row.lease_token = None
                row.lease_until = None
                row.available_at = utc_now()
                row.updated_at = utc_now()
                receipts.remember(
                    scope="manager:index-recovery",
                    key=key,
                    request=call.arguments,
                    response=RootModel[dict[str, object]](prior),
                )
            row = await session.scalar(
                select(CatalogIndexJob).where(
                    CatalogIndexJob.tenant_id == tenant_id,
                    CatalogIndexJob.id == UUID(str(prior["job_id"])),
                )
            )
            if row is None:
                return {"error": "INDEX_JOB_REMOVED"}
            return {
                "job_id": str(row.id),
                "status": row.status,
                "_wait": row.status in {"queued", "running"},
                "verified": row.status == "ready"
                and row.product_count == row.indexed_product_count,
                "error": "INDEX_RECOVERY_FAILED" if row.status == "failed" else None,
                "indexed_count": row.indexed_product_count,
            }

    async def repair_service(
        self, tenant_id: UUID, call: ManagerToolCall, journal: RunJournal
    ) -> JsonObject:
        args = RuntimeRepairInput.model_validate(call.arguments)
        settings = self.database.settings
        if not settings.local_operations_enabled or settings.local_runtime_id is None:
            return {"error": "LOCAL_SUPERVISOR_NOT_ENABLED", "verified": False}
        async with self.database.transaction(tenant_id, write=True) as session:
            await self.guard(session, tenant_id, journal)
            key = canonical_hash({"run": str(journal.run_id), "call": call.call_id})
            row = await session.scalar(
                select(RuntimeOperationRecord).where(
                    RuntimeOperationRecord.tenant_id == tenant_id,
                    RuntimeOperationRecord.idempotency_key == key,
                )
            )
            if row is None:
                row = RuntimeOperationRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    run_id=journal.run_id,
                    runtime_id=settings.local_runtime_id,
                    service=args.service,
                    status="queued",
                    idempotency_key=key,
                    evidence={
                        "policy": "OWNER_AUTHORIZED_LOCAL_RECOVERY",
                        "requires_fresh_failure_probe": True,
                    },
                    rollback={"strategy": "Restart with the prior owned launch configuration"},
                    created_at=utc_now(),
                    updated_at=utc_now(),
                    version=1,
                )
                session.add(row)
            elif row.created_at < utc_now() - timedelta(minutes=5) and row.status in {
                "queued",
                "running",
            }:
                row.status = "failed"
                row.outcome = {"error": "SUPERVISOR_VERIFICATION_TIMEOUT", "verified": False}
            return {
                "operation_id": str(row.id),
                "service": row.service,
                "status": row.status,
                "_wait": row.status in {"queued", "running"},
                **cast(JsonObject, row.outcome or {}),
            }
