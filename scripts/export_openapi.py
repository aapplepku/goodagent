"""Export the FastAPI OpenAPI schema deterministically."""

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from open_commerce.api.main import create_app
from open_commerce.config import Settings

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "openapi" / "openapi.json"


class SchemaSettings(Settings):
    """Validate canonical defaults without reading deployment or developer settings."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def build_schema() -> dict[str, Any]:
    return create_app(SchemaSettings()).openapi()


def main() -> None:
    """Write the OpenAPI document."""

    schema = build_schema()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != source:
            raise SystemExit("OpenAPI schema is stale; run make openapi")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
