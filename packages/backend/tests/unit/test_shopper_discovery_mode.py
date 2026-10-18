"""Pre-turn capability labels do not probe a model or imply connectivity."""

from unittest.mock import create_autospec, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from open_commerce.config import Settings
from open_commerce.manager_agent.model_provider import ManagerModelProvider
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperDiscoveryResponse
from open_commerce.shopper_agent.service import DurableShopperAgentService


def test_older_discovery_payload_does_not_imply_a_model_connection() -> None:
    response = ShopperDiscoveryResponse.model_validate({"catalog_status": "ready"})
    assert response.conversation_mode == "unknown"


@pytest.mark.parametrize("value", ["connected", "healthy", "trained", "", None])
def test_discovery_mode_rejects_unverified_connection_claims(value: object) -> None:
    with pytest.raises(ValidationError):
        ShopperDiscoveryResponse.model_validate({"conversation_mode": value})


@pytest.mark.parametrize("configured", [False, True])
async def test_discovery_reports_actual_provider_without_invocation(configured: bool) -> None:
    database = create_autospec(RuntimeDatabase, instance=True)
    database.settings = Settings(environment="test", manager_model_provider="deterministic")
    provider = create_autospec(ManagerModelProvider, instance=True)
    service = DurableShopperAgentService(
        database, search_service=SearchService(), model_provider=provider if configured else None
    )
    tenant_id = uuid4()
    with (
        patch("open_commerce.shopper_agent.service.catalog_index_status") as status,
        patch("open_commerce.shopper_agent.service.active_catalog_integration") as integration,
        patch("open_commerce.shopper_agent.service.catalog_records") as records,
    ):
        status.return_value.status = "not_configured"
        status.return_value.filename = None
        integration.return_value = None
        response = await service.discovery(tenant_id=tenant_id, account_id=uuid4())
        assert response.conversation_mode == ("model_configured" if configured else "basic")
        assert response.catalog_status == "not_configured"
        assert response.suggestions == []
        provider.begin.assert_not_called()
        records.assert_not_called()
        database.transaction.assert_called_once_with(tenant_id)
        assert status.await_args is not None
        assert integration.await_args is not None
        assert status.await_args.kwargs["tenant_id"] == tenant_id
        assert integration.await_args.kwargs["tenant_id"] == tenant_id
