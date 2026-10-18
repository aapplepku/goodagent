"""Console-only owner bootstrap and recovery; never exposed as an HTTP operation."""

import argparse
import asyncio
import base64
import secrets

from sqlalchemy import select, update

from open_commerce.config import Settings
from open_commerce.core.types import utc_now
from open_commerce.persistence.models.store_setup import (
    MerchantCredentialRecord,
    MerchantSessionRecord,
)
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.shopper_agent.auth import session_token_hash
from open_commerce.stores.auth import MerchantAuthService
from open_commerce.stores.models import StoreError


async def run(command: str, username: str | None) -> None:
    if command == "encryption-key":
        print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        return
    database = RuntimeDatabase(Settings())
    try:
        if database.settings.runtime_profile != "self_hosted":
            raise StoreError("Console owner operations require the self-hosted profile.")
        if command == "bootstrap":
            print(await MerchantAuthService(database).issue_bootstrap())
            return
        if not username:
            raise StoreError("Recovery requires --username.")
        # Console authority is instance-wide. Resolve identity, then scope session revocation.
        async with database.sessions() as session, session.begin():
            record = await session.scalar(
                select(MerchantCredentialRecord)
                .where(MerchantCredentialRecord.username == username.lower())
                .with_for_update()
            )
            if record is None:
                raise StoreError("Owner not found.")
            store = await MerchantAuthService(database)._owned_profile(session, record.user_id)
            recovery = secrets.token_urlsafe(32)
            record.recovery_hash = session_token_hash(recovery)
            await session.execute(
                update(MerchantSessionRecord)
                .where(
                    MerchantSessionRecord.tenant_id == store.id,
                    MerchantSessionRecord.user_id == record.user_id,
                )
                .values(revoked_at=utc_now())
            )
        print(recovery)
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "recover", "encryption-key"])
    parser.add_argument("--username")
    arguments = parser.parse_args()
    try:
        asyncio.run(run(arguments.command, arguments.username))
    except StoreError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
