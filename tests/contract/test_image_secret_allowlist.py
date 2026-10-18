"""Only one public signing fingerprint in exact image fields is exempted."""

import hashlib
import re
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]


def allowance() -> dict[str, Any]:
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    assert config["extend"] == {"useDefault": True}
    rule = next(row for row in config["rules"] if row["id"] == "generic-api-key")
    records = [
        row for row in rule["allowlists"] if row["description"].startswith("Published Python")
    ]
    assert len(records) == 1
    return cast(dict[str, Any], records[0])


def allowed(path: str, match: str) -> bool:
    rule = allowance()
    return any(re.search(pattern, path) for pattern in rule["paths"]) and any(
        re.search(pattern, match) for pattern in rule["regexes"]
    )


def public_match() -> str:
    return str(allowance()["regexes"][0])[1:-1]


def test_exception_is_exact_public_fingerprint_with_context_and_path() -> None:
    rule = allowance()
    assert set(rule) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert rule["condition"] == "AND" and rule["regexTarget"] == "match"
    assert rule["paths"] == [r"^/data/(api|migrate|worker)\.(image-config|scan)\.json$"]
    assert len(rule["regexes"]) == 1
    match = public_match()
    assert re.fullmatch(r'GPG_KEY=[A-F0-9]{40}"', match)
    fingerprint = match.removeprefix("GPG_KEY=").removesuffix('"')
    assert hashlib.sha256(fingerprint.encode()).hexdigest() == (
        "6c3b7674b58d9f7266cd8b823ecf469b0a03d1bf2c8c24df1d0121d8e818f1fa"
    )


@pytest.mark.parametrize("service", ["api", "migrate", "worker"])
@pytest.mark.parametrize("suffix", ["image-config", "scan"])
def test_exact_image_findings_are_allowed(service: str, suffix: str) -> None:
    assert allowed(f"/data/{service}.{suffix}.json", public_match())


@pytest.mark.parametrize(
    "path",
    [
        "/data/web.image-config.json",
        "/data/shopper.scan.json",
        "/data/api.cdx.json",
        "/data/api.image-manifest.json",
        "/data/api.scan.json.bak",
        "api.scan.json",
        "/source/api.scan.json",
        "/tmp/data/api.scan.json",
        "/data/nested/api.scan.json",
        "/data/../data/api.scan.json",
        "/data//api.scan.json",
        "/data/apiXscanXjson",
        "/data/.env",
        "/data/credentials.json",
        "/data/api.scan.json/child",
    ],
)
def test_other_paths_are_not_allowed(path: str) -> None:
    assert not allowed(path, public_match())


def test_other_keys_values_or_extended_matches_are_not_allowed() -> None:
    match = public_match()
    for changed in (
        match.replace("GPG_KEY", "API_KEY"),
        match.replace("GPG_KEY", "OPENAI_API_KEY"),
        match.replace("GPG_KEY", "gpg_key"),
        match.replace("=7", "=8", 1),
        "prefix" + match,
        match + "suffix",
        match + "\nextra",
        match[:-1],
        match.replace("=", "=extra"),
        match.replace('"', 'extra"'),
    ):
        assert not allowed("/data/api.scan.json", changed)
