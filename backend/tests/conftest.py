"""Shared fixtures.

Every test gets its own store, so nothing leaks between tests. The store is
swapped in through FastAPI's dependency override rather than by reaching into
module state — the same seam a real database will arrive on.

`client` is signed in; `anonymous_client` is not. Signing in mints a token
directly rather than posting a password, because scrypt is deliberately slow and
these hundred-odd tests are not testing the password path — `test_auth.py` is,
through the real endpoint.

**Postgres needs a server**, so the fixtures at the bottom skip unless one is
configured:

    NEXTLANE_TEST_POSTGRES=postgresql://postgres:nextlane@localhost/nextlane_test

Point it at a throwaway database — every test empties the NextLane tables before
it runs. CI sets it against a `postgres:16-alpine` service container.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.dependencies import get_store
from app.main import app
from app.models import User
from app.sqlite_store import SqliteStore
from app.store import InMemoryStore, Store

DEMO_PASSWORD = "nextlane"

POSTGRES_DSN = os.environ.get("NEXTLANE_TEST_POSTGRES", "").strip()

NO_POSTGRES = (
    "NEXTLANE_TEST_POSTGRES is not set. Point it at a throwaway database to run "
    "the contract against Postgres too — see backend/README.md."
)

#: Emptied between tests. Listed rather than discovered from the catalogue, so
#: this can only ever truncate NextLane's own tables — a suite pointed at the
#: wrong database should fail, not wipe it.
POSTGRES_TABLES = (
    "card_tags",
    "subtasks",
    "job_requirements",
    "learning_job_links",
    "job_learning_links",
    "job_details",
    "cards",
    "preferences",
    "users",
    "tokens",
)


@pytest.fixture(scope="session")
def demo_user() -> User:
    """Hashed once for the whole session — scrypt costs real milliseconds."""
    return auth.build_demo_user()


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path, demo_user: User) -> Store:
    """Every endpoint test runs twice: against the dict, and against SQLite.

    Issue #19 replaced the in-memory store with a real database. The promise of
    the `Store` protocol is that nothing above it can tell which one it has, and
    the only way to keep that promise honest is to run the API against both.
    """
    store = InMemoryStore() if request.param == "memory" else SqliteStore(tmp_path / "api.sqlite3")
    store.save_user(demo_user)
    return store


@pytest.fixture(params=["memory", "sqlite"])
def seeded_store(request, tmp_path) -> Store:
    """The development fixtures from _docs/specs.md §31, plus the demo account."""
    store = (
        InMemoryStore() if request.param == "memory" else SqliteStore(tmp_path / "seeded.sqlite3")
    )
    store.seed()
    return store


def _client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def anonymous_client(store: Store) -> TestClient:
    with _client(store) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(store: Store, demo_user: User) -> TestClient:
    with _client(store) as test_client:
        token, _ = auth.issue_token(store, demo_user)
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_client(seeded_store: Store) -> TestClient:
    with _client(seeded_store) as test_client:
        user = seeded_store.get_user_by_email("researcher@example.com")
        token, _ = auth.issue_token(seeded_store, user)
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def postgres():
    """One `PostgresStore` for the session — opening a pool per test is waste."""
    if not POSTGRES_DSN:
        pytest.skip(NO_POSTGRES)

    from app.postgres_store import PostgresStore

    store = PostgresStore(POSTGRES_DSN)  # also creates the schema
    yield store
    store.close()


@pytest.fixture
def empty_postgres(postgres):
    """That store, emptied. The schema exists by the time this runs."""
    import psycopg

    with psycopg.connect(POSTGRES_DSN) as connection, connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE {', '.join(POSTGRES_TABLES)} CASCADE")
    return postgres


def make_card(client: TestClient, **overrides) -> dict:
    """Create a card and return it. Defaults to the simplest valid payload."""
    payload = {"title": "A task", "area": "CURRENT_JOB"}
    payload.update(overrides)
    response = client.post("/api/cards", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def make_job(client: TestClient, **job_fields) -> dict:
    job = {"company": "Anthropic", "role": "Research Engineer"}
    job.update(job_fields)
    return make_card(client, title="Anthropic — Research Engineer", area="JOB_SEARCH", job=job)


def make_learning(client: TestClient, title: str = "System design") -> dict:
    return make_card(client, title=title, area="LEARNING")
