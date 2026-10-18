"""Record non-root/privilege/component evidence for exact local Compose images."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.setup_self_hosted import compose_command

DEBIAN_SERVICES = {"api", "migrate", "worker", "web", "shopper", "qdrant"}
REMOVED = (
    "/usr/bin/cp",
    "/usr/bin/install",
    "/usr/bin/mv",
    "/usr/bin/sed",
    "/usr/bin/tar",
    "/usr/sbin/useradd",
    "/usr/sbin/usermod",
    "/usr/lib/aarch64-linux-gnu/libacl.so.1",
    "/usr/lib/x86_64-linux-gnu/libacl.so.1",
    "/usr/bin/perl",
    "/usr/bin/perl5.40.1",
    "/usr/bin/gzip",
    "/usr/bin/infocmp",
    "/usr/bin/mount",
    "/usr/bin/umount",
    "/usr/bin/nsenter",
    "/usr/bin/unshare",
    "/usr/lib/systemd/systemd-homed",
    "/usr/libexec/systemd/systemd-homed",
)
ABSENCE_PROBE = """
for path in "$@"; do
    if [ -e "$path" ] || [ -L "$path" ]; then printf 'PRESENT %s\\n' "$path"; exit 1; fi
done
"""
PROBE = (
    """
set -eu
id -u
while IFS= read -r line; do
    case "$line" in Uid:*|CapEff:*|CapPrm:*|CapBnd:*|NoNewPrivs:*) printf '%s\\n' "$line";; esac
done < /proc/1/status
"""
    + ABSENCE_PROBE
    + """
find /usr /bin /sbin /lib -xdev -type f \\( -perm -4000 -o -perm -2000 \\) -print
"""
)


def docker_json(*args: str) -> Any:
    return json.loads(subprocess.check_output(["docker", *args], text=True))


def validate_probe(output: str) -> dict[str, str]:
    lines = output.splitlines()
    if not lines or not lines[0].isdigit() or int(lines[0]) == 0:
        raise ValueError("runtime must have a non-root numeric UID")
    fields = {
        line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in lines[1:] if ":" in line
    }
    uids = fields.get("Uid", "").split()
    if len(uids) != 4 or any(not value.isdigit() or int(value) == 0 for value in uids):
        raise ValueError("runtime has a root real/effective/saved/filesystem UID")
    if fields.get("NoNewPrivs") != "1":
        raise ValueError("no-new-privileges is not active")
    for capability in ("CapEff", "CapPrm", "CapBnd"):
        if int(fields.get(capability, "1"), 16) != 0:
            raise ValueError(f"runtime retains {capability}")
    if any(line.startswith(("/", "PRESENT ")) for line in lines[1:]):
        raise ValueError("runtime retains a removed executable or setuid/setgid file")
    return {"uid": lines[0], **fields}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".opencommerce/runtime-image-proof.json")
    )
    parser.add_argument("--env-file", type=Path, help="Selected isolated Compose environment")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new evidence output; previous proofs must be preserved")
    command = compose_command(dict(os.environ))
    if args.env_file is not None:
        command.extend(["--env-file", str(args.env_file.resolve())])
    config = json.loads(
        subprocess.check_output([*command, "config", "--format", "json"], text=True)
    )
    records = []
    for service, definition in sorted(config["services"].items()):
        if definition.get("cap_drop") != ["ALL"] or not any(
            flag in {"no-new-privileges:true", "no-new-privileges"}
            for flag in definition.get("security_opt", [])
        ):
            raise ValueError(
                f"{service}: Compose must drop capabilities and prohibit privilege gain"
            )
        if any(port.get("host_ip") != "127.0.0.1" for port in definition.get("ports", [])):
            raise ValueError(f"{service}: published ports must be loopback-only")
        if service in {"api", "migrate", "web", "shopper", "worker"} and not definition.get(
            "read_only"
        ):
            raise ValueError(f"{service}: application root filesystem must be read-only")
        reference = definition.get("image", f"{config['name']}-{service}")
        info = docker_json("image", "inspect", reference)[0]
        user = definition.get("user") or info["Config"].get("User")
        if not user:
            raise ValueError(f"{service}: no explicit runtime user")
        removed: tuple[str, ...] = REMOVED if service in DEBIAN_SERVICES else ()
        if service == "postgres":
            removed = ("/usr/local/bin/gosu",)
        container = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            user,
        ]
        output = subprocess.check_output(
            [
                *container,
                "--entrypoint",
                "sh",
                info["Id"],
                "-c",
                PROBE,
                "probe",
                *removed,
            ],
            text=True,
        )
        facts = validate_probe(output)
        storage_evidence = "not a Python/Node/Qdrant runtime"
        if service in {"api", "worker", "migrate"}:
            environment = definition.get("environment", {})
            if (
                not str(environment.get("OPEN_COMMERCE_DATABASE_URL", "")).startswith(
                    "postgresql+asyncpg://"
                )
                or environment.get("OPEN_COMMERCE_QDRANT_URL") != "http://qdrant:6333"
            ):
                raise ValueError(f"{service}: assessed Compose storage configuration changed")
            probe = Path("scripts/probe-python-storage.py").resolve()
            storage_evidence = subprocess.check_output(
                [
                    *container,
                    "--interactive",
                    "--entrypoint",
                    "python",
                    info["Id"],
                    "-",
                ],
                input=probe.read_text(encoding="utf-8"),
                text=True,
            ).strip()
        if service in {"web", "shopper", "qdrant"}:
            executable = (
                "/usr/local/bin/node" if service in {"web", "shopper"} else "/qdrant/qdrant"
            )
            storage_evidence = subprocess.check_output(
                [
                    *container,
                    "--entrypoint",
                    "ldd",
                    info["Id"],
                    executable,
                ],
                text=True,
            )
            if "sqlite" in storage_evidence.lower():
                raise ValueError(f"{service}: unexpected link to system SQLite")
        records.append(
            {
                "service": service,
                "image_id": info["Id"],
                "architecture": info["Architecture"],
                "configured_user": user,
                "process": facts,
                "absent_components": list(removed),
                "setuid_setgid_files_in_runtime_paths": [],
                "storage_construction_or_native_dependencies": storage_evidence,
            }
        )
        print(
            f"{service}: UID {facts['uid']}, no capabilities or privilege gain; "
            "component check passed"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"complete": True, "images": records}, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
