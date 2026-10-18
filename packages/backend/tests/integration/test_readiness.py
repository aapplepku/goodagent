import os

import pytest

from open_commerce.api.readiness import aggregate_status, run_readiness_checks
from open_commerce.config import Settings

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_dependencies_are_ready() -> None:
    if os.getenv("OPEN_COMMERCE_RUN_INTEGRATION") != "1":
        pytest.skip("integration dependencies are not enabled")

    settings = Settings()
    dependencies = await run_readiness_checks(settings)

    assert aggregate_status(dependencies) == "ready"
    assert {dependency.name for dependency in dependencies} == {"postgres", "redis", "qdrant"}
