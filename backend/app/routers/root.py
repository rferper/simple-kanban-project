"""What this service is — issue #23.

The only other public endpoint besides login, and for a plain reason: someone who
opens the API in a browser should find out what it is, not a 401 telling them to
authenticate before they know what they would be authenticating to.

It says nothing a stranger could not learn by reading the repository: the name,
the version, and where the docs and the frontend are. No counts, no data, no
hints about who has an account here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models import ServiceInfo

router = APIRouter(tags=["service"])


@router.get("/", response_model=ServiceInfo, summary="What this service is")
def root() -> ServiceInfo:
    """Public. It is the sign that points at the door, not the door."""
    return ServiceInfo(
        name="NextLane API",
        version="0.1.0",
        description=(
            "A career-pivot Kanban for academics moving into industry. "
            "This is the API; the app is served separately."
        ),
        docs="/docs",
        openapi="/openapi.json",
        app="http://localhost:8000",
    )
