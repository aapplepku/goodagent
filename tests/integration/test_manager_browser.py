"""Use the current UI with an isolated API, tenant, database and worker for browser QA."""

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from open_commerce.config import Settings
from open_commerce.local_runtime import available_port

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("spec", ["manager-agent.spec.ts", "catalog-browse.spec.ts"])
def test_manager_browser_smoke(integration_settings: Settings, tmp_path: Path, spec: str) -> None:
    base_url = os.getenv("OPEN_COMMERCE_BROWSER_TEST_URL")
    if not base_url:
        pytest.skip("Set OPEN_COMMERCE_BROWSER_TEST_URL to the running operator UI")
    root = Path(__file__).resolve().parents[2]
    port = available_port(58100)
    env = {
        **os.environ,
        "OPEN_COMMERCE_DATABASE_URL": integration_settings.database_url,
        "OPEN_COMMERCE_RUNTIME_PROFILE": "legacy_demo",
        "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": "false",
        "OPEN_COMMERCE_LOCAL_TENANT_ID": str(uuid4()),
        "OPEN_COMMERCE_WORKER_QUEUE": f"arq:browser:{uuid4().hex}",
        "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": "deterministic",
        "OPEN_COMMERCE_MODEL_ENABLED": "false",
        "OPEN_COMMERCE_OPENAI_API_KEY": "",
        "PLAYWRIGHT_BASE_URL": base_url,
        "OPEN_COMMERCE_E2E_API_URL": f"http://127.0.0.1:{port}",
    }
    with (
        (tmp_path / "api.log").open("w") as api_log,
        (tmp_path / "worker.log").open("w") as worker_log,
    ):
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "open_commerce.api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=root,
            env=env,
            stdout=api_log,
            stderr=api_log,
        )
        worker = subprocess.Popen(
            [sys.executable, "-m", "open_commerce.worker.main"],
            cwd=root,
            env=env,
            stdout=worker_log,
            stderr=worker_log,
        )
        try:
            for _ in range(60):
                try:
                    if httpx.get(f"http://127.0.0.1:{port}/health/live").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            subprocess.run(
                [
                    "node",
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    spec,
                    f"--output=test-results/isolated-{spec.removesuffix('.spec.ts')}",
                ],
                cwd=root / "apps/web",
                env=env,
                check=True,
                timeout=300,
            )
        finally:
            for process in (api, worker):
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
