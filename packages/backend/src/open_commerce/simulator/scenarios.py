"""Versioned simulator scenario definitions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from open_commerce.core.enums import ActionType, AutonomyMode, Capability
from open_commerce.simulator.models import (
    CampaignState,
    CatalogGeneratorConfig,
    CustomerSegment,
    EconomicParameters,
    ScenarioDefinition,
    ScenarioId,
    ScenarioSummary,
    TrafficChannel,
)

SCENARIO_START = datetime(2026, 9, 1, tzinfo=UTC)


def _segments() -> list[CustomerSegment]:
    return [
        CustomerSegment(
            id="new_bargain",
            label="New bargain seeker",
            share=Decimal("0.24"),
            price_sensitivity=Decimal("1.35"),
            quality_preference=Decimal("0.28"),
            discount_elasticity=Decimal("1.15"),
            category_affinities={
                "apparel": Decimal("0.25"),
                "footwear": Decimal("0.20"),
                "outdoor": Decimal("0.16"),
                "electronics": Decimal("0.17"),
                "home": Decimal("0.22"),
            },
            base_conversion_adjustment=Decimal("0.04"),
            new_customer_probability=Decimal("0.90"),
        ),
        CustomerSegment(
            id="new_quality",
            label="New quality seeker",
            share=Decimal("0.18"),
            price_sensitivity=Decimal("0.65"),
            quality_preference=Decimal("0.92"),
            discount_elasticity=Decimal("0.38"),
            category_affinities={
                "apparel": Decimal("0.12"),
                "footwear": Decimal("0.20"),
                "outdoor": Decimal("0.25"),
                "electronics": Decimal("0.29"),
                "home": Decimal("0.14"),
            },
            new_customer_probability=Decimal("0.82"),
        ),
        CustomerSegment(
            id="returning_loyal",
            label="Returning loyal customer",
            share=Decimal("0.18"),
            price_sensitivity=Decimal("0.50"),
            quality_preference=Decimal("0.70"),
            discount_elasticity=Decimal("0.20"),
            category_affinities={
                "apparel": Decimal("0.20"),
                "footwear": Decimal("0.18"),
                "outdoor": Decimal("0.21"),
                "electronics": Decimal("0.17"),
                "home": Decimal("0.24"),
            },
            base_conversion_adjustment=Decimal("0.15"),
            new_customer_probability=Decimal("0.05"),
        ),
        CustomerSegment(
            id="category_enthusiast",
            label="Category enthusiast",
            share=Decimal("0.16"),
            price_sensitivity=Decimal("0.72"),
            quality_preference=Decimal("0.83"),
            discount_elasticity=Decimal("0.33"),
            category_affinities={
                "apparel": Decimal("0.10"),
                "footwear": Decimal("0.14"),
                "outdoor": Decimal("0.32"),
                "electronics": Decimal("0.30"),
                "home": Decimal("0.14"),
            },
            base_conversion_adjustment=Decimal("0.08"),
            new_customer_probability=Decimal("0.42"),
        ),
        CustomerSegment(
            id="gift_shopper",
            label="Gift shopper",
            share=Decimal("0.14"),
            price_sensitivity=Decimal("0.82"),
            quality_preference=Decimal("0.64"),
            discount_elasticity=Decimal("0.50"),
            category_affinities={
                "apparel": Decimal("0.18"),
                "footwear": Decimal("0.14"),
                "outdoor": Decimal("0.16"),
                "electronics": Decimal("0.24"),
                "home": Decimal("0.28"),
            },
            new_customer_probability=Decimal("0.66"),
        ),
        CustomerSegment(
            id="low_intent_browser",
            label="Low-intent browser",
            share=Decimal("0.10"),
            price_sensitivity=Decimal("1.05"),
            quality_preference=Decimal("0.26"),
            discount_elasticity=Decimal("0.54"),
            category_affinities={
                "apparel": Decimal("0.20"),
                "footwear": Decimal("0.20"),
                "outdoor": Decimal("0.20"),
                "electronics": Decimal("0.20"),
                "home": Decimal("0.20"),
            },
            base_conversion_adjustment=Decimal("-0.22"),
            new_customer_probability=Decimal("0.72"),
        ),
    ]


def _channels() -> list[TrafficChannel]:
    return [
        TrafficChannel(id="organic_direct", label="Organic/direct", base_sessions=980),
        TrafficChannel(id="paid_search", label="Paid search", base_sessions=0, paid=True),
        TrafficChannel(id="paid_social", label="Paid social", base_sessions=0, paid=True),
        TrafficChannel(id="email", label="Email", base_sessions=180),
        TrafficChannel(
            id="project_search",
            label="Storefront search/recommendations",
            base_sessions=420,
            search_surface=True,
        ),
    ]


def _campaigns() -> list[CampaignState]:
    return [
        CampaignState(
            id="paid_social_prospecting",
            name="Paid social prospecting",
            channel_id="paid_social",
            daily_budget_minor=18_000,
            initial_daily_budget_minor=18_000,
            max_reach=720,
            scale_minor=24_000,
            baseline_quality=Decimal("0.52"),
            saturation_penalty=Decimal("0.22"),
        ),
        CampaignState(
            id="paid_search_intent",
            name="Paid search intent",
            channel_id="paid_search",
            daily_budget_minor=26_000,
            initial_daily_budget_minor=26_000,
            max_reach=900,
            scale_minor=36_000,
            baseline_quality=Decimal("0.62"),
            saturation_penalty=Decimal("0.14"),
        ),
        CampaignState(
            id="paid_display_broad",
            name="Broad display retargeting",
            channel_id="paid_social",
            daily_budget_minor=34_000,
            initial_daily_budget_minor=34_000,
            max_reach=640,
            scale_minor=22_000,
            baseline_quality=Decimal("0.38"),
            saturation_penalty=Decimal("0.28"),
        ),
    ]


def _default_goal(
    name: str, objective: str, constraints: list[dict[str, str]]
) -> dict[str, object]:
    return {
        "name": name,
        "objective": objective,
        "constraints": constraints,
        "allowed_action_types": [
            ActionType.CREATE_DISCOUNT.value,
            ActionType.DISABLE_DISCOUNT.value,
            ActionType.SET_VARIANT_PRICE.value,
            ActionType.SET_SEARCH_BOOST.value,
            ActionType.SET_CAMPAIGN_BUDGET.value,
        ],
    }


def _default_policy() -> dict[str, object]:
    return {
        "default_autonomy": AutonomyMode.APPROVAL_REQUIRED.value,
        "simulator_mode": True,
        "max_discount_rate": "0.15",
        "max_daily_campaign_budget_change_rate": "0.25",
    }


SCENARIOS: dict[str, ScenarioDefinition] = {
    "acquisition_v1": ScenarioDefinition(
        id="acquisition_v1",
        version="2026-09-04.1",
        display_name="Acquire new customers",
        description="Balance acquisition growth, CAC, margin, and a bounded welcome discount.",
        seed=42,
        start_at=SCENARIO_START,
        catalog=CatalogGeneratorConfig(),
        customer_segments=_segments(),
        traffic_channels=_channels(),
        campaigns=_campaigns(),
        economics=EconomicParameters(),
        default_goal=_default_goal(
            "Acquire 200 new customers",
            "new_customers >= 200 over 30 days",
            [
                {"metric": "cac", "operator": "lte", "value": "40"},
                {"metric": "contribution_margin_rate", "operator": "gte", "value": "0.25"},
                {"metric": "discount_rate", "operator": "lte", "value": "0.15"},
            ],
        ),
        default_policy=_default_policy(),
        response_curves={"welcome_discount_elasticity": "moderate"},
    ),
    "excess_inventory_v1": ScenarioDefinition(
        id="excess_inventory_v1",
        version="2026-09-04.1",
        display_name="Clear excess inventory",
        description=(
            "Expose high-inventory product families while protecting margin and "
            "low-stock substitutes."
        ),
        seed=84,
        start_at=SCENARIO_START,
        catalog=CatalogGeneratorConfig(),
        customer_segments=_segments(),
        traffic_channels=_channels(),
        campaigns=_campaigns(),
        economics=EconomicParameters(),
        default_goal=_default_goal(
            "Reduce excess inventory units by 25%",
            "units_sold for excess inventory products increases",
            [
                {"metric": "contribution_margin_rate", "operator": "gte", "value": "0.30"},
                {"metric": "discount_budget", "operator": "lte", "value": "5000"},
            ],
        ),
        default_policy=_default_policy(),
        response_curves={"excess_inventory_search_exposure": "low_baseline"},
    ),
    "search_conversion_v1": ScenarioDefinition(
        id="search_conversion_v1",
        version="2026-09-04.1",
        display_name="Improve search conversion",
        description=(
            "Expose the trade-off between lexical, semantic, and margin-biased search outcomes."
        ),
        seed=126,
        start_at=SCENARIO_START,
        catalog=CatalogGeneratorConfig(),
        customer_segments=_segments(),
        traffic_channels=_channels(),
        campaigns=_campaigns(),
        economics=EconomicParameters(),
        default_goal=_default_goal(
            "Increase search-attributed purchases by 15%",
            "search_attributed_purchases increases without relevance loss",
            [
                {"metric": "search_attributed_purchases", "operator": "gte", "value": "1.15x"},
                {"metric": "relevance_ndcg_delta", "operator": "gte", "value": "-0.02"},
            ],
        ),
        default_policy=_default_policy(),
        response_curves={"hybrid_search_gap": "enabled"},
    ),
}

SIMULATOR_CAPABILITIES = {
    Capability.READ_CATALOG,
    Capability.READ_INVENTORY,
    Capability.READ_ORDERS,
    Capability.READ_CUSTOMER_COHORTS,
    Capability.READ_DISCOUNTS,
    Capability.WRITE_DISCOUNTS,
    Capability.WRITE_PRICE,
    Capability.WRITE_MERCHANDISING,
    Capability.READ_BEHAVIOR_EVENTS,
    Capability.READ_CAMPAIGNS,
    Capability.WRITE_CAMPAIGN_BUDGET,
}


def list_scenarios() -> list[ScenarioSummary]:
    """Return public scenario summaries in deterministic order."""

    return [
        ScenarioSummary(
            id=definition.id,
            version=definition.version,
            display_name=definition.display_name,
            description=definition.description,
            default_seed=definition.seed,
            product_count=definition.catalog.product_count,
            categories=definition.catalog.categories,
            capabilities=sorted(SIMULATOR_CAPABILITIES, key=lambda capability: capability.value),
            default_goal=definition.default_goal,
            default_policy=definition.default_policy,
        )
        for definition in sorted(SCENARIOS.values(), key=lambda scenario: scenario.id)
    ]


def get_scenario(scenario_id: str) -> ScenarioDefinition:
    """Resolve a scenario definition or raise KeyError."""

    return SCENARIOS[scenario_id]


def require_scenario_id(scenario_id: str) -> ScenarioId:
    """Validate a scenario id for dynamic inputs."""

    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    return SCENARIOS[scenario_id].id
