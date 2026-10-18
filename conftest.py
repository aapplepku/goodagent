"""The historical simulator suite explicitly exercises the preserved demo profile."""

import pytest


@pytest.fixture(autouse=True)
def explicit_test_runtime_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    # Self-service tests pass their intended profile explicitly in Settings.
    monkeypatch.setenv("OPEN_COMMERCE_RUNTIME_PROFILE", "legacy_demo")
