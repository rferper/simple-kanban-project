"""One setting chooses the database, and its shape chooses the implementation.

`NEXTLANE_DB` is a path, or `:memory:`, or a Postgres DSN. Getting that wrong is
the kind of mistake that looks like it worked — a server DSN quietly opened as a
SQLite filename would create a file called `postgresql:` and serve an empty
board — so the routing is tested rather than assumed.
"""

import pytest

from app.dependencies import (
    DEFAULT_DB_PATH,
    build_store,
    database_path,
    is_postgres,
)
from app.postgres_store import safe_dsn
from app.sqlite_store import SqliteStore
from app.store import InMemoryStore
from tests.conftest import POSTGRES_DSN


class TestWhichDatabase:
    def test_a_path_is_sqlite(self, tmp_path):
        assert isinstance(build_store(str(tmp_path / "nextlane.sqlite3")), SqliteStore)

    def test_memory_is_the_dict(self):
        assert isinstance(build_store(":memory:"), InMemoryStore)

    @pytest.mark.parametrize(
        "dsn",
        [
            "postgresql://user:pw@localhost/nextlane",
            "postgres://user:pw@localhost/nextlane",  # the older spelling
            "postgresql://localhost/nextlane",
        ],
    )
    def test_a_dsn_is_postgres(self, dsn):
        assert is_postgres(dsn)

    @pytest.mark.parametrize(
        "setting",
        [
            ":memory:",
            "/var/lib/nextlane/nextlane.sqlite3",
            "nextlane.sqlite3",
            # Windows. A drive letter is not a URL scheme, and this is the one
            # that would be easy to get wrong.
            r"C:\Users\someone\nextlane.sqlite3",
        ],
    )
    def test_everything_else_is_not(self, setting):
        assert not is_postgres(setting)

    @pytest.mark.skipif(not POSTGRES_DSN, reason="NEXTLANE_TEST_POSTGRES is not set")
    def test_a_dsn_really_opens_postgres(self):
        from app.postgres_store import PostgresStore

        store = build_store(POSTGRES_DSN)
        try:
            assert isinstance(store, PostgresStore)
        finally:
            store.close()


class TestWhereItLooks:
    def test_it_defaults_to_the_file_beside_the_package(self, monkeypatch):
        monkeypatch.delenv("NEXTLANE_DB", raising=False)
        assert database_path() == str(DEFAULT_DB_PATH)

    def test_the_setting_wins(self, monkeypatch):
        monkeypatch.setenv("NEXTLANE_DB", "postgresql://user:pw@localhost/nextlane")
        assert database_path() == "postgresql://user:pw@localhost/nextlane"

    def test_an_empty_setting_is_the_default(self, monkeypatch):
        """An unset variable and one set to nothing mean the same thing."""
        monkeypatch.setenv("NEXTLANE_DB", "")
        assert database_path() == str(DEFAULT_DB_PATH)


@pytest.mark.skipif(not POSTGRES_DSN, reason="NEXTLANE_TEST_POSTGRES is not set")
class TestTheApiOnPostgres:
    """`tests/test_store.py` proves the contract; this proves the wiring.

    The whole API suite is parametrised over the dict and SQLite and not over
    this, because the store contract is what guarantees the three are
    interchangeable and tripling a hundred endpoint tests buys little for the
    minutes it costs. What it does not cover is that a real request, through
    `get_store`, reaches a real server — so that is what this is.
    """

    @pytest.fixture
    def client(self, empty_postgres):
        from fastapi.testclient import TestClient

        from app import auth
        from app.dependencies import get_store
        from app.main import app

        empty_postgres.seed()
        app.dependency_overrides[get_store] = lambda: empty_postgres
        with TestClient(app) as test_client:
            user = empty_postgres.get_user_by_email("researcher@example.com")
            token, _ = auth.issue_token(empty_postgres, user)
            test_client.headers["Authorization"] = f"Bearer {token}"
            yield test_client
        app.dependency_overrides.clear()

    def test_the_seeded_board_is_served(self, client):
        cards = client.get("/api/cards").json()
        assert len(cards) == 12

    def test_a_card_can_be_created_and_read_back(self, client):
        created = client.post(
            "/api/cards", json={"title": "Written to Postgres", "area": "LEARNING"}
        )
        assert created.status_code == 201

        card_id = created.json()["id"]
        assert client.get(f"/api/cards/{card_id}").json()["title"] == "Written to Postgres"

    def test_a_card_can_be_moved_and_deleted(self, client):
        card_id = client.post("/api/cards", json={"title": "x", "area": "LEARNING"}).json()["id"]

        moved = client.patch(f"/api/cards/{card_id}", json={"status": "LEARNING"})
        assert moved.status_code == 200, moved.text

        assert client.delete(f"/api/cards/{card_id}").status_code == 204
        assert client.get(f"/api/cards/{card_id}").status_code == 404

    def test_signing_in_works_against_it(self, client):
        """The password path, not a minted token — scrypt and the users table."""
        client.headers.pop("Authorization")
        response = client.post(
            "/api/auth/login",
            json={"email": "researcher@example.com", "password": "nextlane"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["token"]


class TestTheDsnInMessages:
    """A connection string is the one setting that routinely carries a secret."""

    def test_the_password_is_hidden(self):
        hidden = safe_dsn("postgresql://nextlane:hunter2@db.example.com:5432/nextlane")
        assert "hunter2" not in hidden
        assert "nextlane:***@db.example.com:5432/nextlane" in hidden

    def test_the_rest_survives_so_it_is_still_useful(self):
        hidden = safe_dsn("postgresql://nextlane:hunter2@db.example.com:5432/nextlane")
        assert hidden.startswith("postgresql://")
        assert hidden.endswith("/nextlane")

    def test_a_dsn_with_no_password_is_left_alone(self):
        assert (
            safe_dsn("postgresql://nextlane@localhost/db") == "postgresql://nextlane@localhost/db"
        )

    def test_a_path_is_left_alone(self):
        assert (
            safe_dsn("/var/lib/nextlane/nextlane.sqlite3") == "/var/lib/nextlane/nextlane.sqlite3"
        )
