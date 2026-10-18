"""A public tokenizer checksum is exempt only at its exact verifier field/path."""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
from scripts.verify_learned_search_runtime import MODEL_HASHES

from open_commerce.search.learned_embeddings import MODEL_FILES

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = "scripts/verify_learned_search_runtime.py"


def allowance() -> dict[str, Any]:
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    assert config["extend"] == {"useDefault": True}
    rule = next(item for item in config["rules"] if item["id"] == "generic-api-key")
    matches = [
        item
        for item in rule["allowlists"]
        if item["description"].startswith("Verified MiniLM tokenizer file checksum")
    ]
    assert len(matches) == 1
    return cast(dict[str, Any], matches[0])


def public_match() -> str:
    return f'tokenizer.json": "{MODEL_HASHES["tokenizer.json"]}"'


def allowed(path: str, match: str) -> bool:
    rule = allowance()
    return any(re.search(pattern, path) for pattern in rule["paths"]) and any(
        re.search(pattern, match) for pattern in rule["regexes"]
    )


def test_only_pinned_model_checksum_with_exact_field_context_is_allowed() -> None:
    rule = allowance()
    assert set(rule) == {"description", "condition", "regexTarget", "paths", "regexes"}
    assert rule["condition"] == "AND" and rule["regexTarget"] == "match"
    assert MODEL_FILES["tokenizer.json"] == ("tokenizer.json", MODEL_HASHES["tokenizer.json"])
    assert len(rule["regexes"]) == 1
    assert rule["regexes"][0] == r'^tokenizer\.json": "' + MODEL_HASHES["tokenizer.json"] + '"$'
    assert rule["paths"] == [
        r"^(?:/source/|/reports/source/)?scripts/verify_learned_search_runtime\.py$"
    ]


@pytest.mark.parametrize("prefix", ["", "/source/", "/reports/source/"])
def test_exact_scan_and_history_locations_are_allowed(prefix: str) -> None:
    assert allowed(prefix + VERIFIER, public_match())


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "scripts/other.py",
        VERIFIER + ".bak",
        VERIFIER + "/child",
        "nested/" + VERIFIER,
        "/tmp/source/" + VERIFIER,
        "/reports/source/nested/" + VERIFIER,
        "/reports/source/../" + VERIFIER,
        "/reports//source/" + VERIFIER,
        "/reports/source-other/" + VERIFIER,
        "scripts/verify_learned_search_runtimeXpy",
    ],
)
def test_other_paths_still_require_secret_review(path: str) -> None:
    assert not allowed(path, public_match())


def test_other_fields_values_and_extended_matches_are_not_exempt() -> None:
    original = public_match()
    for match in (
        original.replace("tokenizer.json", "api_key"),
        original.replace("tokenizer.json", "tokenizerXjson"),
        original.replace(MODEL_HASHES["tokenizer.json"], "synthetic-not-a-public-checksum"),
        original.replace(MODEL_HASHES["tokenizer.json"], MODEL_HASHES["model.onnx"]),
        "prefix" + original,
        original + "suffix",
        original + "\nextra",
        original[:-1],
    ):
        assert not allowed(VERIFIER, match)
