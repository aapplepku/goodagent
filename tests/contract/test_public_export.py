"""Public source staging never inherits private Git history or ambient files."""

import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest
from scripts import export_public_source as exporter
from scripts.export_public_source import export, inventory, omission, validate_destination


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "apps/web/.env.local",
        "qa/claude/report.md",
        ".git/config",
        "examples/datasets/unrelated.zip",
        "apps/shopper/.next/server.js",
        "scripts/claude_exchange.py",
        "tests/contract/test_claude_handoff.py",
        ".opencommerce/session.json",
        "plans/private.md",
        "apps/api/key.pem",
        "apps/api/private.env",
        "infra/docker/hosted.env",
        "apps/web/PRIVATE.ENV.backup",
        "apps/web/.ENV.LOCAL",
        "apps/api/.env~",
        "examples/datasets/unrelated.ZIP",
        "examples/datasets/unrelated.tar.gz",
        "examples/datasets/unrelated.7z",
        "examples/datasets/unrelated.WHL",
        "docs/private.cab",
        "docs/private.lz4",
        "docs/private.cpio",
        "docs/private.unknown",
        "examples/datasets/unrelated.pdf",
        "examples/datasets/amazon-berkeley-objects/unrelated.md",
        "examples/datasets/amazon-berkeley-objects/customer-export.csv",
        "packages/backend/src/open_commerce/stores/sample_data/customer-export.csv",
        "docs/private.png",
        "apps/shopper/public/private.jpeg",
        "apps/shopper/public/shopper-grocery-spread.png",
        "apps/web/public/recording.mp4",
        "examples/eval/merchandising-decisions-v2/hosted/original/api-evidence.json",
        "examples/eval/merchandising-decisions-v2/validation/remote-delivery.json",
        "examples/eval/merchandising-decisions-v2/validation/REMOTE-DELIVERY.JSON",
    ],
)
def test_private_source_is_excluded(path: str) -> None:
    assert omission(path)


@pytest.mark.parametrize("path", ["../README.md", "/etc/passwd", "apps/../.env", "C:/key", "a\\b"])
def test_path_escapes_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        omission(path)


def test_export_is_exact_and_history_free(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "candidate"
    source.mkdir()
    (source / "README.md").write_text("Synthetic public source\n")
    (source / ".env").write_text("PRIVATE_DATA=never-export\n")
    (source / ".git").mkdir()
    (source / ".git/config").write_text("private history metadata")
    manifest = inventory(source, ["README.md", ".env", ".git/config"])
    assert list(manifest["excluded"]) == [".env", ".git/config"]
    checksum = export(source, manifest, output)
    public = json.loads((output / "SOURCE_SNAPSHOT.json").read_bytes())
    assert public["source_tree_sha256"] == checksum
    assert set(p.name for p in output.iterdir()) == {"README.md", "SOURCE_SNAPSHOT.json"}
    assert "excluded" not in public and not (output / ".git").exists()
    with pytest.raises(ValueError, match="new destination"):
        export(source, manifest, output)


def test_tamper_symlink_and_private_manifest_rejected(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "candidate"
    source.mkdir()
    (source / "README.md").write_text("original")
    manifest = inventory(source, ["README.md"])
    (source / "README.md").write_text("changed")
    with pytest.raises(ValueError, match="source changed"):
        export(source, manifest, output)
    assert not output.exists()
    (source / "README.md").unlink()
    (source / ".env").write_text("private")
    (source / "README.md").symlink_to(source / ".env")
    with pytest.raises(ValueError, match="symlink"):
        inventory(source, ["README.md"])
    manifest["files"][0]["path"] = ".env"
    with pytest.raises(ValueError, match="private/unselected"):
        export(source, manifest, output)


def test_public_templates_and_untracked_runnable_source_are_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [
        ".env.example",
        "infra/docker/hosted.env.example",
        "apps/shopper/Dockerfile",
        "packages/backend/src/open_commerce/stores/sample_data/catalog.csv",
        "openapi/openapi.json",
        "scripts/setup_self_hosted.py",
        "packages/backend/src/open_commerce/persistence/migrations/env.py",
    ]
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("public fixture")
    monkeypatch.setattr(
        exporter,
        "RETAINED_ASSETS",
        {paths[3]: exporter.digest(b"public fixture")},
    )
    assert len(inventory(tmp_path, paths)["files"]) == len(paths)
    export(tmp_path, inventory(tmp_path, paths), tmp_path / ".opencommerce/candidate")
    assert (tmp_path / ".opencommerce/candidate" / paths[-1]).is_file()


def test_credential_failure_does_not_repeat_secret(tmp_path: Path) -> None:
    credential = "sk-" + "proj-" + "x" * 40
    (tmp_path / "README.md").write_text(credential)
    with pytest.raises(ValueError, match="credential-shaped") as error:
        inventory(tmp_path, ["README.md"])
    assert credential not in str(error.value)


def test_only_explicit_public_ci_substitution_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / ".github/workflows").mkdir(parents=True)
    (source / "infra/github").mkdir(parents=True)
    (source / ".github/workflows/ci.yml").write_text("private CI guard")
    (source / "infra/github/public-ci.yml").write_text("public CI template")
    manifest = inventory(source, [".github/workflows/ci.yml"])
    export(source, manifest, tmp_path / "candidate")
    assert (tmp_path / "candidate/.github/workflows/ci.yml").read_text() == "public CI template"
    assert (source / ".github/workflows/ci.yml").read_text() == "private CI guard"
    manifest["files"][0]["source"] = ".github/workflows/ci.yml"
    with pytest.raises(ValueError, match="substitution"):
        export(source, manifest, tmp_path / "other")


def test_excluded_files_are_never_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_read(_path: Path) -> bytes:
        pytest.fail("Excluded private source was opened")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    paths = [
        "apps/api/private.env",
        "examples/datasets/private.ZIP",
        "docs/private.tar.gz",
        "docs/private.pdf",
        "docs/private.png",
        "examples/datasets/amazon-berkeley-objects/private.csv",
        "examples/eval/merchandising-decisions-v2/hosted/original/api-evidence.json",
        "examples/eval/merchandising-decisions-v2/validation/remote-delivery.json",
    ]
    report = inventory(tmp_path, paths)
    assert not report["files"]
    assert set(report["excluded"]) == set(paths)


@pytest.mark.parametrize("path", sorted(exporter.PRIVATE_EVIDENCE))
def test_private_evidence_cannot_be_forced_into_export(tmp_path: Path, path: str) -> None:
    (tmp_path / "README.md").write_text("Synthetic fixture\n")
    manifest = inventory(tmp_path, ["README.md"])
    manifest["files"][0]["path"] = path
    destination = tmp_path / ".opencommerce/candidate"
    with pytest.raises(ValueError, match="private/unselected"):
        export(tmp_path, manifest, destination)
    assert not destination.exists()


def test_sanitized_hosted_summary_is_exported_without_private_originals(tmp_path: Path) -> None:
    path = "examples/eval/merchandising-decisions-v2/validation/hosted-public-summary.json"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    public = json.loads((exporter.ROOT / path).read_bytes())
    target.write_text(json.dumps(public))
    manifest = inventory(tmp_path, [path, *sorted(exporter.PRIVATE_EVIDENCE)])
    destination = tmp_path / ".opencommerce/candidate"
    export(tmp_path, manifest, destination)
    assert json.loads((destination / path).read_bytes()) == public
    assert all(not (destination / private).exists() for private in exporter.PRIVATE_EVIDENCE)
    assert public["kind"] == "sanitized_historical_hosted_summary"
    assert len(public["original_records_retained_privately"]) == 2
    assert all(
        len(record["sha256"]) == 64 for record in public["original_records_retained_privately"]
    )
    original, later = public["runs"]
    assert (original["id"], later["id"]) == (34065619247, 34153571264)
    assert original["successful_jobs"] == 6
    assert original["failed_job"]["conclusion"] == "failure"
    assert original["failed_job"]["steps_recorded"] == 0
    assert later["authorization_job"]["conclusion"] == "failure"
    assert later["qualification_job"]["conclusion"] == "skipped"
    for run in public["runs"]:
        assert run["status"] == "completed" and run["conclusion"] == "failure"
        assert run["whole_run_passed"] is False
        assert run["retry_dispatched"] is False


@pytest.mark.parametrize("relative", [".git/candidate", "apps/candidate", "scripts/list.json"])
def test_inventory_and_export_destination_guard(tmp_path: Path, relative: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="destination"):
        validate_destination(source, source / relative)
    validate_destination(source, source / ".opencommerce/candidate")
    validate_destination(source, tmp_path / "outside")


def test_symlink_destination_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".opencommerce").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        validate_destination(source, source / ".opencommerce/candidate")


@pytest.mark.parametrize("archive_type", ["text", "tar"])
def test_retained_archives_have_pinned_bytes_and_inspected_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archive_type: str
) -> None:
    def archive(content: bytes) -> bytes:
        if archive_type == "text":
            return gzip.compress(content)
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as handle:
            member = tarfile.TarInfo("LICENSE")
            member.size = len(content)
            handle.addfile(member, io.BytesIO(content))
        return output.getvalue()

    name = "security/notices.tar.gz" if archive_type == "tar" else "security/report.json.gz"
    target = tmp_path / name
    target.parent.mkdir()
    target.write_bytes(archive(b"public evidence"))
    pins = {name: exporter.digest(target.read_bytes())}
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", pins)
    assert inventory(tmp_path, [name])["files"]
    target.write_bytes(archive(b"changed"))
    with pytest.raises(ValueError, match="archive changed"):
        inventory(tmp_path, [name])
    secret = b"sk-" + b"proj-" + b"x" * 40
    target.write_bytes(archive(secret))
    pins[name] = exporter.digest(target.read_bytes())
    with pytest.raises(ValueError, match="credential-shaped") as error:
        inventory(tmp_path, [name])
    assert secret.decode() not in str(error.value)


def test_archive_expansion_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    name = "security/report.json.gz"
    target = tmp_path / name
    target.parent.mkdir()
    target.write_bytes(gzip.compress(b"x" * 100))
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", {name: exporter.digest(target.read_bytes())})
    monkeypatch.setattr(exporter, "MAX_EXPANDED_BYTES", 10)
    with pytest.raises(ValueError, match="expansion"):
        inventory(tmp_path, [name])


def test_archive_cannot_bypass_review_by_renaming(tmp_path: Path) -> None:
    target = tmp_path / "docs/notes.txt"
    target.parent.mkdir()
    target.write_bytes(gzip.compress(b"private"))
    with pytest.raises(ValueError, match="unapproved archive content"):
        inventory(tmp_path, ["docs/notes.txt"])


@pytest.mark.parametrize(
    "magic",
    [
        b"MSCF",
        b"\x04\x22\x4d\x18",
        b"\x02\x21\x4c\x18",
        b"070701",
        b"070702",
        b"070707",
        b"\x71\xc7",
        b"\xc7\x71",
    ],
)
def test_other_archive_formats_cannot_hide_in_text_or_gzip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, magic: bytes
) -> None:
    target = tmp_path / "docs/notes.txt"
    target.parent.mkdir()
    content = magic + b"synthetic archive header"
    target.write_bytes(content)
    with pytest.raises(ValueError, match="unapproved archive content"):
        inventory(tmp_path, ["docs/notes.txt"])
    relative = "security/report.json.gz"
    target = tmp_path / relative
    target.parent.mkdir()
    target.write_bytes(gzip.compress(content))
    monkeypatch.setattr(
        exporter, "RETAINED_ARCHIVES", {relative: exporter.digest(target.read_bytes())}
    )
    with pytest.raises(ValueError, match="nested archive"):
        inventory(tmp_path, [relative])


def test_nested_archive_is_not_treated_as_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "security/report.json.gz"
    target = tmp_path / name
    target.parent.mkdir()
    target.write_bytes(gzip.compress(gzip.compress(b"private")))
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", {name: exporter.digest(target.read_bytes())})
    with pytest.raises(ValueError, match="nested archive"):
        inventory(tmp_path, [name])


@pytest.mark.parametrize("name", [".env", "qa/notes.txt", "license.txt"])
def test_retained_tar_names_and_metadata_are_inspected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as handle:
        member = tarfile.TarInfo(name)
        member.size = 7
        if name == "license.txt":
            member.pax_headers = {"comment": "/Users/synthetic/private-project"}
        handle.addfile(member, io.BytesIO(b"license"))
    relative = "security/notices.tar.gz"
    path = tmp_path / relative
    path.parent.mkdir()
    path.write_bytes(data.getvalue())
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", {relative: exporter.digest(data.getvalue())})
    with pytest.raises(ValueError, match="private|workstation"):
        inventory(tmp_path, [relative])


def test_upstream_license_paths_are_not_runtime_environment_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as handle:
        for name in ["env_logger@0.11.11/LICENSE", "shaderc-sys/build/glslang/LICENSE"]:
            member = tarfile.TarInfo(name)
            member.size = 7
            handle.addfile(member, io.BytesIO(b"license"))
    relative = "security/notices.tar.gz"
    path = tmp_path / relative
    path.parent.mkdir()
    path.write_bytes(data.getvalue())
    monkeypatch.setattr(exporter, "RETAINED_ARCHIVES", {relative: exporter.digest(data.getvalue())})
    assert inventory(tmp_path, [relative])["files"]


@pytest.mark.parametrize(
    "relative",
    [
        "apps/web/public/unreviewed.csv",
        "apps/shopper/public/unreviewed.CSV",
        "docs/unreviewed.CsV",
        "examples/onboarding/unreviewed.csv",
        "packages/sdk-typescript/unreviewed.csv",
        "tests/fixtures/unreviewed.csv",
        "scripts/unreviewed.csv",
        "infra/unreviewed.csv",
        "security/unreviewed.csv",
    ],
)
def test_unreviewed_csv_is_excluded_before_read_and_cannot_be_manifested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    content = b"product_id,title\nfixture,Synthetic product\n"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    target.chmod(0o644)

    def unexpected_read(_path: Path) -> bytes:
        pytest.fail("Unreviewed CSV was opened")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    selected = inventory(tmp_path, [relative])
    assert selected["files"] == []
    assert selected["excluded"] == {relative: "unreviewed media or dataset file"}
    manifest = {
        "schema_version": 1,
        "files": [
            {
                "path": relative,
                "source": relative,
                "sha256": exporter.digest(content),
                "bytes": len(content),
                "mode": 0o644,
            }
        ],
    }
    output = tmp_path / ".opencommerce/candidate"
    with pytest.raises(ValueError, match="private/unselected"):
        export(tmp_path, manifest, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "relative",
    [
        "apps/web/public/abo-catalog.csv",
        "apps/web/public/abo-engagement.csv",
        "apps/web/public/sample-catalog.csv",
        "apps/web/public/sample-engagement.csv",
    ],
)
def test_reviewed_public_csv_preserves_bytes_and_rejects_changed_content(
    tmp_path: Path, relative: str
) -> None:
    content = (exporter.ROOT / relative).read_bytes()
    assert exporter.RETAINED_ASSETS[relative] == exporter.digest(content)
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    manifest = inventory(tmp_path, [relative])
    output = tmp_path / ".opencommerce/candidate"
    export(tmp_path, manifest, output)
    assert (output / relative).read_bytes() == content

    changed = content + b"\n"
    target.write_bytes(changed)
    with pytest.raises(ValueError, match="retained asset changed"):
        inventory(tmp_path, [relative])
    rejected = tmp_path / ".opencommerce/changed"
    with pytest.raises(ValueError, match="retained asset changed"):
        export(tmp_path, manifest, rejected)
    assert not rejected.exists()

    # A refreshed inventory hash cannot substitute for the reviewed asset hash.
    manifest["files"][0]["sha256"] = exporter.digest(changed)
    manifest["files"][0]["bytes"] = len(changed)
    with pytest.raises(ValueError, match="retained asset changed"):
        export(tmp_path, manifest, rejected)
    assert not rejected.exists()


def test_reviewed_asset_has_exact_identity_and_changed_bytes_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = "docs/assets/fixture.png"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG\x00synthetic image fixture")
    monkeypatch.setattr(
        exporter, "RETAINED_ASSETS", {relative: exporter.digest(target.read_bytes())}
    )
    manifest = inventory(tmp_path, [relative])
    export(tmp_path, manifest, tmp_path / ".opencommerce/candidate")
    assert (tmp_path / ".opencommerce/candidate" / relative).read_bytes() == target.read_bytes()
    target.write_bytes(b"\x89PNG\x00different private image")
    with pytest.raises(ValueError, match="retained asset changed"):
        inventory(tmp_path, [relative])
    with pytest.raises(ValueError, match="retained asset changed"):
        export(tmp_path, manifest, tmp_path / ".opencommerce/other")
    assert not (tmp_path / ".opencommerce/other").exists()


@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.7\nsynthetic document",
        b"\x89PNG\r\n",
        b"GIF89a",
        b"\xff\xd8\xff",
        b"x\x00y",
        b"\xff",
    ],
)
def test_binary_content_renamed_as_text_is_rejected(tmp_path: Path, content: bytes) -> None:
    target = tmp_path / "docs/notes.md"
    target.parent.mkdir()
    target.write_bytes(content)
    with pytest.raises(ValueError, match="unreviewed binary|non-text content"):
        inventory(tmp_path, ["docs/notes.md"])


def synthetic_pdf(preamble: bytes) -> bytes:
    content = bytearray(preamble + b"%PDF-1.4\n")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << >> >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(content)
    content.extend(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(content)


@pytest.mark.parametrize("preamble", [b"", b"\n", b"\xef\xbb\xbf", b"% comment\n", b" " * 1023])
def test_complete_pdf_with_preamble_cannot_export_as_text(tmp_path: Path, preamble: bytes) -> None:
    relative = "docs/notes.md"
    target = tmp_path / relative
    target.parent.mkdir()
    content = synthetic_pdf(preamble)
    target.write_bytes(content)
    target.chmod(0o644)
    with pytest.raises(ValueError, match="unreviewed binary content"):
        inventory(tmp_path, [relative])
    # A stale or handcrafted, hash-correct inventory cannot bypass the content check.
    manifest = {
        "schema_version": 1,
        "files": [
            {
                "path": relative,
                "source": relative,
                "sha256": exporter.digest(content),
                "bytes": len(content),
                "mode": 0o644,
            }
        ],
    }
    output = tmp_path / ".opencommerce/candidate"
    with pytest.raises(ValueError, match="unreviewed binary content"):
        export(tmp_path, manifest, output)
    assert not output.exists()


def test_repo_retained_assets_match_current_bytes_and_sample_provenance() -> None:
    root = Path(__file__).resolve().parents[2]
    sample = "packages/backend/src/open_commerce/stores/sample_data"
    products = json.loads((root / sample / "manifest.json").read_bytes())
    assert len(products) == 48
    for product_id, record in products.items():
        assert record["filename"] == f"{product_id}.jpg"
        assert record["license"] == "CC BY 4.0"
        for prefix in (sample, "apps/web/public/abo-images", "apps/shopper/public/abo-images"):
            assert exporter.RETAINED_ASSETS[f"{prefix}/{record['filename']}"] == record["sha256"]
    assert not any(path.endswith(".pdf") for path in exporter.RETAINED_ASSETS)
    for path, checksum in exporter.RETAINED_ASSETS.items():
        assert omission(path) is None
        assert exporter.digest((root / path).read_bytes()) == checksum
