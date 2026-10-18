"""Run inside a built Python image to verify remote-only storage construction."""

import asyncio
from unittest.mock import patch

from qdrant_client.async_qdrant_remote import AsyncQdrantRemote

from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.search.durable import DurableSearchService


async def main() -> None:
    with (
        patch("sqlite3.connect", side_effect=AssertionError("SQLite is not runtime persistence")),
        patch(
            "sqlite3.dbapi2.connect",
            side_effect=AssertionError("SQLite is not runtime persistence"),
        ),
    ):
        database = RuntimeDatabase(Settings(qdrant_url="http://qdrant:6333"))
        search = DurableSearchService(database)
        try:
            async with database.sessions() as session:
                assert session.bind is not None and session.bind.dialect.name == "postgresql"
            assert isinstance(search.client._client, AsyncQdrantRemote)
        finally:
            await search.close()
            await database.close()
    print("postgresql-and-remote-qdrant; no SQLite connections")


if __name__ == "__main__":
    asyncio.run(main())
