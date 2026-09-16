"""Wiring.

`get_store` is the seam. It opens one store, once, shares it with every request,
and the tests override it with whichever implementation they want. Nothing else
in the application reaches for storage.

One setting chooses the database, and its shape chooses the implementation:

    NEXTLANE_DB=postgresql://user:pw@host/db     a server — Postgres (the default)
    NEXTLANE_DB=/some/path/nextlane.sqlite3      a file — SQLite
    NEXTLANE_DB=:memory:                         RAM, for this process only

**Postgres is what this runs on** (`_docs/decisions.md` #26). Unset, it looks
for the local development server that `make postgres` starts — so `make
postgres` once, then `make run`, and every way of starting the app is looking at
the same board.

SQLite is the fallback, not the normal case: it is there for a machine with no
Docker, and it stays a first-class implementation of the `Store` protocol so the
seam keeps being tested rather than assumed. Point `NEXTLANE_DB` at a path and
you have it.

A DSN rather than a second setting, because "where the data is" is one decision.
Two settings would let them disagree, and something would have to decide which
one wins — which is exactly how a board full of work ends up invisible.
"""

from __future__ import annotations

import os
from functools import lru_cache

from app.sqlite_store import SqliteStore
from app.store import InMemoryStore, Store

#: The local development server, which is the `db` service in
#: `docker-compose.yaml` — the same one the container talks to, so `make run`
#: and `docker compose up` show the same board. `make postgres` starts it. Not
#: 5432, so it cannot collide with a Postgres already running on this machine.
DEFAULT_DB = "postgresql://nextlane:nextlane@localhost:55432/nextlane"

#: The schemes libpq answers to. `postgres://` is the older spelling and is
#: what most hosting providers still hand out, so both are accepted.
POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def database_path() -> str:
    return os.environ.get("NEXTLANE_DB") or DEFAULT_DB


def is_postgres(setting: str) -> bool:
    return setting.startswith(POSTGRES_SCHEMES)


def build_store(setting: str) -> Store:
    """The one place that turns the setting into an implementation."""
    # ":memory:" is a useful escape hatch for a throwaway run, and the only
    # case where the in-memory implementation is what you actually want.
    if setting == ":memory:":
        return InMemoryStore()

    if is_postgres(setting):
        # Imported here rather than at module scope so a SQLite installation
        # never has to load psycopg or its libpq to start.
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
