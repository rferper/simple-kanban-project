# NextLane

A responsive web Kanban for academics moving into industry.

Three connected areas — **Current Job**, **Job Search** and **Learning / Pivot** —
under one dashboard that answers a single question:

> What should I work on today to maximise my chances of successfully moving into
> industry without neglecting my current job?

Job Search is a real application tracker, not a column of to-dos: it carries the
role, the company, the fit, the stage, and the learning work linked to it. The
one AI feature is pasting a job advert and getting back an editable, structured
job card. Everything else works with AI switched off.

## Running it

**WSL, macOS, Linux:**

```sh
make install   # once
make run       # both servers; Ctrl-C stops both
```

**Windows PowerShell** — same targets, no `make` needed:

```powershell
.\make.ps1 install
.\make.ps1 run
```

`make.ps1` exists because GNU make on Windows runs recipes through `cmd.exe`,
and the Makefile's recipes are POSIX shell. The two files are two front doors
onto the same commands.

Then <http://localhost:8000>, and sign in with `researcher@example.com` /
`nextlane`. `make` on its own lists every target; `make test` runs the suite;
API docs are at <http://localhost:8001/docs>.

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

What is still a stand-in is the database — the backend keeps everything in memory,
so restarting the API resets the board to its seed data. Swapping that out is a
second implementation of the `Store` protocol in `backend/app/store.py`.

## Where everything is

| Path | What it is |
| --- | --- |
| [`frontend/`](frontend) | the whole UI |
| [`backend/`](backend) | the FastAPI API, on a mock database |
| [`openapi.yaml`](openapi.yaml) | the API contract both sides answer to |
| [`_docs/specs.md`](_docs/specs.md) | the product specification — the source of truth |
| [`_docs/process.md`](_docs/process.md) | how work moves from issue to merged |
| [`_docs/decisions.md`](_docs/decisions.md) | calls already settled, and why |
| [`_docs/_team/`](_docs/_team) | the PM, engineer and QA briefs |
| [`AGENTS.md`](AGENTS.md) | the short version, for agents and for people |

Start with `AGENTS.md`. Read `_docs/specs.md` §44 if you want the whole product
in one paragraph.
