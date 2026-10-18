"""Generate committed API types with the pinned OpenAPI TypeScript toolchain."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "openapi" / "openapi.json"
OUTPUT = ROOT / "packages" / "sdk-typescript" / "src" / "client.ts"


def _client_source(schema_path: Path = SCHEMA_PATH) -> str:
    return subprocess.run(
        ["node", str(ROOT / "scripts" / "generate-ts-schema.mjs"), str(schema_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = _client_source()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != source:
            raise SystemExit("Generated TypeScript schema is stale; run make openapi")
        return
    OUTPUT.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
