"""Authored synthetic product families, not inferred compatibility or merchant data."""

from dataclasses import dataclass
from decimal import Decimal

from open_commerce.simulator.merchandising_models import CompatibilityEvidence
from open_commerce.simulator.models import ProductState, ProductVariantState
from open_commerce.simulator.randomness import RandomStreams

CATALOG_VERSION = "merchandising-catalog-v1"


@dataclass(frozen=True)
class ProductFamily:
    id: str
    category: str
    title: str
    description: str
    material: str
    use_case: str
    price_minor: int


FAMILIES = (
    ProductFamily(
        "hiking_boots",
        "footwear",
        "Waterproof Hiking Boots",
        "Ankle-supporting boots with a waterproof membrane "
        "and grippy soles for wet mountain trails.",
        "leather",
        "hiking",
        12000,
    ),
    ProductFamily(
        "running_shoes",
        "footwear",
        "Breathable Running Shoes",
        "Light mesh trainers with cushioned soles for road jogging in dry weather. Not waterproof.",
        "mesh",
        "running",
        9000,
    ),
    ProductFamily(
        "hiking_socks",
        "apparel",
        "Merino Hiking Socks",
        "Warm wool socks sized for the catalog hiking boots. "
        "A breathable insulating foot layer for long hikes.",
        "merino wool",
        "hiking",
        1800,
    ),
    ProductFamily(
        "rain_jackets",
        "apparel",
        "Packable Rain Jackets",
        "Light waterproof outerwear with a hood to keep the torso dry during wet walks and travel.",
        "recycled nylon",
        "rain protection",
        8000,
    ),
    ProductFamily(
        "hiking_backpacks",
        "outdoor",
        "Hiking Daypacks",
        "A 24-liter backpack for carrying water, lunch and trail essentials on a day hike.",
        "recycled nylon",
        "hiking",
        6500,
    ),
    ProductFamily(
        "camping_tents",
        "outdoor",
        "Two-Person Camping Tents",
        "A waterproof two-person shelter for overnight camping. Sleeping bags are sold separately.",
        "nylon",
        "camping",
        18000,
    ),
    ProductFamily(
        "sleeping_bags",
        "outdoor",
        "Three-Season Sleeping Bags",
        "An insulated adult sleeping bag for cool nights, "
        "sized to fit the catalog two-person tents.",
        "polyester",
        "camping",
        9500,
    ),
    ProductFamily(
        "wall_chargers",
        "electronics",
        "USB-C Wall Chargers",
        "A 65-watt USB-C Power Delivery wall power adapter. "
        "Requires a compatible USB-C charging cable, sold separately.",
        "polycarbonate",
        "device charging",
        3900,
    ),
    ProductFamily(
        "charging_cables",
        "electronics",
        "USB-C Charging Cables",
        "A two-meter 100-watt USB-C Power Delivery cable certified "
        "in this synthetic catalog for its 65-watt wall chargers.",
        "braided nylon",
        "device charging",
        1600,
    ),
    ProductFamily(
        "headphones",
        "electronics",
        "Wireless Noise-Cancelling Headphones",
        "Over-ear Bluetooth headphones that reduce background noise "
        "for listening on trains and at a desk.",
        "aluminum",
        "listening",
        15000,
    ),
    ProductFamily(
        "mugs",
        "home",
        "Ceramic Coffee Mugs",
        "A dishwasher-safe ceramic cup with a handle for hot coffee or tea at home.",
        "ceramic",
        "hot drinks",
        2200,
    ),
    ProductFamily(
        "food_containers",
        "home",
        "Nesting Food Containers",
        "Reusable sealed lunch containers that nest for compact kitchen storage. "
        "Not drinking cups.",
        "polypropylene",
        "food storage",
        3400,
    ),
)


def generate_merchandising_catalog(
    seed: int,
) -> tuple[list[ProductState], list[CompatibilityEvidence]]:
    products = []
    for family in FAMILIES:
        for index, brand in enumerate(("Northline", "Kanso", "Vale", "Mercer")):
            product_id = f"merch_{family.id}_{index + 1}"
            rng = RandomStreams(seed).rng(f"{CATALOG_VERSION}:{product_id}")
            price = family.price_minor + index * 300
            variants = [
                ProductVariantState(
                    id=f"{product_id}:v{v + 1}",
                    source_variant_id=f"{product_id}:v{v + 1}",
                    sku=f"MERCH-{family.id.upper().replace('_', '-')}-{index + 1:03}-{v + 1}",
                    title=("Standard", "Extended")[v],
                    price_minor=price + v * 500,
                    original_price_minor=price + v * 500,
                    cost_minor=(price + v * 500) * 52 // 100,
                    currency="USD",
                    inventory=240 if index == 0 else 90,
                    initial_inventory=240 if index == 0 else 90,
                )
                for v in range(2)
            ]
            products.append(
                ProductState(
                    id=product_id,
                    source_product_id=product_id,
                    title=f"{brand} {family.title}",
                    category=family.category,
                    brand=brand,
                    description_text=family.description,
                    tags=[family.category, family.use_case],
                    attributes={
                        "product_type": family.id,
                        "material": family.material,
                        "use_case": family.use_case,
                        "color_family": ("black", "green", "blue", "gray")[index],
                    },
                    quality_score=Decimal(str(round(rng.uniform(0.55, 0.90), 4))),
                    popularity_score=Decimal(str(round(rng.uniform(0.35, 0.65), 4))),
                    age_days=60,
                    excess_inventory=index == 0,
                    variants=variants,
                )
            )
    compatibility = [
        CompatibilityEvidence(
            anchor_product_id=anchor.id,
            complement_product_id=other.id,
            evidence_id=f"{CATALOG_VERSION}:{source}:{target}",
        )
        for source, target in (
            ("hiking_boots", "hiking_socks"),
            ("camping_tents", "sleeping_bags"),
            ("wall_chargers", "charging_cables"),
        )
        for anchor in products
        if anchor.attributes["product_type"] == source
        for other in products
        if other.attributes["product_type"] == target
    ]
    return products, compatibility
