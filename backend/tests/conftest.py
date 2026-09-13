"""Shared fixtures.

Every test gets its own store, so nothing leaks between tests. The store is
swapped in through FastAPI's dependency override rather than by reaching into
module state — the same seam a real database will arrive on.

`client` is signed in; `anonymous_client` is not. Signing in mints a token
directly rather than posting a password, because scrypt is deliberately slow and
these hundred-odd tests are not testing the password path — `test_auth.py` is,
through the real endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.dependencies import get_store
from app.main import app
from app.models import User
from app.store import InMemoryStore

DEMO_PASSWORD = "nextlane"


@pytest.fixture(scope="session")
def demo_user() -> User:
    """Hashed once for the whole session — scrypt costs real milliseconds."""
    return auth.build_demo_user()


@pytest.fixture
def store(demo_user: User) -> InMemoryStore:
    """An empty mock database with one account in it."""
    return InMemoryStore(users=[demo_user])


@pytest.fixture
def seeded_store() -> InMemoryStore:
    """The development fixtures from _docs/specs.md §31, plus the demo account."""
    return InMemoryStore.seeded()


def _client(store: InMemoryStore) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


@pytest.fixture
def anonymous_client(store: InMemoryStore) -> TestClient:
    with _client(store) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(store: InMemoryStore, demo_user: User) -> TestClient:
    with _client(store) as test_client:
        token, _ = auth.issue_token(store, demo_user)
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_client(seeded_store: InMemoryStore) -> TestClient:
    with _client(seeded_store) as test_client:
        user = seeded_store.get_user_by_email("researcher@example.com")
        token, _ = auth.issue_token(seeded_store, user)
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


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
