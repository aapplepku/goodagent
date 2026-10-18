"""Public contracts must load independently of pytest's collection order."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "first_module",
    [
        "open_commerce.telemetry.activity_tools",
        "open_commerce.manager_agent.model_provider",
        "open_commerce.shopper_agent.model_agent",
    ],
)
def test_manager_public_exports_without_import_order_dependency(first_module: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {first_module}; "
            "from open_commerce.manager_agent import "
            "DurableManagerAgentService, ManagerReActAgent; "
            "from open_commerce.manager_agent.service import "
            "DurableManagerAgentService as Service; "
            "assert DurableManagerAgentService is Service; "
            "assert ManagerReActAgent.__name__ == 'ManagerReActAgent'",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
