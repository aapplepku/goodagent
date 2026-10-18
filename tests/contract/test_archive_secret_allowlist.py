"""Only verified archive digests receive this narrow secret-scanner exception."""

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "infra/public-export-archives.json"


def archive_allowlist() -> dict[str, object]:
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    rule = next(item for item in config["rules"] if item["id"] == "generic-api-key")
    matches = [
        item
        for item in rule["allowlists"]
        if item["description"].startswith("Verified archive SHA-256 values")
    ]
    assert len(matches) == 1
    return cast(dict[str, object], matches[0])


def test_allowlist_values_are_exact_hashes_of_retained_archives() -> None:
    allowance = archive_allowlist()
    assert allowance["condition"] == "AND"
    assert allowance["regexTarget"] == "secret"
    assert allowance["paths"] == [
        r"^(?:/source/|/reports/source/)?infra/public-export-archives\.json$"
    ]
    for allowed_path in (MANIFEST, f"/source/{MANIFEST}", f"/reports/source/{MANIFEST}"):
        assert re.search(
            r"^(?:/source/|/reports/source/)?infra/public-export-archives\.json$", allowed_path
        )
    assert set(allowance) == {"description", "condition", "regexTarget", "paths", "regexes"}
    expressions = allowance["regexes"]
    assert isinstance(expressions, list) and len(expressions) == 25
    assert len(expressions) == len(set(expressions))
    assert all(re.fullmatch(r"\^[a-f0-9]{64}\$", value) for value in expressions)
    digests = {expression[1:-1] for expression in expressions}
    manifest = json.loads((ROOT / MANIFEST).read_bytes())
    assert digests <= set(manifest.values())
    for relative, expected in manifest.items():
        if expected not in digests:
            continue
        path = ROOT / relative
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
        assert path.name.endswith((".gz", ".zip"))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "src/keys.json",
        "infra/public-export-archives.json.bak",
        "infra/other.json",
        "nested/infra/public-export-archives.json",
        "/source/nested/infra/public-export-archives.json",
        "/reports/source/nested/infra/public-export-archives.json",
        "/other/source/infra/public-export-archives.json",
        "/tmp/reports/source/infra/public-export-archives.json",
        "reports/source/infra/public-export-archives.json",
        "/reports/source-other/infra/public-export-archives.json",
        "/reports/infra/public-export-archives.json",
        "/reports/source/infra/public-export-archives.json.bak",
        "/reports/source/infra/public-export-archivesXjson",
        "/reports//source/infra/public-export-archives.json",
        "/reports/source/../infra/public-export-archives.json",
    ],
)
def test_archive_exception_does_not_match_other_paths(path: str) -> None:
    paths = archive_allowlist()["paths"]
    assert isinstance(paths, list)
    assert not any(re.search(expression, path) for expression in paths)


@pytest.mark.parametrize("path", [MANIFEST, f"/source/{MANIFEST}", f"/reports/source/{MANIFEST}"])
def test_archive_exception_does_not_match_unknown_or_extended_values(path: str) -> None:
    allowance = archive_allowlist()
    paths = allowance["paths"]
    assert isinstance(paths, list)
    path_matches = any(re.search(expression, path) for expression in paths)
    assert path_matches and allowance["condition"] == "AND"
    expressions = allowance["regexes"]
    assert isinstance(expressions, list)
    unknown = hashlib.sha256(b"synthetic-secret-control-not-a-credential").hexdigest()
    known = expressions[0][1:-1]
    for value in (
        unknown,
        "synthetic-secret-not-a-pinned-archive",
        "prefix" + known,
        known + "suffix",
        known + "\nextra",
    ):
        assert not (
            path_matches and any(re.search(expression, value) for expression in expressions)
        )
