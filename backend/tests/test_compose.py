"""The stack in `docker-compose.yaml`, actually running.

Five hundred other tests run the application in-process, against a store handed
to it by a fixture. They cannot fail for any of the reasons this file exists to
catch, because none of them involve an image, a network or a second container:

* the image builds, starts, and the frontend is really inside it;
* the app finds Postgres at `db:5432` and waits for it to be healthy first;
* the database is reachable from the host on the published port, and it is the
  **same** database the app is using (`_docs/decisions.md` #26 — the arrangement
  that replaced two servers, one of which was always the wrong one);
* a board survives restarting the app and recreating the containers;
* a fresh volume seeds exactly once.

So the rule for what belongs here: **only what needs the containers.** A
business rule — which statuses a Learning card may hold, what `completedAt` does
— is `tests/test_cards.py`'s job and is not repeated here at thirty seconds a
run.

**These never touch the development stack.** They run under their own compose
project on their own ports and their own volume, and the teardown that deletes
that volume asserts the project name first. Losing a board to a test suite would
be a poor way to find out the isolation was wrong.

    make test-integration

They are marked `integration` and deselected from `make test`, because they need
Docker and take about a minute.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import psycopg
import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]

#: Never "nextlane". That is the development stack, and the teardown here
#: deletes volumes.
PROJECT = "nextlane-it"

#: Deliberately not 8000 and 55432, so a running development stack and a test
#: run cannot fight over a port or be mistaken for one another.
APP_PORT = 18000
DB_PORT = 15432

DEMO = {"email": "researcher@example.com", "password": "nextlane"}
SEEDED_CARDS = 12

assert PROJECT != "nextlane", "the integration stack must never be the development one"


class Stack:
    """`docker compose`, for one isolated project."""

    base = f"http://127.0.0.1:{APP_PORT}"
    dsn = f"postgresql://nextlane:nextlane@127.0.0.1:{DB_PORT}/nextlane"

    def compose(self, *arguments: str, check: bool = True, timeout: int = 600):
        environment = {**os.environ, "APP_PORT": str(APP_PORT), "DB_PORT": str(DB_PORT)}
        return subprocess.run(
            ["docker", "compose", "-p", PROJECT, *arguments],
            cwd=REPO,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )

    def up(self, *, build: bool = False) -> None:
        self.compose("up", "-d", "--wait", *(["--build"] if build else []))
        self.wait_for_the_app()

    def down(self, *, volumes: bool = False) -> None:
        # The guard is here and not only at import: this is the line that
        # destroys data, so this is where being sure is worth the assertion.
        assert PROJECT != "nextlane", "refusing to remove the development stack"
        self.compose("down", *(["-v"] if volumes else []), check=False)

    def wait_for_the_app(self, seconds: int = 60) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                httpx.get(self.base + "/", timeout=2).raise_for_status()
                return
            except Exception:
                time.sleep(1)
        raise AssertionError(f"the app never answered on {self.base}\n{self.logs()}")

    def logs(self) -> str:
        return self.compose("logs", "--tail", "40", check=False).stdout

    def services(self) -> dict[str, dict]:
        """`docker compose ps`, as {service: row}. One JSON object per line."""
        output = self.compose("ps", "--format", "json").stdout
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
        return {row["Service"]: row for row in rows}

    def token(self) -> str:
        response = httpx.post(self.base + "/api/auth/login", json=DEMO, timeout=10)
        response.raise_for_status()
        return response.json()["token"]

    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base,
            headers={"Authorization": f"Bearer {self.token()}"},
            timeout=10,
        )

    def query(self, sql: str):
        """Straight to Postgres from the host, over the published port."""
        with (
            psycopg.connect(self.dsn, connect_timeout=5) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(sql)
            return cursor.fetchone()


@pytest.fixture(scope="session")
def stack():
    if not shutil.which("docker"):
        pytest.skip("docker is not on PATH")

    running = Stack()
    running.down(volumes=True)  # a leftover from a failed run is not a fixture
    running.up(build=True)
    yield running
    running.down(volumes=True)


@pytest.fixture
def client(stack: Stack):
    with stack.client() as signed_in:
        yield signed_in


# ------------------------------------------------------------------- isolation


class TestItIsIsolated:
    """Read rather than assumed, because the teardown deletes a volume.

    If this file's project name or ports ever drifted onto the development
    stack's, the first symptom would be somebody's board disappearing — the
    exact failure `_docs/decisions.md` #26 is about.
    """

    def development(self) -> dict[str, str]:
        compose = (REPO / "docker-compose.yaml").read_text(encoding="utf-8")
        makefile = (REPO / "Makefile").read_text(encoding="utf-8")
        found = {
            "project": re.search(r"^name:\s*(\S+)", compose, re.MULTILINE),
            "app_port": re.search(r"^APP_PORT\s*\?=\s*(\d+)", makefile, re.MULTILINE),
            "db_port": re.search(r"^DB_PORT\s*\?=\s*(\d+)", makefile, re.MULTILINE),
        }
        for name, match in found.items():
            assert match, f"could not read the development {name}"
        return {name: match.group(1) for name, match in found.items()}  # ty: ignore

    def test_it_is_a_different_compose_project(self):
        assert self.development()["project"] != PROJECT

    def test_it_is_on_different_ports(self):
        development = self.development()
        assert str(APP_PORT) != development["app_port"]
        assert str(DB_PORT) != development["db_port"]

    def test_its_volume_is_its_own(self, stack: Stack):
        """Compose names volumes after the project, so this follows from the
        project name — but it is the thing that actually matters, so say it."""
        volumes = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert f"{PROJECT}_pgdata" in volumes
        assert f"{PROJECT}_pgdata" != f"{self.development()['project']}_pgdata"


# --------------------------------------------------------------------- the image


class TestItStarts:
    def test_both_services_are_healthy(self, stack: Stack):
        """`app` waits on `db`'s health check, so this also says the ordering
        held: an app that started too early would have died, not gone healthy."""
        services = stack.services()
        assert set(services) == {"app", "db"}
        assert services["app"]["Health"] == "healthy", stack.logs()
        assert services["db"]["Health"] == "healthy", stack.logs()

    def test_the_app_did_not_restart_on_its_way_up(self, stack: Stack):
        """A crash loop that eventually succeeds still looks healthy here."""
        assert "Traceback" not in stack.logs()
        assert "Cannot reach Postgres" not in stack.logs()

    def test_it_does_not_run_as_root(self, stack: Stack):
        assert stack.compose("exec", "-T", "app", "id", "-u").stdout.strip() == "10001"


# ------------------------------------------------------------------ the frontend


class TestTheAppIsServed:
    """The frontend is copied into the image by the Dockerfile. A missing COPY,
    or a `.dockerignore` rule that swallowed something, shows up only here."""

    def test_the_root_is_the_app(self, stack: Stack):
        response = httpx.get(stack.base + "/", timeout=10)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<title>NextLane</title>" in response.text

    def test_the_api_base_is_pointed_at_this_origin(self, stack: Stack):
        """Without this the page would call localhost:8001 and fail every
        request while looking like it had loaded."""
        assert (
            "window.NEXTLANE_API_BASE = window.location.origin"
            in httpx.get(stack.base + "/", timeout=10).text
        )

    @pytest.mark.parametrize(
        "path",
        ["/src/main.js", "/src/api/client.js", "/styles/tokens.css", "/styles/layout.css"],
    )
    def test_the_assets_are_there(self, stack: Stack, path: str):
        assert httpx.get(stack.base + path, timeout=10).status_code == 200

    def test_the_docs_are_served_from_the_same_origin(self, stack: Stack):
        assert httpx.get(stack.base + "/docs", timeout=10).status_code == 200

    def test_an_unknown_path_is_the_api_error_shape(self, stack: Stack):
        response = httpx.get(stack.base + "/not-a-real-path", timeout=10)
        assert response.status_code == 404
        assert response.json()["message"]


# ----------------------------------------------------------------------- closed


class TestItIsClosed:
    """§10 through the real container, not a TestClient."""

    @pytest.mark.parametrize("path", ["/api/cards", "/api/preferences", "/api/auth/me"])
    def test_no_token_no_answer(self, stack: Stack, path: str):
        assert httpx.get(stack.base + path, timeout=10).status_code == 401

    def test_the_seeded_account_can_sign_in(self, stack: Stack):
        """The password path — scrypt against the users table in Postgres."""
        response = httpx.post(stack.base + "/api/auth/login", json=DEMO, timeout=10)
        assert response.status_code == 200
        assert response.json()["user"]["email"] == DEMO["email"]

    def test_a_wrong_password_is_refused(self, stack: Stack):
        response = httpx.post(
            stack.base + "/api/auth/login",
            json={**DEMO, "password": "not it"},
            timeout=10,
        )
        assert response.status_code == 401


# --------------------------------------------------------------------- the data


class TestItReallyUsesPostgres:
    def test_the_board_is_served(self, client: httpx.Client):
        assert len(client.get("/api/cards").json()) >= SEEDED_CARDS

    def test_a_card_written_through_the_api_is_in_the_database(self, client, stack: Stack):
        """The regression test for #26: what the app writes and what the host
        sees on the published port have to be one database. When they were two,
        the symptom was a board that looked like it never saved anything."""
        title = "written by the integration suite"
        created = client.post("/api/cards", json={"title": title, "area": "LEARNING"})
        assert created.status_code == 201

        found = stack.query(f"SELECT count(*) FROM cards WHERE title = '{title}'")
        assert found == (1,), "the app and the published port are different databases"

    def test_the_app_and_the_host_agree_on_how_many_cards_there_are(self, client, stack: Stack):
        through_the_api = len(client.get("/api/cards").json())
        in_the_database = stack.query("SELECT count(*) FROM cards")
        assert in_the_database == (through_the_api,)

    def test_the_database_port_is_the_one_everything_agrees_on(self, stack: Stack):
        """`make run` on the host connects to exactly this."""
        assert stack.query("SELECT current_database()") == ("nextlane",)


class TestTheAiFeatureIsOptional:
    """AGENTS.md: the app must stay fully usable with the AI feature off. No
    ANTHROPIC_API_KEY is set for this stack, so this is that arrangement."""

    #: Over `ai.MIN_LENGTH`, because a nine-character advert is a 422 by design
    #: and that rule belongs to `tests/test_ai.py`, not to a container.
    ADVERT = (
        "Research Engineer at Anthropic. Remote, London or San Francisco.\n"
        "Requirements: Python, a research background, and an interest in AI safety."
    )

    def test_an_advert_is_still_read(self, client: httpx.Client):
        response = client.post("/api/ai/extract-job-advert", json={"advert": self.ADVERT})
        assert response.status_code == 200, response.text
        assert response.json()["extracted"]["role"]

    def test_it_says_which_reader_did_it(self, client: httpx.Client):
        """A deployment that lost its API key must not look like a working one."""
        response = client.post("/api/ai/extract-job-advert", json={"advert": self.ADVERT})
        assert response.json()["source"] == "heuristic"


# ------------------------------------------------------------------ persistence
#
# These restart and recreate containers, so they come last: each one puts the
# stack back the way it found it, but a failure halfway through would not.


class TestItSurvives:
    def test_a_card_and_a_session_survive_restarting_the_app(self, stack: Stack):
        """Otherwise every deploy loses work and signs everybody out."""
        token = stack.token()
        headers = {"Authorization": f"Bearer {token}"}
        created = httpx.post(
            stack.base + "/api/cards",
            json={"title": "written before the restart", "area": "LEARNING"},
            headers=headers,
            timeout=10,
        )
        assert created.status_code == 201

        stack.compose("restart", "app")
        stack.wait_for_the_app()

        after = httpx.get(stack.base + "/api/cards", headers=headers, timeout=10)
        assert after.status_code == 200, "the token did not survive the restart"
        assert any(card["title"] == "written before the restart" for card in after.json())

    def test_the_board_survives_recreating_the_containers(self, stack: Stack):
        """`docker compose down` without `-v` keeps the volume, and that is the
        difference between stopping the app and losing the board."""
        with stack.client() as signed_in:
            signed_in.post("/api/cards", json={"title": "written before down", "area": "LEARNING"})

        stack.down()
        stack.up()

        with stack.client() as signed_in:
            titles = [card["title"] for card in signed_in.get("/api/cards").json()]
        assert "written before down" in titles


class TestAFreshVolume:
    """Runs last: it throws the volume away and starts over."""

    def test_an_empty_database_is_seeded_exactly_once(self, stack: Stack):
        stack.down(volumes=True)
        stack.up()

        with stack.client() as signed_in:
            cards = signed_in.get("/api/cards").json()
        assert len(cards) == SEEDED_CARDS, "a fresh volume should hold the §31 fixtures, once"

    def test_starting_again_does_not_seed_a_second_time(self, stack: Stack):
        stack.compose("restart", "app")
        stack.wait_for_the_app()

        with stack.client() as signed_in:
            assert len(signed_in.get("/api/cards").json()) == SEEDED_CARDS
