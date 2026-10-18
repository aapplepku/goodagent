"""The second-owner browser fixture must refuse non-test databases and model access."""

import pytest
from pydantic import SecretStr

from open_commerce.config import Settings
from tests.integration.merchant_browser_fixture import validate_fixture_environment


def fixture_settings() -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "runtime_profile": "self_hosted",
            "database_url": "postgresql+asyncpg://test@127.0.0.1/opencommerce_test_" + "a" * 32,
            "manager_model_provider": "deterministic",
            "model_enabled": False,
            "openai_api_key": None,
            "local_operations_enabled": False,
        }
    )


def test_disposable_fixture_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", raising=False)
    with pytest.raises(RuntimeError, match="isolated"):
        validate_fixture_environment(fixture_settings())
    monkeypatch.setenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", "1")
    validate_fixture_environment(fixture_settings())


@pytest.mark.parametrize(
    "change",
    [
        {"database_url": "postgresql+asyncpg://test@127.0.0.1/opencommerce"},
        {"database_url": "postgresql+asyncpg://test@remote.example/opencommerce_test_" + "a" * 32},
        {"database_url": "postgresql+asyncpg://test@127.0.0.1/opencommerce_test_" + "a" * 31},
        {"runtime_profile": "legacy_demo"},
        {"runtime_profile": "hosted"},
        {"manager_model_provider": "openai"},
        {"model_enabled": True},
        {"openai_api_key": SecretStr("synthetic-not-a-key")},
        {"local_operations_enabled": True},
    ],
)
def test_fixture_rejects_nonisolated_configuration(
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
) -> None:
    monkeypatch.setenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER", "1")
    with pytest.raises(RuntimeError, match="isolated"):
        validate_fixture_environment(fixture_settings().model_copy(update=change))
