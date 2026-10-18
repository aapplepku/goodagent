"""Safe runtime defaults, encrypted staging, and provider admission boundaries."""

import base64
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr, ValidationError

from open_commerce.config import Settings
from open_commerce.manager_agent.errors import ManagerModelUnavailableError
from open_commerce.stores.crypto import decrypt, encrypt
from open_commerce.stores.events import ImportMilestone
from open_commerce.stores.models import OwnerSetupRequest, StoreError
from open_commerce.stores.usage import admit_model_call


def test_new_install_is_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPEN_COMMERCE_RUNTIME_PROFILE")
    assert Settings(_env_file=None).runtime_profile == "self_hosted"


def test_hosted_fails_closed_without_identity_and_budgets() -> None:
    with pytest.raises(ValidationError, match="Hosted mode requires"):
        Settings(_env_file=None, runtime_profile="hosted")
    with pytest.raises(ValidationError, match="exact hostnames"):
        Settings(_env_file=None, public_hosts=["*.example.com"])


def test_upload_encryption_is_scoped_and_randomized() -> None:
    settings = Settings(
        _env_file=None, encryption_key=SecretStr(base64.urlsafe_b64encode(b"k" * 32).decode())
    )
    tenant = str(uuid4())
    encrypted = encrypt(settings, b"private,catalog,rows", context=tenant)
    assert b"private" not in encrypted
    assert encrypt(settings, b"private,catalog,rows", context=tenant) != encrypted
    assert decrypt(settings, encrypted, context=tenant) == b"private,catalog,rows"
    with pytest.raises(InvalidTag):
        decrypt(settings, encrypted, context=str(uuid4()))
    with pytest.raises(StoreError):
        encrypt(Settings(_env_file=None), b"data", context=tenant)


async def test_model_guard_requires_authenticated_scope() -> None:
    with pytest.raises(ManagerModelUnavailableError, match="authenticated store budget"):
        await admit_model_call(10, 10)


def test_setup_payload_hides_credentials() -> None:
    request = OwnerSetupRequest(
        name="Demo",
        username="test-owner",
        password="not-a-real-password",
        bootstrap_token="synthetic-test-token",
    )
    assert "not-a-real-password" not in repr(request)
    assert "synthetic-test-token" not in request.model_dump_json()


def test_setup_milestones_reject_arbitrary_payloads() -> None:
    with pytest.raises(ValidationError):
        ImportMilestone.model_validate({"kind": "track_anything", "import_id": str(uuid4())})
    with pytest.raises(ValidationError):
        ImportMilestone.model_validate(
            {"kind": "products_uploaded", "import_id": str(uuid4()), "rows": ["private data"]}
        )
