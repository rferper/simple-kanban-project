"""Authentication: hashed passwords, bearer tokens, and what they gate.

NextLane holds someone's job search — which roles they want, what rejected them,
what they are quietly learning in order to leave. These tests are about keeping
that shut.
"""

import pytest

from app import auth
from app.models import User
from tests.conftest import DEMO_PASSWORD

PROTECTED_CALLS = [
    ("get", "/api/cards"),
    ("post", "/api/cards"),
    ("get", "/api/cards/seed-slides"),
    ("patch", "/api/cards/seed-slides"),
    ("delete", "/api/cards/seed-slides"),
    ("patch", "/api/cards/seed-slides/job"),
    ("put", "/api/learning/a/jobs/b"),
    ("delete", "/api/learning/a/jobs/b"),
    ("get", "/api/preferences"),
    ("patch", "/api/preferences"),
    ("post", "/api/ai/extract-job-advert"),
    ("get", "/api/auth/me"),
    ("post", "/api/auth/logout"),
]


class TestPasswordHashing:
    def test_the_password_is_not_stored(self, demo_user: User):
        assert DEMO_PASSWORD not in demo_user.password_hash

    def test_the_hash_names_its_scheme(self, demo_user: User):
        assert demo_user.password_hash.startswith("scrypt$")

    def test_the_right_password_verifies(self, demo_user: User):
        assert auth.verify_password(DEMO_PASSWORD, demo_user.password_hash)

    def test_the_wrong_password_does_not(self, demo_user: User):
        assert not auth.verify_password("nextlane ", demo_user.password_hash)
        assert not auth.verify_password("NEXTLANE", demo_user.password_hash)
        assert not auth.verify_password("", demo_user.password_hash)

    def test_the_same_password_hashes_differently_every_time(self):
        """A per-password salt: identical passwords must not collide in the store."""
        assert auth.hash_password("same") != auth.hash_password("same")

    def test_both_of_those_still_verify(self):
        password = "same"
        assert auth.verify_password(password, auth.hash_password(password))
        assert auth.verify_password(password, auth.hash_password(password))

    def test_an_empty_password_cannot_be_hashed(self):
        with pytest.raises(ValueError):
            auth.hash_password("")

    def test_a_malformed_hash_fails_rather_than_explodes(self):
        for rubbish in ["", "nonsense", "scrypt$only-one-part", "md5$aa$bb", "scrypt$zz$zz"]:
            assert auth.verify_password("anything", rubbish) is False


class TestLogin:
    def test_correct_details_return_a_token(self, anonymous_client, demo_user: User):
        response = anonymous_client.post(
            "/api/auth/login",
            json={"email": demo_user.email, "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token"]
        assert body["expiresAt"]
        assert body["user"]["email"] == demo_user.email

    def test_the_response_never_carries_the_hash(self, anonymous_client, demo_user: User):
        response = anonymous_client.post(
            "/api/auth/login",
            json={"email": demo_user.email, "password": DEMO_PASSWORD},
        )
        assert "passwordHash" not in response.text
        assert "password_hash" not in response.text

    def test_the_email_is_case_insensitive(self, anonymous_client, demo_user: User):
        response = anonymous_client.post(
            "/api/auth/login",
            json={"email": demo_user.email.upper(), "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200

    def test_a_wrong_password_is_401(self, anonymous_client, demo_user: User):
        response = anonymous_client.post(
            "/api/auth/login", json={"email": demo_user.email, "password": "wrong"}
        )
        assert response.status_code == 401

    def test_an_unknown_email_is_401(self, anonymous_client):
        response = anonymous_client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": DEMO_PASSWORD}
        )
        assert response.status_code == 401

    def test_the_two_failures_are_indistinguishable(self, anonymous_client, demo_user: User):
        """Otherwise this endpoint tells an attacker which addresses have accounts."""
        wrong_password = anonymous_client.post(
            "/api/auth/login", json={"email": demo_user.email, "password": "wrong"}
        )
        unknown_email = anonymous_client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )
        assert wrong_password.status_code == unknown_email.status_code
        assert wrong_password.json() == unknown_email.json()

    def test_a_401_says_how_to_authenticate(self, anonymous_client):
        response = anonymous_client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "x"}
        )
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_a_missing_password_is_422_not_401(self, anonymous_client, demo_user: User):
        response = anonymous_client.post("/api/auth/login", json={"email": demo_user.email})
        assert response.status_code == 422

    def test_a_nonsense_email_is_422(self, anonymous_client):
        response = anonymous_client.post(
            "/api/auth/login", json={"email": "not-an-email", "password": "x"}
        )
        assert response.status_code == 422

    def test_login_itself_needs_no_token(self, anonymous_client, demo_user: User):
        response = anonymous_client.post(
            "/api/auth/login", json={"email": demo_user.email, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200


class TestProtectedEndpoints:
    @pytest.mark.parametrize("method,path", PROTECTED_CALLS)
    def test_no_token_is_401(self, anonymous_client, method, path):
        response = anonymous_client.request(method, path, json={})
        assert response.status_code == 401, f"{method.upper()} {path} was not protected"

    @pytest.mark.parametrize("method,path", PROTECTED_CALLS)
    def test_a_made_up_token_is_401(self, anonymous_client, method, path):
        anonymous_client.headers["Authorization"] = "Bearer not-a-real-token"
        response = anonymous_client.request(method, path, json={})
        assert response.status_code == 401

    def test_a_401_carries_a_readable_message(self, anonymous_client):
        body = anonymous_client.get("/api/cards").json()
        assert body["message"]
        assert body["kind"] == "unauthorized"

    def test_the_wrong_scheme_is_401(self, anonymous_client, store, demo_user: User):
        token, _ = auth.issue_token(store, demo_user)
        anonymous_client.headers["Authorization"] = f"Basic {token}"
        assert anonymous_client.get("/api/cards").status_code == 401

    def test_an_empty_bearer_is_401(self, anonymous_client):
        anonymous_client.headers["Authorization"] = "Bearer "
        assert anonymous_client.get("/api/cards").status_code == 401

    def test_a_valid_token_gets_through(self, client):
        assert client.get("/api/cards").status_code == 200

    def test_a_token_for_a_deleted_user_is_401(self, anonymous_client, store, demo_user: User):
        token, _ = auth.issue_token(store, demo_user)
        store._users.clear()
        anonymous_client.headers["Authorization"] = f"Bearer {token}"
        assert anonymous_client.get("/api/cards").status_code == 401


class TestTokenLifetime:
    def test_an_expired_token_is_401(self, anonymous_client, store, demo_user: User):
        from datetime import timedelta

        from app.domain import now

        token = "expired-token"
        store.save_token(token, demo_user.id, now() - timedelta(seconds=1))
        anonymous_client.headers["Authorization"] = f"Bearer {token}"

        assert anonymous_client.get("/api/cards").status_code == 401

    def test_an_expired_token_is_cleaned_up(self, anonymous_client, store, demo_user: User):
        from datetime import timedelta

        from app.domain import now

        token = "expired-token"
        store.save_token(token, demo_user.id, now() - timedelta(seconds=1))
        anonymous_client.headers["Authorization"] = f"Bearer {token}"
        anonymous_client.get("/api/cards")

        assert store.get_token(token) is None

    def test_tokens_are_long_and_unguessable(self, store, demo_user: User):
        first, _ = auth.issue_token(store, demo_user)
        second, _ = auth.issue_token(store, demo_user)
        assert first != second
        assert len(first) >= 32

    def test_a_token_expires_in_the_future(self, store, demo_user: User):
        from app.domain import now

        _, expires_at = auth.issue_token(store, demo_user)
        assert expires_at > now()


class TestMe:
    def test_returns_the_signed_in_user(self, client, demo_user: User):
        body = client.get("/api/auth/me").json()
        assert body["email"] == demo_user.email
        assert body["id"] == demo_user.id

    def test_never_returns_the_hash(self, client):
        assert "passwordHash" not in client.get("/api/auth/me").text


class TestLogout:
    def test_logging_out_revokes_the_token(self, client):
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/cards").status_code == 401

    def test_the_token_is_gone_from_the_store(self, client, store):
        token = client.headers["Authorization"].removeprefix("Bearer ")
        client.post("/api/auth/logout")
        assert store.get_token(token) is None

    def test_logging_out_twice_is_401_the_second_time(self, client):
        client.post("/api/auth/logout")
        assert client.post("/api/auth/logout").status_code == 401

    def test_other_sessions_survive(self, client, store, demo_user: User):
        """Signing out of a laptop must not sign you out of a phone."""
        other_token, _ = auth.issue_token(store, demo_user)
        client.post("/api/auth/logout")
        assert store.get_token(other_token) is not None


class TestWhatAuthenticationIsNot:
    def test_the_workspace_is_shared_not_per_user(self, client, store, demo_user: User):
        """§33 rules out multi-user collaboration and §26 says the first user is
        the developer. Authentication decides who may open the workspace; it does
        not partition the data. This test records that, so a future change to
        per-user data is a deliberate one rather than a surprise."""
        from tests.conftest import make_card

        card = make_card(client, title="Only I can see this")

        second = auth.build_demo_user().model_copy(update={"id": "user-second"})
        store.save_user(second)
        token, _ = auth.issue_token(store, second)
        client.headers["Authorization"] = f"Bearer {token}"

        visible = [c["id"] for c in client.get("/api/cards").json()]
        assert card["id"] in visible
