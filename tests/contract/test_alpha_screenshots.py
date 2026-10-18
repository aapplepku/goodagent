"""Public interface screenshots retain their fixture scope and exact pixel identity."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image
from scripts.export_public_source import RETAINED_ASSETS, omission

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs/assets/alpha"


def test_current_screenshots_have_exact_reviewed_identities_and_dimensions() -> None:
    manifest = json.loads((MEDIA / "manifest.json").read_bytes())
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "synthetic_fixture_screenshots"
    records = manifest["images"]
    assert len(records) == 4
    assert {Path(row["path"]).name for row in records} == {
        "owner-products-desktop.png",
        "owner-products-mobile.png",
        "shopper-results-desktop.png",
        "shopper-results-mobile.png",
    }
    for record in records:
        path = ROOT / record["path"]
        assert path.parent == MEDIA
        assert not path.is_symlink()
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert checksum == record["sha256"] == RETAINED_ASSETS[record["path"]]
        assert omission(record["path"]) is None
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (record["width"], record["height"])
            assert image.size in {(1440, 1000), (390, 844)}
            assert not image.info, "Selected frames must not add unreviewed metadata"


def test_fixture_media_does_not_claim_real_model_or_release_approval() -> None:
    manifest = json.loads((MEDIA / "manifest.json").read_bytes())
    fixture = manifest["fixture"]
    assert fixture["model_provider"] == "deterministic"
    assert fixture["real_model_calls"] == 0
    assert fixture["synthetic_prices_and_stock"] is True
    assert fixture["real_payments"] is False
    assert fixture["product_images"] is False
    assert manifest["capture"]["pixel_edits"] is False
    assert manifest["capture"]["private_traces_included"] is False
    assert manifest["capture"]["publication_approved"] is False
    assert manifest["capture"]["release_qualified"] is False
    window = manifest["capture_window_utc"]
    start, end = (
        datetime.fromisoformat(window["started"]),
        datetime.fromisoformat(window["finished"]),
    )
    assert start.utcoffset() is not None and end.utcoffset() is not None
    assert start < end
    assert (ROOT / manifest["source_test"]).is_file()
    assert len(manifest["implementation_source_tree_sha256"]) == 64


def test_current_brand_gallery_has_reviewed_distinct_bytes_and_truthful_scope() -> None:
    directory = MEDIA / "20261018-current"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "synthetic_fixture_screenshots"
    assert manifest["implementation_source_tree_sha256"] == (
        "c9e090dbc1fc54721d12b0876cccf0ca73bcb339d4df6ab2c7453fa532c7a50d"
    )
    assert manifest["source_file_count"] == 1802
    assert manifest["source_unchanged_during_run"] is True
    fixture = manifest["fixture"]
    assert fixture["products"] == 2 and fixture["variants"] == 3
    assert fixture["product_images_in_selected_scenes"] is False
    assert fixture["image_delivery_markers_attached_after_selected_scenes"] is True
    assert fixture["model_provider"] == "deterministic" and fixture["real_model_calls"] == 0
    assert fixture["synthetic_prices_and_stock"] is True
    assert fixture["real_payments"] is False
    for flag in (
        "pixel_edits",
        "masks_applied_to_selected_frames",
        "private_traces_included",
        "publication_approved",
        "release_qualified",
    ):
        assert manifest["capture"][flag] is False
    window = manifest["capture_window_utc"]
    start, end = map(datetime.fromisoformat, (window["started"], window["finished"]))
    assert start.utcoffset() is not None and end.utcoffset() is not None and start < end
    for key in ("source_inventory_sha256", "source_test_sha256"):
        assert len(manifest[key]) == 64 and all(c in "0123456789abcdef" for c in manifest[key])
    assert (ROOT / manifest["source_test"]).is_file()
    assert len(manifest["images"]) == 4
    assert {Path(row["path"]).name for row in manifest["images"]} == {
        "catalog-review-resumed-1440x1000.png",
        "catalog-review-resumed-390x844.png",
        "private-preview-1440x1000.png",
        "private-preview-390x844.png",
    }
    for record in manifest["images"]:
        path = ROOT / record["path"]
        assert path.parent == directory and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert record["sha256"] == RETAINED_ASSETS[record["path"]]
        assert omission(record["path"]) is None
        with Image.open(path) as image:
            assert image.format == "PNG" and not image.info
            assert image.size == (record["width"], record["height"])
            assert image.size in {(1440, 1000), (390, 844)}
    assert {path.name for path in directory.iterdir()} == {
        "manifest.json",
        *(Path(row["path"]).name for row in manifest["images"]),
    }


def test_current_gallery_keeps_historical_manifest_and_links_separate() -> None:
    assert hashlib.sha256((MEDIA / "manifest.json").read_bytes()).hexdigest() == (
        "bfd9aab33cb5c1949c088c81c97d250c85f843fa745826e4e1f7733ae6cd0d33"
    )
    readme = (ROOT / "README.md").read_text()
    gallery = (ROOT / "docs/ALPHA_SCREENSHOTS.md").read_text()
    manifest = json.loads((MEDIA / "20261018-current/manifest.json").read_bytes())
    for image in manifest["images"]:
        assert image["path"].removeprefix("docs/") in gallery
        if image["width"] == 1440:
            assert image["path"] in readme
    assert "Historical Gallery" in gallery and "assets/alpha/manifest.json" in gallery
    assert "Basic mode" in readme and "AI disconnected" in readme
    assert "synthetic" in readme and "not design mockups" in gallery


def test_selected_result_capture_precedes_synthetic_image_attachment() -> None:
    source = (ROOT / "apps/web/e2e/self-service.spec.ts").read_text()
    assert source.index('await captures(preview, "private-preview")') < source.index(
        "await verifyStoreWelcomeImages(preview, testInfo, readiness)"
    )
    assert 'await expect(preview.locator(".product-card img")).toHaveCount(0)' in source
