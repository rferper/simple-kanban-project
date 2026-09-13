"""Sign in, sign out, and who am I.

These are the only endpoints that do not require a token — `/api/auth/login`
because it is how you get one, and `/api/auth/me` and `/api/auth/logout` because
they carry one by definition.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app import auth
from app.dependencies import get_store
from app.models import LoginRequest, LoginResponse, UserPublic
from app.store import Store

router = APIRouter(prefix="/api/auth", tags=["auth"])

StoreDep = Annotated[Store, Depends(get_store)]


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Exchange an email and password for a bearer token",
)
def login(payload: LoginRequest, store: StoreDep) -> LoginResponse:
    """The one public endpoint. A wrong email and a wrong password fail
    identically, so this cannot be used to discover which addresses exist."""
    user = auth.authenticate(store, payload.email, payload.password)
    token, expires_at = auth.issue_token(store, user)

    return LoginResponse(
        token=token,
        expires_at=expires_at,
        user=UserPublic(id=user.id, email=user.email, display_name=user.display_name),
    )


@router.get("/me", response_model=UserPublic, summary="The signed-in user")
def me(user: auth.CurrentUser) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, display_name=user.display_name)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the token used to make this call",
)
def logout(
    store: StoreDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(auth.bearer_scheme)],
    _: auth.CurrentUser,
) -> Response:
    """Revocation is immediate: the token is deleted, not marked. This is the
    thing an opaque server-side token buys that a JWT would not."""
    if credentials is not None:
        auth.revoke_token(store, credentials.credentials)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
