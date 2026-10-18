"""Synthetic browser images cannot be placed in an installation's asset volume."""

from pathlib import Path

import pytest

from tests.contract.test_merchant_browser_fixture import fixture_settings
from tests.integration.shopper_image_fixture import validate_image_fixture


def test_image_fixture_accepts_only_explicit_temporary_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "shopper-welcome-assets"
    settings = fixture_settings().model_copy(update={"asset_directory": directory})
    monkeypatch.setenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", "1")
    monkeypatch.delenv("OPEN_COMMERCE_E2E_ASSET_DIRECTORY", raising=False)
    with pytest.raises(RuntimeError, match="temporary"):
        validate_image_fixture(settings)
    monkeypatch.setenv("OPEN_COMMERCE_E2E_ASSET_DIRECTORY", str(directory))
    assert validate_image_fixture(settings) == directory
    monkeypatch.delenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER")
    with pytest.raises(RuntimeError, match="isolated"):
        validate_image_fixture(settings)


@pytest.mark.parametrize("case", ["mismatch", "persistent", "symlink", "wrong_name"])
def test_image_fixture_rejects_other_asset_locations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str
) -> None:
    directory = tmp_path / "shopper-welcome-assets"
    expected = directory
    if case == "mismatch":
        expected = tmp_path / "another" / "shopper-welcome-assets"
    elif case == "persistent":
        directory = expected = Path.home() / "shopper-welcome-assets"
    elif case == "symlink":
        target = tmp_path / "elsewhere"
        target.mkdir()
        directory.symlink_to(target, target_is_directory=True)
    else:
        directory = expected = tmp_path / "other-assets"
    monkeypatch.setenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", "1")
    monkeypatch.setenv("OPEN_COMMERCE_E2E_ASSET_DIRECTORY", str(expected))
    settings = fixture_settings().model_copy(update={"asset_directory": directory})
    with pytest.raises(RuntimeError, match="temporary"):
        validate_image_fixture(settings)
