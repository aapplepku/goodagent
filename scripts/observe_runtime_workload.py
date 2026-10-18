"""Read-only process evidence from an explicitly selected, already-running test project."""

import argparse
import base64
import hashlib
import json
import os
import re
import selectors
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SERVICES = {"api", "migrate", "worker", "web", "shopper", "postgres", "redis", "qdrant"}
CAPABILITIES = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
STATUS_FIELDS = {"Uid", "Gid", "PPid", *CAPABILITIES, "NoNewPrivs", "Seccomp"}
FD_FIELDS = {"flags", "mnt_id", "ino"}
APP_SERVICES = {"api", "migrate", "worker", "web", "shopper"}
PROBE_PATH = Path(__file__).with_name("probe-runtime-workload.sh")
# Deliberately omit environment, arguments, labels other than ownership, and logs.
INSPECT = """{"id":{{json .Id}},"image_id":{{json .Image}},
"project":{{json (index .Config.Labels "com.docker.compose.project")}},
"service":{{json (index .Config.Labels "com.docker.compose.service")}},
"oneoff":{{json (index .Config.Labels "com.docker.compose.oneoff")}},
"running":{{json .State.Running}},"pid":{{json .State.Pid}},
"started_at":{{json .State.StartedAt}},"restart_count":{{json .RestartCount}},
"exit_code":{{json .State.ExitCode}},"configured_user":{{json .Config.User}},
"privileged":{{json .HostConfig.Privileged}},"cap_drop":{{json .HostConfig.CapDrop}},
"cap_add":{{json .HostConfig.CapAdd}},"security_opt":{{json .HostConfig.SecurityOpt}},
"pid_mode":{{json .HostConfig.PidMode}},"network_mode":{{json .HostConfig.NetworkMode}},
"read_only_root":{{json .HostConfig.ReadonlyRootfs}}}"""


def checksum(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def decoded(value: str) -> str:
    return base64.b64decode(value, validate=True).decode("utf-8", errors="strict")


def process_identity(value: str, pid: int) -> tuple[int, int, str]:
    # comm is parenthesized and may itself contain spaces or parentheses.
    prefix, fields = value.rsplit(")", 1)
    if not prefix.startswith(f"{pid} ("):
        raise ValueError("process stat PID mismatch")
    rest = fields.split()
    if int(rest[1]) < 0 or int(rest[19]) < 0 or len(rest[0]) != 1 or rest[0] not in "RSDZTtXxKWPI":
        raise ValueError("invalid process identity metadata")
    return int(rest[1]), int(rest[19]), rest[0]  # PPid, starttime, state.


def parse_observation(raw: str) -> dict[str, Any]:
    if len(raw.encode()) > 8 * 1024 * 1024:
        raise ValueError("observation exceeded output bound")
    processes: dict[int, dict[str, Any]] = {}
    errors: list[str] = []
    header: dict[str, str] = {}
    finished = False
    final_phase = False
    for line in raw.splitlines():
        fields = line.split("\t")
        kind = fields[0]
        if finished:
            raise ValueError("trailing output after completion marker")
        if final_phase and kind not in {"FINAL", "ERROR", "FINISHED"}:
            raise ValueError("collection resumed after final identity checks")
        if kind in {"VERSION", "SELF", "OBSERVER_UID", "KERNEL", "MOUNTS"}:
            if len(fields) != 2 or kind in header:
                raise ValueError("duplicate or malformed observation header")
            header[kind] = fields[1]
        elif kind == "ERROR":
            errors.append(" ".join(fields[1:]))
        elif kind == "FINISHED" and len(fields) == 1:
            finished = True
        elif kind == "BEGIN":
            pid = int(fields[1])
            if len(fields) != 3 or pid <= 0 or pid in processes:
                raise ValueError("invalid or duplicate process start")
            parent, started, state = process_identity(decoded(fields[2]), pid)
            processes[pid] = {
                "pid": pid,
                "parent": parent,
                "start_ticks": started,
                "state": state,
                "status": {},
                "descriptors": {},
                "ended": False,
            }
        elif kind in {
            "STATUS",
            "EXE",
            "MAPS",
            "FD",
            "FDINFO",
            "FDVERIFY",
            "FDINFOVERIFY",
            "END",
            "FINAL",
        }:
            process = processes[int(fields[1])]
            if process["ended"] and kind != "FINAL":
                raise ValueError("data after process completion")
            if kind == "STATUS":
                name, value = "\t".join(fields[2:]).split(":", 1)
                if name not in STATUS_FIELDS or name in process["status"]:
                    raise ValueError("unexpected or duplicate process status")
                process["status"][name] = value.strip()
            elif kind in {"EXE", "MAPS"}:
                if len(fields) != 3 or kind in process:
                    raise ValueError("duplicate or malformed process metadata")
                value = decoded(fields[2])
                if not value.strip() or (kind == "EXE" and not value.startswith("/")):
                    raise ValueError("missing live executable or mapping metadata")
                if kind == "MAPS":
                    for mapping in value.splitlines():
                        match = re.fullmatch(
                            r"([0-9a-f]+)-([0-9a-f]+) [r-][w-][x-][ps] "
                            r"[0-9a-f]+ [0-9a-f]+:[0-9a-f]+ +[0-9]+(?: +[^\n]*)?",
                            mapping,
                        )
                        if not match or int(match[1], 16) >= int(match[2], 16):
                            raise ValueError("invalid live mapping metadata")
                if kind == "MAPS" and len(value.encode()) > 1048576:
                    errors.append(f"maps-limit-{process['pid']}")
                process[kind] = value
            elif kind == "FD":
                fd = int(fields[2])
                if len(fields) != 4 or fd < 0 or fd in process["descriptors"]:
                    raise ValueError("invalid or duplicate descriptor")
                target = decoded(fields[3])
                if not target:
                    raise ValueError("missing descriptor target")
                process["descriptors"][fd] = {"target": target, "info": {}, "verified_info": {}}
            elif kind == "FDVERIFY":
                descriptor = process["descriptors"][int(fields[2])]
                if len(fields) != 4 or "verified_target" in descriptor:
                    raise ValueError("duplicate or malformed descriptor verification")
                descriptor["verified_target"] = decoded(fields[3])
            elif kind in {"FDINFO", "FDINFOVERIFY"}:
                descriptor = process["descriptors"][int(fields[2])]
                name, value = "\t".join(fields[3:]).split(":", 1)
                values = descriptor["info" if kind == "FDINFO" else "verified_info"]
                if name not in FD_FIELDS or name in values:
                    raise ValueError("unexpected or duplicate descriptor metadata")
                pattern = r"[0-7]+" if name == "flags" else r"[0-9]+"
                if not re.fullmatch(pattern, value.strip()):
                    raise ValueError("non-numeric descriptor metadata")
                values[name] = value.strip()
            else:
                if len(fields) != 3:
                    raise ValueError("malformed process completion")
                parent, started, state = process_identity(decoded(fields[2]), process["pid"])
                if (parent, started) != (
                    process["parent"],
                    process["start_ticks"],
                ):
                    raise ValueError("process identity changed during observation")
                if kind == "END":
                    process["ended"] = True
                    process["end_state"] = state
                else:
                    final_phase = True
                    if not process["ended"] or "final_state" in process:
                        raise ValueError("invalid final process identity check")
                    process["final_state"] = state
        else:
            raise ValueError("unrecognized observation record")
    if (
        header.get("VERSION") != "1"
        or not finished
        or set(header) != {"VERSION", "SELF", "OBSERVER_UID", "KERNEL", "MOUNTS"}
    ):
        raise ValueError("incomplete observation envelope")
    if not header["OBSERVER_UID"].isdigit() or int(header["OBSERVER_UID"]) == 0:
        raise ValueError("observer did not run as a non-root UID")
    if 1 not in processes or int(header["SELF"]) in processes:
        raise ValueError("missing workload root or observer included")
    mounts = decoded(header["MOUNTS"])
    if not mounts.strip():
        raise ValueError("missing or malformed mount metadata")
    for line in mounts.splitlines():
        left, separator, right = line.partition(" - ")
        columns = left.split()
        if (
            not separator
            or len(columns) < 6
            or len(right.split()) < 3
            or not columns[0].isdigit()
            or not columns[1].isdigit()
            or not re.fullmatch(r"[0-9]+:[0-9]+", columns[2])
            or not columns[3].startswith("/")
            or not columns[4].startswith("/")
        ):
            raise ValueError("missing or malformed mount metadata")

    included = {1}
    while True:
        descendants = {pid for pid, item in processes.items() if item["parent"] in included}
        if descendants <= included:
            break
        included |= descendants
    # Validate the complete raw collection before filtering the displayed workload.
    for process in processes.values():
        status = process["status"]
        zombie = process["state"] == process.get("end_state") == process.get("final_state") == "Z"
        process["inactive_zombie"] = zombie
        if "final_state" not in process:
            errors.append(f"missing-final-identity-{process['pid']}")
        if (
            process["parent"] in processes
            and process["start_ticks"] < processes[process["parent"]]["start_ticks"]
        ):
            errors.append(f"inconsistent-parent-generation-{process['pid']}")
        if zombie and ({"EXE", "MAPS"} & process.keys() or process["descriptors"]):
            raise ValueError("inactive zombie has contradictory live metadata")
        if (process["pid"] == 1 and zombie) or not process["ended"]:
            errors.append(f"inactive-or-incomplete-root-{process['pid']}")
        if not zombie and not {"EXE", "MAPS"} <= process.keys():
            errors.append(f"incomplete-process-{process['pid']}")
        if (
            len(
                {
                    state == "Z"
                    for state in (
                        process["state"],
                        process.get("end_state"),
                        process.get("final_state"),
                    )
                }
            )
            != 1
        ):
            errors.append(f"process-exited-during-observation-{process['pid']}")
        if not STATUS_FIELDS <= status.keys():
            errors.append(f"incomplete-status-{process['pid']}")
        if status.get("PPid") != str(process["parent"]):
            errors.append(f"inconsistent-parent-{process['pid']}")
        uids = status.get("Uid", "").split()
        if len(uids) != 4 or any(not uid.isdigit() or int(uid) == 0 for uid in uids):
            errors.append(f"root-or-missing-uid-{process['pid']}")
        gids = status.get("Gid", "").split()
        if (
            len(gids) != 4
            or any(not gid.isdigit() for gid in gids)
            or status.get("Seccomp") not in {"0", "1", "2"}
        ):
            errors.append(f"invalid-process-status-{process['pid']}")
        if status.get("NoNewPrivs") != "1" or any(
            not re.fullmatch(r"0+", status.get(name, "")) for name in CAPABILITIES
        ):
            errors.append(f"privilege-restriction-missing-{process['pid']}")
        for descriptor in process["descriptors"].values():
            if (
                set(descriptor["info"]) != FD_FIELDS
                or descriptor["info"] != descriptor["verified_info"]
                or descriptor["target"] != descriptor.get("verified_target")
            ):
                errors.append(f"incomplete-descriptor-{process['pid']}")
    return {
        "complete": not errors,
        "observer_uid": int(header["OBSERVER_UID"]),
        "kernel_release": header["KERNEL"],
        "mounts": mounts,
        "processes": [processes[pid] for pid in sorted(included)],
        "excluded_pids": sorted(set(processes) - included),
        "errors": errors,
    }


def validate_identity(
    info: dict[str, Any], project: str, service: str, image: str, user: str
) -> None:
    if (info.get("project"), info.get("service"), info.get("image_id")) != (
        project,
        service,
        image,
    ) or str(info.get("oneoff", "")).lower() != "false":
        raise ValueError("container ownership/image mismatch or one-off container")
    uid = user.split(":", 1)[0]
    if (
        not uid
        or uid == "root"
        or (uid.isdigit() and int(uid) == 0)
        or info.get("configured_user") != user
    ):
        raise ValueError("observer user differs from expected non-root image user")
    if service in APP_SERVICES and info.get("read_only_root") is not True:
        raise ValueError("application root filesystem is not read-only")
    if info.get("privileged") is not False or info.get("cap_add"):
        raise ValueError("container has extra privilege")
    if info.get("cap_drop") != ["ALL"] or not any(
        item in {"no-new-privileges", "no-new-privileges:true"}
        for item in info.get("security_opt") or []
    ):
        raise ValueError("container isolation flags differ from assessed deployment")
    network = str(info.get("network_mode", ""))
    if info.get("pid_mode") or network == "host" or network.startswith("container:"):
        raise ValueError("shared host/process namespace is outside this probe")


@dataclass(frozen=True)
class CapturedProcess:
    args: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    capture_error: str = ""


def bounded_process(
    command: list[str],
    input_text: str | None = None,
    *,
    timeout: float = 45,
    stdout_limit: int = 8 * 1024 * 1024,
    stderr_limit: int = 65536,
) -> CapturedProcess:
    """Bound both pipes while reading, before retaining any output on disk."""
    pending = memoryview((input_text or "").encode())
    if len(pending) > 65536:
        raise ValueError("probe input exceeded bound")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    deadline = time.monotonic() + timeout
    failure = ""
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as child:
        assert child.stdin and child.stdout and child.stderr
        with selectors.DefaultSelector() as selector:
            for stream, name in ((child.stdout, "stdout"), (child.stderr, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            if pending:
                os.set_blocking(child.stdin.fileno(), False)
                selector.register(child.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                child.stdin.close()
            while selector.get_map() and not failure:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    failure = "observer deadline exceeded"
                    break
                for key, _ in selector.select(remaining):
                    name = key.data
                    if name == "stdin":
                        try:
                            written = os.write(key.fd, pending[:4096])
                            pending = pending[written:]
                        except BrokenPipeError:
                            pending = pending[len(pending) :]
                        if not pending:
                            selector.unregister(child.stdin)
                            child.stdin.close()
                        continue
                    chunk = os.read(key.fd, 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = limits[name] - len(buffers[name])
                    buffers[name].extend(chunk[:available])
                    if len(chunk) > available:
                        failure = f"observer {name} truncated at {limits[name]} bytes"
                        break
            if failure:
                child.kill()
            try:
                child.wait(timeout=max(0.01, deadline - time.monotonic()) if not failure else 5)
            except subprocess.TimeoutExpired:
                failure = "observer deadline exceeded"
                child.kill()
                child.wait(timeout=5)
        code = (124 if "deadline" in failure else 125) if failure else child.returncode
        return CapturedProcess(
            command, code, bytes(buffers["stdout"]), bytes(buffers["stderr"]), failure
        )


def docker(*arguments: str, input_text: str | None = None) -> CapturedProcess:
    return bounded_process(["docker", *arguments], input_text)


def inspect(container: str) -> dict[str, Any]:
    result = docker("inspect", "--format", INSPECT, container)
    if result.returncode:
        raise ValueError("selected container could not be inspected")
    info: dict[str, Any] = json.loads(result.stdout.decode("utf-8", errors="strict"))
    if info.get("id") != container:
        raise ValueError("container inspection returned a different identity")
    return info


def write_private(path: Path, value: str | bytes) -> None:
    with path.open("xb") as stream:
        path.chmod(0o600)
        stream.write(value.encode("utf-8") if isinstance(value, str) else value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Exact disposable Compose project")
    parser.add_argument("--images", type=Path, required=True, help="Exact-image scan inventory")
    parser.add_argument("--output", type=Path, required=True, help="New private evidence directory")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", args.project):
        raise ValueError("invalid project name")
    inventory_bytes = args.images.read_bytes()
    inventory = json.loads(inventory_bytes)
    images = {item["service"]: item["image_id"] for item in inventory["images"]}
    users = {item["service"]: item.get("user", "") for item in inventory["images"]}
    if (
        inventory.get("complete") is not True
        or set(images) != SERVICES
        or len(inventory["images"]) != 8
    ):
        raise ValueError("complete, unique eight-service image inventory required")
    if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", image) for image in images.values()):
        raise ValueError("invalid exact image identity")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    probe_bytes = PROBE_PATH.read_bytes()
    observer_bytes = Path(__file__).read_bytes()
    probe = probe_bytes.decode("utf-8")
    write_private(args.output / PROBE_PATH.name, probe)
    write_private(args.output / Path(__file__).name, observer_bytes.decode("utf-8"))
    write_private(args.output / "image-inventory.json", inventory_bytes.decode("utf-8"))
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": stamp(),
        "project": args.project,
        "complete": False,
        "inventory_sha256": checksum(inventory_bytes),
        "observer_sha256": checksum(observer_bytes),
        "probe_sha256": checksum(probe_bytes),
        "services": [],
        "limitations": [
            "Current snapshot only: not complete startup/exec history or a native call graph.",
            "Normal service processes are observed without replacing their entrypoint.",
            "Raw metadata is container-wide except the probe shell. "
            "The summarized workload excludes unrelated exec-process trees, with PIDs recorded.",
            "Reparented health-check or timeout helpers may appear among PID 1 descendants; "
            "descendant membership alone does not establish application ownership.",
            "Exited zombie descendants are recorded as inactive; "
            "their absent executable/maps/descriptors provide no live-runtime evidence.",
            "Exited one-shot services are not observed; no service is started or restarted.",
            "Descriptor metadata and mapping paths are private; "
            "no file contents, arguments or environment collected.",
            "This evidence is not an automatic applicability decision or release approval.",
        ],
    }
    try:
        for service in sorted(SERVICES):
            item: dict[str, Any] = {"service": service, "started_at": stamp(), "complete": False}
            report["services"].append(item)
            try:
                found = docker(
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--filter",
                    f"label=com.docker.compose.project={args.project}",
                    "--filter",
                    f"label=com.docker.compose.service={service}",
                    "--format",
                    "{{.ID}}",
                )
                identifiers = found.stdout.decode("utf-8", errors="strict").split()
                if (
                    found.returncode
                    or len(identifiers) != 1
                    or not re.fullmatch(r"[0-9a-f]{64}", identifiers[0])
                ):
                    raise ValueError("missing or ambiguous service container")
                container = identifiers[0]
                before = inspect(container)
                validate_identity(before, args.project, service, images[service], users[service])
                item["before"] = before
                if not before["running"]:
                    item["not_observed"] = "service is not running; no process evidence borrowed"
                    continue
                result = docker(
                    "exec",
                    "--interactive",
                    container,
                    "timeout",
                    "-k",
                    "2",
                    "35",
                    "sh",
                    "-s",
                    input_text=probe,
                )
                write_private(args.output / f"{service}.stdout", result.stdout)
                write_private(args.output / f"{service}.stderr", result.stderr)
                item.update(
                    {
                        "probe_exit": result.returncode,
                        "capture_error": result.capture_error,
                        "stdout_sha256": checksum(result.stdout),
                        "stderr_sha256": checksum(result.stderr),
                    }
                )
                after = inspect(container)
                item["after"] = after
                validate_identity(after, args.project, service, images[service], users[service])
                if before != after or not after["running"]:
                    raise ValueError("container changed or restarted during observation")
                observation = parse_observation(result.stdout.decode("utf-8", errors="strict"))
                item["observation"] = observation
                item["complete"] = bool(
                    result.returncode == 0
                    and not result.capture_error
                    and not result.stderr
                    and observation["complete"]
                )
            except subprocess.TimeoutExpired as exc:
                for name, value in (("stdout", exc.stdout), ("stderr", exc.stderr)):
                    data = value if isinstance(value, bytes) else (value or "").encode("utf-8")
                    write_private(args.output / f"{service}.timeout-{name}", data)
                    item[f"timeout_{name}_sha256"] = checksum(data)
                item["error"] = "Docker observation timed out; partial output retained"
            except (ValueError, KeyError, IndexError, OSError) as exc:
                item["error"] = f"{type(exc).__name__}: observation incomplete"
            finally:
                item["finished_at"] = stamp()
                print(f"{service}: {'observed' if item['complete'] else 'incomplete'}", flush=True)
        if (
            args.images.read_bytes() != inventory_bytes
            or PROBE_PATH.read_bytes() != probe_bytes
            or Path(__file__).read_bytes() != observer_bytes
        ):
            raise ValueError("observation inputs changed")
        report["complete"] = all(item["complete"] for item in report["services"])
    finally:
        report["finished_at"] = stamp()
        write_private(
            args.output / "observation.json", json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
    raise SystemExit(0 if report["complete"] else 1)


if __name__ == "__main__":
    main()
