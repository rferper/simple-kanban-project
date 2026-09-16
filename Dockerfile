# syntax=docker/dockerfile:1

# NextLane, as one container.
#
#   docker build -t nextlane .
#   docker run --rm -p 8000:8000 -v nextlane-data:/data nextlane
#
# Development runs two servers (`make run`); this runs one. The API serves the
# frontend as well, so there is a single port, a single origin and no CORS —
# see `backend/app/frontend.py` for the seam that does it.
#
# Optional at run time:
#   -e ANTHROPIC_API_KEY=...   turns on the job-advert reader (§15). The app is
#                              fully usable without it (AGENTS.md).
#   -e NEXTLANE_DB=...         where the SQLite file lives. Defaults to /data,
#                              which is a volume, because the container is not.


# --------------------------------------------------------------- the frontend
#
# There is no bundler and there never has been (`_docs/decisions.md` #3), so
# "building" the frontend is checking it and copying it: `check.mjs` runs
# `node --check` over every module and resolves every import, which is what
# catches a typo'd path in a no-build frontend before a browser does. A broken
# import fails the image build instead of the first page load.

FROM node:22-alpine AS frontend

WORKDIR /frontend
COPY frontend/ ./
RUN node check.mjs


# ------------------------------------------------------ the backend's packages
#
# uv, against the committed lock file, into a virtualenv that the runtime stage
# copies whole. Only the manifests land in this layer, so the dependency install
# is cached until one of them actually changes.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS packages

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ------------------------------------------------------------------ the image

FROM python:3.12-slim-bookworm AS runtime

# NEXTLANE_FRONTEND is the setting that makes this process serve the whole app;
# NEXTLANE_DB puts the database on the volume rather than inside the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/backend/.venv/bin:$PATH" \
    NEXTLANE_FRONTEND=/app/frontend \
    NEXTLANE_DB=/data/nextlane.sqlite3

# Nothing here needs root, and the database directory is the only thing written.
RUN useradd --create-home --uid 10001 nextlane \
    && mkdir -p /data \
    && chown nextlane:nextlane /data

WORKDIR /app/backend

COPY --from=packages /app/backend/.venv /app/backend/.venv
COPY --from=frontend /frontend /app/frontend
COPY backend/app /app/backend/app

USER nextlane
VOLUME ["/data"]
EXPOSE 8000

# `/docs` is public and needs no database, so this says the process is serving
# without touching anyone's cards.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
