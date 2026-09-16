"""Serving the frontend from the API process.

Development runs two servers — `python -m http.server` on 8000 for the static
files, uvicorn on 8001 for the API — and nothing here changes that. It is the
right arrangement for editing: the frontend has no build step
(`_docs/decisions.md` #3), so a saved file is a reloaded page.

A container is the other case. There is one process, one port and one origin,
and the API is the only thing already listening — so it serves the app too.
That is what this module is: the seam that makes the backend a web server for
the frontend when, and only when, it has been told where the frontend is.

    NEXTLANE_FRONTEND=/app/frontend      serve it, at `/`
    (unset)                              do not — this is the two-server default

Two consequences worth knowing about, both deliberate:

* **`/` becomes the app, not `GET /`'s service info** (`_docs/decisions.md`
  #22). That endpoint is a sign pointing at the door; when the app is served at
  `/` the door is already there, and `app/main.py` registers one or the other,
  never both. The API's own operations — everything under `/api`, plus `/docs`
  and `/openapi.json` — are untouched, so `openapi.yaml` still describes the API
  in either arrangement.
* **`index.html` is rewritten on the way out**, to point the client at this
  origin instead of the hardcoded `http://localhost:8001` default in
  `frontend/src/api/client.js`. That client already documents
  `window.NEXTLANE_API_BASE` as the override; this sets it.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

#: What is injected into `index.html`. `window.location.origin` rather than a
#: baked-in URL, so the same image works on localhost, behind a reverse proxy
#: and under a different hostname without being rebuilt.
API_BASE_SCRIPT = "<script>window.NEXTLANE_API_BASE = window.location.origin;</script>"


def directory() -> Path | None:
    """Where the frontend is, or `None` for the two-server arrangement."""
    configured = os.environ.get("NEXTLANE_FRONTEND", "").strip()
    if not configured:
        return None

    path = Path(configured).expanduser().resolve()
    if not (path / "index.html").is_file():
        raise RuntimeError(
            f"NEXTLANE_FRONTEND is set to {path}, which has no index.html in it. "
            "Point it at the frontend directory, or unset it to run the API alone."
        )
    return path


def index_page(root: Path) -> str:
    """`index.html` with the API base pointed at wherever this is being served."""
    html = (root / "index.html").read_text(encoding="utf-8")
    if API_BASE_SCRIPT in html:
        return html
    if "</head>" in html:
        return html.replace("</head>", f"  {API_BASE_SCRIPT}\n  </head>", 1)
    # No head to put it in. Before everything else still beats not at all: the
    # client reads the global when its module loads.
    return f"{API_BASE_SCRIPT}\n{html}"


def mount(app: FastAPI, root: Path) -> None:
    """Serve `root` as the app. Call this *after* every router is included.

    The mount is at `/` and Starlette matches routes in registration order, so
    it catches only what the API did not: the assets, and nothing else.
    """
    page = index_page(root)

    async def index() -> HTMLResponse:
        # No caching on the entry point. Its assets carry etags and may be
        # cached freely; a stale index.html is how a deploy fails to arrive.
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

    for path in ("/", "/index.html"):
        app.add_api_route(path, index, methods=["GET"], include_in_schema=False)

    app.mount("/", StaticFiles(directory=root), name="frontend")
