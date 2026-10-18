"""Public controller commands cannot revive the process-local demonstration runtime."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_process_local_controller_demo_is_not_a_public_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "open_commerce.cli", "controller", "demo"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice: 'demo'" in result.stderr
