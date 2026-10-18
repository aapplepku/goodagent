"""Real-service tests may not silently substitute local SQLite persistence."""

import sqlite3

import pytest


@pytest.fixture(autouse=True)
def forbid_sqlite_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("real-service integration must not open SQLite")

    monkeypatch.setattr(sqlite3, "connect", reject)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", reject)
