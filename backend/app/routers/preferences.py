"""Preferences. §20 - two fields, and no more."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app import service
from app.auth import current_user
from app.dependencies import get_store
from app.models import Preferences, PreferencesUpdate
from app.store import Store

router = APIRouter(
    prefix="/api/preferences",
    tags=["preferences"],
    dependencies=[Depends(current_user)],
)

Repo = Annotated[Store, Depends(get_store)]


@router.get("", response_model=Preferences, summary="Read preferences")
def read(store: Repo) -> Preferences:
    return service.get_preferences(store)


@router.patch("", response_model=Preferences, summary="Update preferences")
def update(payload: PreferencesUpdate, store: Repo) -> Preferences:
    return service.update_preferences(store, payload)
