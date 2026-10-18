"""Seeded simulator catalog and history generation."""

from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from random import Random

from open_commerce.simulator.models import (
    CampaignState,
    CatalogGeneratorConfig,
    DailyMetrics,
    ProductState,
    ProductVariantState,
    ScenarioDefinition,
)
from open_commerce.simulator.randomness import RandomStreams

CATEGORY_WORDS: dict[str, list[str]] = {
    "apparel": ["linen", "layer", "studio", "thermal", "weekend"],
    "footwear": ["trail", "runner", "commute", "cushion", "weatherproof"],
    "outdoor": ["camp", "summit", "packable", "field", "alpine"],
    "electronics": ["smart", "portable", "wireless", "creator", "pro"],
    "home": ["ceramic", "linen", "modular", "ambient", "storage"],
}

BRANDS = ["Northline", "Kanso", "Vale", "Mercer", "Aster", "Juniper", "Signal", "Haven"]

PRICE_RANGES: dict[str, tuple[int, int]] = {
    "apparel": (1800, 12_000),
    "footwear": (5400, 18_000),
    "outdoor": (2200, 28_000),
    "electronics": (3900, 42_000),
    "home": (1600, 24_000),
}


def _money_from_decimal(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def generate_catalog(definition: ScenarioDefinition, seed: int) -> list[ProductState]:
    """Generate a deterministic rich catalog for a scenario."""

    config = definition.catalog
    streams = RandomStreams(seed)
    products: list[ProductState] = []
    per_category = config.product_count // len(config.categories)
    remainder = config.product_count % len(config.categories)

    for category_index, category in enumerate(config.categories):
        count = per_category + (1 if category_index < remainder else 0)
        for local_index in range(count):
            global_index = len(products)
            rng = streams.rng(f"catalog:{category}:{local_index}")
            products.append(
                _generate_product(definition, config, category, global_index, local_index, rng)
            )

    return products


def _generate_product(
    definition: ScenarioDefinition,
    config: CatalogGeneratorConfig,
    category: str,
    global_index: int,
    local_index: int,
    rng: Random,
) -> ProductState:
    word = CATEGORY_WORDS[category][local_index % len(CATEGORY_WORDS[category])]
    brand = BRANDS[(global_index + rng.randrange(len(BRANDS))) % len(BRANDS)]
    title = f"{brand} {word.title()} {category.title()} {local_index + 1:03d}"
    product_id = f"prod_{category}_{local_index + 1:04d}"
    cold_start = local_index % max(1, int(1 / config.cold_start_rate)) == 0
    excess_inventory = local_index % max(1, int(1 / config.excess_inventory_rate)) == 1
    low_stock = local_index % max(1, int(1 / config.low_stock_rate)) == 2

    if definition.id == "excess_inventory_v1" and category == "outdoor" and local_index < 80:
        excess_inventory = True
        low_stock = False
    if (
        definition.id == "search_conversion_v1"
        and category in {"electronics", "home"}
        and local_index < 45
    ):
        cold_start = False

    variant_count = rng.randint(config.variants_min, config.variants_max)
    variants = [
        _generate_variant(
            category, product_id, local_index, variant_index, excess_inventory, low_stock, rng
        )
        for variant_index in range(variant_count)
    ]
    quality = Decimal(str(round(rng.uniform(0.34, 0.98), 4)))
    popularity = Decimal(str(round(rng.uniform(0.05, 0.95), 4)))
    if cold_start:
        popularity = min(popularity, Decimal("0.18"))

    attributes = {
        "material": ["cotton", "recycled nylon", "aluminum", "ceramic", "mesh"][global_index % 5],
        "use_case": ["travel", "daily", "gift", "performance", "workspace"][local_index % 5],
        "color_family": ["black", "green", "blue", "white", "gray"][rng.randrange(5)],
    }
    tags = [category, word, attributes["use_case"], attributes["color_family"]]
    return ProductState(
        id=product_id,
        source_product_id=f"sim-{product_id}",
        title=title,
        category=category,
        brand=brand,
        description_text=(
            f"{title} for {attributes['use_case']} shoppers. "
            f"Features {attributes['material']} construction and "
            f"{attributes['color_family']} styling."
        ),
        tags=tags,
        attributes=attributes,
        quality_score=quality,
        popularity_score=popularity,
        age_days=rng.randint(0, 220),
        cold_start=cold_start,
        excess_inventory=excess_inventory,
        low_stock=low_stock,
        variants=variants,
    )


def _generate_variant(
    category: str,
    product_id: str,
    local_index: int,
    variant_index: int,
    excess_inventory: bool,
    low_stock: bool,
    rng: Random,
) -> ProductVariantState:
    low, high = PRICE_RANGES[category]
    base_price = rng.randint(low, high)
    variant_price = base_price + variant_index * rng.randint(250, 950)
    cost_ratio = Decimal(str(round(rng.uniform(0.42, 0.68), 4)))
    cost_minor = _money_from_decimal(Decimal(variant_price) * cost_ratio)
    if excess_inventory:
        inventory = rng.randint(180, 340)
    elif low_stock:
        inventory = rng.randint(1, 5)
    else:
        inventory = rng.randint(22, 110)
    variant_id = f"var_{product_id}_{variant_index + 1}"
    return ProductVariantState(
        id=variant_id,
        source_variant_id=f"sim-{variant_id}",
        sku=f"SIM-{category[:3].upper()}-{local_index + 1:04d}-{variant_index + 1}",
        title=f"Option {variant_index + 1}",
        price_minor=variant_price,
        original_price_minor=variant_price,
        cost_minor=cost_minor,
        currency="USD",
        inventory=inventory,
        initial_inventory=inventory,
        available=True,
    )


def generate_initial_history(
    definition: ScenarioDefinition,
    products: list[ProductState],
    campaigns: list[CampaignState],
    seed: int,
    days: int = 7,
) -> list[DailyMetrics]:
    """Generate deterministic pre-scenario aggregate history for initial metrics."""

    rng = RandomStreams(seed).rng("history:daily-metrics")
    metrics: list[DailyMetrics] = []
    inventory_units = sum(product.total_inventory for product in products)
    daily_ad_spend = sum(campaign.daily_budget_minor for campaign in campaigns if campaign.active)

    for offset in range(days, 0, -1):
        sessions = 1_450 + rng.randint(-90, 150)
        orders = max(0, int(sessions * Decimal("0.034")) + rng.randint(-4, 5))
        units = orders + rng.randint(0, max(1, orders // 5))
        gross = units * (5_800 + rng.randint(-450, 650))
        discounts = int(Decimal(gross) * Decimal("0.035"))
        cogs = int(Decimal(gross) * Decimal("0.54"))
        fees = int(Decimal(gross - discounts) * definition.economics.payment_fee_rate)
        contribution = gross - discounts - cogs - fees - daily_ad_spend
        metric_date = (definition.start_at - timedelta(days=offset)).date()
        metrics.append(
            DailyMetrics(
                metric_date=metric_date,
                day_index=-offset,
                is_history=True,
                sessions=sessions,
                impressions=sessions * 4,
                clicks=max(0, int(sessions * Decimal("0.11"))),
                carts=max(0, int(orders * Decimal("1.55"))),
                orders=orders,
                units_sold=units,
                new_customers=max(0, int(orders * Decimal("0.62"))),
                gross_revenue_minor=gross,
                discounts_minor=discounts,
                cogs_minor=cogs,
                variable_fees_minor=fees,
                ad_spend_minor=daily_ad_spend,
                contribution_profit_minor=contribution,
                conversion_rate=(Decimal(orders) / Decimal(sessions)).quantize(Decimal("0.0001")),
                cac_minor=int(daily_ad_spend / max(1, int(orders * Decimal("0.62")))),
                contribution_margin_rate=(
                    Decimal(contribution) / Decimal(gross) if gross > 0 else Decimal("0")
                ).quantize(Decimal("0.0001")),
                discount_rate=(Decimal(discounts) / Decimal(gross)).quantize(Decimal("0.0001")),
                search_attributed_purchases=max(0, int(orders * Decimal("0.20"))),
                ending_inventory_units=inventory_units,
            )
        )

    return metrics
