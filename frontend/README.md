# NextLane — frontend

The whole product, talking to the API in [`../backend`](../backend).

Every screen in `_docs/specs.md` is here and interactive: the unified dashboard
with its workload indicator and Focus Today, all three Kanban boards with drag
and drop, the card detail drawer, the job-application pipeline with its archive,
job ↔ learning links, filters, settings, and the paste-a-job-advert flow.

## Running it

It is plain HTML, CSS and ES modules — no build step, no dependencies, no npm.
It does need to be *served*, because browsers refuse ES module imports over
`file://`, and it needs the API running alongside it:

```sh
make run        # from the repository root: both servers at once
```

or, without `make`:

```sh
cd frontend && python3 -m http.server 8000   # `python` on Windows        # http://localhost:8000
cd backend  && uv run uvicorn app.main:app --reload --port 8001
```

Sign in with the development account: `researcher@example.com` / `nextlane`.

Your board lives on the server now. The only thing this app keeps in the browser
is the bearer token, so a reload keeps you signed in.

## Where the backend is

**`src/api/client.js` is the only module in the app that talks to a backend.**
No view, no component and no domain function fetches anything on its own. It
holds the token, attaches it to every call, maps the API's
`{"message", "kind"}` errors onto `ApiError`, and turns a network failure into a
sentence rather than a stack trace.

It points at `http://localhost:8001` by default. Override it before the app
loads:

```html
<script>window.NEXTLANE_API_BASE = "https://api.example.com";</script>
```

There are no mocks left. `mock-backend.js`, `mock-ai.js` and `seed.js` were
deleted when this was wired up — the seed data now lives in
`backend/app/seed.py`, and the advert parser in `backend/app/ai.py`.

## Signing in

Every endpoint except login needs a bearer token, so the sign-in screen is the
whole app until there is one (`src/ui/login.js`).

- The token is kept in `localStorage` under `nextlane.token`, so a reload keeps
  the session.
- When the API answers 401 — a revoked token, or one that expired while the tab
  sat open — `client.js` drops it and tells the store, which shows the sign-in
  screen. That happens once, centrally, rather than as a wall of failed
  requests.
- Signing out revokes the token server-side, so it is dead immediately. Other
  devices stay signed in.

## Layout

```
frontend/
├── index.html
├── styles/          tokens, layout, components — one hand-written stylesheet each
└── src/
    ├── main.js      entry point
    ├── store.js     app state and session; the only caller of the API client
    ├── api/
    │   └── client.js   ← the only module that talks to the backend
    ├── domain/      pure logic, no DOM: types, validation, workload, focus ranking
    └── ui/          shell, router, login, dashboard, boards, cards, drawer, dialogs
```

The three layers `_docs/specs.md` §27 asks for map onto `ui/`, `domain/` and
`api/`. `domain/` is the part worth guarding: it has no DOM and no network, so
the workload sum (§22) and the Focus Today ranking (§23) stay testable and
reusable whatever happens around them.

Note what did *not* change when the mock was swapped for the real API: nothing
in `ui/` or `domain/`. That was the point of routing everything through one
module.

## What is deliberately missing

- **Account management.** One seeded account, no registration, no password
  reset. §26 warns against spending half the project on it.
- **Offline support.** The board is the server's now. With the API down you get
  a message saying so, not a degraded copy.
- **Real AI.** `backend/app/ai.py` is a heuristic parser standing in for a model
  call. The flow around it is real: extraction output is never saved without the
  user seeing and editing it first (§15.3).
