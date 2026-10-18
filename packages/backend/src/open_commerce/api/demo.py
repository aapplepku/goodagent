"""Release-facing local-demo API aggregation routes."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from open_commerce.api.context import RequestContext, get_request_context
from open_commerce.api.pagination import paginate_items
from open_commerce.api.schemas import (
    AuditFeedEntry,
    AuditFeedResponse,
    CapabilitiesResponse,
    CapabilitySummary,
    GoalDraftRequest,
    GoalDraftResponse,
    InterventionListResponse,
    InterventionSummary,
    InventoryItem,
    InventoryResponse,
    MetricDefinition,
    MetricsDefinitionsResponse,
    MetricSeriesPoint,
    MetricsSeriesResponse,
    MetricsSummaryResponse,
    ProductDetail,
    ProductListResponse,
    ProductSummary,
    ProductVariantSummary,
)
from open_commerce.api.services import ControllerRuntime as ControllerService
from open_commerce.api.services import SimulatorRuntime as SimulatorService
from open_commerce.api.services import resolve
from open_commerce.controller.goal_interpretation import interpret_goal
from open_commerce.controller.merchandising_evidence import (
    MerchandisingEvidenceResponse,
    MerchandisingView,
    merchandising_evidence,
)
from open_commerce.controller.models import GoalCreateRequest
from open_commerce.core.enums import ActionStatus, MetricName
from open_commerce.core.money import Money
from open_commerce.simulator.durable import DurableSimulatorService
from open_commerce.simulator.engine import latest_runtime_metric, totals_for_metrics
from open_commerce.simulator.models import (
    DailyMetrics,
    MetricTotals,
    ProductState,
    SimulatorState,
)
from open_commerce.simulator.scenarios import list_scenarios
from open_commerce.simulator.service import SimulatorInstanceNotFoundError

router = APIRouter(tags=["demo"])


@router.get(
    "/v1/goals/{goal_id}/merchandising/{view}", response_model=MerchandisingEvidenceResponse
)
async def get_merchandising_evidence(
    goal_id: UUID,
    view: MerchandisingView,
    context: Annotated[RequestContext, Depends(get_request_context)],
    request: Request,
    product_id: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=80),
) -> MerchandisingEvidenceResponse:
    """Bounded tenant-owned, read-only observed economics and serving investigation."""
    service = cast(ControllerService, request.app.state.controller_service)
    goal = await resolve(service.get_goal(tenant_id=context.tenant_id, goal_id=goal_id))
    state = await resolve(
        service.simulator_service.get_full_state(
            tenant_id=context.tenant_id,
            instance_id=goal.simulator_instance_id,
        )
    )
    try:
        return MerchandisingEvidenceResponse.model_validate(
            merchandising_evidence(
                state,
                tenant_id=context.tenant_id,
                view=view,
                product_id=product_id,
                category=category,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid merchandising evidence scope") from exc


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name=MetricName.NEW_CUSTOMERS,
        label="New customers",
        unit="count",
        description="First-time simulated buyers attributed to the store during the period.",
        version="metric-new-customers-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.UNITS_SOLD,
        label="Units sold (whole store)",
        unit="count",
        description="Units sold across the whole store, not only the excess-inventory goal scope.",
        version="metric-units-sold-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.REVENUE,
        label="Gross revenue",
        unit="minor_money",
        description="Whole-store gross revenue before discounts and tax, in minor currency units.",
        version="metric-revenue-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.CAC,
        label="Customer acquisition cost",
        unit="minor_money",
        description=(
            "Paid acquisition spend divided by simulated new customers; "
            "unavailable at zero customers."
        ),
        version="metric-cac-v2",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.CONTRIBUTION_MARGIN_RATE,
        label="Contribution margin",
        unit="rate",
        description="Contribution profit divided by gross revenue before tax.",
        version="metric-contribution-margin-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.CONVERSION_RATE,
        label="Conversion rate",
        unit="rate",
        description="Orders divided by simulated store sessions.",
        version="metric-conversion-rate-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.DISCOUNT_RATE,
        label="Discount rate",
        unit="rate",
        description="Discount value divided by gross revenue.",
        version="metric-discount-rate-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.CONTRIBUTION_PROFIT,
        label="Contribution profit",
        unit="minor_money",
        description="Gross revenue less discounts, COGS, variable fees, and ad spend.",
        version="metric-contribution-profit-v1",
        freshness="empty",
    ),
    MetricDefinition(
        name=MetricName.SEARCH_ATTRIBUTED_PURCHASES,
        label="Search-attributed purchases",
        unit="count",
        description="Orders attributed to the simulated search surface.",
        version="metric-search-attributed-purchases-v1",
        freshness="empty",
    ),
)


def get_simulator_service(request: Request) -> SimulatorService:
    """Return the app-level simulator service."""

    return cast(SimulatorService, request.app.state.simulator_service)


def get_controller_service(request: Request) -> ControllerService:
    """Return the app-level controller service."""

    return cast(ControllerService, request.app.state.controller_service)


@router.get("/v1/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    context: Annotated[RequestContext, Depends(get_request_context)],
    controller_service: Annotated[ControllerService, Depends(get_controller_service)],
) -> CapabilitiesResponse:
    """Return local-demo capabilities and current request context."""

    policy = await resolve(controller_service.get_policy(tenant_id=context.tenant_id))
    return CapabilitiesResponse(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        roles=sorted(context.roles),
        default_autonomy=policy.default_mode,
        supported_scenarios=[scenario.id for scenario in list_scenarios()],
        supported_action_types=sorted(
            policy.allowed_action_types,
            key=lambda action_type: action_type.value,
        ),
        capabilities=[
            CapabilitySummary(
                key="simulator",
                label="Seeded simulator",
                status="available",
                detail="Runs fully locally with deterministic scenarios and no store credentials.",
            ),
            CapabilitySummary(
                key="controller",
                label="Policy-bound controller",
                status="available",
                detail=(
                    "Proposes, denies, approves, executes, reconciles, "
                    "and rolls back simulator actions."
                ),
            ),
            CapabilitySummary(
                key="search",
                label="Hybrid search playground",
                status="available",
                detail=(
                    "Uses local sparse, dense, and hybrid ranking with inspectable score traces."
                ),
            ),
            CapabilitySummary(
                key="shopify_shadow",
                label="Shopify shadow mode",
                status="teaser",
                detail=(
                    "Disabled until the connector milestone; no credentials are accepted in v0.1."
                ),
            ),
        ],
        limitations=[
            "No live provider secrets or paid model keys are required.",
            "All commerce writes are simulator-only in this release.",
            "Inventory quantity writes are not implemented.",
        ],
    )


@router.post("/v1/goals/draft", response_model=GoalDraftResponse)
async def draft_goal_route(
    payload: GoalDraftRequest,
    request: Request,
    context: Annotated[RequestContext, Depends(get_request_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=150)] = None,
) -> GoalDraftResponse:
    if payload.planning_mode == "deterministic":
        return await draft_goal(payload)
    from open_commerce.controller.inference import InferenceJournal, InferencePendingError
    from open_commerce.controller.model_goal_interpretation import interpret_with_model

    key = idempotency_key
    if not key:
        raise HTTPException(
            status_code=422, detail="A stable Idempotency-Key is required for model work"
        )
    try:
        interpreted = await interpret_with_model(
            InferenceJournal(request.app.state.database),
            tenant_id=context.tenant_id,
            text=payload.text,
            seed=payload.seed,
            idempotency_key=key,
        )
    except InferencePendingError as exc:
        raise HTTPException(
            status_code=409, detail="Model request is still pending; reuse the same key"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Model request unavailable or stopped; no deterministic fallback",
        ) from exc
    return GoalDraftResponse.model_validate(interpreted.model_dump())


async def draft_goal(payload: GoalDraftRequest) -> GoalDraftResponse:
    """Produce a bounded draft or explicit clarification, never an activation command."""
    if payload.planning_mode != "deterministic":
        raise HTTPException(status_code=503, detail="model-backed interpreter is not configured")
    interpreted = interpret_goal(payload.text, seed=payload.seed)
    return GoalDraftResponse.model_validate(interpreted.model_dump())


@router.post("/v1/goals/review", response_model=GoalDraftResponse)
async def review_goal_configuration(payload: GoalCreateRequest) -> GoalDraftResponse:
    """Review a typed configuration without inference, activation or an invented parser claim."""
    payload.review_hash = payload.configuration_hash
    return GoalDraftResponse(
        status="ready_for_review",
        draft=payload,
        interpretation_mode="typed_review",
        template_version="typed-review-v1",
        warnings=["Typed configuration only; no model interpretation was requested."],
    )


@router.get("/v1/metrics/definitions", response_model=MetricsDefinitionsResponse)
async def get_metric_definitions(
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> MetricsDefinitionsResponse:
    """Return supported metric definitions."""

    items, next_cursor = paginate_items(METRIC_DEFINITIONS, cursor=cursor, limit=limit)
    return MetricsDefinitionsResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/metrics/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
    context: Annotated[RequestContext, Depends(get_request_context)],
    simulator_service: Annotated[SimulatorService, Depends(get_simulator_service)],
    instance_id: UUID | None = None,
) -> MetricsSummaryResponse:
    """Return aggregate simulator metrics for the selected or latest instance."""

    state = await _optional_state(
        simulator_service=simulator_service,
        tenant_id=context.tenant_id,
        instance_id=instance_id,
    )
    if state is None:
        return MetricsSummaryResponse(
            instance_id=None,
            scenario_id=None,
            seed=None,
            totals=_zero_totals(),
            latest=None,
            freshness="empty",
            definitions=list(METRIC_DEFINITIONS),
        )
    latest = latest_runtime_metric(state)
    return MetricsSummaryResponse(
        instance_id=state.id,
        scenario_id=state.scenario_id,
        seed=state.seed,
        totals=totals_for_metrics(state.metrics, include_history=False),
        latest=latest,
        freshness="fresh" if latest is not None else "empty",
        definitions=[
            definition.model_copy(update={"freshness": "fresh" if latest is not None else "empty"})
            for definition in METRIC_DEFINITIONS
        ],
    )


@router.get("/v1/metrics/series", response_model=MetricsSeriesResponse)
async def get_metrics_series(
    context: Annotated[RequestContext, Depends(get_request_context)],
    simulator_service: Annotated[SimulatorService, Depends(get_simulator_service)],
    metric: MetricName = MetricName.NEW_CUSTOMERS,
    instance_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=60, ge=1, le=400),
) -> MetricsSeriesResponse:
    """Return one simulator metric series."""

    state = await _optional_state(
        simulator_service=simulator_service,
        tenant_id=context.tenant_id,
        instance_id=instance_id,
    )
    definition = _definition_for(metric)
    if state is None:
        return MetricsSeriesResponse(
            metric=metric,
            definition_version=definition.version,
            timezone="UTC",
            attribution_model="simulator_v1",
            freshness="empty",
            completeness_warnings=["No simulator instance has been created yet."],
            items=[],
            next_cursor=None,
        )
    points = [
        MetricSeriesPoint(
            timestamp=datetime.combine(item.metric_date, time.min, tzinfo=UTC),
            value=_metric_value(item, metric),
        )
        for item in state.metrics
        if not item.is_history
    ]
    items, next_cursor = paginate_items(points, cursor=cursor, limit=limit)
    warnings = [] if points else ["No simulated days have run yet."]
    if any(point.value is None for point in items):
        warnings.append("Some observations on this page are unavailable; null is not zero.")
    return MetricsSeriesResponse(
        metric=metric,
        definition_version=definition.version,
        timezone="UTC",
        attribution_model="simulator_v1",
        freshness="fresh" if points else "empty",
        completeness_warnings=warnings,
        items=items,
        next_cursor=next_cursor,
    )


@router.get("/v1/catalog/products", response_model=ProductListResponse)
async def list_catalog_products(
    context: Annotated[RequestContext, Depends(get_request_context)],
    simulator_service: Annotated[SimulatorService, Depends(get_simulator_service)],
    instance_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=24, ge=1, le=100),
) -> ProductListResponse:
    """Return a cursor page of simulator products."""

    state = await _optional_state(
        simulator_service=simulator_service,
        tenant_id=context.tenant_id,
        instance_id=instance_id,
    )
    if state is None:
        return ProductListResponse(items=[], next_cursor=None)
    products = [_product_summary(product, state) for product in state.products]
    items, next_cursor = paginate_items(products, cursor=cursor, limit=limit)
    return ProductListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/catalog/products/{product_id}", response_model=ProductDetail)
async def get_catalog_product(
    product_id: str,
    context: Annotated[RequestContext, Depends(get_request_context)],
    simulator_service: Annotated[SimulatorService, Depends(get_simulator_service)],
    instance_id: UUID | None = None,
) -> ProductDetail:
    """Return one simulator product detail."""

    state = await _state_or_404(
        simulator_service=simulator_service,
        tenant_id=context.tenant_id,
        instance_id=instance_id,
    )
    for product in state.products:
        if product.id == product_id:
            summary = _product_summary(product, state)
            return ProductDetail(
                **summary.model_dump(),
                description_text=product.description_text,
                attributes={key: str(value) for key, value in product.attributes.items()},
                variants=[
                    ProductVariantSummary(
                        id=variant.id,
                        sku=variant.sku,
                        title=variant.title,
                        price=Money(amount_minor=variant.price_minor, currency=variant.currency),
                        original_price=Money(
                            amount_minor=variant.original_price_minor,
                            currency=variant.currency,
                        ),
                        inventory=variant.inventory,
                        available=variant.available,
                    )
                    for variant in product.variants
                ],
                search_document_preview=product.description_text[:240],
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")


@router.get("/v1/catalog/inventory", response_model=InventoryResponse)
async def get_catalog_inventory(
    context: Annotated[RequestContext, Depends(get_request_context)],
    simulator_service: Annotated[SimulatorService, Depends(get_simulator_service)],
    instance_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> InventoryResponse:
    """Return inventory summaries."""

    state = await _optional_state(
        simulator_service=simulator_service,
        tenant_id=context.tenant_id,
        instance_id=instance_id,
    )
    if state is None:
        return InventoryResponse(items=[], next_cursor=None)
    rows = [
        InventoryItem(
            product_id=product.id,
            title=product.title,
            category=product.category,
            inventory_units=product.total_inventory,
            stock_state=_stock_state(product),
        )
        for product in state.products
    ]
    items, next_cursor = paginate_items(rows, cursor=cursor, limit=limit)
    return InventoryResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/interventions", response_model=InterventionListResponse)
async def list_interventions(
    context: Annotated[RequestContext, Depends(get_request_context)],
    controller_service: Annotated[ControllerService, Depends(get_controller_service)],
    status_filter: ActionStatus | None = Query(default=None, alias="status"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> InterventionListResponse:
    """Return action/intervention summaries."""

    response = await resolve(
        controller_service.list_actions(
            tenant_id=context.tenant_id,
            status=status_filter,
        )
    )
    rows = [
        InterventionSummary(
            id=record.action.id,
            run_id=record.action.run_id,
            goal_id=record.action.goal_id,
            type=record.action.intent.type,
            status=record.action.status,
            policy_outcome=record.policy_decision.outcome.value,
            summary=record.action.intent.rationale,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in response.items
    ]
    items, next_cursor = paginate_items(rows, cursor=cursor, limit=limit)
    return InterventionListResponse(items=items, next_cursor=next_cursor)


@router.get("/v1/audit", response_model=AuditFeedResponse)
async def list_audit_feed(
    context: Annotated[RequestContext, Depends(get_request_context)],
    controller_service: Annotated[ControllerService, Depends(get_controller_service)],
    action_id: UUID | None = None,
    event_type: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditFeedResponse:
    """Return a redacted tenant audit feed from controller action records."""

    records = (await resolve(controller_service.list_actions(tenant_id=context.tenant_id))).items
    rows = [
        AuditFeedEntry(
            id=entry.id,
            action_id=entry.action_id,
            event_type=entry.event_type,
            actor_role=entry.actor_role.value,
            message=entry.message,
            occurred_at=entry.occurred_at,
            details=entry.details,
        )
        for record in records
        for entry in record.audit
        if (action_id is None or entry.action_id == action_id)
        and (event_type is None or entry.event_type == event_type)
    ]
    rows.sort(key=lambda item: (item.occurred_at, str(item.id)))
    items, next_cursor = paginate_items(rows, cursor=cursor, limit=limit)
    return AuditFeedResponse(items=items, next_cursor=next_cursor)


async def _optional_state(
    *,
    simulator_service: SimulatorService,
    tenant_id: UUID,
    instance_id: UUID | None,
) -> SimulatorState | None:
    if instance_id is not None:
        try:
            return await resolve(
                simulator_service.get_full_state(tenant_id=tenant_id, instance_id=instance_id)
            )
        except SimulatorInstanceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="instance not found",
            ) from exc
    if isinstance(simulator_service, DurableSimulatorService):
        instances = await simulator_service.list_instances(tenant_id=tenant_id)
        if not instances:
            return None
        latest = max(instances, key=lambda state: (state.current_time, state.day, str(state.id)))
        return await simulator_service.get_full_state(tenant_id=tenant_id, instance_id=latest.id)
    states = simulator_service.store.list_for_tenant(tenant_id)
    if not states:
        return None
    return max(states, key=lambda state: (state.current_time, state.day, str(state.id)))


async def _state_or_404(
    *,
    simulator_service: SimulatorService,
    tenant_id: UUID,
    instance_id: UUID | None,
) -> SimulatorState:
    state = await _optional_state(
        simulator_service=simulator_service,
        tenant_id=tenant_id,
        instance_id=instance_id,
    )
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="instance not found")
    return state


def _zero_totals() -> MetricTotals:
    return MetricTotals(
        days=0,
        sessions=0,
        orders=0,
        units_sold=0,
        new_customers=0,
        gross_revenue_minor=0,
        discounts_minor=0,
        cogs_minor=0,
        variable_fees_minor=0,
        ad_spend_minor=0,
        contribution_profit_minor=0,
        search_attributed_purchases=0,
        conversion_rate=Decimal("0"),
        cac_minor=None,
        contribution_margin_rate=Decimal("0"),
    )


def _definition_for(metric: MetricName) -> MetricDefinition:
    for definition in METRIC_DEFINITIONS:
        if definition.name == metric:
            return definition
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported metric")


def _metric_value(metric: DailyMetrics, name: MetricName) -> str | None:
    mapping = {
        MetricName.NEW_CUSTOMERS: metric.new_customers,
        MetricName.CAC: metric.cac_minor,
        MetricName.REVENUE: metric.gross_revenue_minor,
        MetricName.CONTRIBUTION_PROFIT: metric.contribution_profit_minor,
        MetricName.CONTRIBUTION_MARGIN_RATE: metric.contribution_margin_rate,
        MetricName.CONVERSION_RATE: metric.conversion_rate,
        MetricName.DISCOUNT_RATE: metric.discount_rate,
        MetricName.UNITS_SOLD: metric.units_sold,
        MetricName.SEARCH_ATTRIBUTED_PURCHASES: metric.search_attributed_purchases,
    }
    if name not in mapping:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported metric")
    value = mapping[name]
    return None if value is None else str(value)


def _product_summary(product: ProductState, state: SimulatorState) -> ProductSummary:
    variant = min(product.variants, key=lambda item: item.price_minor)
    return ProductSummary(
        product_id=product.id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        price=Money(amount_minor=variant.price_minor, currency=variant.currency),
        inventory_units=product.total_inventory,
        stock_state=_stock_state(product),
        quality_score=product.quality_score,
        popularity_score=product.popularity_score,
        tags=product.tags,
        index_status="not_checked",
        source_updated_at=state.current_time,
        active_action_count=None,
    )


def _stock_state(product: ProductState) -> str:
    if product.total_inventory == 0:
        return "out"
    if product.excess_inventory:
        return "excess"
    if product.low_stock:
        return "low"
    return "normal"
