# NextLane — backend

FastAPI, serving the contract in [`../openapi.yaml`](../openapi.yaml), against a
mock database.

## Running it

```sh
make install    # from the repository root
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

## The mock database

`app/store.py` holds a `Store` Protocol and one implementation,
`InMemoryStore` — a few dicts that live as long as the process. Restarting the
server resets it to the seed data.

Swapping in a real database means writing a second implementation of that same
Protocol and returning it from `get_store` in `app/dependencies.py`.
Nothing in `app/service.py` or `app/routers/` changes, because nothing in them
knows how storage works. Tests already prove this seam works: each test overrides
that dependency with its own fresh store.

Two disciplines the mock imposes on purpose, because a real database imposes
them too:

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
│   ├── store.py         ← the storage seam (the mock database)
│   ├── auth.py          password hashing, tokens, the current_user dependency
│   ├── routers/         one module per group of endpoints
│   ├── domain.py        the vocabulary: areas, statuses, priorities (§28)
│   ├── service.py       the rules: column validity, completedAt, link bookkeeping
│   ├── dependencies.py  wiring; what tests override
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

- **No persistence.** See the mock database above.
- **No account management.** There is one seeded account and no way to register,
  change a password or reset one. §26 warns against spending half the project on
  account management, and nothing in the product needs more than this yet.
- **The AI endpoint is a regex parser**, not a model call. It is good enough to
  make the paste → preview → edit → confirm flow real, which is the part that
  matters: nothing it returns is ever saved without the user seeing it.
