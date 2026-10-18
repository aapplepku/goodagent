"""Source disclosure excludes copied material without clearing runtime attribution."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts import export_public_source as exporter
from scripts.dependency_attribution import require_attribution
from scripts.source_only_notices import (
    COLLECTIONS,
    DERIVED_HASHES,
    archive_bytes,
    derive,
    digest,
    exclusion_text,
    public_file,
    public_retention,
    verify_public_collections,
)
from scripts.verify_release_legal import audit_source_notices, tar_contents, verify_collection_files

ROOT = Path(__file__).resolve().parents[2]


def originals(directory: str) -> tuple[bytes, bytes]:
    policy = COLLECTIONS[directory]
    values = tuple((ROOT / directory / policy[key]).read_bytes() for key in ("manifest", "archive"))
    return values[0], values[1]


@pytest.mark.parametrize("directory", COLLECTIONS)
def test_exact_derivative_preserves_survivors_and_cannot_qualify_runtime(directory: str) -> None:
    original = originals(directory)
    policy = COLLECTIONS[directory]
    names = [f"{directory}/{policy[key]}" for key in ("manifest", "archive")]
    # The exported test suite can recheck derived bytes without private originals.
    if digest(original[0]) == DERIVED_HASHES[names[0]]:
        derived = original
        old_files = None
    else:
        derived = derive(directory, *original)
        assert derived == derive(directory, *original)
        old_files = tar_contents(original[1])
    manifest = json.loads(derived[0])
    files = tar_contents(derived[1])
    assert manifest["complete"] and not manifest["attribution_complete"]
    assert not manifest["source_distribution"]["runtime_redistribution_qualified"]
    assert verify_collection_files(manifest["packages"], files)
    assert all(
        digest(raw) == DERIVED_HASHES[name] for name, raw in zip(names, derived, strict=True)
    )
    for package in manifest["packages"]:
        identity = f"{package['name']}@{package['version']}"
        if identity in policy["excluded"]:
            name = f"{identity}/SOURCE_ONLY_OMISSION.txt"
            assert package["files"] == {name: digest(exclusion_text(identity))}
            assert files[name] == exclusion_text(identity)
            assert not set(package["excluded_files"]) & files.keys()
            assert not any(n.startswith(identity + "/") and n != name for n in files)
        elif old_files is not None:
            assert all(files[name] == old_files[name] for name in package["files"])
    with pytest.raises(ValueError, match="Missing upstream attribution"):
        require_attribution(manifest["packages"], files)


def test_public_export_and_reexport_have_identical_hash_bound_collections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [*DERIVED_HASHES, "infra/public-export-archives.json"]
    for name in paths:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    first = tmp_path / ".opencommerce/first"
    exporter.export(tmp_path, exporter.inventory(tmp_path, paths), first)
    records = verify_public_collections(first)
    assert sum(row["excluded_files"] for row in records) == 78
    report = audit_source_notices_for_copy(first)
    assert report["blocked_occurrences"] == 7 and not report["attribution_complete"]
    retained = json.loads((first / paths[-1]).read_bytes())
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", retained)
    second = tmp_path / ".opencommerce/second"
    exporter.export(first, exporter.inventory(first, paths), second)
    assert verify_public_collections(second) == records
    for path in paths:
        assert (first / path).read_bytes() == (second / path).read_bytes()


def audit_source_notices_for_copy(root: Path) -> dict[str, object]:
    # Inventory inputs are unchanged upstream evidence, not copied affected implementation.
    name = "security/third-party/qdrant-1.19.1/upstream.spdx.json.gz"
    (root / name).write_bytes((ROOT / name).read_bytes())
    return audit_source_notices(root)


@pytest.mark.parametrize("change", ["manifest", "archive", "restored-under-new-name", "provenance"])
def test_changed_or_reintroduced_material_cannot_use_public_profile(change: str) -> None:
    directory = next(iter(COLLECTIONS))
    policy = COLLECTIONS[directory]
    names = [f"{directory}/{policy[key]}" for key in ("manifest", "archive")]
    raw = originals(directory)
    derived = raw if digest(raw[0]) == DERIVED_HASHES[names[0]] else derive(directory, *raw)
    contents = dict(zip(names, derived, strict=True))
    if change in {"manifest", "provenance"}:
        manifest = json.loads(contents[names[0]])
        manifest["source_distribution"]["original_archive_sha256"] = "0" * 64
        contents[names[0]] = json.dumps(manifest).encode()
    elif change == "archive":
        contents[names[1]] += b"tampered"
    else:
        files = tar_contents(contents[names[1]])
        files["other@1/restored.rs"] = b"synthetic restored dependency implementation"
        contents[names[1]] = archive_bytes(files)
    with pytest.raises(ValueError, match="exact reviewed original"):
        public_file(names[0], contents.__getitem__)


def test_retention_cannot_silently_accept_changed_archive() -> None:
    raw = (ROOT / "infra/public-export-archives.json").read_bytes()
    derived = public_retention(raw)
    assert public_retention(derived) == derived
    changed = json.loads(raw)
    changed[next(name for name in DERIVED_HASHES if name.endswith(".tar.gz"))] = "0" * 64
    with pytest.raises(ValueError, match="retention identity"):
        public_retention(json.dumps(changed).encode())


def test_actual_frontend_collector_consumes_disclosed_source_bundle(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the actual frontend collector")
    directory = "security/third-party/sharp-libvips-1.3.4"
    policy = COLLECTIONS[directory]
    names = [f"{directory}/{policy[key]}" for key in ("manifest", "archive")]
    raw = originals(directory)
    derived = raw if digest(raw[0]) == DERIVED_HASHES[names[0]] else derive(directory, *raw)
    for name, data in zip(names, derived, strict=True):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    table = f"{directory}/THIRD-PARTY-NOTICES.md"
    (tmp_path / table).write_bytes((ROOT / table).read_bytes())
    for name, version in [("next", "15.5.27"), ("@img/sharp-libvips-linux-arm64", "1.3.4")]:
        for base in [tmp_path, tmp_path / "apps/web/.next/standalone"]:
            package = base / "node_modules" / name
            package.mkdir(parents=True)
            (package / "package.json").write_text(json.dumps({"name": name, "version": version}))
        installed = tmp_path / "node_modules" / name
        if name == "next":
            (installed / "LICENSE").write_text("Synthetic installed Next license fixture\n")
        else:
            (installed / "README.md").write_text("Synthetic installed native package\n")
            (installed / "versions.json").write_text(json.dumps(json.loads(derived[0])["versions"]))
    result = subprocess.run(
        [node, str(ROOT / "scripts/collect-web-notices.mjs"), str(tmp_path / "web"), "web"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    output = tmp_path / "web/third-party/@img/sharp-libvips-linux-arm64@1.3.4"
    assert (output / "native-notices.tar.gz").read_bytes() == derived[1]
    manifest = json.loads((output / "native-manifest.json").read_bytes())
    with pytest.raises(ValueError, match="Missing upstream attribution"):
        require_attribution(manifest["packages"], tar_contents(derived[1]))
