"""The API serving the frontend — one process, one origin.

This is how the container runs (see the `Dockerfile`). `make run` still runs two
servers and is unaffected, which is most of what these tests are checking: the
mount happens only when `NEXTLANE_FRONTEND` says where to find the frontend, and
when it does it catches the assets without swallowing the API.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import errors, frontend
from app.dependencies import get_store
from app.routers import cards
from app.store import InMemoryStore

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """A stand-in for the frontend directory the image copies in."""
    (tmp_path / "index.html").write_text(
        "<!doctype html>\n<html>\n  <head>\n    <title>NextLane</title>\n"
        "  </head>\n  <body></body>\n</html>\n",
        encoding="utf-8",
    )
    (tmp_path / "styles").mkdir()
    (tmp_path / "styles" / "tokens.css").write_text(":root { --gap: 8px; }", encoding="utf-8")
    return tmp_path


def serve(root: Path) -> TestClient:
    """An app wired the way `app/main.py` wires it: routers first, mount last."""
    app = FastAPI()
    errors.install(app)
    app.include_router(cards.router)
    app.dependency_overrides[get_store] = InMemoryStore
    frontend.mount(app, root)
    return TestClient(app)


class TestWhetherItServesAtAll:
    """Unset is the two-server default, and has to stay the default."""

    def test_it_does_not_by_default(self, monkeypatch):
        monkeypatch.delenv("NEXTLANE_FRONTEND", raising=False)
        assert frontend.directory() is None

    def test_an_empty_setting_is_the_same_as_none(self, monkeypatch):
        monkeypatch.setenv("NEXTLANE_FRONTEND", "   ")
        assert frontend.directory() is None

    def test_it_does_when_pointed_at_a_frontend(self, monkeypatch, bundle: Path):
        monkeypatch.setenv("NEXTLANE_FRONTEND", str(bundle))
        assert frontend.directory() == bundle.resolve()

    def test_a_directory_with_no_index_is_a_startup_error(self, monkeypatch, tmp_path: Path):
        """Better a refusal naming the path than a server answering 404 for the app."""
        monkeypatch.setenv("NEXTLANE_FRONTEND", str(tmp_path))
        with pytest.raises(RuntimeError, match=r"index\.html"):
            frontend.directory()


class TestWhatItServes:
    def test_the_app_is_at_the_root(self, bundle: Path):
        response = serve(bundle).get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<!doctype html>" in response.text

    def test_index_html_is_the_same_page(self, bundle: Path):
        client = serve(bundle)
        assert client.get("/index.html").text == client.get("/").text

    def test_the_entry_point_is_not_cached(self, bundle: Path):
        """A stale index.html is how a deploy fails to arrive."""
        assert serve(bundle).get("/").headers["cache-control"] == "no-cache"

    def test_the_assets_are_served(self, bundle: Path):
        response = serve(bundle).get("/styles/tokens.css")
        assert response.status_code == 200
        assert "--gap" in response.text

    def test_an_unknown_path_is_still_an_honest_404(self, bundle: Path):
        response = serve(bundle).get("/not-a-real-path")
        assert response.status_code == 404
        assert response.json()["message"]


class TestItDoesNotSwallowTheApi:
    """The mount is registered last and must catch only what the routers did not."""

    def test_the_api_still_answers(self, bundle: Path):
        assert serve(bundle).get("/api/cards").status_code == 401

    def test_the_api_is_still_closed(self, bundle: Path):
        """Serving the app from the same process opens no door (§10)."""
        response = serve(bundle).post("/api/cards", json={"title": "x", "area": "LEARNING"})
        assert response.status_code == 401


class TestThePageKnowsWhereTheApiIs:
    """`client.js` defaults to http://localhost:8001. Same-origin, that is wrong."""

    def test_the_api_base_is_injected(self, bundle: Path):
        assert frontend.API_BASE_SCRIPT in serve(bundle).get("/").text

    def test_it_lands_inside_the_head(self, bundle: Path):
        body = serve(bundle).get("/").text
        assert body.index(frontend.API_BASE_SCRIPT) < body.index("</head>")

    def test_it_is_injected_once(self, bundle: Path):
        """Twice would be harmless and would still mean something is wrong."""
        assert serve(bundle).get("/").text.count(frontend.API_BASE_SCRIPT) == 1

    def test_a_page_without_a_head_still_gets_it(self, tmp_path: Path):
        (tmp_path / "index.html").write_text("<body>no head</body>", encoding="utf-8")
        assert frontend.index_page(tmp_path).startswith(frontend.API_BASE_SCRIPT)

    def test_it_points_at_this_origin_rather_than_a_baked_in_url(self):
        """The same image has to work on localhost and behind a proxy."""
        assert "window.location.origin" in frontend.API_BASE_SCRIPT
        assert "localhost" not in frontend.API_BASE_SCRIPT


class TestTheRealFrontend:
    """The one the image actually copies in, so this catches it drifting."""

    def test_it_is_where_the_dockerfile_thinks_it_is(self):
        assert (REPO / "frontend" / "index.html").is_file()

    def test_it_takes_the_injection(self):
        page = frontend.index_page(REPO / "frontend")
        assert page.index(frontend.API_BASE_SCRIPT) < page.index("</head>")

    def test_its_modules_are_served(self):
        client = serve(REPO / "frontend")
        assert client.get("/src/main.js").status_code == 200
        assert client.get("/src/api/client.js").status_code == 200
        assert client.get("/styles/tokens.css").status_code == 200
