"""Inject one failed replacement-index state in an isolated browser test only."""

import argparse
import asyncio
import json
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.catalog_import import CatalogImportRecord
from open_commerce.persistence.models.search import CatalogIndexJob
from open_commerce.persistence.models.store_setup import StoreSetupRecord
from open_commerce.persistence.runtime_db import RuntimeDatabase
from tests.integration.merchant_browser_fixture import validate_fixture_environment


async def fail_replacement(database: RuntimeDatabase, tenant: UUID, catalog: UUID) -> None:
    async with database.transaction(tenant, write=True) as session:
        store = await session.scalar(
            select(StoreSetupRecord).where(StoreSetupRecord.tenant_id == tenant)
        )
        confirmed = await session.scalar(
            select(CatalogImportRecord.id)
            .where(
                CatalogImportRecord.tenant_id == tenant,
                CatalogImportRecord.catalog_id == catalog,
                CatalogImportRecord.status == "confirmed",
            )
            .limit(1)
        )
        job = await session.scalar(
            select(CatalogIndexJob).where(
                CatalogIndexJob.tenant_id == tenant,
                CatalogIndexJob.integration_id == catalog,
            )
        )
        if (
            store is None
            or store.published_catalog_id == catalog
            or confirmed is None
            or job is None
            or job.status not in {"ready", "failed"}
            or job.lease_token is not None
            or job.lease_until is not None
        ):
            raise RuntimeError(
                "Only an idle, confirmed, unpublished fixture replacement is eligible."
            )
        job.status = "failed"
        job.failures = 100
        job.safe_error = {"code": "synthetic_browser_retry_fixture"}
        job.available_at = utc_now() + timedelta(days=1)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", type=UUID, required=True)
    parser.add_argument("--catalog", type=UUID, required=True)
    args = parser.parse_args()
    settings = Settings(_env_file=None)
    validate_fixture_environment(settings)
    database = RuntimeDatabase(settings)
    try:
        await fail_replacement(database, args.tenant, args.catalog)
        print(json.dumps({"injected": "synthetic_browser_retry_fixture"}))
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
