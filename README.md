# NextLane

A responsive web Kanban for job searchers.

Three connected areas — **Current Job**, **Job Search** and **Learning / Pivot** —
under one dashboard that answers a single question:

> What should I work on today to maximise my chances of successfully moving into
> another job without neglecting my current one?

Job Search is a real application tracker, not a column of to-dos: it carries the
role, the company, the fit, the stage, and the learning work linked to it. The
one AI feature is pasting a job advert and getting back an editable, structured
job card. Everything else works with AI switched off.

## Running it

**WSL, macOS, Linux:**

```sh
make install   # once
make postgres  # the database, once per reboot
make run       # both servers; Ctrl-C stops both
```

**Windows PowerShell** — same targets, no `make` needed:

```powershell
.\make.ps1 install
.\make.ps1 postgres
.\make.ps1 run
```

`make postgres` starts the `db` service from
[`docker-compose.yaml`](docker-compose.yaml), and it is the only Postgres this
project runs — so `make run` and `docker compose up` show you the same board.
No Docker? `NEXTLANE_DB=backend/nextlane.sqlite3` falls back to a file.

`make.ps1` exists because GNU make on Windows runs recipes through `cmd.exe`,
and the Makefile's recipes are POSIX shell. The two files are two front doors
onto the same commands.

Then <http://localhost:8000>, and sign in with `researcher@example.com` /
`nextlane`. `make` on its own lists every target; `make test` runs the suite;
API docs are at <http://localhost:8001/docs>.

**In a container** — one process, one port, the API serving the frontend:

```sh
make docker-build
make docker-run       # http://localhost:8000
```

Nothing else is needed: the image carries the frontend, seeds its own database
on the volume, and works with the AI feature switched off. Pass
`-e ANTHROPIC_API_KEY=...` to switch it on. See
[`_docs/decisions.md`](_docs/decisions.md) #23 for why the API serves the
frontend there and two servers stay the way development runs.

**With Postgres**, which is the shape of a real deployment —
[`docker-compose.yaml`](docker-compose.yaml) runs the app and its database
together:

```sh
make compose-up       # http://localhost:8000
make compose-down     # stop; `docker compose down -v` also drops the data
```

The app waits for the database to be healthy before it starts, and the board
survives `down` and `up` because the data is on a volume.

Either runner wraps these two commands, if you would rather run them yourself:

```sh
cd backend  && uv run uvicorn app.main:app --reload --port 8001
cd frontend && python3 -m http.server 8000   # `python` on Windows
```

The API is closed by default — every endpoint needs a bearer token except
`POST /api/auth/login`. The seeded development account is
`researcher@example.com` / `nextlane`.

## Status

The UI is complete and usable end to end. The API is implemented and tested
against [`openapi.yaml`](openapi.yaml).

The two are **wired together**: the frontend signs in, holds the token, and every
card you move is a call to the API. There are no mocks left in the frontend.

**The board is kept in Postgres**, seeded on first run. One setting says where,
and the shape of it chooses the implementation:

```sh
NEXTLANE_DB=postgresql://user:password@host/nextlane   # the default
NEXTLANE_DB=backend/nextlane.sqlite3                   # a file, for no-Docker
NEXTLANE_DB=:memory:                                   # a throwaway run
```

All three are implementations of one `Store` protocol, and the contract in
`backend/tests/test_store.py` runs against every one of them, so none can
quietly drift from the others. See [`_docs/decisions.md`](_docs/decisions.md)
#24 and #26.

## Where everything is

| Path | What it is |
| --- | --- |
| [`frontend/`](frontend) | the whole UI |
| [`backend/`](backend) | the FastAPI API, on SQLite |
| [`openapi.yaml`](openapi.yaml) | the API contract both sides answer to |
| [`Dockerfile`](Dockerfile) | the whole app as one image |
| [`docker-compose.yaml`](docker-compose.yaml) | that image, plus Postgres |
| [`_docs/specs.md`](_docs/specs.md) | the product specification — the source of truth |
| [`_docs/process.md`](_docs/process.md) | how work moves from issue to merged |
| [`_docs/decisions.md`](_docs/decisions.md) | calls already settled, and why |
| [`_docs/_team/`](_docs/_team) | the PM, engineer and QA briefs |
| [`AGENTS.md`](AGENTS.md) | the short version, for agents and for people |

Start with `AGENTS.md`. Read `_docs/specs.md` §44 if you want the whole product
in one paragraph.
