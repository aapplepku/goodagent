"""Real PostgreSQL merchant reports: scopes, complete counts and no mutations."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from open_commerce.catalog.models import CatalogProductInput, CatalogVariantInput
from open_commerce.catalog.persistence import activate_catalog, stage_catalog_upload
from open_commerce.commerce.models import CartItemAddRequest, CheckoutPreviewRequest
from open_commerce.commerce.service import DurableCommerceService
from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.manager_agent.catalog_operations import catalog_facts
from open_commerce.manager_agent.model_provider import ManagerToolCall
from open_commerce.manager_agent.models import ManagerMessageRequest, ManagerThreadCreateRequest
from open_commerce.manager_agent.operations import StoreOperations
from open_commerce.manager_agent.operations_models import OperationsWindow
from open_commerce.manager_agent.workspace_tools import WorkspaceTools
from open_commerce.persistence.models.catalog import InventorySnapshot, ProductVariant
from open_commerce.persistence.models.commerce import (
    InventoryReservationRecord,
    PaymentAttemptRecord,
    ShopperCartRecord,
    ShopperOrderRecord,
)
from open_commerce.persistence.models.shopper_activity import ShopperActivityRecord
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.providers.local_payment import LocalTestPaymentProvider
from open_commerce.search.service import SearchService
from open_commerce.shopper_agent.models import ShopperRegisterRequest
from open_commerce.shopper_agent.service import DurableShopperAgentService

pytestmark = pytest.mark.integration


async def seed_catalog(db: RuntimeDatabase, tenant: UUID, title: str = "Tea") -> UUID:
    now = utc_now()
    async with db.transaction(tenant, write=True) as session:
        index = await stage_catalog_upload(
            session,
            tenant_id=tenant,
            filename="private-source.csv",
            source_version=f"sha256:{uuid4().hex}{uuid4().hex}",
            products=[
                CatalogProductInput(
                    source_product_id="tea",
                    title=title,
                    description_text="",
                    source_updated_at=now,
                    attributes={"image_failed": True, "private": "do-not-send-raw-attributes"},
                    variants=[
                        CatalogVariantInput(
                            source_variant_id="tea-small",
                            sku="TEA",
                            title="Small",
                            price_minor=1200,
                            currency="USD",
                            available=True,
                            inventory_quantity=10,
                        )
                    ],
                )
            ],
        )
        assert index.catalog_id is not None
        await activate_catalog(
            session,
            tenant_id=tenant,
            integration_id=index.catalog_id,
            indexed_count=1,
            completed_at=now,
        )
    return index.catalog_id


async def seed_account(db: RuntimeDatabase, tenant: UUID) -> UUID:
    service = DurableShopperAgentService(db, search_service=SearchService())
    response, _ = await service.register(
        tenant_id=tenant,
        request=ShopperRegisterRequest(
            username=f"buyer-{uuid4().hex[:8]}",
            display_name="Private Customer",
            password="private-testing-password",
        ),
    )
    return response.account.id


async def test_catalog_stock_reports_use_latest_observation_and_scoped_reservations(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        catalog = await seed_catalog(db, tenant, "Tea contact owner@example.com")
        await seed_catalog(db, other, "Other private store")
        account = await seed_account(db, tenant)
        commerce = DurableCommerceService(db, payment_provider=LocalTestPaymentProvider())
        cart = await commerce.add_item(
            tenant_id=tenant,
            account_id=account,
            request=CartItemAddRequest(product_id="tea", quantity=3),
            idempotency_key="cart",
            request_id="test",
        )
        await commerce.preview_checkout(
            tenant_id=tenant,
            account_id=account,
            request=CheckoutPreviewRequest(cart_version=cart.version),
            idempotency_key="preview",
            request_id="test",
        )
        now = utc_now()
        async with db.transaction(tenant, write=True) as session:
            variant = await session.scalar(
                select(ProductVariant).where(ProductVariant.tenant_id == tenant)
            )
            assert variant
            # Imported quantity 10, latest 6, then a future record that must not be used.
            session.add_all(
                [
                    InventorySnapshot(
                        id=uuid4(),
                        tenant_id=tenant,
                        integration_id=catalog,
                        variant_id=variant.id,
                        available_quantity=quantity,
                        observed_at=at,
                    )
                    for quantity, at in [
                        (100, now - timedelta(days=10)),
                        (6, now),
                        (999, now + timedelta(days=1)),
                    ]
                ]
            )
        tools = WorkspaceTools(db)
        stock = await tools.execute(
            ManagerToolCall(name="review_inventory_risks", call_id="stock", arguments={}),
            tenant,
            None,
        )
        examples = stock["examples"]
        assert isinstance(examples, list) and examples[0]["sellable_quantity"] == 3
        assert examples[0]["observed_quantity"] == 6
        assert examples[0]["reserved_quantity"] == 3
        assert stock["counts"]["low"] == 1  # type: ignore[index]
        quality = await tools.execute(
            ManagerToolCall(name="audit_catalog_quality", call_id="quality", arguments={}),
            tenant,
            None,
        )
        assert quality["issue_counts"]["image_failed"] == 1  # type: ignore[index]
        for forbidden in (
            "owner@example.com",
            "Other private store",
            "do-not-send-raw-attributes",
            "Private Customer",
            str(account),
            "private-source.csv",
        ):
            assert forbidden not in str(stock) + str(quality)
        empty = await catalog_facts(db, uuid4())
        assert empty.catalog_id is None and empty.product_count == 0
        async with db.transaction(tenant) as session:
            quantities = list(
                await session.scalars(
                    select(InventorySnapshot.available_quantity).where(
                        InventorySnapshot.tenant_id == tenant
                    )
                )
            )
        assert sorted(quantities) == [6, 10, 100, 999]
        service = StoreOperations(db)
        checkout = await service.checkout(tenant, OperationsWindow())
        assert checkout.nonempty_open_carts == 1 and checkout.inactive_open_carts == 0
        async with db.transaction(tenant, write=True) as session:
            hold = await session.scalar(
                select(InventoryReservationRecord).where(
                    InventoryReservationRecord.tenant_id == tenant
                )
            )
            saved_cart = await session.scalar(
                select(ShopperCartRecord).where(ShopperCartRecord.tenant_id == tenant)
            )
            payment = await session.scalar(
                select(PaymentAttemptRecord).where(PaymentAttemptRecord.tenant_id == tenant)
            )
            assert hold and saved_cart and payment
            hold.expires_at = now - timedelta(seconds=1)
            saved_cart.updated_at = now - timedelta(hours=25)
            payment.status = "processing"
            payment.updated_at = now - timedelta(minutes=16)
        # Expired holds are ignored even before the cleanup worker marks them expired.
        refreshed = await catalog_facts(db, tenant)
        assert refreshed.variants[0].reserved_quantity == 0
        checkout = await service.checkout(tenant, OperationsWindow())
        assert checkout.inactive_open_carts == 1 and checkout.overdue_processing == 1
        assert {action.topic for action in checkout.next_actions} == {
            "inactive_carts",
            "checkout_processing",
        }
        async with db.transaction(tenant, write=True) as session:
            payment = await session.scalar(
                select(PaymentAttemptRecord).where(PaymentAttemptRecord.tenant_id == tenant)
            )
            assert payment
            payment.status = "requires_payment_method"
        checkout = await service.checkout(tenant, OperationsWindow())
        assert checkout.overdue_processing == 0
        assert "checkout_declines" in {action.topic for action in checkout.next_actions}
    finally:
        await db.close()


async def test_activity_reports_exclude_test_scopes_and_use_measured_denominators(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    now = utc_now()
    monkeypatch.setattr("open_commerce.manager_agent.operations.utc_now", lambda: now)
    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        account = await seed_account(db, tenant)
        other_account = await seed_account(db, other)
        rows = []
        for t, a, status, results, at, preview, sample in [
            *[
                (tenant, account, "ok", 0 if i < 2 else 5, now - timedelta(minutes=1), False, False)
                for i in range(5)
            ],
            (tenant, account, "ok", None, now - timedelta(minutes=1), False, False),
            (tenant, account, "error", 0, now - timedelta(minutes=1), False, False),
            (tenant, account, "ok", 0, now - timedelta(minutes=1), True, False),
            (tenant, account, "ok", 0, now - timedelta(minutes=1), False, True),
            (tenant, account, "ok", 5, now - timedelta(hours=24), False, False),
            (tenant, account, "ok", 0, now - timedelta(hours=25), False, False),
            (tenant, account, "ok", 0, now, False, False),
            (other, other_account, "ok", 0, now - timedelta(minutes=1), False, False),
        ]:
            rows.append(
                ShopperActivityRecord(
                    id=uuid4(),
                    tenant_id=t,
                    account_id=a,
                    event_key=uuid4().hex,
                    kind="search",
                    status=status,
                    duration_ms=10,
                    result_count=results,
                    occurred_at=at,
                    is_preview=preview,
                    is_sample=sample,
                )
            )
        async with db.transaction(tenant, write=True) as session:
            session.add_all(rows)
        service = StoreOperations(db)
        report = await service.performance(tenant, OperationsWindow())
        assert report.current.events == 8
        assert report.current.measured_searches == 6
        assert report.current.empty_searches == 2
        assert report.current.empty_result_percent == 33.33
        assert report.current.unsuccessful_by_kind == {"search": 1}
        assert report.previous.events == 1 and report.previous.empty_result_percent is None
        assert report.previous_window_within_retention
        assert str(account) not in report.model_dump_json()
        included = await service.performance(tenant, OperationsWindow(include_test_sessions=True))
        assert included.current.events == 10 and included.current.empty_searches == 4
        long_window = await service.performance(tenant, OperationsWindow(hours=720))
        assert not long_window.previous_window_within_retention
        empty = await service.performance(uuid4(), OperationsWindow())
        assert empty.current.empty_result_percent is None
        assert empty.next_actions[0].topic == "activity_missing"
    finally:
        await db.close()


async def seed_orders(
    db: RuntimeDatabase, tenant: UUID, account: UUID, count: int, currency: str, created: datetime
) -> None:
    async with db.transaction(tenant, write=True) as session:
        for _ in range(count):
            cart, payment = uuid4(), uuid4()
            session.add(
                ShopperCartRecord(
                    id=cart,
                    tenant_id=tenant,
                    account_id=account,
                    status="converted",
                    currency=currency,
                    created_at=created,
                    updated_at=created,
                    version=1,
                )
            )
            await session.flush()
            session.add(
                PaymentAttemptRecord(
                    id=payment,
                    tenant_id=tenant,
                    account_id=account,
                    cart_id=cart,
                    cart_version=1,
                    provider="local_test",
                    provider_reference="private-provider-reference",
                    status="succeeded",
                    amount_minor=1200,
                    currency=currency,
                    idempotency_key_digest=uuid4().hex,
                    policy_decision={},
                    preconditions=[],
                    rollback_metadata={},
                    created_at=created,
                    updated_at=created,
                    version=1,
                )
            )
            await session.flush()
            session.add(
                ShopperOrderRecord(
                    id=uuid4(),
                    tenant_id=tenant,
                    account_id=account,
                    cart_id=cart,
                    payment_attempt_id=payment,
                    order_number=uuid4().hex,
                    status="paid",
                    amount_minor=1200,
                    currency=currency,
                    line_snapshots=[],
                    created_at=created,
                )
            )


async def test_checkout_report_counts_more_than_overview_limit_and_separates_currencies(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant, other = uuid4(), uuid4()
    now = utc_now()
    try:
        await db.initialize_tenant(tenant)
        await db.initialize_tenant(other)
        account = await seed_account(db, tenant)
        other_account = await seed_account(db, other)
        await seed_orders(db, tenant, account, 53, "USD", now - timedelta(hours=1))
        await seed_orders(db, tenant, account, 2, "EUR", now - timedelta(hours=1))
        await seed_orders(db, tenant, account, 1, "USD", now - timedelta(days=2))
        await seed_orders(db, other, other_account, 1, "USD", now - timedelta(hours=1))
        result = await StoreOperations(db).checkout(tenant, OperationsWindow())
        assert result.orders_by_status == {"paid": 55}
        assert result.payments_by_status == {"succeeded": 55}
        assert {item.currency: item.amount_minor for item in result.demo_paid_totals} == {
            "USD": 63600,
            "EUR": 2400,
        }
        assert result.payment_mode == "local_test"
        assert "private-provider-reference" not in result.model_dump_json()
        assert str(account) not in result.model_dump_json()
        assert result.nonempty_open_carts == 0
    finally:
        await db.close()


async def test_daily_review_does_not_publish_replacement_or_fake_legacy_setup(
    integration_settings: Settings,
) -> None:
    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    try:
        await db.initialize_tenant(tenant)
        service = StoreOperations(db)
        legacy = await service.readiness(tenant)
        assert not legacy.setup_available and legacy.sharing_enabled is None
        old = await seed_catalog(db, tenant)
        latest = await seed_catalog(db, tenant, "Replacement Tea")
        async with db.transaction(tenant, write=True) as session:
            session.add(
                StoreSetupRecord(
                    tenant_id=tenant,
                    sharing_enabled=True,
                    published_catalog_id=old,
                    readiness={"tested_catalog_id": str(old)},
                    created_at=utc_now(),
                )
            )
        output = await service.execute(
            ManagerToolCall(name="review_store_day", call_id="brief", arguments={}), tenant
        )
        assert output["read_only"] is True
        readiness = output["readiness"]
        assert isinstance(readiness, dict)
        assert readiness["replacement_pending"] is True
        assert readiness["published_catalog_id"] == str(old)
        assert readiness["indexed_catalog_id"] == str(latest)
        assert readiness["checklist"]["search_tested"] is False
        assert output["catalog"]["product_count"] == 1  # type: ignore[index]
        async with db.transaction(tenant) as session:
            setup = await session.scalar(
                select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == tenant)
            )
        assert setup and setup.published_catalog_id == old and setup.sharing_enabled
    finally:
        await db.close()


async def test_daily_review_runs_through_durable_model_receipts_and_events(
    integration_settings: Settings,
) -> None:
    import json

    import httpx
    from pydantic import SecretStr

    from open_commerce.manager_agent.runs import ManagerRunService
    from open_commerce.manager_agent.service import DurableManagerAgentService
    from open_commerce.providers.openai_manager import OpenAIManagerProvider

    from .test_manager_runs import call, message

    db = RuntimeDatabase(integration_settings)
    tenant = uuid4()
    receipts: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert len(request.content) <= 64000
        outputs = [item for item in payload["input"] if item.get("type") == "function_call_output"]
        if not outputs:
            output = call(
                "review_store_day", {"hours": 24, "include_test_sessions": False}, "review"
            )
        else:
            report = json.loads(outputs[-1]["output"])
            assert "private-source.csv" not in outputs[-1]["output"]
            receipts.append(report)
            assert report["catalog"]["product_count"] == 1
            assert report["read_only"] is True
            output = message(
                "Your catalog has missing images. Review them in Store setup; "
                "no products or sharing changed."
            )
        return httpx.Response(200, json={"status": "completed", "output": [output]})

    try:
        await db.initialize_tenant(tenant)
        await seed_catalog(db, tenant)
        service = DurableManagerAgentService(
            db,
            model_provider=OpenAIManagerProvider(
                api_key=SecretStr("test-only"),
                model_id="fixture-model",
                max_input_bytes=64000,
                transport=httpx.MockTransport(respond),
            ),
        )
        thread = await service.create_thread(
            tenant_id=tenant,
            request=ManagerThreadCreateRequest(title="Operations"),
            idempotency_key="thread",
        )
        runs = ManagerRunService(db)
        request = ManagerMessageRequest(content="What needs my attention today?")
        run = await runs.submit(
            tenant_id=tenant, thread_id=thread.thread.id, request=request, idempotency_key="daily"
        )
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert (await runs.get(tenant_id=tenant, run_id=run.id)).status == "completed"
        assert len(receipts) == 1
        events = await runs.events(tenant_id=tenant, run_id=run.id)
        assert any(
            event.tool == "review_store_day" and event.kind == "tool_result"
            for event in events.items
        )
        replay = await runs.submit(
            tenant_id=tenant, thread_id=thread.thread.id, request=request, idempotency_key="daily"
        )
        assert replay.id == run.id
        assert await runs.process(tenant_id=tenant, run_id=run.id, service=service)
        assert len(receipts) == 1
        detail = await service.get_thread(tenant_id=tenant, thread_id=thread.thread.id)
        assert "missing images" in detail.messages[-1].content
    finally:
        await db.close()
