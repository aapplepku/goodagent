"""Setup readiness uses one eligible import without changing publication state."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import (
    BinaryExpression,
    BindParameter,
    BooleanClauseList,
    ClauseElement,
)

from open_commerce.catalog.models import CatalogIndexStatus
from open_commerce.persistence.models.catalog import Product
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.identity import Tenant
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.stores import setup as store_setup
from open_commerce.stores.setup import StoreReadiness, StoreSetupService

TENANT, FOREIGN = UUID(int=13001), UUID(int=13002)
CATALOG_A, CATALOG_B, PUBLISHED = (UUID(int=value) for value in (13003, 13004, 13005))
NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


def imported(
    ordinal: int,
    *,
    status: str = "confirmed",
    catalog: UUID | None = CATALOG_A,
    expires: datetime = NOW + timedelta(days=1),
    tenant: UUID = TENANT,
) -> CatalogImportRecord:
    return CatalogImportRecord(
        id=UUID(int=ordinal),
        tenant_id=tenant,
        filename=f"synthetic-{ordinal}.csv",
        created_at=NOW + timedelta(seconds=ordinal),
        expires_at=expires,
        status=status,
        catalog_id=catalog,
        encrypted_data=b"",
        mapping={},
        currency="USD",
        report={},
    )


def matches(record: CatalogImportRecord, clause: ClauseElement) -> bool:
    """Evaluate only the selection predicate against synthetic rows, not actual SQL."""
    if isinstance(clause, BooleanClauseList):
        results = [matches(record, child) for child in clause.clauses]
        if clause.operator is operators.and_:
            return all(results)
        assert clause.operator is operators.or_
        return any(results)
    assert isinstance(clause, BinaryExpression)
    assert isinstance(clause.right, BindParameter)
    assert clause.left.key is not None
    value, expected = getattr(record, clause.left.key), clause.right.value
    if clause.operator is operators.eq:
        return bool(value == expected)
    if clause.operator is operators.gt:
        return bool(value > expected)
    assert clause.operator is operators.in_op
    assert isinstance(expected, list)
    return value in expected


@dataclass
class Harness:
    database: MagicMock
    session: MagicMock
    index: AsyncMock
    setup: StoreSetupRecord
    imports: list[CatalogImportRecord] = field(default_factory=list)
    image_failures: int = 0
    image_rows: list[Product] = field(default_factory=list)

    async def readiness(self) -> StoreReadiness:
        return await StoreSetupService(self.database).readiness(TENANT)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    database = create_autospec(RuntimeDatabase, instance=True)
    session = create_autospec(AsyncSession, instance=True)
    database.transaction.return_value.__aenter__.return_value = session
    owner = Tenant(id=TENANT, slug="synthetic", display_name="Synthetic", default_currency="USD")
    setup = StoreSetupRecord(
        tenant_id=TENANT,
        description="Synthetic store",
        goal="Synthetic",
        sharing_enabled=True,
        published_catalog_id=PUBLISHED,
        sample_data=False,
        readiness={
            "catalog_id": str(CATALOG_B),
            "tested_catalog_id": str(CATALOG_B),
            "images_reviewed": True,
            "ai_verified": True,
            "checkout_acknowledged": True,
        },
    )

    async def index_status(
        selected_session: AsyncSession, *, tenant_id: UUID, integration_id: UUID | None = None
    ) -> CatalogIndexStatus:
        assert selected_session is session and tenant_id == TENANT
        return CatalogIndexStatus(
            catalog_id=integration_id or CATALOG_B,
            job_id=UUID(int=13006),
            status="ready",
            product_count=2,
            indexed_product_count=2,
        )

    index = AsyncMock(side_effect=index_status)
    fixture = Harness(cast(MagicMock, database), cast(MagicMock, session), index, setup)

    async def scalar(statement: Select[Any]) -> object:
        assert TENANT in statement.compile().params.values()
        if statement.column_descriptions[0]["entity"] is CatalogImportRecord:
            rows = [
                row
                for row in fixture.imports
                if all(matches(row, clause) for clause in statement._where_criteria)
            ]
            if statement._order_by_clauses:
                assert [str(clause) for clause in statement._order_by_clauses] == [
                    "catalog_imports.created_at DESC",
                    "catalog_imports.id DESC",
                ]
                rows.sort(key=lambda row: (row.created_at, row.id), reverse=True)
            if not rows:
                return None
            return rows[0].id if list(statement.selected_columns.keys()) == ["id"] else rows[0]
        assert "count(" in str(statement) and "FROM products" in str(statement)
        return fixture.image_failures

    async def scalars(statement: Select[Any]) -> list[Product]:
        assert "FROM products" in str(statement)
        return fixture.image_rows[:100]

    session.scalar.side_effect = scalar
    session.scalars.side_effect = scalars
    monkeypatch.setattr(store_setup, "store_records", AsyncMock(return_value=(owner, setup)))
    monkeypatch.setattr(store_setup, "catalog_index_status", index)
    monkeypatch.setattr(store_setup, "utc_now", lambda: NOW)
    yield fixture
    session.execute.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    assert setup.published_catalog_id == PUBLISHED and setup.sharing_enabled
    assert all(
        call.kwargs.get("write", False) is False for call in database.transaction.call_args_list
    )


def assert_no_candidate(result: StoreReadiness) -> None:
    assert result.indexing == CatalogIndexStatus()
    assert result.image_failures == 0 and result.image_issues == []
    assert not result.image_issues_truncated
    for key in ("catalog_verified", "images_reviewed", "search_tested"):
        assert result.checklist[key] is False
    assert result.checklist["ai_verified"]
    assert result.checklist["demo_checkout_acknowledged"]
    assert result.checklist["sharing_enabled"]
    assert result.store.published_catalog_id == PUBLISHED


async def test_reused_catalog_resolves_exact_selected_import(harness: Harness) -> None:
    harness.imports = [imported(1), imported(2, catalog=CATALOG_B), imported(3)]
    harness.image_failures = 1
    harness.image_rows = [Product(source_product_id="a", title="A image")]

    result = await harness.readiness()

    assert result.latest_import_id == UUID(int=3)
    assert result.indexing.catalog_id == CATALOG_A
    harness.index.assert_awaited_once_with(
        harness.session, tenant_id=TENANT, integration_id=CATALOG_A
    )
    assert result.checklist["catalog_verified"]
    assert not result.checklist["images_reviewed"]
    assert not result.checklist["search_tested"]
    assert result.image_issues[0].product_id == "a"
    image_queries = [harness.session.scalar.call_args, harness.session.scalars.call_args]
    for call in image_queries:
        params = call.args[0].compile().params
        assert params["tenant_id_1"] == TENANT
        assert params["integration_id_1"] == CATALOG_A


@pytest.mark.parametrize(
    ("status", "expiry", "eligible"),
    [
        ("cancelled", NOW + timedelta(days=1), False),
        ("expired", NOW + timedelta(days=1), False),
        ("unknown", NOW + timedelta(days=1), False),
        ("mapping", NOW - timedelta(microseconds=1), False),
        ("mapping", NOW, False),
        ("review", NOW, False),
        ("mapping", NOW + timedelta(microseconds=1), True),
        ("review", NOW + timedelta(microseconds=1), True),
        ("confirmed", NOW - timedelta(days=1), True),
    ],
)
async def test_selection_eligibility(
    harness: Harness, status: str, expiry: datetime, eligible: bool
) -> None:
    older = imported(1, catalog=CATALOG_B)
    newer = imported(2, status=status, expires=expiry)
    harness.imports = [older, newer]

    result = await harness.readiness()

    assert result.latest_import_id == (newer.id if eligible else older.id)
    if eligible and status != "confirmed":
        assert_no_candidate(result)
        harness.index.assert_not_awaited()
    else:
        assert result.indexing.catalog_id == (CATALOG_A if eligible else CATALOG_B)


async def test_cancelled_replacement_resumes_failed_catalog(harness: Harness) -> None:
    harness.imports = [imported(1), imported(2, status="cancelled", catalog=None)]
    harness.index.side_effect = None
    harness.index.return_value = CatalogIndexStatus(catalog_id=CATALOG_A, status="failed")

    result = await harness.readiness()

    assert result.latest_import_id == UUID(int=1)
    assert result.indexing.catalog_id == CATALOG_A and result.indexing.status == "failed"
    assert not result.checklist["catalog_verified"]


async def test_ties_and_foreign_rows_are_deterministic(harness: Harness) -> None:
    lower, higher = imported(1), imported(2, catalog=CATALOG_B)
    higher.created_at = lower.created_at
    harness.imports = [imported(3, tenant=FOREIGN), lower, higher]

    result = await harness.readiness()

    assert result.latest_import_id == higher.id and result.indexing.catalog_id == CATALOG_B
    query = harness.session.scalar.call_args_list[0].args[0]
    assert query.compile().params["expires_at_1"] == NOW
    assert query.compile().params["param_1"] == 1


@pytest.mark.parametrize("status", ["mapping", "review"])
async def test_pending_review_does_not_borrow_previous_checks(
    harness: Harness, status: str
) -> None:
    harness.imports = [imported(1, catalog=CATALOG_B), imported(2, status=status, catalog=None)]

    result = await harness.readiness()

    assert result.latest_import_id == UUID(int=2)
    assert_no_candidate(result)
    harness.index.assert_not_awaited()
    harness.session.scalars.assert_not_awaited()
    assert harness.session.scalar.await_count == 1


@pytest.mark.parametrize("broken", ["missing_id", "missing_job", "missing_integration", "wrong_id"])
async def test_broken_confirmed_reference_does_not_fall_back(harness: Harness, broken: str) -> None:
    harness.imports = [imported(1, catalog=None if broken == "missing_id" else CATALOG_A)]
    harness.index.side_effect = None
    harness.index.return_value = CatalogIndexStatus(
        catalog_id=CATALOG_B if broken == "wrong_id" else None,
        status="ready" if broken == "wrong_id" else "not_configured",
        serving_catalog_id=CATALOG_B,
    )

    result = await harness.readiness()

    assert result.latest_import_id == UUID(int=1)
    assert_no_candidate(result)
    if broken == "missing_id":
        harness.index.assert_not_awaited()
    else:
        harness.index.assert_awaited_once_with(
            harness.session, tenant_id=TENANT, integration_id=CATALOG_A
        )
    harness.session.scalars.assert_not_awaited()


@pytest.mark.parametrize("status", ["cancelled", "mapping", "unknown"])
async def test_closed_only_history_never_uses_legacy_fallback(
    harness: Harness, status: str
) -> None:
    harness.imports = [imported(1, status=status, expires=NOW)]

    result = await harness.readiness()

    assert result.latest_import_id is None
    assert_no_candidate(result)
    harness.index.assert_not_awaited()


async def test_no_tenant_import_history_preserves_direct_legacy_catalog(harness: Harness) -> None:
    harness.imports = [imported(1, tenant=FOREIGN)]

    result = await harness.readiness()

    assert result.latest_import_id is None and result.indexing.catalog_id == CATALOG_B
    assert result.checklist["catalog_verified"]
    harness.index.assert_awaited_once_with(harness.session, tenant_id=TENANT)


async def test_empty_store_has_no_catalog_checks(harness: Harness) -> None:
    harness.index.side_effect = None
    harness.index.return_value = CatalogIndexStatus()

    result = await harness.readiness()

    assert result.latest_import_id is None
    assert_no_candidate(result)
    harness.session.scalars.assert_not_awaited()


@pytest.mark.parametrize(
    ("total", "verified", "ready"), [(0, 0, False), (2, 1, False), (2, 2, True)]
)
async def test_ready_job_requires_verified_positive_counts(
    harness: Harness, total: int, verified: int, ready: bool
) -> None:
    harness.imports = [imported(1)]
    harness.index.side_effect = None
    harness.index.return_value = CatalogIndexStatus(
        catalog_id=CATALOG_A, status="ready", product_count=total, indexed_product_count=verified
    )

    assert (await harness.readiness()).checklist["catalog_verified"] is ready


async def test_matching_image_and_search_markers_and_truncation(harness: Harness) -> None:
    harness.imports = [imported(1, catalog=CATALOG_B)]
    harness.image_failures = 101
    harness.image_rows = [Product(source_product_id=str(i), title="Image") for i in range(101)]

    result = await harness.readiness()

    assert result.checklist["images_reviewed"] and result.checklist["search_tested"]
    assert result.image_failures == 101 and len(result.image_issues) == 100
    assert result.image_issues_truncated
    assert harness.session.scalars.call_args.args[0].compile().params["param_1"] == 100
