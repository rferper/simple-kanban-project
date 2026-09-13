"""Wiring.

`get_store` is the seam. Today it hands out one process-wide
`InMemoryStore`; tomorrow it opens a database session. Tests override it
per test, which is why nothing else in the app reaches for storage directly.
"""

from __future__ import annotations

from functools import lru_cache

from app.store import InMemoryStore, Store


@lru_cache(maxsize=1)
def _singleton() -> InMemoryStore:
    """The mock database, seeded so a fresh server has something to show."""
    return InMemoryStore.seeded()


def get_store() -> Store:
    return _singleton()
