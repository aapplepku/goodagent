"""Reviewed-state preconditions with real parsing/receipts and mocked persistence."""

import asyncio
import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Self, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from open_commerce.api import stores
from open_commerce.api.errors import register_exception_handlers
from open_commerce.api.store_auth import current_owner
from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.config import Settings
from open_commerce.core.types import canonical_hash, utc_now
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.workflow import IdempotencyRecord
from open_commerce.persistence.repositories.requests import IdempotencyConflictError
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores.import_models import ImportMapping, ImportReview
from open_commerce.stores.imports import CatalogImportService, review_fingerprint
from open_commerce.stores.models import OwnerIdentity, StoreError

TENANT, CATALOG = UUID(int=13601), UUID(int=13602)
CSV = b"product_id,title,retail,cost\none,Synthetic product,100,1\n"
MAPPING = {"product_id": "product_id", "title": "title", "price": "retail"}


class Memory:
    def __init__(self) -> None:
        self.settings = Settings(
            _env_file=None,
            runtime_profile="self_hosted",
            encryption_key=SecretStr(base64.urlsafe_b64encode(b"u" * 32).decode()),
        )
        self.rows: list[Any] = []
        self.lock = asyncio.Lock()
        self.session = MagicMock(spec=AsyncSession)
        self.session.scalar = AsyncMock(side_effect=self.scalar)
        self.session.add.side_effect = self.rows.append

    async def scalar(self, statement: Any) -> Any:
        entity = statement.column_descriptions[0]["entity"]
        rows = [row for row in self.rows if isinstance(row, entity)]
        for clause in statement._where_criteria:
            assert clause.operator.__name__ == "eq"
            rows = [row for row in rows if getattr(row, clause.left.name) == clause.right.value]
        return rows[0] if rows else None

    @asynccontextmanager
    async def transaction(
        self, tenant: UUID, *, write: bool = False
    ) -> AsyncIterator[AsyncSession]:
        if write:
            async with self.lock:
                yield self.session
        else:
            yield self.session


@dataclass
class Harness:
    memory: Memory
    service: CatalogImportService
    uploaded: ImportReview
    stage: AsyncMock

    @property
    def row(self) -> CatalogImportRecord:
        return next(row for row in self.memory.rows if isinstance(row, CatalogImportRecord))

    async def reviewed(self, *, price: str = "retail", currency: str = "USD") -> ImportReview:
        return await self.service.review(
            TENANT,
            self.uploaded.id,
            ImportMapping.model_validate(
                {"mapping": {**MAPPING, "price": price}, "currency": currency}
            ),
        )

    async def confirm(self, review: ImportReview, key: str = "confirm") -> ImportReview:
        assert review.review_fingerprint
        return await self.service.confirm(
            TENANT, review.id, key, expected_review_fingerprint=review.review_fingerprint
        )


@pytest.fixture
async def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    memory = Memory()
    monkeypatch.setattr(stores, "CatalogImportService", CatalogImportService)
    monkeypatch.setattr("open_commerce.stores.imports.record_import_milestone", AsyncMock())
    index = CatalogIndexStatus(status="queued", catalog_id=CATALOG, product_count=1)
    stage = AsyncMock(return_value=index)
    monkeypatch.setattr("open_commerce.stores.imports.stage_catalog_upload", stage)
    monkeypatch.setattr(
        "open_commerce.stores.imports.catalog_index_status", AsyncMock(return_value=index)
    )
    service = CatalogImportService(cast(RuntimeDatabase, memory))
    uploaded = await service.upload(TENANT, "synthetic.csv", CSV)
    return Harness(memory, service, uploaded, stage)


async def test_fingerprint_ignores_parser_clock_and_mapping_key_order(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = datetime(2026, 10, 18, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Self:
            return cls.fromtimestamp(clock.timestamp(), tz=tz)

    monkeypatch.setattr("open_commerce.catalog.csv_import.datetime", Clock)
    first = await harness.reviewed()
    clock += timedelta(minutes=5)
    second = await harness.service.review(TENANT, first.id)
    third = await harness.service.review(
        TENANT,
        first.id,
        ImportMapping(mapping=dict(reversed(list(MAPPING.items()))), currency="USD"),
    )
    assert first.products[0].source_updated_at != second.products[0].source_updated_at
    assert first.review_fingerprint == second.review_fingerprint == third.review_fingerprint
    assert first.review_fingerprint and len(first.review_fingerprint) == 71


@pytest.mark.parametrize("changed", ["mapping", "currency", "upload", "tenant", "import"])
async def test_fingerprint_binds_each_persisted_input(harness: Harness, changed: str) -> None:
    reviewed = await harness.reviewed()
    row = harness.row
    if changed == "mapping":
        row.mapping = {**MAPPING, "price": "cost"}
    elif changed == "currency":
        row.currency = "EUR"
    elif changed == "upload":
        row.encrypted_data += b"synthetic-change"
    elif changed == "tenant":
        row.tenant_id = uuid4()
    else:
        row.id = uuid4()
    assert review_fingerprint(row) != reviewed.review_fingerprint


async def test_stale_review_has_no_staging_erasure_or_receipt_and_refresh_confirms(
    harness: Harness,
) -> None:
    first = await harness.reviewed()
    latest = await harness.reviewed(price="cost", currency="EUR")
    before = (harness.row.encrypted_data, dict(harness.row.report), len(harness.memory.rows))
    with pytest.raises(StoreError, match="review changed") as rejected:
        await harness.confirm(first)
    assert rejected.value.status_code == 409
    assert before == (harness.row.encrypted_data, harness.row.report, len(harness.memory.rows))
    harness.stage.assert_not_awaited()
    confirmed = await harness.confirm(latest)
    assert confirmed.review_fingerprint == latest.review_fingerprint
    assert not harness.row.encrypted_data
    product = harness.stage.call_args.kwargs["products"][0]
    assert (product.variants[0].price_minor, product.variants[0].currency) == (100, "EUR")


async def test_exact_replay_and_second_key_keep_one_staging_after_expiry(harness: Harness) -> None:
    reviewed = await harness.reviewed()
    first, duplicate = await asyncio.gather(harness.confirm(reviewed), harness.confirm(reviewed))
    assert first == duplicate
    harness.row.expires_at = utc_now() - timedelta(days=1)
    assert await harness.confirm(reviewed, "second-key") == first
    harness.stage.assert_awaited_once()
    changed = reviewed.model_copy(update={"review_fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(IdempotencyConflictError):
        await harness.confirm(changed)
    with pytest.raises(StoreError) as mismatch:
        await harness.confirm(changed, "new-key")
    assert mismatch.value.status_code == 409
    with pytest.raises(IdempotencyConflictError):
        await harness.service.confirm(
            TENANT,
            uuid4(),
            "second-key",
            expected_review_fingerprint=reviewed.review_fingerprint or "",
        )
    assert (
        await harness.service.review(TENANT, reviewed.id)
    ).review_fingerprint == reviewed.review_fingerprint


@pytest.mark.parametrize("closed", ["confirmed", "cancelled"])
async def test_legacy_closed_reports_are_readable_without_allowing_confirmation(
    harness: Harness, closed: str
) -> None:
    reviewed = await harness.reviewed()
    harness.row.status = closed
    harness.row.encrypted_data = b""
    harness.row.report = reviewed.model_copy(update={"status": closed}).model_dump(
        mode="json", exclude={"review_fingerprint"}
    )
    assert (await harness.service.review(TENANT, reviewed.id)).review_fingerprint is None
    with pytest.raises(StoreError) as rejected:
        await harness.confirm(reviewed)
    assert rejected.value.status_code == 409
    harness.stage.assert_not_awaited()


async def test_old_id_only_receipt_never_falls_back_to_unsafe_confirmation(
    harness: Harness,
) -> None:
    reviewed = await harness.reviewed()
    harness.memory.rows.append(
        IdempotencyRecord(
            tenant_id=TENANT,
            scope="import:confirm",
            key="confirm",
            fingerprint=canonical_hash({"id": str(reviewed.id)}),
            response=reviewed.model_dump(mode="json", exclude={"review_fingerprint"}),
        )
    )
    with pytest.raises(IdempotencyConflictError):
        await harness.confirm(reviewed)
    assert harness.row.encrypted_data
    harness.stage.assert_not_awaited()


@pytest.mark.parametrize("closed", ["cancelled", "expired", "invalid"])
async def test_preconditions_do_not_weaken_closed_expired_or_invalid_imports(
    harness: Harness, closed: str
) -> None:
    reviewed = await harness.reviewed()
    if closed == "cancelled":
        await harness.service.cancel(TENANT, reviewed.id)
    elif closed == "expired":
        harness.row.expires_at = utc_now() - timedelta(seconds=1)
    else:
        reviewed = await harness.service.review(TENANT, reviewed.id, ImportMapping(mapping=MAPPING))
    raw = harness.row.encrypted_data
    with pytest.raises(StoreError) as rejected:
        await harness.confirm(reviewed)
    assert rejected.value.status_code == (410 if closed == "expired" else 409)
    assert harness.row.encrypted_data == raw
    harness.stage.assert_not_awaited()


async def test_other_tenant_does_not_gain_access_with_known_token(harness: Harness) -> None:
    reviewed = await harness.reviewed()
    assert reviewed.review_fingerprint
    with pytest.raises(StoreError) as rejected:
        await harness.service.confirm(
            uuid4(), reviewed.id, "foreign", expected_review_fingerprint=reviewed.review_fingerprint
        )
    assert rejected.value.status_code == 404
    harness.stage.assert_not_awaited()


def api(harness: Harness) -> FastAPI:
    app = FastAPI()
    app.state.database = harness.memory
    app.dependency_overrides[current_owner] = lambda: OwnerIdentity(
        user_id=uuid4(), tenant_id=TENANT
    )
    app.include_router(stores.router)
    register_exception_handlers(app)
    return app


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"expected_review_fingerprint": None},
        {"expected_review_fingerprint": "sha256:bad"},
        {"expected_review_fingerprint": "sha256:" + "a" * 65},
    ],
)
async def test_api_requires_well_formed_expected_review_without_effects(
    harness: Harness, body: Any
) -> None:
    reviewed = await harness.reviewed()
    before = len(harness.memory.rows)
    async with AsyncClient(
        transport=ASGITransport(app=api(harness)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/merchant/imports/{reviewed.id}/confirm",
            json=body,
            headers={"Idempotency-Key": "confirm"},
        )
    assert response.status_code == 422
    assert harness.row.encrypted_data and len(harness.memory.rows) == before
    harness.stage.assert_not_awaited()


async def test_api_delivers_precondition_to_service_and_returns_confirmed_token(
    harness: Harness,
) -> None:
    reviewed = await harness.reviewed()
    async with AsyncClient(
        transport=ASGITransport(app=api(harness)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/merchant/imports/{reviewed.id}/confirm",
            json={"expected_review_fingerprint": reviewed.review_fingerprint},
            headers={"Idempotency-Key": "confirm"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["review_fingerprint"] == reviewed.review_fingerprint
    harness.stage.assert_awaited_once()
