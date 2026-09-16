# AGENTS.md

**NextLane** — a responsive web Kanban for academics moving into industry. It
holds three connected areas, Current Job, Job Search and Learning / Pivot, under
one dashboard that answers a single question: what should I work on today?

`_docs/specs.md` is the product. Read the sections your task touches before
adding anything that is not in it. §44 is the condensed version when context is
short.

## Commands

Two processes: a static frontend on 8000, the API on 8001. This table is the
single place commands live; do not hardcode them into the other documents.

Prefer the task runner at the repository root — `make` in WSL, macOS and CI,
`.\make.ps1` in Windows PowerShell. They carry the same targets; change one,
change the other.

Do not share `backend/.venv` between WSL and Windows: a Linux venv has a `lib64`
symlink Windows cannot delete, and uv then fails to rebuild it. `rm -rf
backend/.venv` clears it.

| What | Command | Underneath |
| --- | --- | --- |
| run the whole app | `make run` | both servers, Ctrl-C stops both |
| run just the API | `make api` | `cd backend && uv run uvicorn app.main:app --reload --port 8001` |
| run just the frontend | `make web` | `cd frontend && python -m http.server 8000` |
| install dependencies | `make install` | `cd backend && uv sync` |
| the whole test suite | `make test` | `cd backend && uv run pytest` |
| one test module | `make test-one T=test_auth` | `uv run pytest -k test_auth` |
| the database | `make postgres` | `docker compose up -d --wait db` — needed before `make run` |
| the suite against Postgres too | `make test-postgres` | the same suite with `NEXTLANE_TEST_POSTGRES` set |
| the compose stack, tested | `make test-integration` | `pytest -m integration` — builds and runs the real stack |
| list every target | `make` | — |
| lint | `make lint` | Ruff over the backend, `frontend/check.mjs` over the frontend |
| type-check | `make types` | `uv run ty check` (the `app` package) |
| everything before a commit | `make check` | lint + types + tests |
| build the container image | `make docker-build` | `docker build -t nextlane .` |
| run the container | `make docker-run` | one process on 8000, the API serving the frontend |
| run it with Postgres | `make compose-up` | `docker compose up --build -d` — app + database |
| stop those | `make compose-down` | keeps the data; `docker compose down -v` drops it |

CI runs `make lint`, `make types` and `make test` on Linux for every push and
pull request, and `make test-integration` as a second job
(`.github/workflows/check.yml`) — through the Makefile, so there is only one
copy of how to check this project.

Frontend <http://localhost:8000>, API <http://localhost:8001>, docs at `/docs`.
Sign in with `researcher@example.com` / `nextlane`.

The container is the other arrangement: one process, one port, one origin,
because the API serves the frontend there (`_docs/decisions.md` #23). Two
servers stays the way development runs.

Ports are Makefile variables: `make run API_PORT=8091`. Changing one permanently
means changing it in three places — the Makefile, `servers:` in `openapi.yaml`,
and `API_BASE` in `frontend/src/api/client.js`.

The frontend has no toolchain and no test runner of its own
(`_docs/decisions.md` #3).

`NEXTLANE_DB` chooses the database and its shape chooses the implementation: a
`postgresql://` DSN is Postgres (**the default**), a path is SQLite, `:memory:`
is the dict (`_docs/decisions.md` #24, #26). Unset, it is the local `db` service
from `docker-compose.yaml` on 55432 — **the only Postgres this project starts**,
so `make run` and `docker compose up` are one board. The Postgres tests skip
unless `NEXTLANE_TEST_POSTGRES` points at a throwaway database; CI always sets it.

`DEFAULT_DB` in `backend/app/dependencies.py`, `DEV_DSN` in the `Makefile`,
`$DevDsn` in `make.ps1` and the credentials in `docker-compose.yaml` must all
name the same database. `tests/test_dependencies.py` reads all four and fails if
they disagree.

## Layout

| Path | What it is |
| --- | --- |
| `_docs/specs.md` | the product specification — the source of truth |
| `_docs/tasks.md` | the backlog, mirrored to GitHub issues #1–#23 |
| `_docs/process.md` | how work moves from issue to merged |
| `_docs/decisions.md` | calls already settled; read before re-litigating one |
| `_docs/task-template.md` | the shape a groomed issue takes |
| `_docs/_team/` | the role briefs the subagents run on |
| `openapi.yaml` | the API contract, derived from the frontend client (#7) |
| `Dockerfile` | the whole app as one image — Node checks the frontend, Python serves it |
| `docker-compose.yaml` | that image plus the Postgres it deploys against |
| `frontend/` | the whole UI, talking to the API — start at its README |
| `backend/` | the FastAPI API, on SQLite or Postgres — start at its README |
| `backend/app/store.py` | **the storage seam** — the `Store` protocol |
| `backend/app/sqlite_store.py` | the SQLite implementation of it |
| `backend/app/postgres_store.py` | the Postgres implementation, for deployments |
| `backend/app/dependencies.py` | which implementation `NEXTLANE_DB` selects |
| `backend/app/auth.py` | password hashing, bearer tokens, `current_user` |
| `backend/app/frontend.py` | serving the frontend from the API, when `NEXTLANE_FRONTEND` says where |
| `backend/tests/` | written before the endpoints; the contract test guards drift |
| `backend/tests/test_compose.py` | the real stack, marked `integration` and opt-in |
| `frontend/src/api/client.js` | **the only module that talks to a backend** |
| `frontend/src/domain/` | pure logic: validation, workload (§22), focus ranking (§23) |
| `src/simple_kanban_project/` | uv package stub — see Rules |
| `pyproject.toml` | dependencies and the uv build configuration |

## Rules

- Dependencies are added in `pyproject.toml`. Do not add one without asking. The
  frontend has none and is meant to keep it that way — no npm, no bundler, no
  framework, without asking first.
- Every backend call goes through `frontend/src/api/client.js`. If you find
  yourself reaching for `fetch` anywhere else, add a method there instead.
- `openapi.yaml` and the running API must agree. `backend/tests/test_contract.py`
  checks both directions — change the contract and the code in the same commit.
- Backend storage goes through the `Store` protocol. Routers and
  `app/service.py` must not know how anything is stored. Every implementation
  must pass `tests/test_store.py`, which runs one contract against all of them
  — the dict, SQLite and Postgres. A fourth one is a new module and a new
  parameter on that test's `store` fixture, and nothing else.
- The API is closed by default: every endpoint requires a bearer token except
  `POST /api/auth/login`. Adding a public endpoint means changing `PUBLIC` in
  `backend/tests/test_contract.py`, which is deliberately a visible edit.
- Never put a password or a hash in a response model. A contract test walks
  every response schema to check.
- Do not delete `src/simple_kanban_project/`. `pyproject.toml` declares the
  `uv_build` backend and a `[project.scripts]` entry pointing into it, so
  removing the directory on its own breaks `uv sync`.
- The product is **NextLane**. Preserve the domain terminology — Current Job,
  Job Search, Learning / Pivot — and do not rename it into Workspaces, Projects
  or Tickets.
- `_docs/specs.md` §33 is the non-goals list and it is binding. No calendar, no
  time tracking, no multi-user, no notifications.
- The app must stay fully usable with the AI feature switched off or failing.
- One issue at a time, one branch per issue, merged into `main`. The engineer
  does not merge and does not close the issue.
- Any judgment call the issue did not settle goes into `_docs/decisions.md` in
  the same commit that makes it.

## The team

Work runs through three roles, launched as subagents by the main session:

- **PM** grooms a task before anyone implements it — `_docs/_team/pm.md`
- **Engineer** implements one groomed task — `_docs/_team/software-engineer.md`
- **QA** checks the result against the acceptance criteria and returns PASS or
  FAIL — `_docs/_team/qa-engineer.md`

The main session is the orchestrator. It does not groom, implement or test
itself. The full lifecycle is in `_docs/process.md`.

## Documents

- `_docs/specs.md` — the product, including §33 non-goals, §41 development
  order, §42 definition of done, and §43 the agent operating rules
- `_docs/tasks.md` — the backlog; #1–#18 are done, real work starts at #19
- `_docs/process.md` — the lifecycle, the branch convention, the pre-close checks
- `_docs/decisions.md` — settled calls and their reasoning
- `_docs/task-template.md` — read before writing an issue
