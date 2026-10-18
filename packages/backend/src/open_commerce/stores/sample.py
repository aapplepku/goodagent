"""Fixed public sample assets, never browser-selected filesystem paths."""

import json
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, Field


class SampleImage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    filename: str = Field(pattern=r"^[A-Z0-9]{10}\.jpg$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_url: str
    license: str


@lru_cache(maxsize=1)
def sample_images() -> dict[str, SampleImage]:
    manifest = json.loads(
        files("open_commerce.stores").joinpath("sample_data/manifest.json").read_text()
    )
    return {key: SampleImage.model_validate(value) for key, value in manifest.items()}


def sample_catalog_bytes() -> bytes:
    return files("open_commerce.stores").joinpath("sample_data/catalog.csv").read_bytes()


def sample_image_bytes(identifier: str) -> bytes:
    image = sample_images().get(identifier)
    if image is None:
        raise ValueError("Unknown bundled sample image")
    data = files("open_commerce.stores").joinpath("sample_data", image.filename).read_bytes()
    if sha256(data).hexdigest() != image.sha256:
        raise ValueError("Bundled sample image checksum mismatch")
    return data
