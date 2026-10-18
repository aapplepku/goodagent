"""The local dependency guard must survive frozen installs, builds and public export."""

import hashlib
import json
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from scripts.export_public_source import omission

PATCH = "infra/patches/braces@3.0.3.patch"


def test_braces_patch_is_locked_exported_and_bound_to_deployment_review() -> None:
    manifest = json.loads(Path("package.json").read_bytes())
    assert manifest["pnpm"]["patchedDependencies"]["braces@3.0.3"] == PATCH
    lock = yaml.safe_load(Path("pnpm-lock.yaml").read_bytes())
    checksum = hashlib.sha256(Path(PATCH).read_bytes()).hexdigest()
    assert lock["patchedDependencies"]["braces@3.0.3"] == {"hash": checksum, "path": PATCH}
    assert any(f"braces@3.0.3(patch_hash={checksum})" == key for key in lock["snapshots"])
    assert omission(PATCH) is None
    assert omission("infra/patches/braces-3.0.3/LICENSE") is None
    assert omission("tests/dependencies/braces.test.cjs") is None
    files = runpy.run_path("scripts/check-image-findings.py")["deployment_files"](Path("."))
    assert files[PATCH] == checksum
    assert "pnpm-workspace.yaml" in files


@pytest.mark.parametrize("app", ["web", "shopper"])
def test_client_docker_build_applies_patch_before_dependency_installation(app: str) -> None:
    source = Path(f"apps/{app}/Dockerfile").read_text()
    assert source.index("COPY infra/patches ./infra/patches") < source.index(
        "RUN pnpm install --frozen-lockfile"
    )


def test_both_installed_client_dependency_chains_reject_excessive_nesting() -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to verify the installed dependency patch"
    result = subprocess.run(
        [node, "--test", "--test-timeout=10000", "tests/dependencies/braces.test.cjs"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={},
    )
    assert result.returncode == 0, result.stdout + result.stderr
