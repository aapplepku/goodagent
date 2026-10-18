"""The image-evidence checker must fail closed on missing or privileged facts."""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

module = runpy.run_path(str(Path("scripts/verify-runtime-images.py")))
validate = module["validate_probe"]
SAFE = (
    "10001\nUid:\t10001\t10001\t10001\t10001\nCapEff:\t0\nCapPrm:\t0\nCapBnd:\t0\nNoNewPrivs:\t1\n"
)


def test_valid_runtime_facts() -> None:
    assert validate(SAFE)["uid"] == "10001"


@pytest.mark.parametrize(
    "path",
    [
        "/usr/bin/cp",
        "/usr/bin/install",
        "/usr/bin/mv",
        "/usr/bin/sed",
        "/usr/bin/tar",
        "/usr/sbin/useradd",
        "/usr/sbin/usermod",
        "/usr/lib/aarch64-linux-gnu/libacl.so.1",
        "/usr/lib/x86_64-linux-gnu/libacl.so.1",
    ],
)
def test_acl_selected_paths_are_required_absent(path: str) -> None:
    assert path in module["REMOVED"]


@pytest.mark.parametrize("kind", ["file", "directory", "link", "dangling-link", "absent"])
def test_absence_probe_rejects_existing_nodes_and_dangling_links(tmp_path: Path, kind: str) -> None:
    target = tmp_path / "removed component"
    if kind == "file":
        target.write_text("synthetic")
    elif kind == "directory":
        target.mkdir()
    elif kind == "link":
        retained = tmp_path / "retained"
        retained.write_text("synthetic")
        target.symlink_to(retained)
    elif kind == "dangling-link":
        target.symlink_to(tmp_path / "missing")
    result = subprocess.run(
        ["sh", "-c", module["ABSENCE_PROBE"], "probe", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (0 if kind == "absent" else 1)
    assert result.stdout == ("" if kind == "absent" else f"PRESENT {target}\n")
    assert not result.stderr


def test_direct_entrypoint_accepts_selected_installation() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify-runtime-images.py", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--env-file" in result.stdout


@pytest.mark.parametrize("app", ["web", "shopper"])
def test_both_standalone_apps_ship_public_downloads(app: str) -> None:
    dockerfile = Path(f"apps/{app}/Dockerfile").read_text()
    assert f"/app/apps/{app}/public ./apps/{app}/public" in dockerfile


@pytest.mark.parametrize("app", ["api", "worker"])
def test_python_images_do_not_opt_into_generated_bytecode(app: str) -> None:
    dockerfile = Path(f"apps/{app}/Dockerfile").read_text()
    assert "ENV UV_COMPILE_BYTECODE=0" in dockerfile
    assert "UV_COMPILE_BYTECODE=1" not in dockerfile
    assert "--compile-bytecode" not in dockerfile
    assert "ENV PYTHONDONTWRITEBYTECODE=1" in dockerfile
    assert "--frozen --all-packages --no-dev --all-extras" in dockerfile
    assert "COPY packages/backend ./packages/backend" in dockerfile
    assert "COPY --from=build /app /app" in dockerfile


@pytest.mark.parametrize(
    "dockerfile",
    [
        "apps/api/Dockerfile",
        "apps/worker/Dockerfile",
        "apps/web/Dockerfile",
        "apps/shopper/Dockerfile",
        "infra/docker/qdrant/Dockerfile",
    ],
)
def test_debian_runtime_refreshes_packages_before_component_removal(dockerfile: str) -> None:
    assert "sh /usr/local/sbin/harden-debian" in Path(dockerfile).read_text()
    script = Path("infra/docker/harden-debian.sh").read_text()
    assert script.index("apt-get update") < script.index("apt-get upgrade -y")
    assert script.index("apt-get upgrade -y") < script.index("rm -f /usr/bin/perl")


@pytest.mark.parametrize("service", ["postgres", "redis"])
def test_alpine_services_refresh_security_updates(service: str) -> None:
    dockerfile = Path(f"infra/docker/{service}/Dockerfile").read_text()
    assert "apk upgrade --no-cache" in dockerfile
    assert "@sha256:" in dockerfile
    assert dockerfile.rstrip().endswith(f"USER {service}")


@pytest.mark.parametrize(
    "unsafe",
    [
        SAFE.replace("10001", "0"),
        SAFE.replace("10001\t10001", "10001\t0"),
        SAFE.replace("CapEff:\t0", "CapEff:\t1"),
        SAFE.replace("CapPrm:\t0", "CapPrm:\t1"),
        SAFE.replace("CapBnd:\t0", "CapBnd:\t1"),
        SAFE.replace("NoNewPrivs:\t1", "NoNewPrivs:\t0"),
        SAFE.replace("CapBnd:\t0\n", ""),
        SAFE.replace("Uid:\t10001\t10001\t10001\t10001\n", ""),
        SAFE + "/usr/bin/su\n",
        SAFE + "PRESENT /usr/bin/perl\n",
        "",
    ],
)
def test_reject_privileged_or_incomplete_facts(unsafe: str) -> None:
    with pytest.raises(ValueError):
        validate(unsafe)
