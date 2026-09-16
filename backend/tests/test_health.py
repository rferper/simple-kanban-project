"""`GET /api/health`.

The endpoint a deploy believes. Most of these are about it being willing to say
no: a health check that cannot fail is a green light wired to nothing.
"""

import pytest

from app.dependencies import get_store
from app.main import app
from app.store import InMemoryStore


class Unreachable(InMemoryStore):
    """A store whose database has gone away underneath it."""

    def get_preferences(self):
        raise RuntimeError("connection refused")


@pytest.fixture
def broken_client(anonymous_client):
    app.dependency_overrides[get_store] = Unreachable
    yield anonymous_client
    app.dependency_overrides.clear()


class TestWhenItIsWell:
    def test_it_answers_without_a_token(self, anonymous_client):
        """A load balancer cannot hold one."""
        assert anonymous_client.get("/api/health").status_code == 200

    def test_it_says_it_is_serving(self, anonymous_client):
        body = anonymous_client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"

    def test_it_still_answers_when_signed_in(self, client):
        assert client.get("/api/health").status_code == 200


class TestWhenItIsNot:
    """The half that matters. If this cannot go red, nothing downstream works."""

    def test_a_dead_database_is_a_503(self, broken_client):
        """503 rather than 500: the difference between "take me out of the pool"
        and "something threw"."""
        assert broken_client.get("/api/health").status_code == 503

    def test_and_it_says_which_half_is_broken(self, broken_client):
        body = broken_client.get("/api/health").json()
        assert body["status"] == "degraded"
        assert body["database"] == "unreachable"

    def test_the_web_server_being_up_is_not_enough(self, broken_client):
        """The process is the easy half. A check that only proved this much
        would report green while every request 500s."""
        assert broken_client.get("/api/health").status_code != 200


class TestItGivesNothingAway:
    """It is reachable by anyone, so it carries nothing worth protecting."""

    def test_it_is_two_words(self, seeded_client):
        body = seeded_client.get("/api/health").json()
        assert set(body) == {"status", "database"}

    def test_it_leaks_no_card_data(self, seeded_client):
        from tests.conftest import make_card

        make_card(seeded_client, title="Confidential rebuttal")
        assert "Confidential rebuttal" not in seeded_client.get("/api/health").text

    def test_it_leaks_no_account(self, seeded_client):
        assert "researcher@example.com" not in seeded_client.get("/api/health").text

    def test_it_leaks_no_connection_string(self, broken_client):
        """The failure path is where a DSN usually escapes — into the message
        of the exception that caused it."""
        body = broken_client.get("/api/health").text
        assert "postgresql://" not in body
        assert "connection refused" not in body

    def test_everything_else_is_still_closed(self, anonymous_client):
        """Adding a public endpoint must not have opened anything else."""
        for path in ["/api/cards", "/api/preferences", "/api/auth/me"]:
            assert anonymous_client.get(path).status_code == 401, path
