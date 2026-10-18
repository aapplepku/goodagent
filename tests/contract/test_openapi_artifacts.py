import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.export_openapi import build_schema
from scripts.generate_ts_client import _client_source

ROOT = Path(__file__).resolve().parents[2]


def test_export_ignores_developer_environment_overrides() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/export_openapi.py"), "--check"],
        cwd=ROOT,
        env={
            **os.environ,
            "OPEN_COMMERCE_APP_NAME": "Local custom name",
            "OPEN_COMMERCE_APP_VERSION": "99.0.0",
            "OPEN_COMMERCE_CORS_ALLOW_ORIGINS": "invalid-local-json",
            "OPEN_COMMERCE_ENVIRONMENT": "production",
        },
        capture_output=True,
        text=True,
        check=True,
    )


def test_committed_openapi_schema_is_current() -> None:
    committed = json.loads((ROOT / "openapi" / "openapi.json").read_text(encoding="utf-8"))
    current = build_schema()

    assert committed == current


def test_generated_typescript_client_is_current() -> None:
    committed = (ROOT / "packages" / "sdk-typescript" / "src" / "client.ts").read_text(
        encoding="utf-8"
    )

    assert committed == _client_source()


def test_types_follow_schema_changes_not_a_handwritten_template(tmp_path: Path) -> None:
    schema = build_schema()
    meta = schema["components"]["schemas"]["MetaResponse"]
    meta["properties"]["contract_sentinel"] = {"type": "boolean"}
    meta["required"].append("contract_sentinel")
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
    generated = _client_source(changed)
    assert "contract_sentinel: boolean;" in generated
    assert generated == _client_source(changed)


def test_removed_write_routes_stay_absent_and_error_envelopes_are_documented() -> None:
    schema = build_schema()
    assert "post" not in schema["paths"]["/v1/search/rules"]
    assert "/v1/search/rules/{rule_id}" not in schema["paths"]
    assert "/v1/controller/evaluate" not in schema["paths"]
    response = schema["paths"]["/v1/goals"]["post"]["responses"]["422"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
