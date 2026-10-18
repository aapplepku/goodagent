"""Final-runtime pruning contracts; only disposable synthetic roots are executed."""

import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra/docker/prune-runtime-acl.sh"
CONSUMERS = (
    "usr/bin/cp",
    "usr/bin/install",
    "usr/bin/mv",
    "usr/bin/sed",
    "usr/bin/tar",
    "usr/sbin/useradd",
    "usr/sbin/usermod",
)
TRIPLETS = {"arm64": "aarch64-linux-gnu", "amd64": "x86_64-linux-gnu"}
DOCKERFILES = (
    "apps/api/Dockerfile",
    "apps/worker/Dockerfile",
    "apps/web/Dockerfile",
    "apps/shopper/Dockerfile",
    "infra/docker/qdrant/Dockerfile",
)
PAYLOAD = b"SYNTHETIC_FILE_CONTENT_MUST_NOT_BE_READ_OR_PRINTED\n"


def put(root: Path, name: str, data: bytes = PAYLOAD) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def library_paths(root: Path, architecture: str = "arm64") -> tuple[Path, Path]:
    directory = root / "usr/lib" / TRIPLETS[architecture]
    return directory / "libacl.so.1", directory / "libacl.so.1.1.2302"


def package_list(root: Path, architecture: str = "arm64") -> Path:
    return root / f"var/lib/dpkg/info/libacl1:{architecture}.list"


def populate(root: Path, architecture: str) -> None:
    soname, library = library_paths(root, architecture)
    for name in CONSUMERS:
        put(root, name).chmod(0o755)
    put(root, str(library.relative_to(root)))
    soname.symlink_to(library.name)
    for directory in ("bin", "sbin", "lib"):
        (root / directory).symlink_to(f"usr/{directory}")
    paths = [
        "/.",
        "/usr",
        "/usr/lib",
        f"/usr/lib/{TRIPLETS[architecture]}",
        "/" + str(library.relative_to(root)),
        "/usr/share",
        "/usr/share/doc",
        "/usr/share/doc/libacl1",
        f"/usr/share/doc/libacl1/changelog.Debian.{architecture}.gz",
        "/usr/share/doc/libacl1/changelog.Debian.gz",
        "/usr/share/doc/libacl1/changelog.gz",
        "/usr/share/doc/libacl1/copyright",
        "/usr/share/lintian",
        "/usr/share/lintian/overrides",
        "/usr/share/lintian/overrides/libacl1",
        "/" + str(soname.relative_to(root)),
    ]
    put(root, str(package_list(root, architecture).relative_to(root)), "\n".join(paths).encode())
    put(root, "var/lib/dpkg/status")
    put(root, f"var/lib/dpkg/info/libacl1:{architecture}.md5sums")
    for name in paths:
        if name.startswith("/usr/share/doc/libacl1/") or name.endswith("overrides/libacl1"):
            put(root, name.lstrip("/"))
    put(root, "usr/share/doc/open-commerce-agent/NOTICE")
    for name in ("sh", "rm", "mkdir", "chown", "find", "chmod", "awk", "stat"):
        put(root, f"usr/bin/{name}").chmod(0o755)
    put(root, "usr/lib/retained.so")


@pytest.fixture
def image_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="runtime-acl-prune.", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        populate(root, "arm64")
        yield root


def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(SCRIPT), *arguments],
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def run_prune(root: Path, architecture: str = "arm64") -> subprocess.CompletedProcess[str]:
    return invoke("--test-root", str(root), architecture)


def snapshot(root: Path) -> dict[str, tuple[int, bytes | str]]:
    result: dict[str, tuple[int, bytes | str]] = {}
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if path.is_symlink():
            value: bytes | str = os.readlink(path)
        elif stat.S_ISREG(mode):
            value = path.read_bytes()
        else:
            value = "directory"
        result[str(path.relative_to(root))] = mode, value
    return result


def assert_refused_without_deletion(root: Path, architecture: str = "arm64") -> None:
    before = snapshot(root)
    result = run_prune(root, architecture)
    assert result.returncode != 0, result.stdout
    assert "ACL pruning refused:" in result.stderr
    assert "awk:" not in result.stderr
    assert PAYLOAD.decode().strip() not in result.stdout + result.stderr
    assert snapshot(root) == before


@pytest.mark.parametrize("architecture", TRIPLETS)
def test_prunes_exact_targets_and_preserves_metadata_and_tools(architecture: str) -> None:
    with tempfile.TemporaryDirectory(prefix="runtime-acl-prune.", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        populate(root, architecture)
        (root / "unrelated-absolute-link").symlink_to("/not-present-in-image")
        (root / "unrelated-relative-link").symlink_to("usr/lib/retained.so")
        before = snapshot(root)
        soname, library = library_paths(root, architecture)
        result = run_prune(root, architecture)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "seven consumers and libacl; package metadata retained" in result.stdout
        removed = {*CONSUMERS, str(soname.relative_to(root)), str(library.relative_to(root))}
        assert snapshot(root) == {key: value for key, value in before.items() if key not in removed}
        assert not (root / "lib" / TRIPLETS[architecture] / soname.name).is_symlink()
        assert not (root / "bin/tar").exists()
        assert PAYLOAD.decode().strip() not in result.stdout + result.stderr


def test_package_owned_version_is_not_hardcoded(image_root: Path) -> None:
    soname, library = library_paths(image_root)
    replacement = library.with_name("libacl.so.1.1.2400")
    library.rename(replacement)
    soname.unlink()
    soname.symlink_to(replacement.name)
    listing = package_list(image_root)
    listing.write_text(listing.read_text().replace(library.name, replacement.name))
    result = run_prune(image_root)
    assert result.returncode == 0, result.stderr
    assert not replacement.exists()


@pytest.mark.parametrize("marker", ["/", ""])
def test_package_root_marker_variants(image_root: Path, marker: str) -> None:
    listing = package_list(image_root)
    remainder = listing.read_text().split("\n", 1)[1]
    listing.write_text(f"{marker}\n{remainder}" if marker else remainder)
    result = run_prune(image_root)
    assert result.returncode == 0, result.stderr


def test_binary_contents_are_not_needed(image_root: Path) -> None:
    _, library = library_paths(image_root)
    for path in [*(image_root / name for name in CONSUMERS), library]:
        path.chmod(0)
    result = run_prune(image_root)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["directory", "fifo", "symlink"])
def test_nonregular_library_is_rejected(image_root: Path, kind: str) -> None:
    _, library = library_paths(image_root)
    library.unlink()
    if kind == "directory":
        library.mkdir()
    elif kind == "fifo":
        os.mkfifo(library)
    else:
        library.symlink_to("/not-an-image-library")
    assert_refused_without_deletion(image_root)


def test_hardlinked_soname_is_rejected(image_root: Path, tmp_path: Path) -> None:
    soname, _ = library_paths(image_root)
    alias = tmp_path / "link"
    os.link(soname, alias, follow_symlinks=False)
    assert_refused_without_deletion(image_root)
    assert alias.is_symlink()


@pytest.mark.parametrize("name", CONSUMERS)
def test_missing_consumer_refuses_every_removal(image_root: Path, name: str) -> None:
    (image_root / name).unlink()
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("name", CONSUMERS)
def test_consumer_symlink_refuses_every_removal(image_root: Path, name: str) -> None:
    target = image_root / name
    target.unlink()
    target.symlink_to("/usr/bin/retained")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("name", (*CONSUMERS, "usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302"))
def test_hardlink_alias_refuses_every_removal(image_root: Path, name: str) -> None:
    os.link(image_root / name, image_root / "renamed-hardlink")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize(
    "name",
    [
        "opt/libacl.so.1",
        "usr/lib/x86_64-linux-gnu/libacl.so.1.1.2302",
        "usr/lib/aarch64-linux-gnu/libacl.so",
        "usr/lib/aarch64-linux-gnu/libacl.a",
        "usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302.backup",
        "opt/libacl-custom.so.1",
    ],
)
def test_unexpected_library_copy_refuses_every_removal(image_root: Path, name: str) -> None:
    put(image_root, name)
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize(
    "target",
    [
        "/usr/lib/aarch64-linux-gnu/libacl.so.1",
        "usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302",
        "/bin/cp",
        "usr/bin",
        "/usr/lib/aarch64-linux-gnu",
        "/",
        "usr/../usr/bin/./tar",
    ],
)
def test_unexpected_symlink_alias_refuses_every_removal(image_root: Path, target: str) -> None:
    (image_root / "opaque-alias").symlink_to(target)
    assert_refused_without_deletion(image_root)


def test_alias_chain_refuses_every_removal(image_root: Path) -> None:
    (image_root / "first").symlink_to("second")
    (image_root / "second").symlink_to("/lib/aarch64-linux-gnu/libacl.so.1")
    assert_refused_without_deletion(image_root)


def test_dotdot_after_directory_symlink_is_not_lexically_collapsed(image_root: Path) -> None:
    (image_root / "deep").symlink_to("usr/share/doc")
    (image_root / "opaque-alias").symlink_to("deep/../../bin/tar")
    assert_refused_without_deletion(image_root)


def test_unresolvable_alias_cycle_refuses_every_removal(image_root: Path) -> None:
    (image_root / "first").symlink_to("second")
    (image_root / "second").symlink_to("first")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize(
    "target",
    [
        "../libacl.so.1.1.2302",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302",
        "missing",
        "libacl.so.1.1.2302\n",
    ],
)
def test_unexpected_soname_target_refuses_every_removal(image_root: Path, target: str) -> None:
    soname, _ = library_paths(image_root)
    soname.unlink()
    soname.symlink_to(target)
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("directory", ["bin", "sbin", "lib"])
def test_usrmerge_target_must_be_exact(image_root: Path, directory: str) -> None:
    target = image_root / directory
    target.unlink()
    target.symlink_to(f"/usr/{directory}")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("name", ["usr/bin", "usr/lib/aarch64-linux-gnu", "var/lib/dpkg/info"])
def test_symlink_parent_cannot_escape_root(image_root: Path, name: str, tmp_path: Path) -> None:
    target = image_root / name
    target.rename(image_root / "retained-directory")
    target.symlink_to(tmp_path)
    assert_refused_without_deletion(image_root)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "entry",
    [
        "/opt/opaque-library",
        "/usr/lib/x86_64-linux-gnu/libacl.so.1",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1.9",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1.1.2302/../elsewhere",
        "/usr/share/doc/libacl1/../../outside",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1\x00",
    ],
)
def test_malformed_or_unexpected_package_paths_fail(image_root: Path, entry: str) -> None:
    listing = package_list(image_root)
    listing.write_text(listing.read_text() + "\n" + entry + "\n")
    assert_refused_without_deletion(image_root)


def test_missing_package_soname_fails(image_root: Path) -> None:
    listing = package_list(image_root)
    listing.write_text(listing.read_text().rsplit("\n", 1)[0])
    assert_refused_without_deletion(image_root)


def test_missing_package_list_fails(image_root: Path) -> None:
    package_list(image_root).unlink()
    assert_refused_without_deletion(image_root)


def test_oversized_package_list_fails(image_root: Path) -> None:
    package_list(image_root).write_bytes(b"x" * 65537)
    assert_refused_without_deletion(image_root)


def test_symlink_package_list_is_not_read(image_root: Path) -> None:
    listing = package_list(image_root)
    listing.unlink()
    listing.symlink_to("../status")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("name", ["libacl1:amd64.list", "libacl1.list"])
def test_foreign_or_unqualified_package_list_fails(image_root: Path, name: str) -> None:
    put(image_root, f"var/lib/dpkg/info/{name}")
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize("architecture", ["riscv64", "", "arm64\n", "../../"])
def test_architecture_is_closed(image_root: Path, architecture: str) -> None:
    assert_refused_without_deletion(image_root, architecture)


@pytest.mark.parametrize(
    "name,target",
    [
        ("odd\nname", "missing"),
        ("odd\tname", "missing"),
        ("alias", "missing\n"),
        ("alias", "missing\t"),
    ],
)
def test_unsupported_link_metadata_cannot_corrupt_inventory(
    image_root: Path, name: str, target: str
) -> None:
    (image_root / name).symlink_to(target)
    assert_refused_without_deletion(image_root)


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("--image",),
        ("--test-root", "/", "arm64"),
        ("--test-root", "/tmp", "arm64"),
        ("--test-root", ".", "arm64"),
    ],
)
def test_unsafe_invocation_never_enters_image_mode(arguments: tuple[str, ...]) -> None:
    result = invoke(*arguments)
    assert result.returncode != 0
    assert "ACL pruning refused:" in result.stderr


def test_test_root_symlink_and_nested_path_are_rejected(image_root: Path) -> None:
    before = snapshot(image_root)
    (image_root / "nested").mkdir()
    assert run_prune(image_root / "nested").returncode != 0
    (image_root / "nested").rmdir()
    alias = image_root.with_name(image_root.name + "-alias")
    alias.symlink_to(image_root)
    try:
        assert run_prune(alias).returncode != 0
    finally:
        alias.unlink()
    assert snapshot(image_root) == before


@pytest.mark.parametrize("filename", DOCKERFILES)
def test_final_runtime_copy_and_build_order(filename: str) -> None:
    source = (ROOT / filename).read_text()
    runtime = source[source.rfind("FROM ") :]
    assert source.count("COPY infra/docker/prune-runtime-acl.sh ") == 1
    copy = runtime.index("COPY infra/docker/prune-runtime-acl.sh /usr/local/sbin/prune-runtime-acl")
    harden = runtime.index("RUN sh /usr/local/sbin/harden-debian")
    assert copy < harden
    if filename in {"apps/api/Dockerfile", "apps/worker/Dockerfile"}:
        assert runtime.index("RUN useradd --create-home --uid 10001 appuser") < copy
    if filename == "infra/docker/qdrant/Dockerfile":
        assert runtime.index("USER root") < copy < runtime.index("USER 1000:1000")
    for command in re.findall(r"^RUN (.*)$", runtime[harden:], re.MULTILINE):
        assert not re.search(r"\b(cp|install|mv|sed|tar|useradd|usermod|apt-get|apt)\b", command)
    assert "COPY --from=build" in runtime[harden:] or filename.endswith("qdrant/Dockerfile")


def test_hardener_finishes_package_operations_before_pruning() -> None:
    source = (ROOT / "infra/docker/harden-debian.sh").read_text()
    prune = source.index("sh /usr/local/sbin/prune-runtime-acl --image")
    assert source.index("apt-get update") < source.index("apt-get upgrade -y") < prune
    assert source.index("rm /usr/local/sbin/prune-runtime-acl") > prune
    assert "apt" not in source[prune:]
    assert "chmod a-s" in source[prune:]


def test_module_is_metadata_only_and_has_no_package_manager_mutations() -> None:
    source = SCRIPT.read_text()
    assert "dpkg --print-architecture" in source
    assert "apt-get" not in source and "apt purge" not in source
    assert "readelf" not in source and "objdump" not in source and "ldd " not in source
    assert 'rm -- "$path"' in source
    assert not re.search(r"\brm\s+(?:-[^ ]+\s+)?/usr", source)
    assert "--image or --test-root" in source
