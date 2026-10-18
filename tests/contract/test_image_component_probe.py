"""Metadata-only image inventory, exercised only on isolated synthetic roots."""

import base64
import os
import re
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/probe-image-components.sh"


@pytest.fixture
def image_root() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="image-component-probe.", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        (root / "var/lib/dpkg/info").mkdir(parents=True)
        yield root


def run_probe(root: Path, source: str | None = None) -> subprocess.CompletedProcess[str]:
    arguments = ["/bin/sh", str(SCRIPT)] if source is None else ["/bin/sh", "-s", "--"]
    arguments += ["--test-root", str(root)]
    with subprocess.Popen(
        arguments,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(input=source, timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)


def decode(value: str) -> str:
    return os.fsdecode(base64.b64decode(value, validate=True))


def assert_no_payload(result: subprocess.CompletedProcess[str]) -> None:
    payload = b"PRIVATE_SYNTHETIC_PAYLOAD_MUST_NOT_APPEAR"
    output = result.stdout + result.stderr
    assert payload.decode() not in output
    assert base64.b64encode(payload + b"\n").decode() not in output
    assert payload.hex() not in output


def parse_output(output: str) -> tuple[list[list[str]], list[str]]:
    """A strict example consumer: a missing trailer is never successful evidence."""
    assert len(output.encode()) <= 2_097_152 + 256
    records = [line.split("\t") for line in output.splitlines()]
    assert records
    assert records[0] == ["VERSION", "1"]
    assert sum(row[0] == "FINISHED" for row in records) == 1
    final = records[-1]
    assert len(final) == 6 and final[0] == "FINISHED"
    assert final[1] in {"complete", "incomplete"}
    assert all(value.isdigit() for value in final[2:])
    assert int(final[3]) == len(records) - 1 - sum(
        row == ["ERROR", "producer-incomplete"] or row == ["ERROR", "output-limit-exceeded"]
        for row in records
    )
    errors = 0
    for row in records[:-1]:
        kind = row[0]
        if kind == "ENTRY":
            assert len(row) == 11
            assert row[1] == "filesystem" or row[1].startswith("package:")
            assert decode(row[2]).startswith("/")
            assert row[3] in {"file", "symlink", "directory", "other"}
            assert re.fullmatch(r"[0-7]{1,4}", row[4])
            assert all(value.isdigit() for value in row[5:10])
            if row[3] == "symlink":
                assert decode(row[10])
            else:
                assert row[10] == "-"
        elif kind == "MISSING":
            assert len(row) == 3 and row[1].startswith("package:")
            assert decode(row[2]).startswith("/")
        elif kind == "PACKAGE":
            assert len(row) == 3 and row[1] in {"dpkg", "apk"}
            assert re.fullmatch(r"[a-zA-Z0-9+._:-]+", row[2])
        elif kind == "LIMITS":
            assert row == ["LIMITS", "10000", "2097152", "16384"]
        elif kind == "ROOT":
            assert len(row) == 3 and row[1] in {"0", "1"}
            assert decode(row[2]).startswith("/")
            assert row[1] == "1" or decode(row[2]) == "/"
        elif kind == "DIAGNOSTIC_HEX":
            assert len(row) == 2
            bytes.fromhex(row[1])
            errors += 1
        else:
            assert kind in {"VERSION", "SCOPE", "LIMITATION", "STAT", "BACKEND", "ERROR"}
            assert len(row) == 2
            errors += kind == "ERROR"
    if final[1] == "complete":
        assert errors == int(final[4]) == int(final[5]) == 0
        assert int(final[2]) == int(final[3]) + 1
        assert sum(row[0] == "STAT" for row in records) == 1
        assert sum(row[0] == "BACKEND" for row in records) == 1
        assert sum(row[0] == "ROOT" for row in records) == 1
    else:
        assert int(final[4]) > 0
    return records, final


def write_fixture(root: Path, name: str, mode: int = 0o644) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("PRIVATE_SYNTHETIC_PAYLOAD_MUST_NOT_APPEAR\n")
    path.chmod(mode)
    return path


def test_inventory_names_permissions_aliases_and_package_paths(image_root: Path) -> None:
    names = [
        "opt/alternate/infocmp-versioned",
        "opt/alternate/perl5.40",
        "opt/alternate/miniperl",
        "opt/alternate/libperl.so.5.40",
        "opt/alternate/libacl.so.1",
        "opt/alternate/libmount.so.1",
        "opt/modules/Archive/Tar.pm",
        "opt/modules/Archive/Tar/File.pm",
        "opt/tools/systemd-homed",
        "opt/tools/mount.custom",
        "opt/tools/umount.custom",
        "opt/tools/nsenter",
        "opt/tools/unshare",
        "opt/renamed-package-tool",
    ]
    for name in names:
        write_fixture(image_root, name)
    special_path = write_fixture(image_root, "opt/perl-special odd\nname", 0o751)
    (image_root / "arbitrary-alias").symlink_to("opt/alternate/libperl.so.5.40")
    (image_root / "dangling-alias").symlink_to("missing\n\t\n")
    (image_root / "var/lib/dpkg/info/perl-base.list").write_text(
        "/.\n/opt/renamed-package-tool\n/opt/removed-tool\n"
    )
    result = run_probe(image_root)
    assert result.returncode == 0, result.stdout + result.stderr
    records, final = parse_output(result.stdout)
    assert final[1] == "complete"
    entries = {decode(row[2]): row for row in records if row[0] == "ENTRY"}
    assert set("/" + name for name in names) <= entries.keys()
    assert entries["/opt/renamed-package-tool"][1] == "package:perl-base"
    special = entries["/opt/perl-special odd\nname"]
    assert int(special[4], 8) == special_path.stat().st_mode & 0o7777
    assert int(special[5]) == os.getuid()
    assert decode(entries["/arbitrary-alias"][10]) == "opt/alternate/libperl.so.5.40"
    assert decode(entries["/dangling-alias"][10]) == "missing\n\t\n"
    assert any(row[0] == "MISSING" and decode(row[2]) == "/opt/removed-tool" for row in records)
    assert_no_payload(result)


@pytest.mark.parametrize("package", ["libacl1:arm64", "libudev1:arm64", "libmount1:arm64"])
def test_shared_source_package_paths(image_root: Path, package: str) -> None:
    write_fixture(image_root, "opt/opaque-package-member")
    (image_root / f"var/lib/dpkg/info/{package}.list").write_text("/opt/opaque-package-member\n")
    result = run_probe(image_root)
    assert result.returncode == 0
    records, _ = parse_output(result.stdout)
    assert ["PACKAGE", "dpkg", package] in records
    assert any(
        row[0] == "ENTRY"
        and row[1] == f"package:{package}"
        and decode(row[2]) == "/opt/opaque-package-member"
        for row in records
    )
    assert_no_payload(result)


def test_special_bits_on_arbitrarily_named_files(image_root: Path) -> None:
    path = write_fixture(image_root, "opt/arbitrary-special-file", 0o6751)
    if path.stat().st_mode & 0o6000 != 0o6000:
        pytest.skip("host sandbox strips setuid/setgid bits from synthetic fixtures")
    result = run_probe(image_root)
    assert result.returncode == 0
    records, _ = parse_output(result.stdout)
    entry = next(
        row
        for row in records
        if row[0] == "ENTRY" and decode(row[2]) == "/opt/arbitrary-special-file"
    )
    assert int(entry[4], 8) & 0o6000 == 0o6000


def test_no_payload_reads_or_symlink_traversal(image_root: Path) -> None:
    for directory in ("proc", "sys", "dev", "run"):
        write_fixture(image_root, f"{directory}/infocmp")
    os.mkfifo(image_root / "perl-fifo")
    write_fixture(image_root, "opt/perl-unreadable", 0)
    with tempfile.TemporaryDirectory(prefix="image-component-probe.", dir="/tmp") as outside:
        other = Path(outside).resolve()
        write_fixture(other, "infocmp-outside")
        (image_root / "escape").symlink_to(other, target_is_directory=True)
        result = run_probe(image_root)
    assert result.returncode == 0
    records, _ = parse_output(result.stdout)
    entries = {decode(row[2]): row for row in records if row[0] == "ENTRY"}
    assert entries["/perl-fifo"][3] == "other"
    assert "/opt/perl-unreadable" in entries
    assert "/escape" in entries
    assert not any(
        "outside" in name or name.startswith(("/proc/", "/sys/", "/dev/", "/run/"))
        for name in entries
    )


@pytest.mark.parametrize("bad_path", ["relative", "/../etc/passwd", "/proc/1/environ", "/a//b"])
def test_bad_package_paths_fail_closed(image_root: Path, bad_path: str) -> None:
    (image_root / "var/lib/dpkg/info/perl-base.list").write_text(bad_path + "\n")
    result = run_probe(image_root)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert final[1] == "incomplete"
    assert not any(
        row[0] in {"ENTRY", "MISSING"} and row[1].startswith("package:") for row in records
    )


def test_package_symlink_escapes_fail_closed(image_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="image-component-probe.", dir="/tmp") as outside:
        other = Path(outside).resolve()
        write_fixture(other, "secret")
        (image_root / "escape").symlink_to(other, target_is_directory=True)
        (image_root / "var/lib/dpkg/info/perl-base.list").write_text("/escape/secret\n")
        (image_root / "var/lib/dpkg/info/perl-other.list").symlink_to(other / "secret")
        result = run_probe(image_root)
    assert result.returncode != 0
    records, _ = parse_output(result.stdout)
    assert ["ERROR", "package-parent-escaped"] in records
    assert ["ERROR", "unsafe-or-unreadable-package-list"] in records
    assert_no_payload(result)


def test_missing_backend_is_incomplete(image_root: Path) -> None:
    (image_root / "var/lib/dpkg/info").rmdir()
    result = run_probe(image_root)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert ["ERROR", "package-path-inspection-unsupported"] in records
    assert final[1] == "incomplete"


@pytest.mark.parametrize(
    "failure", ["none", "warning", "query-failed", "list-failed", "bad-header"]
)
def test_apk_installed_only_queries_and_strict_failures(image_root: Path, failure: str) -> None:
    """CLI-contract fixture, not a substitute for the exact Alpine image run."""
    (image_root / "var/lib/dpkg/info").rmdir()
    write_fixture(image_root, "opt/opaque-package-member")
    source = SCRIPT.read_text()
    query = "printf 'perl\\nunrelated\\n'"
    listing = "printf 'perl-5.40-r1 contains:\\nopt/opaque-package-member\\n'"
    if failure == "warning":
        query += "; printf 'WARNING: synthetic APKINDEX unavailable\\n' >&2"
    elif failure == "query-failed":
        query = "return 42"
    elif failure == "list-failed":
        listing = "return 43"
    elif failure == "bad-header":
        listing = "printf 'unexpected listing format\\n'"
    fixture = f"""apk() {{
    case "$*" in
        '--no-network --repositories-file /dev/null info') {query};;
        '--no-network --repositories-file /dev/null info -L perl') {listing};;
        *) printf 'unexpected APK arguments\\n' >&2; return 99;;
    esac
}}
"""
    assert source.count('elif [ "$test_mode" = 0 ] && command -v apk') == 1
    # Only this in-memory fixture enables APK under a synthetic root. The shell
    # function replaces the CLI; no host package manager or external files run.
    source = source.replace('elif [ "$test_mode" = 0 ] && command -v apk', "elif command -v apk")
    source = source.replace("packages() {\n", fixture + "packages() {\n", 1)
    result = run_probe(image_root, source)
    records, final = parse_output(result.stdout)
    assert ["BACKEND", "apk-path-lists"] in records
    assert_no_payload(result)
    if failure == "none":
        assert result.returncode == 0 and final[1] == "complete"
        assert ["PACKAGE", "apk", "perl"] in records
        assert any(
            row[0] == "ENTRY"
            and row[1] == "package:perl"
            and decode(row[2]) == "/opt/opaque-package-member"
            for row in records
        )
    else:
        assert result.returncode != 0 and final[1] == "incomplete"
        expected = {
            "warning": "DIAGNOSTIC_HEX",
            "query-failed": "apk-info-failed",
            "list-failed": "apk-list-failed",
            "bad-header": "unsupported-apk-list-format",
        }[failure]
        assert any(expected in row for row in records)


@pytest.mark.parametrize("tool", ["base64", "tr"])
@pytest.mark.parametrize("partial", ["", "c3ludGhldGlj"])
def test_encoder_failure_never_emits_complete_target(
    image_root: Path, tool: str, partial: str
) -> None:
    (image_root / "alias").symlink_to("synthetic-link-target")
    trigger = "synthetic-link-target"
    if tool == "tr":
        trigger = base64.b64encode(trigger.encode()).decode()
    fixture = f"""{tool}() {{
    IFS= read -r value || :
    if [ "$value" = "{trigger}" ]; then printf "%s" "{partial}"; return 17; fi
    printf "%s" "$value" | command {tool} "$@"
}}
"""
    source = SCRIPT.read_text().replace("encode() {\n", fixture + "encode() {\n", 1)
    result = run_probe(image_root, source)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert final[1] == "incomplete"
    assert ["ERROR", "target-encoding-failed"] in records
    assert not any(row[0] == "ENTRY" for row in records)


def test_root_encoder_failure_is_incomplete(image_root: Path) -> None:
    source = SCRIPT.read_text().replace("root=/\n", "base64() { return 17; }\nroot=/\n", 1)
    result = run_probe(image_root, source)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert ["ERROR", "root-encoding-failed"] in records
    assert final[1] == "incomplete"


def test_unreadable_tree_preserves_diagnostics(image_root: Path) -> None:
    directory = image_root / "unreadable"
    directory.mkdir()
    directory.chmod(0)
    try:
        if os.access(directory, os.R_OK | os.X_OK):
            pytest.skip("current process can bypass directory permissions")
        result = run_probe(image_root)
    finally:
        directory.chmod(0o700)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert ["ERROR", "filesystem-traversal-failed"] in records
    assert any(row[0] == "DIAGNOSTIC_HEX" for row in records)
    assert final[1] == "incomplete"


@pytest.mark.parametrize("root", ["/", "/tmp", "/private/tmp", "/tmp/image-component-probe.x/.."])
def test_unsafe_roots_rejected_without_inventory(root: str) -> None:
    result = run_probe(Path(root))
    assert result.returncode == 2
    assert "ENTRY\t" not in result.stdout


def test_symlink_test_root_rejected(image_root: Path) -> None:
    alias = image_root.with_name(image_root.name + "-alias")
    alias.symlink_to(image_root, target_is_directory=True)
    try:
        assert run_probe(alias).returncode == 2
    finally:
        alias.unlink()


def test_output_limit_is_bounded_and_incomplete(image_root: Path) -> None:
    # Invalid package paths exercise the real collector without 10,000 subprocesses.
    (image_root / "var/lib/dpkg/info/perl-base.list").write_text("/\n" + "relative\n" * 10020)
    result = run_probe(image_root)
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert ["ERROR", "output-limit-exceeded"] in records
    assert int(final[5]) > 0


@pytest.mark.parametrize("failure", ["producer-exit", "stderr", "long-record", "byte-limit"])
def test_collector_retains_failures_and_caps_bytes(image_root: Path, failure: str) -> None:
    header = run_probe(image_root).stdout.rsplit("FINISHED\t", 1)[0]
    if failure == "producer-exit":
        stream = header
    elif failure == "stderr":
        stream = header + "stat: synthetic failure\nPRODUCER_FINISHED\n"
    elif failure == "long-record":
        stream = header + "LIMITATION\t" + "x" * 20000 + "\nPRODUCER_FINISHED\n"
    else:
        stream = header + ("LIMITATION\t" + "x" * 16000 + "\n") * 140 + "PRODUCER_FINISHED\n"
    collector = SCRIPT.read_text().split("} 2>&1 | awk '\n", 1)[1].removesuffix("'\n")
    result = subprocess.run(
        ["/usr/bin/awk", collector],
        input=stream,
        capture_output=True,
        text=True,
        env={"LC_ALL": "C"},
        timeout=5,
        check=False,
    )
    assert result.returncode != 0
    records, final = parse_output(result.stdout)
    assert final[1] == "incomplete"
    if failure == "producer-exit":
        assert ["ERROR", "producer-incomplete"] in records
    elif failure == "stderr":
        assert ["DIAGNOSTIC_HEX", b"stat: synthetic failure".hex()] in records
    else:
        assert ["ERROR", "output-limit-exceeded"] in records
        assert int(final[5]) > 0


@pytest.mark.parametrize("corruption", ["no-trailer", "wrong-base64", "wrong-mode", "no-backend"])
def test_consumer_rejects_malformed_evidence(image_root: Path, corruption: str) -> None:
    write_fixture(image_root, "perl")
    output = run_probe(image_root).stdout
    if corruption == "no-trailer":
        output = "\n".join(output.splitlines()[:-1]) + "\n"
    elif corruption == "wrong-base64":
        output = output.replace("L3Blcmw=", "!!not-base64!!")
    elif corruption == "wrong-mode":
        output = output.replace("\t644\t", "\t999\t")
    else:
        output = output.replace("BACKEND\tdpkg-path-lists\n", "")
    with pytest.raises((AssertionError, ValueError)):
        parse_output(output)


def test_static_privacy_and_portability_contract() -> None:
    source = SCRIPT.read_text()
    assert source.startswith("#!/bin/sh\n")
    assert "root=/\n" in source and "--test-root" in source
    assert "-xdev" in source and "-type l" in source
    assert "-perm -4000" in source and "-perm -2000" in source
    assert "apk --no-network --repositories-file /dev/null info -L" in source
    assert source.count("apk --no-network --repositories-file /dev/null info") == 2
    assert (
        "DAC_READ_SEARCH" in source and "NOT normal-entrypoint/runtime privilege evidence" in source
    )
    assert "package-metadata-worker-failed" in source
    assert "PRODUCER_FINISHED" in source and "finished != 1" in source
    assert "2>&1 | awk" in source
    assert re.findall(r'<\s*"\$([^"\n]+)"', source) == ["list"]
    for forbidden in (
        "eval ",
        "curl ",
        "wget ",
        "docker ",
        "/environ",
        "/cmdline",
        "cat ",
        "mktemp ",
    ):
        assert forbidden not in source
    subprocess.run(["/bin/sh", "-n", str(SCRIPT)], check=True, capture_output=True)
