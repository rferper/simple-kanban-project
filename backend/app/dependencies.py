"""Wiring.

`get_store` is the seam. It opens one store, once, shares it with every request,
and the tests override it with whichever implementation they want. Nothing else
in the application reaches for storage.

One setting chooses the database, and its shape chooses the implementation:

    NEXTLANE_DB=/some/path/nextlane.sqlite3      a file — SQLite (the default)
    NEXTLANE_DB=:memory:                         RAM, for this process only
    NEXTLANE_DB=postgresql://user:pw@host/db     a server — Postgres

It defaults to `nextlane.sqlite3` beside the backend package, and whichever
database it opens is seeded with the `_docs/specs.md` §31 fixtures the first
time it is empty — so a fresh clone has something to show, and an existing
database is never overwritten.

A DSN rather than a second setting, because "where the data is" is one decision.
Two settings would let them disagree, and something would have to decide which
one wins.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.sqlite_store import SqliteStore
from app.store import InMemoryStore, Store

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "nextlane.sqlite3"

#: The schemes libpq answers to. `postgres://` is the older spelling and is
#: what most hosting providers still hand out, so both are accepted.
POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def database_path() -> str:
    return os.environ.get("NEXTLANE_DB") or str(DEFAULT_DB_PATH)


def is_postgres(setting: str) -> bool:
    return setting.startswith(POSTGRES_SCHEMES)


def build_store(setting: str) -> Store:
    """The one place that turns the setting into an implementation."""
    # ":memory:" is a useful escape hatch for a throwaway run, and the only
    # case where the in-memory implementation is what you actually want.
    if setting == ":memory:":
        return InMemoryStore()

    if is_postgres(setting):
        # Imported here rather than at module scope so that a SQLite
        # installation never has to load psycopg or its libpq to start.
        from app.postgres_store import PostgresStore

        return PostgresStore(setting)

    return SqliteStore(setting)


@lru_cache(maxsize=1)
def _singleton() -> Store:
    store = build_store(database_path())
    store.seed()
    return store


def get_store() -> Store:
    return _singleton()


def reset_store_cache() -> None:
    """Drop the cached store so the next call opens a fresh one. Tests only."""
    _singleton.cache_clear()
