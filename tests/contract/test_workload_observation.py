"""Workload evidence must not borrow shell-probe facts or read service secrets."""

import base64
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import observe_runtime_workload as observer


def encoded(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def process(pid: int = 1, parent: int = 0, started: int = 123, state: str = "S") -> str:
    stat = f"{pid} (name with ) parentheses) {state} {parent}" + " 0" * 17 + f" {started}"
    lines = [f"BEGIN\t{pid}\t{encoded(stat)}"]
    values = {
        "Uid": "10001\t10001\t10001\t10001",
        "Gid": "10001\t10001\t10001\t10001",
        "PPid": str(parent),
        "NoNewPrivs": "1",
        "Seccomp": "2",
        **{name: "0000000000000000" for name in observer.CAPABILITIES},
    }
    lines.extend(f"STATUS\t{pid}\t{name}:\t{value}" for name, value in values.items())
    lines.extend(
        [
            f"EXE\t{pid}\t{encoded('/usr/local/bin/python')}",
            f"MAPS\t{pid}\t{encoded('00400000-00410000 r-xp 0 00:00 123 /usr/local/bin/python')}",
            f"FD\t{pid}\t0\t{encoded('/dev/null')}",
            f"FDINFO\t{pid}\t0\tflags:\t0100000",
            f"FDINFO\t{pid}\t0\tmnt_id:\t22",
            f"FDINFO\t{pid}\t0\tino:\t3",
            f"FDVERIFY\t{pid}\t0\t{encoded('/dev/null')}",
            f"FDINFOVERIFY\t{pid}\t0\tflags:\t0100000",
            f"FDINFOVERIFY\t{pid}\t0\tmnt_id:\t22",
            f"FDINFOVERIFY\t{pid}\t0\tino:\t3",
            f"END\t{pid}\t{encoded(stat)}",
        ]
    )
    return "\n".join(lines) + "\n"


HEADER = "VERSION\t1\nSELF\t999\nOBSERVER_UID\t10001\nKERNEL\t6.12.0\n"
HEADER += f"MOUNTS\t{encoded('22 1 0:1 / / rw - overlay overlay rw')}\n"


def envelope(*processes: str) -> str:
    body = "".join(processes)
    final = "\n".join(
        line.replace("END\t", "FINAL\t", 1)
        for line in body.splitlines()
        if line.startswith("END\t")
    )
    return HEADER + body + final + "\nFINISHED\n"


SAFE = envelope(process(), process(2, 1), process(10, 0))


def identity(service: str = "api") -> dict[str, Any]:
    return {
        "id": f"{sorted(observer.SERVICES).index(service) + 1:064x}",
        "project": "test-fixture",
        "service": service,
        "image_id": "sha256:" + "a" * 64,
        "oneoff": "False",
        "running": True,
        "pid": 321,
        "started_at": "2026-10-16T23:00:00Z",
        "restart_count": 0,
        "exit_code": 0,
        "configured_user": "appuser",
        "privileged": False,
        "cap_drop": ["ALL"],
        "cap_add": None,
        "security_opt": ["no-new-privileges"],
        "pid_mode": "",
        "network_mode": "test-fixture_default",
        "read_only_root": True,
    }


def test_actual_root_and_descendants_included_without_unrelated_exec_tree() -> None:
    result = observer.parse_observation(SAFE)
    assert result["complete"]
    assert [item["pid"] for item in result["processes"]] == [1, 2]
    assert result["excluded_pids"] == [10]
    assert result["processes"][0]["descriptors"][0]["target"] == "/dev/null"


@pytest.mark.parametrize(
    "raw",
    [
        SAFE.replace("FINISHED\n", ""),
        SAFE + "surprise\n",
        SAFE.replace("VERSION\t1", "VERSION\t2"),
        SAFE.replace("SELF\t999", "SELF\t1"),
        SAFE.replace("OBSERVER_UID\t10001", "OBSERVER_UID\t0"),
        SAFE.replace("FINISHED", "VERSION\t1\nFINISHED"),
        envelope(process(2, 0)),
        SAFE.replace("EXE\t1\t", "UNRECOGNIZED\t1\t"),
        SAFE.replace("EXE\t1\t", "EXE\t1\t!!"),
        SAFE.replace("flags:\t0100000", "flags:\t9", 1),
        SAFE.replace("mnt_id:\t22", "mnt_id:\tnot-a-number", 1),
        envelope(process(), process()),
        SAFE.replace(f"EXE\t1\t{encoded('/usr/local/bin/python')}", "EXE\t1\t"),
        SAFE.replace(
            encoded("00400000-00410000 r-xp 0 00:00 123 /usr/local/bin/python"),
            encoded("not a mapping"),
            1,
        ),
        SAFE.replace(
            encoded("00400000-00410000 r-xp 0 00:00 123 /usr/local/bin/python"),
            encoded("   "),
            1,
        ),
        SAFE.replace(f"MOUNTS\t{encoded('22 1 0:1 / / rw - overlay overlay rw')}", "MOUNTS\t"),
    ],
)
def test_malformed_or_incomplete_envelopes_fail(raw: str) -> None:
    with pytest.raises(ValueError):
        observer.parse_observation(raw)


@pytest.mark.parametrize(
    "raw",
    [
        SAFE.replace("Uid:\t10001", "Uid:\t0", 1),
        SAFE.replace("NoNewPrivs:\t1", "NoNewPrivs:\t0", 1),
        SAFE.replace("CapAmb:\t0000000000000000", "CapAmb:\t0000000000000001", 1),
        SAFE.replace("FDINFO\t1\t0\tino:\t3\n", ""),
        SAFE.replace("STATUS\t1\tSeccomp:\t2\n", ""),
        SAFE.replace("FINISHED", "ERROR\tdescriptor-raced-1-0\nFINISHED"),
        SAFE.replace("Gid:\t10001", "Gid:\tnope", 1),
        SAFE.replace("Seccomp:\t2", "Seccomp:\t9", 1),
        SAFE.replace("FDINFOVERIFY\t1\t0\tino:\t3", "FDINFOVERIFY\t1\t0\tino:\t4", 1),
        SAFE.replace(
            f"FDVERIFY\t1\t0\t{encoded('/dev/null')}", f"FDVERIFY\t1\t0\t{encoded('/different')}"
        ),
        envelope(process(), process(2, 1, started=122)),
    ],
)
def test_missing_privileges_or_descriptor_metadata_remain_incomplete(raw: str) -> None:
    assert not observer.parse_observation(raw)["complete"]


def test_pid_reuse_or_parent_change_is_rejected() -> None:
    end = process(started=124).splitlines()[-1]
    raw = envelope(process().replace(process().splitlines()[-1], end))
    with pytest.raises(ValueError, match="identity changed"):
        observer.parse_observation(raw)


@pytest.mark.parametrize("phase", ["BEGIN", "END", "FINAL"])
@pytest.mark.parametrize("state", ["RS", "ZT"])
def test_process_state_is_one_kernel_state_not_a_substring(phase: str, state: str) -> None:
    raw = []
    for line in SAFE.splitlines():
        if line.startswith(f"{phase}\t1\t"):
            stat = observer.decoded(line.split("\t")[2])
            line = f"{phase}\t1\t{encoded(stat.replace(') S ', f') {state} '))}"
        raw.append(line)
    with pytest.raises(ValueError, match="identity metadata"):
        observer.parse_observation("\n".join(raw))


@pytest.mark.parametrize("omitted", [("END", "FINAL"), ("FINAL",)])
def test_excluded_processes_still_require_complete_identity_frames(
    omitted: tuple[str, ...],
) -> None:
    raw = "\n".join(
        line
        for line in SAFE.splitlines()
        if not any(line.startswith(f"{kind}\t10\t") for kind in omitted)
    )
    result = observer.parse_observation(raw)
    assert not result["complete"]
    assert "missing-final-identity-10" in result["errors"]
    assert result["excluded_pids"] == [10]


def test_zombie_descendants_are_recorded_but_never_counted_as_live_evidence() -> None:
    zombie = process(3, 1, state="Z").splitlines()
    zombie = [line for line in zombie if line.startswith(("BEGIN", "STATUS", "END"))]
    result = observer.parse_observation(envelope(process(), "\n".join(zombie) + "\n"))
    assert result["complete"]
    assert result["processes"][1]["inactive_zombie"]
    assert "EXE" not in result["processes"][1]
    assert not result["processes"][0]["inactive_zombie"]
    root = (
        "\n".join(
            line
            for line in process(state="Z").splitlines()
            if line.startswith(("BEGIN", "STATUS", "END"))
        )
        + "\n"
    )
    root_zombie = observer.parse_observation(envelope(root))
    assert not root_zombie["complete"]
    with pytest.raises(ValueError, match="contradictory"):
        observer.parse_observation(envelope(process(), process(3, 1, state="Z")))


def test_process_exiting_during_the_snapshot_is_incomplete() -> None:
    live = process().splitlines()
    live[-1] = process(state="Z").splitlines()[-1]
    result = observer.parse_observation(envelope("\n".join(live) + "\n"))
    assert not result["complete"]
    assert "process-exited-during-observation-1" in result["errors"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", "real-store"),
        ("service", "web"),
        ("image_id", "sha256:" + "b" * 64),
        ("oneoff", "True"),
        ("privileged", True),
        ("cap_add", ["SYS_ADMIN"]),
        ("cap_drop", []),
        ("security_opt", []),
        ("pid_mode", "host"),
        ("network_mode", "host"),
        ("network_mode", "container:other"),
        ("configured_user", "0:0"),
        ("read_only_root", False),
    ],
)
def test_reject_foreign_or_differently_isolated_containers(field: str, value: object) -> None:
    info = {**identity(), field: value}
    with pytest.raises(ValueError):
        observer.validate_identity(info, "test-fixture", "api", "sha256:" + "a" * 64, "appuser")


def test_probe_and_inspect_do_not_collect_secret_or_descriptor_contents() -> None:
    script = observer.PROBE_PATH.read_text()
    assert "/environ" not in script and "/cmdline" not in script
    assert 'readlink "$descriptor"' in script
    assert script.index("observer_uid=$(id -u)") < script.index("encode < /proc/1/mountinfo")
    assert 'done < "$directory/fdinfo/$fd"' in script
    assert '< "$descriptor"' not in script and 'cat "$descriptor"' not in script
    assert ".Config.Env" not in observer.INSPECT and ".Args" not in observer.INSPECT
    assert ".Config.Cmd" not in observer.INSPECT and ".LogPath" not in observer.INSPECT


@pytest.mark.parametrize("scenario", ["running", "exited", "restarted", "timeout", "invalid-utf8"])
def test_retains_exact_scoped_raw_evidence_and_never_restarts_services(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario: str,
) -> None:
    inventory = {
        "complete": True,
        "images": [
            {"service": name, "image_id": "sha256:" + "a" * 64, "user": "appuser"}
            for name in observer.SERVICES
        ],
    }
    images = tmp_path / "images.json"
    images.write_text(json.dumps(inventory))
    output = tmp_path / "evidence"
    monkeypatch.setattr(
        sys,
        "argv",
        ["observer", "--project", "test-fixture", "--images", str(images), "--output", str(output)],
    )
    identities = {identity(service)["id"]: identity(service) for service in observer.SERVICES}
    calls: list[tuple[str, ...]] = []
    inspections: dict[str, int] = {}

    def run(*args: str, input_text: str | None = None) -> observer.CapturedProcess:
        calls.append(args)
        if args[0] == "ps":
            service = next(
                value.split("=", 2)[2]
                for value in args
                if value.startswith("label=com.docker.compose.service=")
            )
            return observer.CapturedProcess(
                list(args), 0, (identity(service)["id"] + "\n").encode(), b""
            )
        assert args[0] == "exec" and args[1] == "--interactive"
        assert args[3:] == ("timeout", "-k", "2", "35", "sh", "-s")
        assert input_text == observer.PROBE_PATH.read_text()
        if scenario == "timeout":
            raise subprocess.TimeoutExpired(args, 45, output=b"partial\xff", stderr=b"timed out")
        raw = SAFE.encode()
        if scenario == "invalid-utf8":
            raw = raw.replace(b"KERNEL\t6", b"KERNEL\t\xff6")
        return observer.CapturedProcess(list(args), 0, raw, b"")

    def inspect(container: str) -> dict[str, Any]:
        inspections[container] = inspections.get(container, 0) + 1
        info = copy.deepcopy(identities[container])
        if scenario == "exited" and info["service"] == "migrate":
            info["running"] = False
        if scenario == "restarted" and inspections[container] > 1:
            info["restart_count"] = 1
        return info

    monkeypatch.setattr(observer, "docker", run)
    monkeypatch.setattr(observer, "inspect", inspect)
    with pytest.raises(SystemExit) as stopped:
        observer.main()
    assert stopped.value.code == (0 if scenario == "running" else 1)
    report = json.loads((output / "observation.json").read_bytes())
    assert len(report["services"]) == 8
    assert report["probe_sha256"] == observer.checksum(observer.PROBE_PATH.read_bytes())
    assert report["inventory_sha256"] == observer.checksum(images.read_bytes())
    assert (output / observer.PROBE_PATH.name).read_bytes() == observer.PROBE_PATH.read_bytes()
    assert (output / Path(observer.__file__).name).read_bytes() == Path(
        observer.__file__
    ).read_bytes()
    for item in report["services"]:
        assert item["started_at"] <= item["finished_at"]
        if "stdout_sha256" in item:
            assert (
                observer.checksum((output / f"{item['service']}.stdout").read_bytes())
                == item["stdout_sha256"]
            )
        if scenario == "timeout":
            assert (output / f"{item['service']}.timeout-stdout").read_bytes() == b"partial\xff"
        if scenario == "invalid-utf8":
            assert not item["complete"]
            assert item["error"] == "UnicodeDecodeError: observation incomplete"
            assert b"\xff" in (output / f"{item['service']}.stdout").read_bytes()
    assert all(args[0] in {"ps", "exec"} for args in calls)
    assert (output.stat().st_mode & 0o777) == 0o700
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in output.iterdir())


def test_new_observer_is_bound_to_deployment_hash() -> None:
    import runpy

    files = runpy.run_path("scripts/check-image-findings.py")["deployment_files"](Path("."))
    assert "scripts/observe_runtime_workload.py" in files
    assert "scripts/probe-runtime-workload.sh" in files


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_capture_enforces_byte_bounds_before_retention(stream: str) -> None:
    result = observer.bounded_process(
        [sys.executable, "-c", f"import sys; sys.{stream}.write('x'*4096); sys.{stream}.flush()"],
        stdout_limit=1024,
        stderr_limit=1024,
    )
    assert result.returncode == 125
    assert f"{stream} truncated" in result.capture_error
    assert len(result.stdout) <= 1024
    assert len(result.stderr) <= 1024


def test_capture_deadline_kills_own_child_and_retains_prefix() -> None:
    result = observer.bounded_process(
        [sys.executable, "-c", "import time; print('prefix',flush=True); time.sleep(10)"],
        timeout=0.15,
    )
    assert result.returncode == 124
    assert result.stdout == b"prefix\n"
    assert not result.stderr
    assert "deadline exceeded" in result.capture_error


def test_capture_preserves_invalid_bytes_without_manufacturing_stderr() -> None:
    result = observer.bounded_process(
        [sys.executable, "-c", "import os; os.write(1,b'\\xff'); os.write(2,b'\\xfe')"],
    )
    assert result.returncode == 0
    assert result.stdout == b"\xff" and result.stderr == b"\xfe"
    assert not result.capture_error
