"""Is this process actually serving?

Public, because the things that ask are not people and cannot hold a token: a
load balancer deciding whether to send traffic here, the container's own
`HEALTHCHECK`, and the deploy pipeline deciding whether the release worked.

**It says whether the database answers, not what is in it.** A liveness check
that only proves the web server is up is the one that reports green while every
request 500s — the process is the easy half. So this does one cheap read
through the `Store` protocol and reports whether it came back.

Nothing here is worth protecting: two words, neither of which is a fact about
anybody's job search. That is the same discipline as `GET /` (§22 in
`_docs/decisions.md`), and a test asserts the exact set of keys so that adding
to it is a deliberate act.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_store
from app.models import Health
from app.store import Store

router = APIRouter(tags=["service"])

# The same alias the other routers use, so the dependency reads one way
# across the whole API.
Repo = Annotated[Store, Depends(get_store)]


@router.get("/api/health", response_model=Health, summary="Is this process serving?")
def health(response: Response, store: Repo) -> Health:
    """Public. 200 when it can serve, 503 when it cannot.

    The status code is the part a load balancer reads, so it has to be wrong
    only when something really is.
    """
    try:
        store.get_preferences()
    except Exception:
        # Deliberately broad: a dropped connection, a timeout and a server that
        # went away are one thing from here — this process cannot serve.
        response.status_code = 503
        return Health(status="degraded", database="unreachable")

    return Health(status="ok", database="ok")
