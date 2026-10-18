"""Local launch configuration and observational worker health contracts."""

import json
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from open_commerce.api.readiness import check_local_worker
from open_commerce.config import Settings
from open_commerce.local_runtime import LocalSupervisor, available_port


def test_port_probe_reuses_closed_connections_but_skips_an_occupied_port() -> None:
    occupied, available = MagicMock(), MagicMock()
    occupied.__enter__.return_value = occupied
    available.__enter__.return_value = available
    occupied.bind.side_effect = OSError("Address in use")
    with patch("open_commerce.local_runtime.socket.socket", side_effect=[occupied, available]):
        assert available_port(58025) == 58026
    for connection in (occupied, available):
        connection.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    available.bind.assert_called_once_with(("127.0.0.1", 58026))


def test_launcher_preserves_model_config_without_publishing_secret(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        manager_model_provider="openai",
        manager_model_id="configured-test-model",
        openai_api_key="synthetic-test-secret",
        manager_model_max_iterations=9,
        local_tenant_id=uuid4(),
    )
    with patch("open_commerce.local_runtime.available_port", return_value=58024):
        supervisor = LocalSupervisor(tmp_path, settings)
    assert supervisor.env["OPEN_COMMERCE_MANAGER_MODEL_ID"] == "configured-test-model"
    assert supervisor.env["OPEN_COMMERCE_MANAGER_MODEL_MAX_ITERATIONS"] == "9"
    assert supervisor.env["OPEN_COMMERCE_LOCAL_TENANT_ID"] == str(settings.local_tenant_id)
    assert supervisor.env["OPEN_COMMERCE_OPENAI_API_KEY"] == "synthetic-test-secret"
    supervisor.write_manifest()
    manifest = json.loads(supervisor.manifest_path.read_text())
    assert manifest["credential_configured"] is True
    assert "synthetic-test-secret" not in json.dumps(manifest)
    assert supervisor.manifest_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("heartbeat", [0, 1])
async def test_worker_probe_requires_current_runtime_heartbeat(heartbeat: int) -> None:
    settings = Settings(_env_file=None, local_runtime_id=uuid4())
    client = AsyncMock()
    client.exists.return_value = heartbeat
    with patch("open_commerce.api.readiness.Redis.from_url", return_value=client):
        if heartbeat:
            await check_local_worker(settings)
        else:
            with pytest.raises(ConnectionError):
                await check_local_worker(settings)
    client.exists.assert_awaited_once_with(f"opencommerce:worker:{settings.local_runtime_id}")
    client.aclose.assert_awaited_once()


async def test_supervisor_rejects_recovery_outside_legacy_demo(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, runtime_profile="self_hosted")
    with patch("open_commerce.local_runtime.available_port", return_value=58024):
        supervisor = LocalSupervisor(tmp_path, settings)
    assert supervisor.env["OPEN_COMMERCE_LOCAL_OPERATIONS_ENABLED"] == "false"
    with patch.object(supervisor.database, "transaction") as transaction:
        with pytest.raises(RuntimeError, match="disabled outside legacy demo"):
            await supervisor.operation(uuid4())
        transaction.assert_not_called()
    await supervisor.database.close()
