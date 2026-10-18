"""FastAPI application factory for the bootstrap control plane."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from open_commerce.api.activity import router as activity_router
from open_commerce.api.connectors import router as connectors_router
from open_commerce.api.controller import router as controller_router
from open_commerce.api.demo import router as demo_router
from open_commerce.api.errors import register_exception_handlers
from open_commerce.api.manager import router as manager_router
from open_commerce.api.middleware import RequestIdMiddleware
from open_commerce.api.ranking import router as ranking_router
from open_commerce.api.readiness import (
    aggregate_status,
    run_readiness_checks,
)
from open_commerce.api.schemas import (
    DependencyStatus,
    ErrorEnvelope,
    LiveResponse,
    MetaResponse,
    ReadinessResponse,
)
from open_commerce.api.search import router as search_router
from open_commerce.api.security import DemoSecurityMiddleware
from open_commerce.api.shopper import router as shopper_router
from open_commerce.api.simulator import router as simulator_router
from open_commerce.api.store_auth import router as store_auth_router
from open_commerce.api.stores import router as stores_router
from open_commerce.commerce.models import CommerceRuntime
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings, get_settings
from open_commerce.controller.durable import DurableControllerService
from open_commerce.controller.service import ControllerService
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.manager_agent.models import ManagerAgentRuntime
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.runtime_services import manager_model_provider, manager_service
from open_commerce.search.durable import DurableSearchService
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperAgentRuntime
from open_commerce.shopper_agent.service import DurableShopperAgentService
from open_commerce.simulator.durable import DurableSimulatorService
from open_commerce.simulator.service import SimulatorService
from open_commerce.telemetry.logging import configure_logging

ReadinessChecker = Callable[[Settings], Awaitable[list[DependencyStatus]]]


def create_app(
    settings: Settings | None = None,
    readiness_checker: ReadinessChecker = run_readiness_checks,
    simulator_service: SimulatorService | DurableSimulatorService | None = None,
    search_service: SearchService | DurableSearchService | None = None,
    controller_service: ControllerService | DurableControllerService | None = None,
    manager_agent_service: ManagerAgentRuntime | None = None,
    shopper_agent_service: ShopperAgentRuntime | None = None,
    commerce_service: CommerceRuntime | None = None,
) -> FastAPI:
    """Create the FastAPI app without performing network checks at import time."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    database = RuntimeDatabase(resolved_settings)
    resolved_simulator_service = simulator_service or (
        controller_service.simulator_service
        if controller_service
        else DurableSimulatorService(database)
    )
    resolved_controller_service = controller_service or (
        ControllerService(simulator_service=resolved_simulator_service)
        if isinstance(resolved_simulator_service, SimulatorService)
        else DurableControllerService(database)
    )
    resolved_search_service = search_service or DurableSearchService(database)

    model_provider = _manager_model_provider(resolved_settings)
    resolved_manager_agent_service = manager_agent_service or manager_service(
        database, resolved_search_service
    )
    resolved_shopper_agent_service = shopper_agent_service or DurableShopperAgentService(
        database,
        search_service=resolved_search_service,
        model_provider=model_provider,
    )
    resolved_commerce_service = commerce_service or DurableCommerceService(
        database, payment_provider=LocalTestPaymentProvider()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.runtime_profile == "legacy_demo" and isinstance(
            resolved_controller_service, DurableControllerService
        ):
            await database.initialize_tenant(resolved_settings.local_tenant_id)
            await resolved_controller_service.get_policy(
                tenant_id=resolved_settings.local_tenant_id
            )
        try:
            yield
        finally:
            if isinstance(resolved_search_service, DurableSearchService):
                await resolved_search_service.close()
            await database.close()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        summary="Local simulator, agent, search, and test-commerce control plane.",
        license_info={"name": "Apache-2.0", "identifier": "Apache-2.0"},
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
        responses={
            code: {"model": ErrorEnvelope}
            for code in (400, 401, 403, 404, 405, 409, 412, 413, 422, 429, 431, 500, 503)
        },
    )
    app.state.settings = resolved_settings
    app.state.readiness_checker = readiness_checker
    app.state.database = database
    app.state.simulator_service = resolved_simulator_service
    app.state.search_service = resolved_search_service
    app.state.controller_service = resolved_controller_service
    app.state.manager_agent_service = resolved_manager_agent_service
    app.state.shopper_agent_service = resolved_shopper_agent_service
    app.state.commerce_service = resolved_commerce_service
    app.add_middleware(DemoSecurityMiddleware, settings=resolved_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "accept",
            "content-type",
            "idempotency-key",
            "last-event-id",
            resolved_settings.request_id_header,
        ],
    )
    app.add_middleware(RequestIdMiddleware, request_id_header=resolved_settings.request_id_header)
    register_exception_handlers(app)
    app.include_router(controller_router)
    app.include_router(demo_router)
    app.include_router(manager_router)
    app.include_router(connectors_router)
    app.include_router(ranking_router)
    app.include_router(search_router)
    app.include_router(shopper_router)
    app.include_router(activity_router)
    app.include_router(simulator_router)
    app.include_router(store_auth_router)
    app.include_router(stores_router)

    logger = structlog.get_logger(__name__)
    if resolved_settings.runtime_profile == "legacy_demo":
        logger.warning(
            "auth.local_demo_only", warning="Not production authentication; loopback only"
        )

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    async def live() -> LiveResponse:
        return LiveResponse()

    @app.get(
        "/health/ready",
        response_model=ReadinessResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
        tags=["health"],
    )
    async def ready(response: Response) -> ReadinessResponse:
        dependencies = await readiness_checker(resolved_settings)
        readiness = aggregate_status(dependencies)
        if readiness != "ready":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status=readiness, dependencies=dependencies)

    @app.get("/v1/meta", response_model=MetaResponse, tags=["meta"])
    async def meta() -> MetaResponse:
        dependencies = await readiness_checker(resolved_settings)
        readiness = aggregate_status(dependencies)
        logger.info("meta.requested", readiness=readiness)
        return MetaResponse(
            app_name=resolved_settings.app_name,
            version=resolved_settings.app_version,
            environment=resolved_settings.environment,
            status=readiness,
            dependencies=dependencies,
        )

    return app


def _manager_model_provider(settings: Settings) -> ManagerModelProvider | None:
    return manager_model_provider(settings)


def main() -> None:
    """Run the development API server."""

    settings = get_settings()
    uvicorn.run(
        "open_commerce.api.main:create_app",
        factory=True,
        host=settings.api_host,
        port=8000,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
