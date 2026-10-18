"""Isolated real-stack setup and guest browser journey, explicitly opted in."""

import asyncio
import base64
import os
import secrets
import signal
import subprocess
import sys
import time
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from open_commerce.config import Settings
from open_commerce.local_runtime import available_port
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService

pytestmark = pytest.mark.integration


def test_self_service_browser(integration_settings: Settings, tmp_path: Path) -> None:
    if os.getenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER") != "1":
        pytest.skip("Set OPEN_COMMERCE_SELF_SERVICE_BROWSER=1 for the isolated browser journey")
    root = Path(__file__).resolve().parents[2]
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    settings = integration_settings.model_copy(
        update={
            "runtime_profile": "self_hosted",
            "encryption_key": SecretStr(key),
            "asset_directory": tmp_path / "shopper-welcome-assets",
        }
    )

    async def bootstrap() -> str:
        db = RuntimeDatabase(settings)
        try:
            return await MerchantAuthService(db).issue_bootstrap()
        finally:
            await db.close()

    token = asyncio.run(bootstrap())
    api_port = available_port(58130)
    web_port = available_port(53130)
    shopper_port = available_port(53330)
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"
    shopper_url = f"http://127.0.0.1:{shopper_port}"
    env = {
        **os.environ,
        "OPEN_COMMERCE_DATABASE_URL": settings.database_url,
        "OPEN_COMMERCE_REDIS_URL": settings.redis_url,
        "OPEN_COMMERCE_QDRANT_URL": settings.qdrant_url,
        "OPEN_COMMERCE_RUNTIME_PROFILE": "self_hosted",
        "OPEN_COMMERCE_ENCRYPTION_KEY": key,
        "OPEN_COMMERCE_ASSET_DIRECTORY": str(settings.asset_directory),
        "OPEN_COMMERCE_E2E_ASSET_DIRECTORY": str(settings.asset_directory),
        "OPEN_COMMERCE_LOCAL_RUNTIME_ID": str(uuid4()),
        "OPEN_COMMERCE_MANAGER_MODEL_PROVIDER": "deterministic",
        "OPEN_COMMERCE_MODEL_ENABLED": "false",
        "OPEN_COMMERCE_OPENAI_API_KEY": "",
        "OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED": "false",
        "OPEN_COMMERCE_API_BASE_URL": api_url,
        "OPEN_COMMERCE_SHOPPER_PUBLIC_URL": shopper_url,
        "OPEN_COMMERCE_NEXT_DIST_DIR": ".next-self-service-qa",
        "OPEN_COMMERCE_E2E_SETUP_TOKEN": token,
        "OPEN_COMMERCE_E2E_PYTHON": sys.executable,
        "PLAYWRIGHT_BASE_URL": web_url,
        "SHOPPER_PLAYWRIGHT_BASE_URL": shopper_url,
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    env.pop("OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST", None)
    processes: list[subprocess.Popen[bytes]] = []
    with ExitStack() as stack:
        try:
            for name, command, cwd in (
                (
                    "api",
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "open_commerce.api.main:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                    ],
                    root,
                ),
                ("worker", [sys.executable, "-m", "open_commerce.worker.main"], root),
                (
                    "web",
                    ["node", "node_modules/next/dist/bin/next", "dev", "-p", str(web_port)],
                    root / "apps/web",
                ),
                (
                    "shopper",
                    ["node", "node_modules/next/dist/bin/next", "dev", "-p", str(shopper_port)],
                    root / "apps/shopper",
                ),
            ):
                log = stack.enter_context((tmp_path / f"{name}.log").open("wb"))
                processes.append(
                    subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log)
                )
            for url in (f"{api_url}/health/live", f"{web_url}/health", f"{shopper_url}/health"):
                for _ in range(120):
                    try:
                        if httpx.get(url, timeout=2).is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.5)
                else:
                    pytest.fail(f"Test service did not start: {url}; logs in {tmp_path}")
            # Authentication traces may include recovery tokens; keep raw output private.
            browser_log = stack.enter_context((tmp_path / "browser.log").open("wb"))
            subprocess.run(
                [
                    "node",
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "self-service.spec.ts",
                    "--output=" + os.getenv("OPEN_COMMERCE_E2E_OUTPUT", str(tmp_path / "browser")),
                ],
                cwd=root / "apps/web",
                env=env,
                stdout=browser_log,
                stderr=browser_log,
                check=True,
                timeout=420,
            )
        finally:
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def test_catalog_image_optimizer_rejects_warm_cache(tmp_path: Path) -> None:
    """Real Next/proxy with synthetic API; separate journey tests cover authorization."""
    if os.getenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER") != "1":
        pytest.skip("Set OPEN_COMMERCE_SELF_SERVICE_BROWSER=1 for the isolated cache regression")
    root = Path(__file__).resolve().parents[2]
    app = root / "apps/shopper"
    asset = tmp_path / "synthetic.png"
    Image.new("RGB", (2, 2), "green").save(asset)
    image = asset.read_bytes()
    asset_url = f"/api/runtime/v1/shopper/assets/{uuid4()}?store=cache-fixture"
    requests: list[str] = []
    published = True

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            valid = (
                self.path == asset_url.removeprefix("/api/runtime")
                and self.headers.get("x-store-slug") == "cache-fixture"
            )
            status = (200 if published else 404) if valid else 400
            self.send_response(status)
            self.send_header("Content-Type", "image/png" if status == 200 else "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(image if status == 200 else b"{}")

        def log_message(self, format: str, *args: object) -> None:
            pass

    backend = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    process = None
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env.update(
        {
            "OPEN_COMMERCE_NEXT_DIST_DIR": ".next-self-service-qa",
            "OPEN_COMMERCE_API_BASE_URL": f"http://127.0.0.1:{backend.server_port}",
            "OPEN_COMMERCE_LOCAL_RUNTIME_MANIFEST": "",
            "OPEN_COMMERCE_PUBLIC_ORIGINS": "[]",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
    )
    try:
        # A prior version could populate this cache even for a no-store API image.
        # Use Next's serializer and confirm a readable, non-stale entry exists.
        subprocess.run(
            [
                "node",
                "tests/integration/seed_image_cache.cjs",
                str(app / ".next-self-service-qa"),
                str(asset),
                asset_url,
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
        port = available_port(53430)
        with (tmp_path / "cache-next.log").open("wb") as log:
            process = subprocess.Popen(
                [
                    "node",
                    "node_modules/next/dist/bin/next",
                    "dev",
                    "--hostname",
                    "127.0.0.1",
                    "-p",
                    str(port),
                ],
                cwd=app,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
                for _ in range(90):
                    assert process.poll() is None, "Owned Next process exited"
                    try:
                        if client.get("/health", timeout=2).is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.5)
                else:
                    pytest.fail("Owned Next process did not start")

                def optimized(url: str) -> httpx.Response:
                    return client.get("/_next/image?" + urlencode({"url": url, "w": 640, "q": 75}))

                direct = client.get(asset_url)
                assert direct.status_code == 200 and direct.content == image
                assert direct.headers["cache-control"] == "no-store"
                hits = len(requests)
                assert optimized(asset_url).status_code == 400
                assert len(requests) == hits
                published = False
                assert client.get(asset_url).status_code == 404
                hits = len(requests)
                assert optimized(asset_url).status_code == 400
                assert len(requests) == hits
                assert optimized("/shopper-grocery-spread.png").status_code == 400
                assert client.get("/shopper-grocery-spread.png").status_code == 404
                for alias in (
                    "/x/%2e%2e/shopper-grocery-spread.png",
                    "/shopper-grocery-spread.png#fragment",
                    "/shopper-grocery-spread.png?",
                    "/_next/static/media/..%2f..%2f..%2fapi/runtime/v1/shopper/assets/fixture",
                ):
                    response = optimized(alias)
                    assert response.status_code in {400, 404}
                    assert len(requests) == hits, "Normalized/static path reached the API"
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        backend.shutdown()
        backend.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
