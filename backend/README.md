# NextLane — backend

FastAPI, serving the contract in [`../openapi.yaml`](../openapi.yaml), against
Postgres.

## Running it

```sh
make install    # from the repository root
make postgres   # the database — once per reboot
make api        # just this; `make run` also starts the frontend
```

or directly:

```sh
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8001
```

- API: <http://localhost:8001/api/cards>
- Interactive docs: <http://localhost:8001/docs>

Port 8001 leaves 8000 for the static frontend, and CORS is already open to it.

**It can also serve that frontend itself**, which is how the container runs it
— one process, one port, one origin, no CORS:

```sh
NEXTLANE_FRONTEND=../frontend uv run uvicorn app.main:app --port 8000
```

Unset, nothing changes and the two-server arrangement above is what you get.
Set, `/` is the app rather than the service info, `index.html` is served with
`window.NEXTLANE_API_BASE` pointed at this origin, and everything under `/api`
is exactly where it was. `app/frontend.py` is the whole of it;
`_docs/decisions.md` #23 says why.

Every endpoint needs a token except login, so start there:

```sh
curl -s -X POST localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"researcher@example.com","password":"nextlane"}'
```

In `/docs`, use **Authorize** and paste the `token` from that response.

**The demo account is a development convenience.** It is seeded in the clear in
`app/auth.py` so a fresh clone can sign in. It has no place anywhere real.

## The tests

```sh
uv run pytest                       # the whole suite
uv run pytest tests/test_cards.py   # one module
uv run pytest -k archive            # one behaviour
```

They were written before the endpoints existed and they are the specification of
what the endpoints do. `tests/test_contract.py` is the one to watch: it compares
every path and method in `openapi.yaml` against the running app in both
directions, so the documentation cannot quietly drift from the code.

## The database

`app/store.py` holds a `Store` Protocol; `app/sqlite_store.py` implements it
against SQLite through the standard library's `sqlite3` — no ORM, no new
dependency. The schema is normalised rather than a JSON blob, because
`_docs/specs.md` §24 describes real relations and a blob would hide every one of
them from the database.

**`NEXTLANE_DB` chooses the database, and its shape chooses the
implementation:**

```sh
NEXTLANE_DB=postgresql://user:pw@host/nextlane   # a DSN   → Postgres (the default)
NEXTLANE_DB=/some/path/nextlane.sqlite3          # a path  → SQLite
NEXTLANE_DB=:memory:                             # the dict, for a throwaway run
```

One setting rather than two, because "where the data is" is one decision;
`app/dependencies.py` is the only place that reads it.

### Postgres, which is what this runs on

`app/postgres_store.py`. The same schema in Postgres types — `TIMESTAMPTZ`,
`DATE`, `BOOLEAN`, `DOUBLE PRECISION` — behind the same protocol, still
hand-written SQL and still no ORM. A connection pool rather than one locked
connection, every connection pinned to UTC, and seeding behind an advisory lock
so two containers starting at once against one empty database cannot both fill
it (`_docs/decisions.md` #24).

`psycopg[binary,pool]` is the only dependency it adds, and it is imported lazily
— a SQLite installation never loads it.

**There is one local Postgres**: the `db` service in `docker-compose.yaml`,
published on 55432. `make run` and `docker compose up` both use it, on purpose —
two servers is how work ends up invisible (#26). Two databases on it, `nextlane`
for the app and `nextlane_test` for the store contract.

Unset, `NEXTLANE_DB` points at exactly that. If it is not running you get a
message saying so, naming the database with the password stripped out.

### SQLite, which is the fallback

`app/sqlite_store.py`, one setting away, for a machine with no Docker:

```sh
NEXTLANE_DB=backend/nextlane.sqlite3
```

It is a first-class implementation and stays one — the store contract runs
against it on every push. It is simply not what you get by accident any more.
The file is gitignored and disposable: delete it and the next start reseeds.

### Running the suite against Postgres

```sh
make postgres        # the db service, if it is not already up
make test-postgres   # the whole suite, with NEXTLANE_TEST_POSTGRES set
```

Without that variable the Postgres runs skip and everything else is unaffected,
so `make test` still needs no server. CI always sets it, against a service
container, so the store contract really is checked against all three
implementations on every push.

**The implementations are interchangeable, and a test keeps them that way.**
`tests/test_store.py` runs one contract against all three, and `tests/conftest.py`
parametrises the whole API suite over the dict and SQLite — so every endpoint
test runs twice.
That is what turns "nothing above the seam can tell the difference" from a claim
into something checked. It has already earned its keep: running the API against
SQLite found a place where the dict silently allowed two accounts to share an
email address and SQLite did not.

Two disciplines `InMemoryStore` imposes on purpose, because a real database
imposes them too:

- **stored objects are copied on the way in and on the way out**, so holding a
  `Card` cannot let you mutate what is stored;
- **`list_cards` returns insertion order**, rather than whatever a dict felt
  like.

## Layout

```
backend/
├── app/
│   ├── main.py          FastAPI app, CORS, error handlers
│   ├── models.py        wire models — snake_case in Python, camelCase on the wire
│   ├── store.py         ← the storage seam, and the in-memory implementation
│   ├── sqlite_store.py  SQLite behind it — the default
│   ├── postgres_store.py  Postgres behind it — for deployments
│   ├── auth.py          password hashing, tokens, the current_user dependency
│   ├── routers/         one module per group of endpoints
│   ├── domain.py        the vocabulary: areas, statuses, priorities (§28)
│   ├── service.py       the rules: column validity, completedAt, link bookkeeping
│   ├── dependencies.py  wiring; what tests override
│   ├── frontend.py      serving the frontend, when NEXTLANE_FRONTEND says where
│   ├── seed.py          the §31 fixtures
│   └── ai.py            advert extraction — isolated, §27
└── tests/               written first
```

`service.py` is where the rules live, and they are worth knowing:

- **A status must belong to its board.** A Learning card cannot sit in the
  Current Job board's `WAITING` column; the attempt is a 422 naming the columns
  that are legal.
- **`completedAt` is the server's business.** It is stamped when a card enters
  its area's done column (`DONE`, `DONE`, `OFFER` respectively) and cleared when
  it leaves. Clients never set it.
- **Links move in pairs.** Linking a learning card to a job writes both
  `relatedJobCardIds` and `job.relatedLearningCardIds`, and deleting either card
  removes it from the other end. No card is left pointing at something that no
  longer exists.

## Reading job adverts

Two readers, one contract (`app/ai.py`):

| `NEXTLANE_AI` | Reader |
| --- | --- |
| `auto` (default) | the model when `ANTHROPIC_API_KEY` is set, the parser otherwise |
| `model` | always the model → `app/ai_model.py`, a Claude call with a validated schema |
| `heuristic` | always the built-in parser |

```sh
ANTHROPIC_API_KEY=sk-ant-... uv run uvicorn app.main:app --port 8001
```

Every result says which read it, in `source`. A regex's reading and a model's are
not the same quality, and a deployment that lost its API key should not quietly
look like a working one.

**The parser is kept, not deleted.** A fresh clone has no API key, and a
portfolio project that shows a broken feature to anyone who has not signed up for
an API account is worse than one that reads adverts a little less well. It also
means the test suite needs no credentials and no network.

**A failed model call is an error, not a downgrade.** When the model is the
configured reader and the call fails, the endpoint returns 422 with a friendly
message; §15.3 already says what happens next: the client keeps the pasted
text and offers manual entry. Falling back to the regex would hide a broken
integration behind output that looks plausible.

The advert is untrusted text pasted from the internet, and the system prompt says
so: an advert containing instructions is an advert to extract, not orders to
follow. The schema has no field for the candidate's fit, because §15.2 says
the app must not judge suitability - a field the model cannot fill is one it
cannot invent.

## Authentication

Every endpoint requires a bearer token except `POST /api/auth/login`.

NextLane holds someone's job search — which roles they want, what rejected them,
what they are quietly learning in order to leave. No part of it is safe to leave
open, so the default is closed and login is the single exception. Two contract
tests enforce that: a new endpoint that forgets its token requirement fails the
suite rather than production.

**Passwords** are hashed with `hashlib.scrypt` from the standard library — no
bcrypt, no passlib, no new dependency. Each password gets its own 16-byte salt,
and verification is `hmac.compare_digest`. Stored as
`scrypt$<salt-hex>$<hash-hex>`, so the scheme is named and can be migrated.

**Tokens** are `secrets.token_urlsafe(32)` — 256 bits from the OS CSPRNG — held
server-side and valid for 14 days. Deliberately not JWTs: a JWT cannot be
revoked without keeping the very same server-side list, and logout needs to mean
something. Logging out deletes the token; other sessions for that user survive,
so signing out of a laptop does not sign you out of a phone.

**A wrong password and an unknown email fail identically**, same status and same
body, and the unknown-email path still does the scrypt work so it cannot be
spotted by timing. Otherwise this endpoint becomes a way to discover which
addresses have accounts.

**What this is not: multi-tenancy.** §33 rules out multi-user collaboration and
§26 notes the first user is the developer, so authentication decides who may
open the workspace — it does not partition the data. Every authenticated user
sees the same board. A test records that explicitly, so making it per-user later
is a deliberate change rather than a surprise.

## Conventions worth knowing

- **The wire is camelCase.** Python stays snake_case and Pydantic's alias
  generator bridges the two, because `frontend/src/api/client.js` already speaks
  camelCase and the contract follows the frontend, not the other way round.
- **`extra="forbid"` on every model.** A typo'd field name is a 422, not a
  silently ignored write.
- **One error shape**, `{"message": ..., "kind": ...}`, including for validation
  failures. `message` is written to be shown to a person verbatim (§37) — which
  is why the handler rewrites Pydantic's default `detail` list into a sentence.

## Not done yet

- **No account management.** There is one seeded account and no way to register,
  change a password or reset one. §26 warns against spending half the project on
  account management, and nothing in the product needs more than this yet.
- **The model call is unverified against the real API.** The integration is
  written and tested against a stub, but no Anthropic API key was available
  when it was built, so nobody has yet watched Claude read an advert through
  it. The first person with a key should try it and say whether the prompt
  holds up.
