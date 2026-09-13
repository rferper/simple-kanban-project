"""Job to learning links. §9.3"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app import service
from app.auth import current_user
from app.dependencies import get_store
from app.models import Card
from app.store import Store

router = APIRouter(
    prefix="/api/learning",
    tags=["links"],
    dependencies=[Depends(current_user)],
)

Repo = Annotated[Store, Depends(get_store)]


@router.put(
    "/{learningId}/jobs/{jobId}",
    response_model=list[Card],
    summary="Link a learning card to a job card",
)
def link(learningId: str, jobId: str, store: Repo) -> list[Card]:
    """Idempotent. Returns both affected cards, learning card first, so the
    client can update each end without refetching."""
    learning, job = service.set_link(store, learningId, jobId, connected=True)
    return [learning, job]


@router.delete(
    "/{learningId}/jobs/{jobId}",
    response_model=list[Card],
    summary="Unlink a learning card from a job card",
)
def unlink(learningId: str, jobId: str, store: Repo) -> list[Card]:
    learning, job = service.set_link(store, learningId, jobId, connected=False)
    return [learning, job]
