"""One error shape for the whole API: `{"message": ..., "kind": ...}`.

`message` is written to be shown to a person verbatim (§37), which is why the
validation handler below rewrites FastAPI's default `detail` list into a
sentence instead of leaking a schema dump into the UI.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    status_code = 500
    kind = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ApiError):
    status_code = 404
    kind = "not_found"


class Unauthorized(ApiError):
    """No usable token. The client should send the user to sign in."""

    status_code = 401
    kind = "unauthorized"


class Conflict(ApiError):
    status_code = 409
    kind = "conflict"


class Invalid(ApiError):
    status_code = 422
    kind = "validation"


class AiUnreadable(ApiError):
    """§15.3 — the advert could not be read. The client keeps the pasted text."""

    status_code = 422
    kind = "ai"


def _body(message: str, kind: str) -> dict[str, str]:
    return {"message": message, "kind": kind}


def readable(error: RequestValidationError) -> str:
    """Turn pydantic's first complaint into something worth showing a user."""
    errors = error.errors()
    if not errors:
        return "That doesn't look right."

    first = errors[0]
    location = [str(part) for part in first.get("loc", ()) if part not in ("body", "query")]
    field = " → ".join(location) if location else "the request"
    message = first.get("msg", "is not valid")
    message = message.removeprefix("Value error, ")
    return f"{field}: {message}"


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
        return JSONResponse(
            status_code=error.status_code,
            content=_body(error.message, error.kind),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_body(readable(error), "validation"))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content=_body(str(error.detail), "error")
        )
