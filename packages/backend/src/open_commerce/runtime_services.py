"""Shared API/worker model configuration and observational service probes."""

from datetime import timedelta
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import select

from open_commerce.api.readiness import run_manager_status_checks
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.manager_agent.models import ManagerRuntimeComponent
from open_commerce.manager_agent.service import DurableManagerAgentService
from open_commerce.persistence.models.manager_runs import ManagerRunEventRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.openai_manager import OpenAIManagerProvider
from open_commerce.search.agent_tools import CatalogSearchRuntime
from open_commerce.stores.usage import admit_model_call


def manager_model_provider(settings: Settings) -> ManagerModelProvider | None:
    if settings.manager_model_provider == "deterministic":
        return None
    # Keep the API available with a truthful connection failure when credentials are absent.
    return OpenAIManagerProvider(
        api_key=settings.openai_api_key or SecretStr(""),
        model_id=settings.manager_model_id,
        base_url=settings.openai_api_base_url,
        timeout_seconds=settings.manager_model_timeout_seconds,
        max_input_bytes=settings.manager_model_max_input_bytes,
        usage_guard=admit_model_call if settings.runtime_profile != "legacy_demo" else None,
    )


def manager_service(
    database: RuntimeDatabase, search: CatalogSearchRuntime
) -> DurableManagerAgentService:
    settings = database.settings

    async def probe() -> list[ManagerRuntimeComponent]:
        checks = await run_manager_status_checks(settings)
        labels = {
            "postgres": "PostgreSQL",
            "redis": "Redis jobs",
            "qdrant": "Qdrant search",
            "manager_web": "Operator app",
            "shopper_web": "Shopper app",
            "worker": "Agent worker",
        }
        return [
            ManagerRuntimeComponent(
                key=check.name,
                label=labels.get(check.name, check.name),
                state="green" if check.ok else "red",
                detail=(
                    "Recent worker heartbeat verified"
                    if check.name == "worker"
                    else "Connection verified"
                )
                if check.ok
                else "No recent worker heartbeat; check the local worker and Redis connection"
                if check.name == "worker"
                else f"Unreachable: {check.detail}",
                latency_ms=check.latency_ms,
                observed_at=utc_now(),
                evidence_kind="probe",
                repair_available=settings.local_operations_enabled
                and check.name in {"manager_web", "shopper_web", "worker"},
            )
            for check in checks
        ]

    return DurableManagerAgentService(
        database,
        model_provider=manager_model_provider(settings),
        search_service=search,
        status_probe=probe,
    )


async def model_connection(
    database: RuntimeDatabase, tenant_id: UUID
) -> ManagerRuntimeComponent | None:
    if database.settings.manager_model_provider != "openai":
        return None
    async with database.transaction(tenant_id) as session:
        event = await session.scalar(
            select(ManagerRunEventRecord)
            .where(
                ManagerRunEventRecord.tenant_id == tenant_id,
                ManagerRunEventRecord.title.in_(["Model connected", "Model unavailable"]),
            )
            .order_by(ManagerRunEventRecord.created_at.desc())
            .limit(1)
        )
        if event is None:
            return None
        return ManagerRuntimeComponent(
            key="manager_agent",
            label="Conversation model",
            state="red"
            if event.title == "Model unavailable"
            else "green"
            if utc_now() - event.created_at < timedelta(minutes=5)
            else "unknown",
            detail=event.detail
            + " Last observed response; not a continuous connectivity guarantee.",
            observed_at=event.created_at,
            evidence_kind="model_call",
        )
