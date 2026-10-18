"""Synthetic evidence only; no private bundle, network, scanner, or Docker calls."""

from __future__ import annotations

import ast
import gzip
import hashlib
import io
import os
import stat
import tarfile
from pathlib import Path
from typing import Any

import pytest
from scripts import release_evidence_archive as bundle


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def info(name: str, *, directory: bool = False, size: int = 0) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    member.mode = 0o755 if directory else 0o644
    member.size = size
    return member


def archive_bytes(
    *entries: tuple[tarfile.TarInfo, bytes], format: int = tarfile.USTAR_FORMAT
) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=format, encoding="ascii") as archive:
        archive.addfile(info(".", directory=True))
        for member, raw in entries:
            archive.addfile(member, io.BytesIO(raw))
    return stream.getvalue()


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir(mode=0o750)
    (root / "source").mkdir(mode=0o751)
    (root / "source/run.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    (root / "source/run.sh").chmod(0o751)
    (root / "review.json").write_bytes(b'{"synthetic":true}\n')
    (root / "review.json").chmod(0o640)
    (root / "empty").mkdir(mode=0o711)
    (root / ".config").write_bytes(b"")
    return root


def target(tmp_path: Path) -> Path:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    return parent / "evidence"


def reject(raw: bytes, tmp_path: Path, expected: str | None = None) -> None:
    archive = tmp_path / "input.tar"
    archive.write_bytes(raw)
    destination = target(tmp_path)
    with pytest.raises(bundle.ArchiveError):
        bundle.unpack_bundle(archive, destination, expected or digest(raw))
    assert not destination.exists()
    assert not list(destination.parent.iterdir())


def test_deterministic_pack_preserves_bytes_modes_and_normalizes_metadata(
    tree: Path, tmp_path: Path
) -> None:
    first, second = tmp_path / "one.tar", tmp_path / "two.tar"
    expected = bundle.pack_bundle(tree, first)
    for path in [tree, *tree.rglob("*")]:
        os.utime(path, (123456, 654321))
    assert bundle.pack_bundle(tree, second) == expected == digest(first.read_bytes())
    assert first.read_bytes() == second.read_bytes()
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    with tarfile.open(first, mode="r:") as archive:
        members = archive.getmembers()
        assert [m.name for m in members] == [
            ".",
            ".config",
            "empty",
            "review.json",
            "source",
            "source/run.sh",
        ]
        for member in members:
            assert member.uid == member.gid == member.mtime == 0
            assert member.uname == member.gname == member.linkname == ""
            assert member.pax_headers == {} and member.sparse is None
    destination = target(tmp_path)
    bundle.unpack_bundle(first, destination, expected)
    for original in [tree, *tree.rglob("*")]:
        restored = destination / original.relative_to(tree)
        assert stat.S_IMODE(restored.stat().st_mode) == stat.S_IMODE(original.stat().st_mode)
        assert restored.is_dir() == original.is_dir()
        if original.is_file():
            assert restored.read_bytes() == original.read_bytes()
            assert restored.stat().st_nlink == 1


def test_repository_style_brackets_and_long_ustar_prefix_round_trip(
    tree: Path, tmp_path: Path
) -> None:
    relative = Path("a" * 60) / ("b" * 60) / ("route[...path]-" + "x" * 66 + ".ts")
    path = tree / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic source\n")
    archive = tmp_path / "long.tar"
    expected = bundle.pack_bundle(tree, archive)
    destination = target(tmp_path)
    bundle.unpack_bundle(archive, destination, expected)
    assert (destination / relative).read_bytes() == path.read_bytes()


@pytest.mark.parametrize("name", [" proof", "-proof", "+proof", "(proof)"])
@pytest.mark.parametrize("directory", [False, True])
def test_root_precedes_early_sorting_descendants_round_trip(
    tree: Path, tmp_path: Path, name: str, directory: bool
) -> None:
    assert name < "."
    path = tree / name
    if directory:
        path.mkdir(mode=0o750)
        path.chmod(0o750)
        path = path / "nested.py"
    path.write_bytes(b"synthetic evidence\n")
    path.chmod(0o751)
    first, second = tmp_path / "one.tar", tmp_path / "two.tar"
    expected = bundle.pack_bundle(tree, first)
    assert bundle.pack_bundle(tree, second) == expected == digest(first.read_bytes())
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, mode="r:") as archive:
        names = [member.name for member in archive.getmembers()]
    assert names[0] == "." and names[1] == name
    assert names[1:] == sorted(names[1:])
    destination = target(tmp_path)
    bundle.unpack_bundle(first, destination, expected)
    restored = destination / path.relative_to(tree)
    assert restored.read_bytes() == path.read_bytes()
    assert stat.S_IMODE(restored.stat().st_mode) == 0o751
    if directory:
        assert stat.S_IMODE((destination / name).stat().st_mode) == 0o750


@pytest.mark.parametrize("names", [("-proof", "+proof"), ("-proof", "-proof")])
def test_early_sorting_descendants_still_reject_disorder_and_duplicates(
    tmp_path: Path, names: tuple[str, str]
) -> None:
    reject(archive_bytes(*[(info(name), b"") for name in names]), tmp_path)


@pytest.mark.parametrize("mode", [0o4000, 0o2000, 0o1000])
@pytest.mark.parametrize("directory", [False, True])
def test_pack_rejects_special_permission_bits(
    tree: Path, tmp_path: Path, mode: int, directory: bool
) -> None:
    path = tree / ("empty" if directory else "review.json")
    path.chmod(mode | 0o700)
    if stat.S_IMODE(path.stat().st_mode) & mode != mode:
        pytest.skip("host filesystem clears this special permission bit")
    output = tmp_path / "output.tar"
    with pytest.raises(bundle.ArchiveError, match="special_permission_bits"):
        bundle.pack_bundle(tree, output)
    assert not output.exists()


@pytest.mark.parametrize("mode", [0o4000, 0o2000, 0o1000])
def test_permission_guard_rejects_each_special_bit_without_host_support(mode: int) -> None:
    metadata = os.stat_result((stat.S_IFREG | mode | 0o700, 1, 1, 1, 0, 0, 0, 0, 0, 0))
    with pytest.raises(bundle.ArchiveError, match="special_permission_bits"):
        bundle._mode(metadata)


@pytest.mark.parametrize("mode", [0o4755, 0o2755, 0o1755])
def test_archive_special_bits_are_rejected_without_host_support(tmp_path: Path, mode: int) -> None:
    member = info("special")
    member.mode = mode
    reject(archive_bytes((member, b"")), tmp_path)


def test_readonly_directory_and_file_modes_are_applied_after_writing(tmp_path: Path) -> None:
    directory = info("readonly", directory=True)
    directory.mode = 0o500
    member = info("readonly/data", size=3)
    member.mode = 0o400
    raw = archive_bytes((directory, b""), (member, b"abc"))
    archive = tmp_path / "readonly.tar"
    archive.write_bytes(raw)
    destination = target(tmp_path)
    try:
        bundle.unpack_bundle(archive, destination, digest(raw))
        assert (destination / "readonly/data").read_bytes() == b"abc"
        assert stat.S_IMODE((destination / "readonly").stat().st_mode) == 0o500
        assert stat.S_IMODE((destination / "readonly/data").stat().st_mode) == 0o400
    finally:
        if (destination / "readonly").exists():
            (destination / "readonly").chmod(0o700)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory-symlink"])
def test_pack_rejects_links_and_nonregular_members(tree: Path, tmp_path: Path, kind: str) -> None:
    path = tree / "alias"
    if kind == "symlink":
        path.symlink_to(tree / "review.json")
    elif kind == "directory-symlink":
        path.symlink_to(tree / "source", target_is_directory=True)
    elif kind == "hardlink":
        os.link(tree / "review.json", path)
    else:
        os.mkfifo(path)
    with pytest.raises(bundle.ArchiveError):
        bundle.pack_bundle(tree, tmp_path / "output.tar")
    assert not (tmp_path / "output.tar").exists()


@pytest.mark.parametrize("subject", ["root", "root-parent", "output-parent"])
def test_pack_rejects_linked_roots_or_parents(tree: Path, tmp_path: Path, subject: str) -> None:
    link = tmp_path / "link"
    link.symlink_to(tree if subject == "root" else tmp_path, target_is_directory=True)
    root = link if subject == "root" else link / "source" if subject == "root-parent" else tree
    output = link / "output.tar" if subject == "output-parent" else tmp_path / "output.tar"
    with pytest.raises(bundle.ArchiveError):
        bundle.pack_bundle(root, output)
    assert not (tmp_path / "output.tar").exists()


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling-link"])
def test_pack_never_overwrites_existing_output(tree: Path, tmp_path: Path, kind: str) -> None:
    output = tmp_path / "output.tar"
    if kind == "file":
        output.write_bytes(b"original")
    elif kind == "directory":
        output.mkdir()
    else:
        output.symlink_to(tmp_path / ("missing" if kind == "dangling-link" else "source"))
    with pytest.raises(bundle.ArchiveError, match="output_exists"):
        bundle.pack_bundle(tree, output)
    assert os.path.lexists(output)
    if kind == "file":
        assert output.read_bytes() == b"original"


def test_pack_refuses_output_within_source(tree: Path) -> None:
    with pytest.raises(bundle.ArchiveError, match="output_inside_source"):
        bundle.pack_bundle(tree, tree / "bundle.tar")


@pytest.mark.parametrize("limit", ["file", "total", "members", "archive", "depth", "name"])
def test_pack_limits_before_output_creation(
    tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    if limit == "file":
        with (tree / "large").open("wb") as stream:
            stream.truncate(bundle.MAX_FILE_BYTES + 1)
    elif limit == "total":
        monkeypatch.setattr(bundle, "MAX_TOTAL_BYTES", 1)
    elif limit == "members":
        monkeypatch.setattr(bundle, "MAX_MEMBERS", 2)
    elif limit == "archive":
        monkeypatch.setattr(bundle, "MAX_ARCHIVE_BYTES", 512)
    elif limit == "depth":
        path = tree.joinpath(*(["d"] * 65))
        path.mkdir(parents=True)
    else:
        (tree / ("n" * 101)).write_bytes(b"")
    output = tmp_path / "output.tar"
    with pytest.raises(bundle.ArchiveError):
        bundle.pack_bundle(tree, output)
    assert not output.exists()


@pytest.mark.parametrize("mutation", ["bytes", "mode", "add", "remove", "replace-root"])
@pytest.mark.parametrize("call", [1, 2])
def test_pack_refuses_changed_input_before_or_during_writes(
    tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, call: int
) -> None:
    snapshot = bundle._snapshot
    calls = 0

    def changing_snapshot(root: int, *, keep_data: bool) -> list[bundle._Member]:
        nonlocal calls
        result = snapshot(root, keep_data=keep_data)
        calls += 1
        if calls == call:
            path = tree / "review.json"
            if mutation == "bytes":
                path.write_bytes(b"different")
            elif mutation == "mode":
                path.chmod(0o600)
            elif mutation == "add":
                (tree / "added").write_bytes(b"")
            elif mutation == "remove":
                path.unlink()
            else:
                tree.rename(tmp_path / "old-root")
                tree.mkdir()
        return result

    monkeypatch.setattr(bundle, "_snapshot", changing_snapshot)
    with pytest.raises(bundle.ArchiveError, match="input_changed"):
        bundle.pack_bundle(tree, tmp_path / "output.tar")


@pytest.mark.parametrize(
    "kind",
    [
        tarfile.SYMTYPE,
        tarfile.LNKTYPE,
        tarfile.CHRTYPE,
        tarfile.BLKTYPE,
        tarfile.FIFOTYPE,
        tarfile.CONTTYPE,
        tarfile.XHDTYPE,
        tarfile.XGLTYPE,
        tarfile.GNUTYPE_LONGNAME,
        tarfile.GNUTYPE_LONGLINK,
        tarfile.GNUTYPE_SPARSE,
    ],
)
def test_unpack_refuses_links_devices_and_extension_headers(tmp_path: Path, kind: bytes) -> None:
    member = info("forbidden")
    member.type = kind
    member.linkname = "outside"
    reject(archive_bytes((member, b"")), tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "/absolute",
        "../outside",
        "dir/../outside",
        "./alias",
        "a//b",
        "a/./b",
        "a\\b",
        "C:/outside",
        "bad\nname",
        "bad\x00tail",
    ],
)
def test_unpack_refuses_traversal_and_noncanonical_paths(tmp_path: Path, name: str) -> None:
    reject(archive_bytes((info(name), b"")), tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        "uid",
        "gid",
        "uname",
        "gname",
        "mtime",
        "linkname",
        "devmajor",
        "devminor",
        "mode",
        "negative-size",
    ],
)
def test_unpack_refuses_noncanonical_or_privileged_metadata(tmp_path: Path, change: str) -> None:
    member = info("ordinary")
    if change in {"uname", "gname", "linkname"}:
        setattr(member, change, "UNTRUSTED-HEADER-SECRET")
    elif change == "mode":
        member.mode = 0o4755
    elif change == "negative-size":
        # GNU base-256 permits this encoding; the strict reader must still reject it.
        member.size = -1
        raw = (
            info(".", directory=True).tobuf(format=tarfile.USTAR_FORMAT)
            + member.tobuf(format=tarfile.GNU_FORMAT)
            + bytes(1024)
        )
        reject(raw, tmp_path)
        return
    else:
        setattr(member, change, 1)
    raw = archive_bytes((member, b""))
    if change in {"devmajor", "devminor"}:
        # tarfile intentionally drops device numbers on regular-file serialization.
        # Put the forbidden raw value back and repair its checksum for this fixture.
        header = bytearray(raw[512:1024])
        offset = 329 if change == "devmajor" else 337
        header[offset : offset + 8] = b"0000001\x00"
        header[148:156] = b"        "
        header[148:156] = f"{sum(header):06o}\x00 ".encode()
        raw = raw[:512] + bytes(header) + raw[1024:]
    reject(raw, tmp_path)


@pytest.mark.parametrize(
    "case",
    ["duplicate", "file-parent", "missing-parent", "root-again", "unsorted", "directory-payload"],
)
def test_unpack_refuses_conflicting_or_incomplete_membership(tmp_path: Path, case: str) -> None:
    entries = {
        "duplicate": [(info("a"), b""), (info("a"), b"")],
        "file-parent": [(info("a"), b""), (info("a/b"), b"")],
        "missing-parent": [(info("a/b"), b"")],
        "root-again": [(info(".", directory=True), b"")],
        "unsorted": [(info("z"), b""), (info("a"), b"")],
        "directory-payload": [(info("a", directory=True, size=1), b"x")],
    }
    reject(archive_bytes(*entries[case]), tmp_path)


@pytest.mark.parametrize(
    "case",
    [
        "header",
        "payload",
        "terminator",
        "one-zero",
        "checksum",
        "padding",
        "trailer",
        "concatenation",
        "compressed",
        "no-root",
    ],
)
def test_unpack_refuses_corrupted_truncated_and_ambiguous_archives(
    tmp_path: Path, case: str
) -> None:
    raw = archive_bytes((info("a", size=3), b"abc"))
    if case == "header":
        raw = raw[:600]
    elif case == "payload":
        raw = raw[:1024]
    elif case == "terminator":
        raw = raw[:1536]
    elif case == "one-zero":
        raw = raw[:2048]
    elif case == "checksum":
        raw = b"x" + raw[1:]
    elif case == "padding":
        raw = raw[:1027] + b"x" + raw[1028:]
    elif case == "trailer":
        raw = raw[:-1] + b"x"
    elif case == "concatenation":
        raw += archive_bytes()
    elif case == "compressed":
        raw = gzip.compress(raw)
    else:
        raw = bytes(1024)
    reject(raw, tmp_path)


@pytest.mark.parametrize("case", ["file", "total", "members", "depth", "archive"])
def test_unpack_size_and_depth_limits_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    if case == "file":
        raw = (
            info(".", directory=True).tobuf(format=tarfile.USTAR_FORMAT)
            + info("large", size=bundle.MAX_FILE_BYTES + 1).tobuf(format=tarfile.USTAR_FORMAT)
            + bytes(1024)
        )
    elif case == "depth":
        entries = [(info("/".join(["d"] * depth), directory=True), b"") for depth in range(1, 66)]
        raw = archive_bytes(*entries)
    else:
        raw = archive_bytes((info("a", size=3), b"abc"), (info("b", size=3), b"def"))
        monkeypatch.setattr(
            bundle,
            {"total": "MAX_TOTAL_BYTES", "members": "MAX_MEMBERS", "archive": "MAX_ARCHIVE_BYTES"}[
                case
            ],
            2,
        )
    reject(raw, tmp_path)


def test_oversized_archive_stat_fails_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "oversized.tar"
    with archive.open("wb") as stream:
        stream.truncate(bundle.MAX_ARCHIVE_BYTES + 1)
    destination = target(tmp_path)

    def forbid_fdopen(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("oversized input must not be read")

    monkeypatch.setattr(os, "fdopen", forbid_fdopen)
    with pytest.raises(bundle.ArchiveError, match="file_size_limit"):
        bundle.unpack_bundle(archive, destination, "a" * 64)
    assert not destination.exists()


@pytest.mark.parametrize("expected", ["a" * 64, "A" * 64, "invalid", "", "0" * 65])
def test_entire_archive_digest_required_before_extraction(tmp_path: Path, expected: str) -> None:
    raw = archive_bytes((info("a", size=3), b"abc"))
    reject(raw, tmp_path, expected=expected if expected else "invalid")


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling-link"])
def test_unpack_never_overwrites_existing_destination(tmp_path: Path, kind: str) -> None:
    archive = tmp_path / "input.tar"
    archive.write_bytes(archive_bytes())
    destination = target(tmp_path)
    if kind == "file":
        destination.write_bytes(b"original")
    elif kind == "directory":
        destination.mkdir()
    else:
        destination.symlink_to(tmp_path / ("missing" if kind == "dangling-link" else "input.tar"))
    with pytest.raises(bundle.ArchiveError, match="destination_exists"):
        bundle.unpack_bundle(archive, destination, digest(archive.read_bytes()))
    assert os.path.lexists(destination)
    if kind == "file":
        assert destination.read_bytes() == b"original"


@pytest.mark.parametrize(
    "case",
    [
        "public-parent",
        "nonempty-parent",
        "linked-parent",
        "archive-symlink",
        "archive-hardlink",
        "archive-linked-parent",
    ],
)
def test_unpack_requires_private_parent_and_unaliased_input(tmp_path: Path, case: str) -> None:
    raw = archive_bytes()
    archive = tmp_path / "input.tar"
    archive.write_bytes(raw)
    destination = target(tmp_path)
    if case == "public-parent":
        destination.parent.chmod(0o755)
    elif case == "nonempty-parent":
        (destination.parent / "existing").write_bytes(b"original")
    elif case == "linked-parent":
        (tmp_path / "alias").symlink_to(destination.parent, target_is_directory=True)
        destination = tmp_path / "alias/evidence"
    elif case == "archive-symlink":
        (tmp_path / "alias").symlink_to(archive)
        archive = tmp_path / "alias"
    elif case == "archive-hardlink":
        os.link(archive, tmp_path / "alias")
    else:
        (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
        archive = tmp_path / "alias/input.tar"
    with pytest.raises(bundle.ArchiveError):
        bundle.unpack_bundle(archive, destination, digest(raw))
    assert not destination.exists()


@pytest.mark.parametrize("change", ["archive", "archive-replaced", "parent-mode", "parent-member"])
def test_input_changes_after_hashing_and_parsing_block_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    raw = archive_bytes()
    archive = tmp_path / "input.tar"
    archive.write_bytes(raw)
    destination = target(tmp_path)
    parse = bundle._parse

    def mutate(value: bytes) -> list[bundle._Member]:
        members = parse(value)
        if change == "archive":
            archive.write_bytes(b"changed")
        elif change == "archive-replaced":
            archive.rename(tmp_path / "original.tar")
            archive.write_bytes(raw)
        elif change == "parent-mode":
            destination.parent.chmod(0o755)
        else:
            (destination.parent / "other").write_bytes(b"unrelated")
        return members

    monkeypatch.setattr(bundle, "_parse", mutate)
    with pytest.raises(bundle.ArchiveError):
        bundle.unpack_bundle(archive, destination, digest(raw))
    assert not destination.exists()


def test_library_parser_errors_never_expose_raw_header_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = archive_bytes()
    archive = tmp_path / "input.tar"
    archive.write_bytes(raw)
    destination = target(tmp_path)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("UNTRUSTED-HEADER-SECRET")

    monkeypatch.setattr(tarfile.TarInfo, "frombuf", fail)
    with pytest.raises(bundle.ArchiveError) as error:
        bundle.unpack_bundle(archive, destination, digest(raw))
    assert str(error.value) == "unpack_failed"
    assert error.value.__suppress_context__
    assert not destination.exists()


def test_helper_never_extracts_or_executes_with_general_purpose_apis() -> None:
    source = Path(bundle.__file__).read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imports & {"subprocess", "pickle", "marshal", "socket", "requests"}
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not any(
        call.endswith((".extractall", ".extract", ".system", ".popen")) for call in calls
    )
    assert not calls & {"eval", "exec", "__import__"}
