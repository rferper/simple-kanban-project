"""`GET /` — issue #23.

The endpoint exists because a bare "Not Found" is a dead end for anyone who
opens the API in a browser. It is public, which is the whole point, so most of
these tests are about it being public *and* boring.
"""


class TestTheRoot:
    def test_it_answers_without_a_token(self, anonymous_client):
        """Public. Being told to authenticate before you know to what is the
        dead end this replaces."""
        assert anonymous_client.get("/").status_code == 200

    def test_it_says_what_this_is(self, anonymous_client):
        body = anonymous_client.get("/").json()
        assert body["name"] == "NextLane API"
        assert body["version"]
        assert "Kanban" in body["description"]

    def test_it_points_at_the_docs_and_the_app(self, anonymous_client):
        body = anonymous_client.get("/").json()
        assert body["docs"] == "/docs"
        assert body["openapi"] == "/openapi.json"
        assert body["app"]

    def test_the_paths_it_points_at_are_real(self, anonymous_client):
        body = anonymous_client.get("/").json()
        assert anonymous_client.get(body["docs"]).status_code == 200
        assert anonymous_client.get(body["openapi"]).status_code == 200

    def test_it_still_answers_when_signed_in(self, client):
        assert client.get("/").status_code == 200


class TestItGivesNothingAway:
    """It is reachable by anyone, so it must carry nothing worth protecting."""

    def test_it_leaks_no_card_data(self, seeded_client):
        from tests.conftest import make_card

        make_card(seeded_client, title="Confidential rebuttal")
        body = seeded_client.get("/").text
        assert "Confidential rebuttal" not in body

    def test_it_leaks_no_account(self, seeded_client):
        assert "researcher@example.com" not in seeded_client.get("/").text

    def test_it_leaks_no_counts(self, seeded_client):
        """Not even "12 cards" - that is a fact about someone's job search."""
        body = seeded_client.get("/").json()
        assert set(body) == {"name", "version", "description", "docs", "openapi", "app"}

    def test_everything_else_is_still_closed(self, anonymous_client):
        """Adding a public endpoint must not have opened anything else."""
        for path in ["/api/cards", "/api/preferences", "/api/auth/me"]:
            assert anonymous_client.get(path).status_code == 401, path


class TestTheOldDeadEnd:
    def test_an_unknown_path_is_still_an_honest_404(self, anonymous_client):
        response = anonymous_client.get("/not-a-real-path")
        assert response.status_code == 404
        assert response.json()["message"]
