"""SQLAlchemy engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from open_commerce.config import Settings


class Base(DeclarativeBase):
    """Base class for future ORM models."""


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the application async SQLAlchemy engine."""

    return create_async_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory."""

    return async_sessionmaker(create_engine(settings), expire_on_commit=False)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped session."""

    async with session_factory() as session:
        async with session.begin():
            yield session
