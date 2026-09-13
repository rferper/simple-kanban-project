"""Card and job-details endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app import service
from app.auth import current_user
from app.dependencies import get_store
from app.models import Card, CardCreate, CardUpdate, JobDetailsInput
from app.store import Store

router = APIRouter(
    prefix="/api/cards",
    tags=["cards"],
    # Every card endpoint requires a token (see app/auth.py).
    dependencies=[Depends(current_user)],
)

Repo = Annotated[Store, Depends(get_store)]


@router.get("", response_model=list[Card], summary="Every card, across all three areas")
def list_cards(store: Repo) -> list[Card]:
    return service.list_cards(store)


@router.post("", response_model=Card, status_code=status.HTTP_201_CREATED, summary="Create a card")
def create_card(payload: CardCreate, store: Repo) -> Card:
    """Only `title` and `area` are required (§13). `status` defaults to the
    area's first column."""
    return service.create_card(store, payload)


@router.get("/{cardId}", response_model=Card, summary="One card")
def get_card(cardId: str, store: Repo) -> Card:
    return service.get_card(store, cardId)


@router.patch("/{cardId}", response_model=Card, summary="Update a card")
def update_card(cardId: str, payload: CardUpdate, store: Repo) -> Card:
    """A partial update. This one endpoint serves moving a card between columns
    (§14), the planned-this-week toggle (§10.5) and marking complete (§12.1).
    `completedAt` is managed by the server."""
    return service.update_card(store, cardId, payload)


@router.delete("/{cardId}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a card")
def delete_card(cardId: str, store: Repo) -> Response:
    service.delete_card(store, cardId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{cardId}/job",
    response_model=Card,
    summary="Update a job card's application details",
)
def update_job_details(cardId: str, payload: JobDetailsInput, store: Repo) -> Card:
    """Also the archive path: setting `outcome` to REJECTED, WITHDRAWN or
    DECLINED takes the application off the board while keeping everything it
    held (§8.1, §16.8)."""
    return service.update_job_details(store, cardId, payload)
