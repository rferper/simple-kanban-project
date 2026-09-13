"""Wiring.

`get_store` is the seam. It hands out a `SqliteStore` — one connection, opened
once, shared by every request — and the tests override it with whichever
implementation they want. Nothing else in the application reaches for storage.

Where the database lives:

    NEXTLANE_DB=/some/path/nextlane.sqlite3   # anywhere you like
    NEXTLANE_DB=:memory:                      # keep it in RAM for this process

It defaults to `nextlane.sqlite3` beside the backend package, and is seeded with
the `_docs/specs.md` §31 fixtures the first time it is created — so a fresh
clone has something to show, and an existing database is never overwritten.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.sqlite_store import SqliteStore
from app.store import InMemoryStore, Store

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "nextlane.sqlite3"


def database_path() -> str:
    return os.environ.get("NEXTLANE_DB") or str(DEFAULT_DB_PATH)


@lru_cache(maxsize=1)
def _singleton() -> Store:
    path = database_path()

    # ":memory:" is a useful escape hatch for a throwaway run, and the only
    # case where the in-memory implementation is what you actually want.
    store: Store = InMemoryStore() if path == ":memory:" else SqliteStore(path)
    store.seed()
    return store


def get_store() -> Store:
    return _singleton()


def reset_store_cache() -> None:
    """Drop the cached store so the next call opens a fresh one. Tests only."""
    _singleton.cache_clear()
