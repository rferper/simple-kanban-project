# Decisions

Calls already settled. `_docs/specs.md` is a product specification and leaves
implementation questions open; they are answered here so that issues stop
re-litigating them.

Where an issue and this file disagree, this file wins — raise it on the issue
rather than quietly doing it another way.

Each entry says what was decided, why, and what it costs. The cost line is not
optional: a decision with no cost written down is one nobody stress-tested.

## 1. The product is called NextLane

Everywhere the product is named — UI, page titles, README, portfolio material —
it is NextLane. Not "the kanban app", not "Career Pivot Kanban", not a
placeholder.

Why: the working title described the mechanism rather than the product, and a
portfolio project that cannot say its own name reads as unfinished.

Cost accepted: the repository, the uv package and the GitHub remote are all
still `simple-kanban-project`. Renaming them means editing the build
configuration mid-project — a real chance of breaking `uv sync` for no
functional gain. The directory name and the product name are allowed to
disagree.

## 2. The stack: FastAPI behind a static frontend

`_docs/specs.md` leaves the technology stack unspecified on purpose. It is now
settled: a no-build ES-module frontend (#3) served statically on port 8000, and a
FastAPI backend on port 8001, managed with uv, tested with pytest.

Every document that needs a command points at the Commands table in `AGENTS.md`,
which is the single place those live.

Why FastAPI: the contract was already written as OpenAPI, and FastAPI generates
its own OpenAPI document from the code — which is what makes the drift test in
`backend/tests/test_contract.py` possible at all. Pydantic also gives the
validation rules of §29 a single home rather than scattering them through the
handlers.

Cost accepted: two processes to run in development instead of one, and CORS
configuration that would not exist if the backend served the frontend.

## 3. The frontend is plain ES modules, with no build step

`frontend/` is hand-written HTML, CSS and ES modules. No framework, no bundler,
no npm dependencies. It runs from any static file server.

Why: the frontend had to be built before the course had picked a stack. A
no-build frontend commits the project to nothing — it can be served by whatever
backend arrives, or ported, without a toolchain decision having been made on its
behalf. It also keeps the diff readable, which matters for a portfolio project
where someone will actually look at the code.

Cost accepted: no JSX, no reactive framework, and re-renders are coarse — a
state change re-renders the whole view rather than a subtree. At this size that
is imperceptible; at ten times this size it would not be.

## 4. All backend access goes through `frontend/src/api/client.js`

One module holds every read and every write. Nothing else in the app fetches
anything. It was served by in-browser mocks first and by the real API since
(#13).

Why: it is the seam the real backend landed on. The mock imposed two disciplines
a real server imposes anyway — every call async with real latency, every returned
object a copy — so the UI never grew a dependency on synchronous, shared-mutable
data that would have broken on the day it was wired up.

Cost accepted: a little ceremony for operations that were trivially local at the
time. It paid for itself: wiring the real API changed this one file and nothing
in `ui/` or `domain/`.

## 5. Job details live on the card, not in a second record

`_docs/specs.md` §24 models `Card 1 ── 0..1 JobDetails`. In the frontend a job
card carries its details in a `job` object on the card itself, and the job ↔
learning many-to-many is stored as an id list on both ends, kept in step by the
mock backend.

Why: one fetch, one object, no join to reassemble in the client. The `client.js`
surface still exposes them as separate operations (`api.jobs.update`,
`api.links.connect`), so a backend that really does keep two tables can serve
the same calls without the UI noticing.

Cost accepted: if the backend splits them, `client.js` has to reassemble the
card — which is exactly what that module is for.

## 6. Routing is hash-based

`#/`, `#/work`, `#/jobs`, `#/learning`, `#/settings` — the conceptual routes from
`_docs/specs.md` §19, behind a `#`.

Why: it works on a static file server with no rewrite rules, so the frontend
runs today with nothing behind it. Swapping to real paths later is a change to
`src/ui/app.js` alone.

Cost accepted: the URLs are uglier than `/jobs`.

## 7. `openapi.yaml` was derived from the frontend, not the other way round

The contract at the repository root was written by reading
`frontend/src/api/client.js`, where every method had already been annotated with
the HTTP call it stood in for. The backend was then built to that contract.

Why: the frontend was built first and is the only real consumer. A contract
designed in the abstract would have been a second opinion about what the client
needs, and the client would have had to be changed to match it.

`backend/tests/test_contract.py` compares the file against the running app in
both directions, so neither can drift.

Cost accepted: the API is shaped by one client's needs. `PATCH /api/cards/{id}`
carrying drag-and-drop, the weekly-planning toggle and completion all at once is
a frontend convenience, not a REST purist's design.

## 8. The database is a Protocol, so the implementation can change

`backend/app/store.py` defines a `Store` Protocol. It began with one
implementation, a dict, and `get_store` in `app/dependencies.py` is the swap
point. Issue #19 added the second — see #15.

Why: it was explicitly a mock from the start, so the seam had to be real rather
than something to be retrofitted. Making the tests use the same seam proved it
worked rather than asserting that it would.

Cost accepted at the time: restarting the server lost everything. That is what
#15 fixed, and the seam is why it was a contained change.

## 9. `completedAt` is server-owned

The client cannot set it. It is stamped when a card enters its area's done
column and cleared when it leaves.

Why: the frontend, the backend and any future client would each have had to
remember to do it, and the one that forgot would produce cards that are done but
never completed.

Cost accepted: a client that wants to backdate a completion cannot.

## 10. Every endpoint requires a token except login

`_docs/specs.md` §26 says authentication is not required by the product and may
be postponed. It is no longer postponed: the backend is closed by default, and
`POST /api/auth/login` is the only public endpoint.

Why: NextLane holds someone's job search — which roles they want, what rejected
them, what they are quietly learning in order to leave their current job. There
is no part of that which is safe to leave open, so "closed unless stated" is the
only sensible default. Two contract tests enforce it, so an endpoint added
without a token requirement fails the suite rather than production.

Cost accepted: `frontend/src/api/client.js` sends no `Authorization` header, so
the two halves cannot be wired together until it learns to log in and carry a
token. Nothing breaks today only because the frontend still runs on its own mock.

## 11. scrypt from the standard library, and opaque server-side tokens

Passwords: `hashlib.scrypt`, per-password 16-byte salt, `hmac.compare_digest` to
verify, stored as `scrypt$<salt-hex>$<hash-hex>`.

Tokens: `secrets.token_urlsafe(32)`, held server-side, valid 14 days.

Why scrypt rather than bcrypt or passlib: it is memory-hard, it is what
`hashlib` documents for passwords, and it needs no new dependency — `AGENTS.md`
says not to add one without asking.

Why opaque tokens rather than JWTs: a JWT cannot be revoked without keeping the
very same server-side list, so the JWT buys nothing here and hand-rolled JWT
signing is a well-known way to get this wrong. Logout deletes the token and it is
dead immediately.

Cost accepted: tokens do not survive a restart, because the store does not. The
naming of the hash scheme is what makes migrating off scrypt possible later.

## 12. Authentication gates the workspace; it does not partition the data

Every authenticated user sees the same board. There is one seeded account and no
registration, password change or reset.

Why: §33 rules out multi-user collaboration and §26 notes the first user is the
developer. Per-user data would be multi-tenancy — a product decision nobody has
made, and one §33 currently forbids. §26 also warns specifically against spending
half the project on account management.

Cost accepted: a second account added to the store today would see the first
user's cards. A test records this explicitly so that it reads as a decision
rather than a bug, and so that making the data per-user later is deliberate.

## 13. The frontend talks to the real API; the mocks are deleted

`frontend/src/api/client.js` now makes HTTP calls to `backend/`.
`mock-backend.js`, `mock-ai.js` and `frontend/src/api/seed.js` were deleted
rather than kept behind a flag.

Why delete rather than keep: a mock kept "just in case" is a second
implementation of the product that nobody runs and nobody updates, and it drifts
until it lies. The seed data lives in `backend/app/seed.py` now, and the advert
parser in `backend/app/ai.py`; keeping second copies in the frontend would mean
two versions of both.

What this confirmed: nothing in `src/ui/` or `src/domain/` changed. The whole
swap was `client.js`, plus the new sign-in screen that authentication required.

Cost accepted: there is no offline mode and no way to demo the frontend without
the API running. With the API down you get a message saying so.

## 14. The token lives in `localStorage`, and a 401 is handled in one place

`nextlane.token` in `localStorage`, attached by `client.js` to every request.
When any call comes back 401, the client drops the token and notifies the store,
which shows the sign-in screen.

Why `localStorage` rather than an httpOnly cookie: a cookie would be better
against XSS, but it needs the API to set it, CORS credentials, and a CSRF story
for every non-GET call. For a single-user portfolio app on localhost that is a
lot of machinery for a threat model that does not yet exist. The choice is
written down here so it is revisited rather than inherited if this is ever
deployed.

Why centralise the 401: a token expiring while a tab sat open would otherwise
surface as five simultaneous failed requests and five error toasts. Handled in
the client, it is one transition to the sign-in screen.

Cost accepted: a script running on this origin could read the token. That is the
known cost of `localStorage`, and the reason this is decision-worthy rather than
a detail.

## 15. SQLite through the standard library, with a normalised schema

`backend/app/sqlite_store.py` implements the `Store` protocol against SQLite
using `sqlite3` from the standard library. No ORM, no new dependency. The schema
is normalised — tables for cards, tags, subtasks, job details, requirements and
each side of the job to learning links — rather than a JSON document in a column.

Why the standard library: `AGENTS.md` says not to add a dependency without
asking, and this project already prefers it — scrypt rather than passlib, plain
ES modules rather than a framework. The schema is small enough that the SQL is
clearer than the machinery that would avoid writing it.

Why normalised: `_docs/specs.md` §24 describes real relations. A JSON blob would
store the data but hide every relation from the database, which is most of what
having a database is for.

Cost accepted: hand-written SQL, and a schema change means a migration rather
than nothing. `SCHEMA_VERSION` exists so an older database is refused loudly
instead of being read as though the columns still mean what they used to.

## 16. Both store implementations are kept interchangeable by the test suite

`tests/test_store.py` runs one contract against every implementation, and
`tests/conftest.py` parametrises the entire API suite over both — so every
endpoint test runs twice, once on the dict and once on SQLite.

Why: "nothing above the seam can tell the difference" is a claim, and a claim
about behaviour is worth exactly as much as the test that checks it. The in-memory
store still earns its place: it is what `NEXTLANE_DB=:memory:` selects, and it
keeps the suite fast.

It paid for itself the first time it ran. Putting the API tests on SQLite found
that the dict silently allowed two accounts to share an email address while
SQLite's unique index refused — a divergence neither implementation's own tests
could have caught. The dict now enforces it too.

Cost accepted: the suite takes about three times as long, and a new
implementation has to pass the contract before it can be wired in. Both are the
point rather than a side effect.

## 17. Two advert readers, and the result says which one read it

`backend/app/ai.py` dispatches between a Claude call (`app/ai_model.py`) and the
original heuristic parser. `NEXTLANE_AI` chooses: `auto` by default, meaning the
model when `ANTHROPIC_API_KEY` is set and the parser otherwise. Every result
carries `source`.

Why keep the parser: a fresh clone has no API key, and a portfolio project that
shows a broken feature to anyone who has not signed up for an API account is
worse than one that reads adverts a little less well. It also means the test
suite needs no credentials and no network.

Why say which: a regex's reading and a model's are not the same quality. Without
`source`, a deployment that lost its API key looks exactly like a working one,
and the person reading a half-filled preview has no way to know why.

Cost accepted: two readers to maintain, and one more field in the contract.

## 18. A failed model call is an error, not a silent downgrade

When the model is the configured reader and the call fails - auth, rate limit,
network, or a response that will not validate - the endpoint returns 422 with a
friendly message. It does not fall back to the parser.

Why: `_docs/specs.md` §15.3 already says what happens on failure, and the
frontend already does it - keep the pasted advert, say something useful, offer
manual creation. Falling back would hide a broken integration behind output that
looks plausible, which is the worst of both.

The detail goes to the log; the person pasting sees one sentence. An exception
message can carry an API key or an internal URL, and a paste box is not the place
for either. A test asserts that.

Cost accepted: a transient blip becomes a visible error rather than a quietly
worse answer. That is the intended trade.

## 19. The advert is untrusted input, and the prompt says so

The system prompt in `app/ai_model.py` states that the advert is untrusted text
pasted from the internet and that anything resembling an instruction inside it
should be ignored. The extraction schema has no field for the candidate's fit.

Why: a job advert is attacker-controllable text. The realistic risk here is
small - the output is a form the user reviews before anything is saved - but the
cost of saying so in the prompt is one paragraph.

Leaving fit out is `_docs/specs.md` §15.2 enforced by construction rather than by
instruction: a field the model cannot fill is a field it cannot invent.

Cost accepted: none worth the name.

## 20. Ruff and ty for the backend; no npm linter for the frontend

`ruff check` and `ruff format` over the whole backend, `ty check` over `app/`.
Both are dev dependencies, both run from `make lint` / `make types`, and
`make check` is lint + types + tests.

The frontend gets `frontend/check.mjs` instead of ESLint: a dependency-free
script that syntax-checks every module and cross-references imports against
exports - a path that does not resolve, a name that is not exported, an import
that is never used.

Why not ESLint: it means npm, a `node_modules` and a build-adjacent toolchain,
which #3 deliberately avoided. That is a real trade - a proper linter would catch
more - but reversing #3 is the user's call, not something to slip in through a
lint task. The script covers what actually breaks a no-build frontend: a typo'd
import path or a renamed export, neither of which shows up until the browser
reaches that line.

Why ty checks only `app/`: tests deliberately do things a checker cannot narrow -
`store.get_card(id).title`, where the fixture guarantees the card exists - and
littering them with assertions would make them harder to read for no gain in
safety. Ruff still covers everything.

Cost accepted: the frontend has no real linter, and adopting the formatter
reflowed twelve files in one commit.

## 21. CI runs the Makefile, not a copy of it

`.github/workflows/check.yml` runs `make lint`, `make types` and `make test` on
Linux for every push and pull request.

Why through the Makefile: two copies of "how to check this project" drift, and
the copy in CI is the one nobody runs locally until it breaks. This way the
commands a contributor runs and the commands that gate a merge are the same
strings.

This is what the `.gitattributes` LF pin (#12-adjacent) and the `python3`
detection in the Makefile were for - CI is the Linux environment that would have
found both the hard way.

Cost accepted: CI depends on the Makefile staying correct, so `make.ps1` is now
the copy that can drift instead. The two are short and the header of each says
to change them together.

## 22. `GET /` is public, and says nothing worth protecting

The API answers at `/` with its name, version, a one-line description, and where
the docs and the frontend are. No token needed.

Why public: the alternative is what it replaced - a bare "Not Found" to anyone
who opens the API in a browser. A 401 would be no better, because it tells
someone to authenticate before they know what they would be authenticating to.

Why it is boring: it is reachable by anyone, so it carries nothing a stranger
could not read in the repository. No counts - not even "12 cards", which is a
fact about somebody's job search - no account, no data. A test asserts the exact
set of keys, so adding a field to it is a deliberate act.

Adding it meant editing `PUBLIC` in `backend/tests/test_contract.py`, which is
the point of that set: opening a door should be a visible edit in a file called
"contract", not a line nobody notices in review. The contract test failed first
and was what caught the endpoint being undocumented.

Cost accepted: two public endpoints instead of one, and the description now
duplicates a sentence that also lives in the README and the spec.

## 23. The container is one process: the API serves the frontend

`make run` starts two servers and always will — the frontend has no build step
(#3), so a saved file is a reloaded page, and that is the right arrangement for
editing.

A deployment is the other case. The `Dockerfile` builds one image: a Node stage
runs `frontend/check.mjs` over the frontend, and the Python stage takes those
files and serves them from the API process. One port, one origin, no CORS.

Why not nginx in front of uvicorn: it is a second image, a second config file
and a second place the paths have to agree, in exchange for serving seventeen ES
modules and three stylesheets. Starlette's `StaticFiles` does that well at this
size, and the day it does not, the seam to change is one module.

The seam is `backend/app/frontend.py`, and it is off unless told otherwise:

    NEXTLANE_FRONTEND=/app/frontend   serve the app at `/`
    (unset)                           the two-server default, unchanged

Two consequences, both deliberate:

**`/` goes to whichever is in front of the user.** When this process serves the
app, `/` is the app and the `GET /` service info from #22 is not registered —
`app/main.py` picks one or the other. That endpoint is a sign pointing at the
door; when the door is right there the sign is noise. The API's own operations
are untouched in either arrangement, so `openapi.yaml` still describes the API
either way.

**`index.html` is rewritten on the way out**, to inject
`window.NEXTLANE_API_BASE = window.location.origin`. Without it the page would
call the `http://localhost:8001` default baked into `frontend/src/api/client.js`
and a container on any other host would load and then fail every request. The
origin rather than a baked-in URL, so one image works on localhost, behind a
reverse proxy, and under a different hostname without being rebuilt. The client
already documented that global as its override; this is the documented door, not
a new one.

Cost accepted: two ways to run the app instead of one, and
`backend/tests/test_frontend.py` is what keeps the second honest — that the mount catches the
assets without swallowing the API, that the API stays closed behind it, and that
the real `frontend/index.html` still takes the injection.

## 24. Postgres is a third implementation, not a migration

`NEXTLANE_DB` already said where the database was. It now also says which
database, because the shape of the setting is enough to tell:

    /some/path/nextlane.sqlite3          SQLite — the default, and a fresh clone
    :memory:                             the dict, for a throwaway run
    postgresql://user:pw@host/nextlane   Postgres

One setting rather than two. Two would let them disagree, and something would
then have to decide which of them won.

**SQLite stays the default and stays supported.** `make install && make run` on
a fresh clone must still give someone a working board without a server, a
container or a connection string, and `_docs/specs.md` §26 is explicit that this
project is not to spend itself on infrastructure. Postgres is what you point it
at when the data has to outlive the container.

`app/postgres_store.py` is `app/sqlite_store.py`'s schema in Postgres types —
`TIMESTAMPTZ`, `DATE`, `BOOLEAN`, `DOUBLE PRECISION` — behind the same `Store`
protocol, with hand-written SQL and no ORM for the same reason as #15. The three
differences that are not cosmetic:

* **A connection pool** rather than one connection behind a lock, because
  FastAPI runs sync endpoints on a threadpool and that is what psycopg's pool is
  for. The transaction boundary is the `_cursor()` block.
* **Every connection is pinned to UTC**, so a stored `createdAt` cannot mean
  something different depending on the server's timezone setting.
* **Seeding takes a transaction-scoped advisory lock.** Two containers starting
  at once against one empty database would otherwise both find it empty and both
  fill it — which SQLite, being one file and one process, never had to consider.

`psycopg[binary,pool]` is the one new dependency, and it was asked for before it
was added, as `AGENTS.md` requires. `binary` because it ships libpq and a
Windows contributor should not need a compiler; the alternatives were asyncpg,
which would have made the whole `Store` protocol async for throughput this app
will never notice, and SQLAlchemy, which #15 already turned down.

**The contract test is what makes the claim honest.** `tests/test_store.py` runs
one set of tests against all three implementations, so the Postgres runs need a
server: they skip unless `NEXTLANE_TEST_POSTGRES` points at a throwaway
database, and CI sets it against a `postgres:16-alpine` service container so
they run on every push. Locally, `make postgres` starts one and
`make test-postgres` uses it.

Cost accepted: a dependency a SQLite user does not need — imported lazily, so it
is never loaded unless a DSN asks for it — and a third implementation to keep in
step whenever the schema changes. The endpoint suite is still parametrised over
the dict and SQLite only, because tripling a hundred endpoint tests buys little
once the store contract holds; a handful of tests in `tests/test_dependencies.py`
cover the part that contract cannot, which is that a real request reaches a real
server.
