"""Bind OCI/index-based Docker IDs to the config ID that Trivy actually scans."""

import hashlib
import io
import json
import runpy
import stat
import subprocess
import sys
import tarfile
import traceback
from pathlib import Path
from typing import Any

import pytest

MODULE = runpy.run_path("scripts/scan-images.py")
LAYER = "sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64


def test_scan_output_starts_incomplete_and_never_overwrites_evidence(tmp_path: Path) -> None:
    output = tmp_path / "fresh-scan"
    MODULE["initialize_output"](output)
    assert json.loads((output / "inventory.json").read_text()) == {
        "complete": False,
        "images": [],
    }
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "inventory.json").stat().st_mode) == 0o600
    retained = b'{"complete": true, "images": [{"service": "api"}]}\n'
    (output / "inventory.json").write_bytes(retained)
    (output / "raw.json").write_bytes(b"preserved scan output")
    with pytest.raises(FileExistsError):
        MODULE["initialize_output"](output)
    assert (output / "inventory.json").read_bytes() == retained
    assert (output / "raw.json").read_bytes() == b"preserved scan output"


def test_scan_output_also_rejects_existing_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        MODULE["initialize_output"](tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_direct_script_entrypoint_preserves_compose_environment_selection() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/scan-images.py", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--env-file" in result.stdout


def saved_image(tmp_path: Path, *, duplicate: bool = False) -> tuple[Path, dict[str, Any], str]:
    config = {
        "architecture": "arm64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [LAYER]},
        "config": {"Env": ["SYNTHETIC_BUILT_DEFAULT=private-fixture"]},
    }
    raw = (json.dumps(config, indent=2) + "\n").encode()
    items = {"config.json": raw}
    manifest = [{"Config": "config.json", "Layers": ["layer.tar"], "RepoTags": None}]
    if duplicate:
        items["other.json"] = json.dumps({**config, "config": {"Cmd": ["different"]}}).encode()
        manifest.append({"Config": "other.json", "Layers": ["layer.tar"]})
    items["manifest.json"] = json.dumps(manifest).encode()
    items["layer.tar"] = b"synthetic layer payload: must never be read by identity selection"
    archive = tmp_path / "image.tar"
    write_archive(archive, list(items.items()))
    inspected = {
        "Id": IMAGE_ID,
        "Architecture": "arm64",
        "Os": "linux",
        "RootFS": {"Type": "layers", "Layers": [LAYER]},
        "Config": {
            "User": "10001",
            "Env": ["LIVE_ENV_FIXTURE=must-not-be-retained"],
            "Cmd": ["live-command-fixture"],
            "Entrypoint": ["live-entrypoint-fixture"],
        },
        "Args": ["live-arguments-fixture"],
    }
    return archive, inspected, "sha256:" + hashlib.sha256(raw).hexdigest()


def write_archive(archive: Path, items: list[tuple[str, bytes]]) -> None:
    with tarfile.open(archive, "w") as saved:
        for name, data in items:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            saved.addfile(member, io.BytesIO(data))


def fixture_entries(archive: Path) -> dict[str, bytes]:
    with tarfile.open(archive) as saved:
        entries = {}
        for member in saved:
            stream = saved.extractfile(member)
            assert stream is not None
            entries[member.name] = stream.read()
        return entries


def test_oci_index_id_is_not_confused_with_config_id(tmp_path: Path) -> None:
    archive, inspected, expected = saved_image(tmp_path)
    assert MODULE["image_config_identity"](archive, inspected) == expected
    assert expected != inspected["Id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("Architecture", "amd64"),
        ("Os", "windows"),
        ("RootFS", {"Type": "layers", "Layers": ["sha256:" + "c" * 64]}),
    ],
)
def test_wrong_export_context_fails(tmp_path: Path, field: str, value: Any) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    inspected[field] = value
    with pytest.raises(ValueError, match="uniquely match"):
        MODULE["image_config_identity"](archive, inspected)


def test_multiple_configs_for_one_filesystem_are_ambiguous(tmp_path: Path) -> None:
    archive, inspected, _ = saved_image(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match="uniquely match"):
        MODULE["image_config_identity"](archive, inspected)


def test_retained_inputs_are_exact_private_and_independently_reproducible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive, inspected, expected = saved_image(tmp_path)
    originals = fixture_entries(archive)
    output = tmp_path / "evidence"
    MODULE["initialize_output"](output)
    result = MODULE["retain_image_identity"](archive, inspected, output, "api")
    archive.unlink()
    assert result["image_config_id"] == expected
    inputs = result["identity_inputs"]
    for kind, reference in inputs.items():
        path = output / reference["file"]
        assert path.name == f"api.image-{kind}.json"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"]
    assert (output / inputs["manifest"]["file"]).read_bytes() == originals["manifest.json"]
    config_raw = (output / inputs["config"]["file"]).read_bytes()
    assert config_raw == originals["config.json"]
    assert expected == "sha256:" + hashlib.sha256(config_raw).hexdigest()
    manifest = json.loads((output / inputs["manifest"]["file"]).read_bytes())
    assert manifest[0]["Config"] == inputs["config"]["archive_member"]
    selected = json.loads((output / inputs["inspection"]["file"]).read_bytes())
    assert set(selected) == {"Id", "Architecture", "Os", "RootFS"}
    assert set(selected["RootFS"]) == {"Type", "Layers"}
    config = json.loads(config_raw)
    assert selected["Id"] == IMAGE_ID
    assert selected["Architecture"] == config["architecture"]
    assert selected["Os"] == config["os"]
    assert selected["RootFS"]["Layers"] == config["rootfs"]["diff_ids"]
    assert "LIVE_ENV_FIXTURE" not in json.dumps(selected)
    assert "live-command-fixture" not in json.dumps(selected)
    assert "live-arguments-fixture" not in json.dumps(selected)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("kind", ["manifest", "config", "inspection"])
@pytest.mark.parametrize("symlink", [False, True])
def test_retention_refuses_existing_files_and_symlinks(
    tmp_path: Path, kind: str, symlink: bool
) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    output = tmp_path / "evidence"
    MODULE["initialize_output"](output)
    existing = output / f"api.image-{kind}.json"
    if symlink:
        existing.symlink_to(output / "missing-target")
    else:
        existing.write_bytes(b"previous evidence")
    with pytest.raises(FileExistsError):
        MODULE["retain_image_identity"](archive, inspected, output, "api")
    assert set(output.iterdir()) == {output / "inventory.json", existing}
    if symlink:
        assert existing.is_symlink() and not (output / "missing-target").exists()
    else:
        assert existing.read_bytes() == b"previous evidence"


@pytest.mark.parametrize("service", ["../api", "/api", "", "api/a", "a" * 129])
def test_unsafe_service_names_fail_before_reading_archive(tmp_path: Path, service: str) -> None:
    with pytest.raises(ValueError, match="unsafe service"):
        MODULE["retain_image_identity"](tmp_path / "absent", {}, tmp_path, service)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("member_name", ["manifest.json", "config.json", "./config.json"])
def test_duplicate_or_aliased_metadata_members_rejected(tmp_path: Path, member_name: str) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    raw = entries[member_name.removeprefix("./")]
    write_archive(archive, [*entries.items(), (member_name, raw)])
    with pytest.raises(ValueError, match="duplicate or aliased"):
        MODULE["image_config_identity"](archive, inspected)


@pytest.mark.parametrize("duplicate_reference", [False, True])
def test_identical_config_bytes_do_not_hide_ambiguous_records(
    tmp_path: Path, duplicate_reference: bool
) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    name = "config.json" if duplicate_reference else "other.json"
    entries[name] = entries["config.json"]
    entries["manifest.json"] = json.dumps(
        [{"Config": value, "Layers": ["layer.tar"]} for value in ["config.json", name]]
    ).encode()
    write_archive(archive, list(entries.items()))
    with pytest.raises(ValueError, match="duplicate|uniquely match"):
        MODULE["image_config_identity"](archive, inspected)


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b"null",
        b"[null]",
        b"[{}]",
        b'[{"Config":"../config.json"}]',
        b'[{"Config":"config.json","Config":"other.json"}]',
        b"NaN",
        b"\xff",
    ],
)
def test_malformed_manifest_rejected(tmp_path: Path, raw: bytes) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    entries["manifest.json"] = raw
    write_archive(archive, list(entries.items()))
    with pytest.raises(ValueError):
        MODULE["image_config_identity"](archive, inspected)


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"null",
        b"{}",
        b'{"rootfs":[]}',
        b'{"architecture":"arm64","architecture":"amd64"}',
        b"NaN",
        b"{",
        b"\xff",
    ],
)
def test_malformed_config_rejected(tmp_path: Path, raw: bytes) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    entries["config.json"] = raw
    write_archive(archive, list(entries.items()))
    with pytest.raises(ValueError):
        MODULE["image_config_identity"](archive, inspected)


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE])
def test_config_must_be_a_regular_member(tmp_path: Path, member_type: bytes) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    with tarfile.open(archive, "w") as saved:
        raw = entries["manifest.json"]
        manifest = tarfile.TarInfo("manifest.json")
        manifest.size = len(raw)
        saved.addfile(manifest, io.BytesIO(raw))
        config = tarfile.TarInfo("config.json")
        config.type = member_type
        config.linkname = "not-read"
        saved.addfile(config)
    with pytest.raises(ValueError, match="unexpected image"):
        MODULE["image_config_identity"](archive, inspected)


@pytest.mark.parametrize(
    "limit",
    [
        "MAX_METADATA_BYTES",
        "MAX_TOTAL_METADATA_BYTES",
        "MAX_ARCHIVE_MEMBERS",
        "MAX_MANIFEST_IMAGES",
        "MAX_ARCHIVE_READ_BYTES",
    ],
)
def test_archive_metadata_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    monkeypatch.setitem(MODULE["selected_archive_metadata"].__globals__, limit, 0)
    with pytest.raises(ValueError):
        MODULE["image_config_identity"](archive, inspected)


def test_oversized_pax_header_is_rejected_before_implicit_read(tmp_path: Path) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    with tarfile.open(archive, "w") as saved:
        member = tarfile.TarInfo("pax-header")
        member.type = tarfile.XHDTYPE
        member.size = MODULE["MAX_METADATA_BYTES"] * 2
        saved.addfile(member)
    assert archive.stat().st_size < 20000
    with pytest.raises(ValueError, match="read size limit"):
        MODULE["image_config_identity"](archive, inspected)


def test_sparse_header_parse_error_never_discloses_archive_values(tmp_path: Path) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    marker = "SYNTHETIC_PRIVATE_SPARSE_VALUE"
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as saved:
        member = tarfile.TarInfo("manifest.json")
        member.pax_headers = {"GNU.sparse.map": f"0,{marker}"}
        member.size = 2
        saved.addfile(member, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match="^cannot read image archive metadata$") as caught:
        MODULE["image_config_identity"](archive, inspected)
    assert caught.value.__suppress_context__ is True
    assert marker not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("missing", ["manifest.json", "config.json"])
def test_missing_metadata_is_rejected(tmp_path: Path, missing: str) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    entries = fixture_entries(archive)
    del entries[missing]
    write_archive(archive, list(entries.items()))
    with pytest.raises(ValueError, match="missing"):
        MODULE["image_config_identity"](archive, inspected)


def test_truncated_archive_is_rejected(tmp_path: Path) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    archive.write_bytes(archive.read_bytes()[:600])
    with pytest.raises(ValueError):
        MODULE["image_config_identity"](archive, inspected)


def test_layer_payloads_and_filesystem_extraction_are_never_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, inspected, expected = saved_image(tmp_path)
    original = tarfile.TarFile.extractfile
    reads: list[tuple[str, int]] = []

    class BoundedStream:
        def __init__(self, stream: Any, name: str) -> None:
            self.stream = stream
            self.name = name

        def __enter__(self) -> "BoundedStream":
            return self

        def __exit__(self, *_args: Any) -> None:
            self.stream.close()

        def read(self, size: int = -1) -> bytes:
            assert 0 <= size <= MODULE["MAX_METADATA_BYTES"] + 1
            reads.append((self.name, size))
            raw = self.stream.read(size)
            assert isinstance(raw, bytes)
            return raw

    def extractfile(saved: tarfile.TarFile, member: tarfile.TarInfo) -> BoundedStream:
        assert member.name in {"manifest.json", "config.json"}
        return BoundedStream(original(saved, member), member.name)

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("filesystem extraction attempted")

    monkeypatch.setattr(tarfile.TarFile, "extractfile", extractfile)
    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden)
    assert MODULE["image_config_identity"](archive, inspected) == expected
    assert [name for name, _ in reads] == ["manifest.json", "config.json"]


@pytest.mark.parametrize("failure", ["none", "scanner", "wrong-report-id"])
def test_main_retains_identity_before_scanning_and_archive_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    archive, inspected, expected = saved_image(tmp_path)
    archive_bytes = archive.read_bytes()
    output = tmp_path / "scan"
    scope = MODULE["main"].__globals__
    calls = []

    def compose_config(arguments: list[str], **_kwargs: Any) -> str:
        assert arguments == ["docker", "compose", "config", "--format", "json"]
        return json.dumps({"name": "synthetic", "services": {"api": {"image": "synthetic:local"}}})

    def inspect(*arguments: str) -> list[dict[str, Any]]:
        assert arguments == ("image", "inspect", "synthetic:local")
        return [inspected]

    def run(*arguments: str) -> None:
        calls.append(arguments)
        if arguments[:3] == ("docker", "image", "save"):
            assert arguments[-1] == inspected["Id"]
            Path(arguments[4]).write_bytes(archive_bytes)
            return
        current = json.loads((output / "inventory.json").read_bytes())
        assert current["complete"] is False
        record = current["images"][0]
        assert record["complete"] is False
        assert record["image_config_id"] == expected
        for reference in record["identity_inputs"].values():
            raw = (output / reference["file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
        if failure == "scanner":
            raise subprocess.CalledProcessError(1, arguments)
        destination = output / Path(arguments[-1]).name
        assert destination.stat().st_size == 0
        if "cyclonedx" in arguments:
            destination.write_text('{"bomFormat":"CycloneDX"}')
        else:
            image_id = IMAGE_ID if failure == "wrong-report-id" else expected
            destination.write_text(json.dumps({"Metadata": {"ImageID": image_id}, "Results": []}))

    monkeypatch.setattr(
        sys, "argv", ["scan-images.py", "--output", str(output), "--service", "api"]
    )
    monkeypatch.setitem(scope, "compose_command", lambda _environment: ["docker", "compose"])
    monkeypatch.setitem(scope, "docker_json", inspect)
    monkeypatch.setitem(scope, "run", run)
    monkeypatch.setattr(subprocess, "check_output", compose_config)
    if failure == "none":
        MODULE["main"]()
    else:
        with pytest.raises((subprocess.CalledProcessError, ValueError)):
            MODULE["main"]()
    inventory = json.loads((output / "inventory.json").read_bytes())
    assert inventory["complete"] is (failure == "none")
    assert inventory["images"][0]["complete"] is (failure == "none")
    assert len(calls) == (2 if failure == "scanner" else 3)
    assert not (output / "api.tar").exists()
    assert len(inventory["images"][0]["identity_inputs"]) == 3
    for path in output.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    captured = capsys.readouterr()
    assert "SYNTHETIC_BUILT_DEFAULT" not in captured.out + captured.err
    assert "LIVE_ENV_FIXTURE" not in captured.out + captured.err


@pytest.mark.parametrize("failure", ["malformed", "manifest", "config", "inspection", "inventory"])
def test_main_preserves_private_original_archive_when_identity_retention_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    archive, inspected, _ = saved_image(tmp_path)
    if failure == "malformed":
        entries = fixture_entries(archive)
        entries["manifest.json"] = b"{}"
        write_archive(archive, list(entries.items()))
    archive_bytes = archive.read_bytes()
    output = tmp_path / "scan"
    scope = MODULE["main"].__globals__
    original_write = scope["write_private_new"]
    original_write_text = Path.write_text
    calls: list[tuple[str, ...]] = []

    def write_private_new(path: Path, raw: bytes) -> None:
        if path.name == f"api.image-{failure}.json":
            original_write(path, raw[:1])
            raise OSError("synthetic partial identity write failure")
        original_write(path, raw)

    def write_text(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if failure == "inventory" and path == output / "inventory.json":
            original_write_text(path, data[:1])
            raise OSError("synthetic partial inventory write failure")
        return original_write_text(path, data, *args, **kwargs)

    def run(*arguments: str) -> None:
        calls.append(arguments)
        assert arguments == (
            "docker",
            "image",
            "save",
            "--output",
            str(output / "api.tar"),
            IMAGE_ID,
        )
        Path(arguments[4]).write_bytes(archive_bytes)

    monkeypatch.setattr(
        sys, "argv", ["scan-images.py", "--output", str(output), "--service", "api"]
    )
    monkeypatch.setitem(scope, "compose_command", lambda _environment: ["docker", "compose"])
    monkeypatch.setitem(scope, "docker_json", lambda *_args: [inspected])
    monkeypatch.setitem(scope, "run", run)
    monkeypatch.setitem(scope, "write_private_new", write_private_new)
    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *_args, **_kwargs: json.dumps({"name": "synthetic", "services": {"api": {}}}),
    )
    reason = "malformed image manifest list" if failure == "malformed" else "synthetic partial"
    with pytest.raises((ValueError, OSError), match=reason):
        MODULE["main"]()
    assert len(calls) == 1
    assert (output / "api.tar").read_bytes() == archive_bytes
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    for path in output.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not (output / "api.scan.json").exists()
    assert not (output / "api.cdx.json").exists()
    if failure != "inventory":
        assert json.loads((output / "inventory.json").read_bytes()) == {
            "complete": False,
            "images": [],
        }
    expected_files = {"malformed": 0, "manifest": 1, "config": 2, "inspection": 3, "inventory": 3}
    assert len(list(output.glob("api.image-*.json"))) == expected_files[failure]
    assert capsys.readouterr() == ("", "")
