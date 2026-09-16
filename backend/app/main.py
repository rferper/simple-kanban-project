"""NextLane API.

Run it:

    uv run uvicorn app.main:app --reload --port 8001

The frontend expects it on port 8001 (see `openapi.yaml`), leaving 8000 for the
static frontend itself.

It can also serve that frontend itself, which is what the container does — one
process, one port, one origin. Set `NEXTLANE_FRONTEND` to the directory and see
`app/frontend.py`; unset, nothing below changes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors, frontend
from app.routers import ai, auth, cards, links, preferences, root

DESCRIPTION = """
The backend for NextLane — a career-pivot Kanban for academics moving into
industry.

The contract is `openapi.yaml` at the store root, derived from
`frontend/src/api/client.js`. A test keeps the two from drifting apart.

Storage is behind the `Store` protocol in `app/store.py`: SQLite by default,
Postgres when `NEXTLANE_DB` is a `postgresql://` DSN, and a dict in the tests.
Nothing above that protocol knows which one it has.
"""

app = FastAPI(
    title="NextLane API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_url="/openapi.json",
    docs_url="/docs",
)

# When the frontend is served separately as static files it is cross-origin, and
# these are the two addresses it is served from. When this process serves it
# instead the requests are same-origin and never reach this middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errors.install(app)

app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(links.router)
app.include_router(preferences.router)
app.include_router(ai.router)

# `/` belongs to whichever of the two is actually in front of the user: the app
# when this process serves it, and otherwise the sign that points at it
# (`_docs/decisions.md` #22, #23). The mount goes last, because it matches
# every path the routers above did not.
FRONTEND = frontend.directory()
if FRONTEND is None:
    app.include_router(root.router)
else:
    frontend.mount(app, FRONTEND)
