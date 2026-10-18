"""Release identity agrees across Python, JavaScript and the public API schema."""

import json
import tomllib
from pathlib import Path

from packaging.version import Version

from open_commerce import __version__
from open_commerce.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_release_versions_are_consistent() -> None:
    expected = Version(__version__)
    assert Version(Settings(_env_file=None).app_version) == expected
    assert Version(Settings(_env_file=ROOT / ".env.example").app_version) == expected
    for path in ("pyproject.toml", "packages/backend/pyproject.toml"):
        with (ROOT / path).open("rb") as source:
            assert Version(tomllib.load(source)["project"]["version"]) == expected
    for path in ("package.json", "apps/web/package.json", "packages/sdk-typescript/package.json"):
        assert Version(json.loads((ROOT / path).read_bytes())["version"]) == expected
    assert Version(json.loads((ROOT / "openapi/openapi.json").read_bytes())["info"]["version"]) == (
        expected
    )
