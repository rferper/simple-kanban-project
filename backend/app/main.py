"""NextLane API.

Run it:

    uv run uvicorn app.main:app --reload --port 8001

The frontend expects it on port 8001 (see `openapi.yaml`), leaving 8000 for the
static frontend itself.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.routers import ai, auth, cards, links, preferences, root

DESCRIPTION = """
The backend for NextLane — a career-pivot Kanban for academics moving into
industry.

The contract is `openapi.yaml` at the store root, derived from
`frontend/src/api/client.js`. A test keeps the two from drifting apart.

**The database is a mock.** Everything lives in memory for the life of the
process, behind the `Store` protocol in `app/store.py`.
"""

app = FastAPI(
    title="NextLane API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_url="/openapi.json",
    docs_url="/docs",
)

# The frontend is served separately as static files, so it is always cross-origin.
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

app.include_router(root.router)
app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(links.router)
app.include_router(preferences.router)
app.include_router(ai.router)
