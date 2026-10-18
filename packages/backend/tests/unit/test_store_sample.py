"""Bundled image IDs cannot be used as arbitrary filesystem/network paths."""

import io

import pytest
from PIL import Image

from open_commerce.providers.catalog_images import ImageIngestionError, SafeCatalogImages
from open_commerce.stores.import_validation import validate_import
from open_commerce.stores.sample import sample_catalog_bytes, sample_images


async def test_sample_validates_with_real_hashed_bounded_images() -> None:
    _, products, errors = validate_import(sample_catalog_bytes().decode(), "sample.csv")
    assert not errors and len(products) == 48
    assert len(sample_images()) == 48
    for product in products:
        assert product.description_text and product.primary_image_url
        image = await SafeCatalogImages().fetch(product.primary_image_url)
        with Image.open(io.BytesIO(image)) as decoded:
            assert decoded.format == "PNG" and max(decoded.size) <= 1600


@pytest.mark.parametrize(
    "url",
    [
        "sample-abo:../../.env",
        "sample-abo:/etc/passwd",
        "sample-abo:UNKNOWN",
        "sample-abo:B07QC4DZ2L/../other",
        "/abo-images/B07QC4DZ2L.jpg",
    ],
)
async def test_sample_rejects_non_allowlisted_paths(url: str) -> None:
    with pytest.raises(ImageIngestionError):
        await SafeCatalogImages().fetch(url)
