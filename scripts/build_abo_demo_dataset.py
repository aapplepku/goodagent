#!/usr/bin/env python3
"""Build a small, deterministic image-backed demo catalog from Amazon ABO.

The source listings and image metadata remain under the Amazon Berkeley
Objects CC BY 4.0 license. Prices, availability, popularity, ratings, and all
engagement events produced here are synthetic demo fields.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import shutil
import urllib.request
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SOURCE_BASE = "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com"
TARGET_TYPES = (
    "GROCERY",
    "COFFEE",
    "TEA",
    "KITCHEN",
    "DRINKING_CUP",
    "HOME",
    "HOME_BED_AND_BATH",
    "OFFICE_PRODUCTS",
    "PET_SUPPLIES",
    "SPORTING_GOODS",
    "OUTDOOR_LIVING",
    "TOOLS",
    "BEAUTY",
    "HEALTH_PERSONAL_CARE",
    "SHOES",
    "HANDBAG",
)
TYPE_LABELS = {
    "GROCERY": "Grocery",
    "COFFEE": "Coffee & tea",
    "TEA": "Coffee & tea",
    "KITCHEN": "Kitchen",
    "DRINKING_CUP": "Kitchen",
    "HOME": "Home",
    "HOME_BED_AND_BATH": "Home",
    "OFFICE_PRODUCTS": "Office",
    "PET_SUPPLIES": "Pet supplies",
    "SPORTING_GOODS": "Sports & outdoors",
    "OUTDOOR_LIVING": "Sports & outdoors",
    "TOOLS": "Tools",
    "BEAUTY": "Beauty",
    "HEALTH_PERSONAL_CARE": "Wellness",
    "SHOES": "Apparel",
    "HANDBAG": "Apparel",
}
PRICE_RANGES = {
    "GROCERY": (3.49, 24.99),
    "COFFEE": (7.99, 54.99),
    "TEA": (4.99, 34.99),
    "KITCHEN": (8.99, 124.99),
    "DRINKING_CUP": (6.99, 39.99),
    "HOME": (11.99, 179.99),
    "HOME_BED_AND_BATH": (12.99, 159.99),
    "OFFICE_PRODUCTS": (6.99, 139.99),
    "PET_SUPPLIES": (5.99, 84.99),
    "SPORTING_GOODS": (9.99, 159.99),
    "OUTDOOR_LIVING": (12.99, 179.99),
    "TOOLS": (7.99, 179.99),
    "BEAUTY": (4.99, 79.99),
    "HEALTH_PERSONAL_CARE": (4.99, 89.99),
    "SHOES": (24.99, 139.99),
    "HANDBAG": (24.99, 179.99),
}


def _english(values: list[dict[str, Any]], *, limit: int) -> str:
    preferred = [
        item.get("value", "")
        for item in values
        if str(item.get("language_tag", "")).startswith("en_")
    ]
    return " ".join(str(preferred[0]).split())[:limit] if preferred else ""


def _records(listings_dir: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(listings_dir.glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                yield json.loads(line)


def _select_products(listings_dir: Path, *, per_type: int) -> list[dict[str, Any]]:
    selected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _records(listings_dir):
        product_type = str((item.get("product_type") or [{}])[0].get("value", ""))
        if product_type not in TARGET_TYPES or len(selected[product_type]) >= per_type:
            continue
        title = _english(item.get("item_name") or [], limit=160)
        image_id = str(item.get("main_image_id") or "")
        if not title or not image_id or len(title) < 8:
            continue
        selected[product_type].append(item)
        if all(len(selected[kind]) >= per_type for kind in TARGET_TYPES):
            break
    return [item for kind in TARGET_TYPES for item in selected[kind]]


def _image_paths(metadata_path: Path, image_ids: set[str]) -> dict[str, str]:
    paths: dict[str, str] = {}
    with gzip.open(metadata_path, "rt", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            image_id = row["image_id"]
            if image_id in image_ids:
                paths[image_id] = row["path"]
                if len(paths) == len(image_ids):
                    break
    return paths


def _catalog_rows(
    products: list[dict[str, Any]], image_paths: dict[str, str]
) -> list[dict[str, str | int | float]]:
    rng = random.Random(240901)
    rows: list[dict[str, str | int | float]] = []
    for ordinal, item in enumerate(products, start=1):
        product_type = str((item.get("product_type") or [{}])[0].get("value", "HOME"))
        item_id = str(item["item_id"])
        image_id = str(item["main_image_id"])
        bullets = [
            _english([value], limit=240)
            for value in item.get("bullet_point") or []
            if _english([value], limit=240)
        ][:3]
        nodes = item.get("node") or []
        category = TYPE_LABELS[product_type]
        node_name = str(nodes[0].get("node_name", "")) if nodes else ""
        if node_name:
            leaf = node_name.rstrip("/").split("/")[-1].strip()
            if leaf and leaf.casefold() != "categories":
                category = f"{category} > {leaf[:100]}"
        popularity = round(0.48 + rng.random() * 0.51, 4)
        rating = round(3.7 + rng.random() * 1.25, 2)
        review_count = rng.randint(18, 6800)
        price = round(rng.uniform(*PRICE_RANGES[product_type]), 2)
        rows.append(
            {
                "product_id": item_id,
                "title": _english(item.get("item_name") or [], limit=160),
                "description": " ".join(bullets)[:1200]
                or f"Image-backed {TYPE_LABELS[product_type].lower()} product from Amazon ABO.",
                "brand": _english(item.get("brand") or [], limit=120) or "Unbranded",
                "category": category,
                "variant_id": f"{item_id}-default",
                "sku": f"ABO-{ordinal:04d}",
                "price": f"{price:.2f}",
                "currency": "USD",
                "inventory_quantity": rng.randint(0, 180),
                "image_url": f"{SOURCE_BASE}/images/small/{image_paths[image_id]}",
                "updated_at": "2026-09-01T00:00:00Z",
                "tags": (
                    f"abo|demo|{TYPE_LABELS[product_type].lower().replace(' ', '-')}|image-backed"
                ),
                "popularity_score": popularity,
                "average_rating": rating,
                "review_count": review_count,
                "data_provenance": "Amazon Berkeley Objects metadata; demo fields synthetic",
            }
        )
    return rows


def _engagement_rows(catalog: list[dict[str, str | int | float]]) -> list[dict[str, Any]]:
    rng = random.Random(240902)
    weighted = sorted(catalog, key=lambda row: float(row["popularity_score"]), reverse=True)
    weights = [max(1, len(weighted) - index) for index in range(len(weighted))]
    start = datetime(2026, 7, 1, 12, tzinfo=UTC)
    events: list[dict[str, Any]] = []
    event_number = 1
    for session_number in range(1, 601):
        product = rng.choices(weighted, weights=weights, k=1)[0]
        product_id = str(product["product_id"])
        category = str(product["category"]).split(" > ")[0].lower()
        query_id = f"qry-{session_number:05d}"
        session_id = f"sess-{session_number:05d}"
        anonymous_id = f"anon-{((session_number - 1) % 180) + 1:04d}"
        occurred = start + timedelta(minutes=session_number * 137)
        position = rng.randint(1, 8)
        device = rng.choice(("mobile", "mobile", "desktop", "tablet"))
        country = rng.choice(("US", "US", "US", "CA", "GB", "AU"))
        sequence = ["search", "product_view"]
        if rng.random() < 0.48:
            sequence.append("add_to_cart")
        if sequence[-1] == "add_to_cart" and rng.random() < 0.43:
            sequence.append("purchase")
        for step, event_type in enumerate(sequence):
            is_search = event_type in {"search", "product_view"}
            is_purchase = event_type == "purchase"
            events.append(
                {
                    "event_id": f"evt-{event_number:06d}",
                    "event_type": event_type,
                    "occurred_at": (occurred + timedelta(seconds=step * 42))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "product_id": product_id,
                    "anonymous_id": anonymous_id,
                    "session_id": session_id,
                    "query_id": query_id if is_search else "",
                    "position": position if is_search else "",
                    "surface": "search" if is_search else "product_detail",
                    "query": f"popular {category} products" if is_search else "",
                    "device": device,
                    "country": country,
                    "quantity": 1 if event_type in {"add_to_cart", "purchase"} else "",
                    "revenue": product["price"] if is_purchase else "",
                    "currency": "USD" if is_purchase else "",
                    "data_provenance": "synthetic pseudonymous demo event",
                }
            )
            event_number += 1
    return events


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mirror_images(
    catalog: list[dict[str, str | int | float]], *, output_dir: Path, manifest_dir: Path
) -> None:
    image_dir = output_dir / "abo-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    for row in catalog:
        product_id = str(row["product_id"])
        source_url = str(row["image_url"])
        filename = f"{product_id}.jpg"
        target = image_dir / filename
        request = urllib.request.Request(
            source_url,
            headers={"User-Agent": "open-commerce-demo-dataset-builder/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        local_path = f"/abo-images/{filename}"
        row["image_url"] = local_path
        manifest.append(
            {
                "product_id": product_id,
                "local_path": local_path,
                "source_url": source_url,
                "sha256": digest,
                "license": "CC BY 4.0",
            }
        )
    _write_csv(manifest_dir / "image-sources.csv", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listings-dir", type=Path, required=True)
    parser.add_argument("--image-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path)
    parser.add_argument("--shopper-public-dir", type=Path)
    parser.add_argument("--per-type", type=int, default=3)
    args = parser.parse_args()

    products = _select_products(args.listings_dir, per_type=args.per_type)
    expected = len(TARGET_TYPES) * args.per_type
    if len(products) != expected:
        raise SystemExit(f"Expected {expected} products, found {len(products)}")
    image_paths = _image_paths(
        args.image_metadata, {str(item["main_image_id"]) for item in products}
    )
    if len(image_paths) != len(products):
        raise SystemExit("Image metadata is incomplete for the selected products")

    catalog = _catalog_rows(products, image_paths)
    engagement = _engagement_rows(catalog)
    image_root = args.shopper_public_dir or args.public_dir
    if image_root:
        _mirror_images(
            catalog,
            output_dir=image_root,
            manifest_dir=args.output_dir,
        )
        if args.public_dir and args.public_dir != image_root:
            shutil.copytree(
                image_root / "abo-images", args.public_dir / "abo-images", dirs_exist_ok=True
            )
    _write_csv(args.output_dir / "catalog.csv", catalog)
    _write_csv(args.output_dir / "engagement.csv", engagement)
    if args.public_dir:
        _write_csv(args.public_dir / "abo-catalog.csv", catalog)
        _write_csv(args.public_dir / "abo-engagement.csv", engagement)
    print(f"Wrote {len(catalog)} products and {len(engagement)} synthetic events")


if __name__ == "__main__":
    main()
