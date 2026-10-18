"""Create a second synthetic browser identity only in an opted-in disposable test DB.

This is local test setup, not an OIDC protocol test or a public application route.
Stdout is private IPC containing the fixture session; do not publish it in reports.
"""

import asyncio
import json
import os
import re
from uuid import uuid4

from sqlalchemy.engine import make_url

from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import StoreProfileUpdate
from open_commerce.stores.setup import StoreSetupService


def validate_fixture_environment(settings: Settings) -> None:
    url = make_url(settings.database_url)
    if (
        os.getenv("OPEN_COMMERCE_SELF_SERVICE_BROWSER") != "1"
        or settings.runtime_profile != "self_hosted"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or not re.fullmatch(r"opencommerce_test_[a-f0-9]{32}", url.database or "")
        or settings.manager_model_provider != "deterministic"
        or settings.model_enabled
        or settings.openai_api_key
        or settings.local_operations_enabled
    ):
        raise RuntimeError("Merchant fixture requires the isolated, model-disabled browser test.")


async def main() -> None:
    settings = Settings(_env_file=None)
    validate_fixture_environment(settings)
    database = RuntimeDatabase(settings)
    try:
        identity, token = await MerchantAuthService(database).oidc_identity(
            "https://merchant-browser-fixture.invalid", uuid4().hex
        )
        store = await StoreSetupService(database).profile(
            identity.store.id, StoreProfileUpdate(name="Second Fixture Store")
        )
        print(
            json.dumps(
                {
                    "identity": identity.model_dump(mode="json"),
                    "store": store.model_dump(mode="json"),
                    "token": token,
                }
            )
        )
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
