"""Provenance and join-contract checks for the image-backed ABO demo bundle."""

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATASET = ROOT / "examples" / "datasets" / "amazon-berkeley-objects"


def test_abo_catalog_is_image_backed_and_engagement_is_synthetic() -> None:
    with (DATASET / "catalog.csv").open(encoding="utf-8", newline="") as source:
        catalog = list(csv.DictReader(source))
    with (DATASET / "engagement.csv").open(encoding="utf-8", newline="") as source:
        engagement = list(csv.DictReader(source))
    with (DATASET / "image-sources.csv").open(encoding="utf-8", newline="") as source:
        image_sources = {row["product_id"]: row for row in csv.DictReader(source)}

    product_ids = {row["product_id"] for row in catalog}
    assert len(catalog) == 48
    assert len(product_ids) == 48
    assert all(row["image_url"] == f"/abo-images/{row['product_id']}.jpg" for row in catalog)
    assert set(image_sources) == product_ids
    assert all(
        row["source_url"].startswith(
            "https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/images/small/"
        )
        and row["license"] == "CC BY 4.0"
        and len(row["sha256"]) == 64
        for row in image_sources.values()
    )
    for row in image_sources.values():
        for app in ("web", "shopper"):
            image_path = ROOT / "apps" / app / "public" / row["local_path"].lstrip("/")
            assert image_path.is_file()
            assert hashlib.sha256(image_path.read_bytes()).hexdigest() == row["sha256"]
    assert all("demo fields synthetic" in row["data_provenance"] for row in catalog)

    assert len(engagement) >= 1_500
    assert {row["product_id"] for row in engagement} <= product_ids
    assert all(row["anonymous_id"].startswith("anon-") for row in engagement)
    assert all(row["data_provenance"] == "synthetic pseudonymous demo event" for row in engagement)
    assert not any("@" in value for row in engagement for value in row.values())
