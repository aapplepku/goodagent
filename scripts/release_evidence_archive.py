"""Deterministic, bounded transport for an explicitly privacy-reviewed evidence tree.

This does not select, redact, approve, or execute evidence. Only uncompressed USTAR
is supported: ASCII paths, a 100-byte final name and 155-byte directory prefix when
splitting is needed. PAX/GNU extensions (including sparse files) are unsupported.
Unix permission bits are preserved; ownership, owner names and times are normalized.
The first member is the root directory, named '.', followed by sorted descendants.

Limits are 32 MiB/file, 256 MiB of contents, 8192 members including directories/root,
and 64 descendant path components. Inputs are read without following links and
rechecked for changes. The whole archive is hashed before any extraction writes.
Unpack requires a nonexistent destination inside an empty, caller-owned 0700 real
directory, normally created with tempfile.TemporaryDirectory. Use a new parent per
attempt. An I/O failure can leave a private partial output; never consume a failed
call. Same-user/privileged hostile concurrent filesystem mutation is not isolated.

POSIX descriptor-relative filesystem APIs are required. No archive extraction API,
subprocess, network, or code loading is used. Working memory is bounded by the input
limits; pack retains file bytes and unpack retains the raw archive in memory.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 8192
MAX_DEPTH = 64
MAX_ARCHIVE_BYTES = MAX_TOTAL_BYTES + MAX_MEMBERS * 1024 + tarfile.RECORDSIZE + 512
ZERO_BLOCK = bytes(tarfile.BLOCKSIZE)


class ArchiveError(ValueError):
    """Fixed diagnostics, never untrusted header values or file contents."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ArchiveError(code)


def _absolute(path: Path) -> Path:
    require(".." not in path.parts, "unsafe_filesystem_path")
    return path.absolute()


def _directory(path: Path) -> int:
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in _absolute(path).parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _empty(fd: int) -> bool:
    with os.scandir(fd) as listing:
        return next(listing, None) is None


def _mode(info: os.stat_result) -> int:
    mode = stat.S_IMODE(info.st_mode)
    require(mode & ~0o777 == 0, "special_permission_bits")
    return mode


def _name(name: str) -> None:
    parts = name.split("/")
    require(
        len(parts) <= MAX_DEPTH
        and all(part not in {"", ".", ".."} for part in parts)
        and re.fullmatch(r"[A-Za-z0-9_.@+()\[\] /-]+", name) is not None,
        "unsafe_member_path",
    )


@dataclass(frozen=True)
class _Member:
    name: str
    directory: bool
    mode: int
    size: int = 0
    digest: str = ""
    identity: tuple[int, ...] = ()
    data: bytes | memoryview = field(default=b"", compare=False, repr=False)


def _header(member: _Member) -> bytes:
    info = tarfile.TarInfo(member.name)
    info.type = tarfile.DIRTYPE if member.directory else tarfile.REGTYPE
    info.mode = member.mode
    info.size = member.size
    # TarInfo defaults normalize uid/gid, uname/gname, mtime and link/device metadata.
    return info.tobuf(format=tarfile.USTAR_FORMAT, encoding="ascii", errors="strict")


def _read_file(parent: int, name: str, limit: int) -> tuple[bytes, tuple[int, ...]]:
    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    require(stat.S_ISREG(named.st_mode) and named.st_nlink == 1, "not_single_regular_file")
    _mode(named)
    require(0 <= named.st_size <= limit, "file_size_limit")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(_identity(before) == _identity(named), "input_changed")
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        require(
            len(raw) == before.st_size
            and _identity(before) == _identity(after) == _identity(named),
            "input_changed",
        )
    return raw, _identity(before)


def _snapshot(root: int, *, keep_data: bool) -> list[_Member]:
    members: list[_Member] = []
    total = 0

    def walk(fd: int, prefix: str) -> None:
        nonlocal total
        before = os.fstat(fd)
        require(len(members) < MAX_MEMBERS, "member_count_limit")
        directory = _Member(prefix or ".", True, _mode(before), identity=_identity(before))
        _header(directory)
        members.append(directory)
        # Bound enumeration before sorting; do not allocate an unbounded directory listing.
        names: list[str] = []
        with os.scandir(fd) as listing:
            for item in listing:
                require(len(names) + len(members) < MAX_MEMBERS, "member_count_limit")
                names.append(item.name)
        for leaf in sorted(names):
            name = f"{prefix}/{leaf}" if prefix else leaf
            _name(name)
            info = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    require(_identity(os.fstat(child)) == _identity(info), "input_changed")
                    walk(child, name)
                    require(
                        _identity(os.stat(leaf, dir_fd=fd, follow_symlinks=False))
                        == _identity(info),
                        "input_changed",
                    )
                finally:
                    os.close(child)
            else:
                require(len(members) < MAX_MEMBERS, "member_count_limit")
                require(total + info.st_size <= MAX_TOTAL_BYTES, "total_size_limit")
                raw, identity = _read_file(fd, leaf, MAX_FILE_BYTES)
                require(identity == _identity(info), "input_changed")
                total += len(raw)
                require(total <= MAX_TOTAL_BYTES, "total_size_limit")
                member = _Member(
                    name,
                    False,
                    _mode(info),
                    len(raw),
                    hashlib.sha256(raw).hexdigest(),
                    identity,
                    raw if keep_data else b"",
                )
                _header(member)
                members.append(member)
        require(_identity(os.fstat(fd)) == _identity(before), "input_changed")

    walk(root, "")
    return [members[0], *sorted(members[1:], key=lambda member: member.name)]


def _recheck_root(path: Path, expected: int) -> None:
    current = _directory(path)
    try:
        require(_identity(os.fstat(current)) == _identity(os.fstat(expected)), "input_changed")
    finally:
        os.close(current)


def pack_bundle(root: Path, output: Path) -> str:
    """Create a new 0600 USTAR bundle and return its entire SHA-256, never approval."""
    root_fd = parent = -1
    try:
        root, output = _absolute(root), _absolute(output)
        require(not output.is_relative_to(root), "output_inside_source")
        root_fd = _directory(root)
        parent = _directory(output.parent)
        require(not os.path.lexists(output), "output_exists")
        members = _snapshot(root_fd, keep_data=True)
        archive_size = 1024 + sum(512 + member.size + (-member.size % 512) for member in members)
        require(archive_size <= MAX_ARCHIVE_BYTES, "archive_size_limit")
        require(members == _snapshot(root_fd, keep_data=False), "input_changed")
        _recheck_root(root, root_fd)
        _recheck_root(output.parent, parent)
        fd = os.open(
            output.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(fd, "w+b") as stream:
            os.fchmod(stream.fileno(), 0o600)
            digest = hashlib.sha256()
            size = 0
            for member in members:
                for part in (_header(member), member.data, bytes(-member.size % 512)):
                    size += len(part)
                    require(size <= MAX_ARCHIVE_BYTES, "archive_size_limit")
                    require(stream.write(part) == len(part), "short_write")
                    digest.update(part)
            require(stream.write(ZERO_BLOCK * 2) == 1024, "short_write")
            digest.update(ZERO_BLOCK * 2)
            stream.flush()
            info = os.fstat(stream.fileno())
            require(info.st_size == size + 1024 <= MAX_ARCHIVE_BYTES, "archive_size_limit")
            stream.seek(0)
            require(
                hashlib.file_digest(stream, "sha256").hexdigest() == digest.hexdigest(),
                "output_changed",
            )
            require(members == _snapshot(root_fd, keep_data=False), "input_changed")
            _recheck_root(root, root_fd)
            _recheck_root(output.parent, parent)
            require(
                _identity(info)
                == _identity(os.fstat(stream.fileno()))
                == _identity(os.stat(output.name, dir_fd=parent, follow_symlinks=False)),
                "output_changed",
            )
            return digest.hexdigest()
    except ArchiveError:
        raise
    except (OSError, ValueError, tarfile.TarError):
        raise ArchiveError("pack_failed") from None
    finally:
        for fd in (root_fd, parent):
            if fd >= 0:
                os.close(fd)


def _parse(raw: bytes) -> list[_Member]:
    require(len(raw) <= MAX_ARCHIVE_BYTES and len(raw) % 512 == 0, "archive_size_limit")
    members: list[_Member] = []
    seen: dict[str, bool] = {}
    offset = total = 0
    while True:
        require(offset + 512 <= len(raw), "truncated_archive")
        block = raw[offset : offset + 512]
        offset += 512
        if block == ZERO_BLOCK:
            tail = memoryview(raw)[offset:]
            require(512 <= len(tail) <= tarfile.RECORDSIZE and not any(tail), "invalid_trailer")
            require(bool(members), "missing_root")
            return members
        require(len(members) < MAX_MEMBERS, "member_count_limit")
        info = tarfile.TarInfo.frombuf(block, encoding="ascii", errors="strict")
        require(info.type in {tarfile.REGTYPE, tarfile.DIRTYPE}, "unsupported_member_type")
        require(0 <= info.mode <= 0o777, "special_permission_bits")
        require(0 <= info.size <= MAX_FILE_BYTES, "file_size_limit")
        directory = info.type == tarfile.DIRTYPE
        require(not directory or info.size == 0, "directory_payload")
        member = _Member(info.name, directory, info.mode, info.size)
        require(_header(member) == block, "noncanonical_metadata")
        if not members:
            require(info.name == "." and directory, "missing_root")
        else:
            _name(info.name)
            require(info.name not in seen, "duplicate_member")
            parent = info.name.rpartition("/")[0] or "."
            require(seen.get(parent) is True, "missing_or_file_parent")
            if len(members) > 1:
                require(info.name > members[-1].name, "unsorted_members")
        seen[info.name] = directory
        total += info.size
        require(total <= MAX_TOTAL_BYTES, "total_size_limit")
        end = offset + info.size
        padded = end + (-info.size % 512)
        require(padded <= len(raw), "truncated_archive")
        require(not any(memoryview(raw)[end:padded]), "nonzero_padding")
        members.append(
            _Member(info.name, directory, info.mode, info.size, data=memoryview(raw)[offset:end])
        )
        offset = padded


def unpack_bundle(archive: Path, destination: Path, expected_sha256: str) -> None:
    """Verify the whole archive and extract data only into a fresh private parent."""
    archive_parent = parent = root = -1
    try:
        require(
            isinstance(expected_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
            "invalid_digest",
        )
        archive, destination = _absolute(archive), _absolute(destination)
        archive_parent = _directory(archive.parent)
        parent = _directory(destination.parent)
        require(not os.path.lexists(destination), "destination_exists")
        info = os.fstat(parent)
        require(
            info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, "parent_not_private"
        )
        require(_empty(parent), "parent_not_empty")
        raw, identity = _read_file(archive_parent, archive.name, MAX_ARCHIVE_BYTES)
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "digest_mismatch")
        members = _parse(raw)
        require(
            _identity(os.stat(archive.name, dir_fd=archive_parent, follow_symlinks=False))
            == identity,
            "input_changed",
        )
        _recheck_root(archive.parent, archive_parent)
        _recheck_root(destination.parent, parent)
        require(_identity(os.fstat(parent)) == _identity(info), "parent_changed")
        require(_empty(parent), "parent_not_empty")
        os.mkdir(destination.name, 0o700, dir_fd=parent)
        root = os.open(
            destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        parent_identity = _identity(os.fstat(parent))
        for member in members[1:]:
            parts = member.name.split("/")
            fd = os.dup(root)
            try:
                for part in parts[:-1]:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = child
                if member.directory:
                    os.mkdir(parts[-1], 0o700, dir_fd=fd)
                else:
                    child = os.open(
                        parts[-1],
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=fd,
                    )
                    with os.fdopen(child, "wb") as stream:
                        require(stream.write(member.data) == member.size, "short_write")
                        stream.flush()
                        os.fchmod(stream.fileno(), member.mode)
            finally:
                os.close(fd)
        require(
            _identity(os.stat(archive.name, dir_fd=archive_parent, follow_symlinks=False))
            == identity,
            "input_changed",
        )
        _recheck_root(archive.parent, archive_parent)
        _recheck_root(destination.parent, parent)
        require(_identity(os.fstat(parent)) == parent_identity, "parent_changed")
        require(
            _identity(os.stat(destination.name, dir_fd=parent, follow_symlinks=False))
            == _identity(os.fstat(root)),
            "destination_changed",
        )
        # Apply restrictive directory modes only after all descendants have been written.
        for member in reversed(members):
            if member.directory:
                fd = os.dup(root)
                try:
                    if member.name != ".":
                        for part in member.name.split("/"):
                            child = os.open(
                                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                            )
                            os.close(fd)
                            fd = child
                    os.fchmod(fd, member.mode)
                finally:
                    os.close(fd)
        require(
            _identity(os.stat(archive.name, dir_fd=archive_parent, follow_symlinks=False))
            == identity,
            "input_changed",
        )
        _recheck_root(archive.parent, archive_parent)
        _recheck_root(destination.parent, parent)
        require(_identity(os.fstat(parent)) == parent_identity, "parent_changed")
    except ArchiveError:
        raise
    except (OSError, ValueError, tarfile.TarError):
        raise ArchiveError("unpack_failed") from None
    finally:
        for fd in (archive_parent, parent, root):
            if fd >= 0:
                os.close(fd)
