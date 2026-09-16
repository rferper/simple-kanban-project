"""Postgres behind the `Store` protocol — what NextLane runs on.

`make postgres` starts one locally, `docker-compose.yaml` runs one beside the
app, and `app/dependencies.py` points at the first of those unless `NEXTLANE_DB`
says otherwise. `app/sqlite_store.py` is still there and still supported, for a
machine with no Docker (`_docs/decisions.md` #26).

**It is one implementation of a contract, not a second way to write the
backend.** `tests/test_store.py` runs the same tests against the dict, SQLite
and this; `app/service.py`, `app/auth.py` and the routers cannot tell which one
they have. The schema below is `app/sqlite_store.py`'s schema in Postgres
types: normalised for the same reason (`_docs/specs.md` §24 describes real
relations), and with each card owning its own side of a job ↔ learning link
because `app/service.py` is the one place that keeps the two ends in step.

What is genuinely different from SQLite, and why:

* **Real column types.** `TIMESTAMPTZ`, `DATE`, `BOOLEAN`, `DOUBLE PRECISION`
  rather than SQLite's ISO strings and integers. Every connection is pinned to
  UTC, so a timestamp comes back the way it went in whatever the server's own
  timezone is set to.
* **A connection pool** rather than one connection behind a lock. FastAPI runs
  sync endpoints on a threadpool, which is what psycopg's pool is built for.
* **Seeding takes an advisory lock.** Two containers starting at once against
  one empty database would otherwise both find it empty and both fill it.

Selected by the DSN: `NEXTLANE_DB=postgresql://user:password@host/nextlane`.
See `app/dependencies.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.models import Card, JobDetails, Preferences, Subtask, TokenSession, User

SCHEMA_VERSION = 1

#: Arbitrary but fixed: the key two starting processes agree to queue on before
#: either decides an empty database is theirs to fill.
SEED_LOCK = 0x4E4C5345  # "NLSE"

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id                TEXT PRIMARY KEY,
    position          INTEGER          NOT NULL,
    title             TEXT             NOT NULL,
    description       TEXT             NOT NULL DEFAULT '',
    area              TEXT             NOT NULL,
    status            TEXT             NOT NULL,
    priority          TEXT             NOT NULL,
    deadline          DATE,
    estimated_hours   DOUBLE PRECISION,
    planned_this_week BOOLEAN          NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ      NOT NULL,
    updated_at        TIMESTAMPTZ      NOT NULL,
    completed_at      TIMESTAMPTZ,
    -- Distinguishes a Learning card with no links (an empty list) from a card
    -- that cannot have any (null). The two are not the same thing.
    tracks_job_links  BOOLEAN          NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS cards_area_status ON cards (area, status);
CREATE INDEX IF NOT EXISTS cards_position    ON cards (position);

CREATE TABLE IF NOT EXISTS card_tags (
    card_id  TEXT    NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    tag      TEXT    NOT NULL,
    PRIMARY KEY (card_id, position)
);

CREATE TABLE IF NOT EXISTS subtasks (
    card_id  TEXT    NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
    id       TEXT    NOT NULL,
    position INTEGER NOT NULL,
    title    TEXT    NOT NULL,
    done     BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (card_id, id)
);

CREATE TABLE IF NOT EXISTS job_details (
    card_id              TEXT PRIMARY KEY REFERENCES cards (id) ON DELETE CASCADE,
    company              TEXT NOT NULL DEFAULT '',
    role                 TEXT NOT NULL DEFAULT '',
    job_url              TEXT NOT NULL DEFAULT '',
    location             TEXT NOT NULL DEFAULT '',
    salary_text          TEXT NOT NULL DEFAULT '',
    work_mode            TEXT NOT NULL DEFAULT 'UNKNOWN',
    contact_name         TEXT NOT NULL DEFAULT '',
    contact_details      TEXT NOT NULL DEFAULT '',
    job_description      TEXT NOT NULL DEFAULT '',
    application_deadline DATE,
    interview_date       DATE,
    cv_version           TEXT NOT NULL DEFAULT '',
    fit                  TEXT NOT NULL DEFAULT 'MEDIUM',
    outcome              TEXT NOT NULL DEFAULT 'ACTIVE',
    notes                TEXT NOT NULL DEFAULT ''
);

-- Requirements and nice-to-haves share a table; `kind` tells them apart.
CREATE TABLE IF NOT EXISTS job_requirements (
    card_id  TEXT    NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
    kind     TEXT    NOT NULL,
    position INTEGER NOT NULL,
    text     TEXT    NOT NULL,
    PRIMARY KEY (card_id, kind, position)
);

-- Each card owns its own side of the relationship (§9.3).
CREATE TABLE IF NOT EXISTS learning_job_links (
    card_id     TEXT    NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    job_card_id TEXT    NOT NULL,
    PRIMARY KEY (card_id, job_card_id)
);

CREATE TABLE IF NOT EXISTS job_learning_links (
    card_id          TEXT    NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    learning_card_id TEXT    NOT NULL,
    PRIMARY KEY (card_id, learning_card_id)
);

CREATE TABLE IF NOT EXISTS preferences (
    id                     INTEGER PRIMARY KEY CHECK (id = 1),
    display_name           TEXT NOT NULL DEFAULT '',
    weekly_available_hours DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT        NOT NULL,
    display_name  TEXT        NOT NULL DEFAULT '',
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS tokens (
    token      TEXT        PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS tokens_user ON tokens (user_id);
"""

JOB_COLUMNS = (
    "company",
    "role",
    "job_url",
    "location",
    "salary_text",
    "work_mode",
    "contact_name",
    "contact_details",
    "job_description",
    "application_deadline",
    "interview_date",
    "cv_version",
    "fit",
    "outcome",
    "notes",
)

#: Replaced wholesale on every write: a card's tags, subtasks and links are the
#: card's current state, not accumulated history.
CHILD_TABLES = (
    "card_tags",
    "subtasks",
    "job_requirements",
    "learning_job_links",
    "job_learning_links",
)


class PostgresStore:
    """The `Store` protocol, backed by a Postgres server."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 8) -> None:
        self.dsn = dsn

        # One plain connection before the pool exists, purely to fail well. A
        # pool answers an unreachable server by retrying in the background, so
        # the first symptom would be a request timing out half a minute later
        # with a message that names neither the database nor the fix.
        try:
            psycopg.connect(dsn, connect_timeout=5).close()
        except psycopg.OperationalError as unreachable:
            # libpq's own reason distinguishes "nothing is listening" from
            # "wrong password", which the two hints below cannot. It names the
            # user but never the password.
            reason = str(unreachable).strip().splitlines()[0]
            raise RuntimeError(
                f"Cannot reach Postgres at {safe_dsn(dsn)}\n"
                f"  {reason}\n"
                "  Start the development database:  make postgres\n"
                "  Or use a file instead:           NEXTLANE_DB=backend/nextlane.sqlite3"
            ) from unreachable

        self._pool = ConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            open=True,
            # Waiting half a minute to be told the server is not there is not
            # useful to anyone. This is how long a request waits for a
            # connection, and on startup it is how long a wrong DSN takes to
            # say so.
            timeout=10,
            kwargs={
                # Timestamps go in and come out UTC whatever the server is set
                # to, so this cannot disagree with SQLite about what a stored
                # `createdAt` means.
                "options": "-c timezone=UTC",
            },
        )

        self._migrate()

    @contextmanager
    def _cursor(self) -> Iterator[psycopg.Cursor[DictRow]]:
        """A cursor on a pooled connection, and a transaction around the block.

        psycopg commits when the connection's block ends and rolls back if it
        leaves by an exception, so every method below is atomic without saying
        so. The row factory is set here rather than on the connection because
        this is where it can be seen: `cursor()` is what carries the row type.
        """
        with (
            self._pool.connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            yield cursor

    def _migrate(self) -> None:
        with self._cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            if row is None:
                cur.execute("INSERT INTO schema_version (version) VALUES (%s)", (SCHEMA_VERSION,))
            elif row["version"] != SCHEMA_VERSION:
                # Nothing to migrate from yet. When there is, it branches here
                # rather than silently running against a schema it does not know.
                raise RuntimeError(
                    f"Database at {safe_dsn(self.dsn)} is schema version {row['version']}, "
                    f"this code expects {SCHEMA_VERSION}."
                )

    def close(self) -> None:
        self._pool.close()

    # ------------------------------------------------------------------ cards

    def list_cards(self) -> list[Card]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cards ORDER BY position")
            # Drained before hydrating, because hydration reuses this cursor.
            rows = cur.fetchall()
            return [self._hydrate(cur, row) for row in rows]

    def get_card(self, card_id: str) -> Card | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cards WHERE id = %s", (card_id,))
            row = cur.fetchone()
            return self._hydrate(cur, row) if row else None

    def save_card(self, card: Card) -> Card:
        with self._cursor() as cur:
            self._save_card(cur, card)
        return self._reread(self.get_card(card.id), card.id)

    def _save_card(self, cur: psycopg.Cursor[DictRow], card: Card) -> None:
        """The write itself, on a caller's cursor, so seeding can batch them."""
        cur.execute("SELECT position FROM cards WHERE id = %s", (card.id,))
        existing = cur.fetchone()

        if existing is None:
            cur.execute("SELECT COALESCE(MAX(position), -1) + 1 AS n FROM cards")
            position = self._reread(cur.fetchone(), "the next position")["n"]
        else:
            position = existing["position"]  # an update keeps its place

        cur.execute(
            """
            INSERT INTO cards (
                id, position, title, description, area, status, priority,
                deadline, estimated_hours, planned_this_week,
                created_at, updated_at, completed_at, tracks_job_links
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                area = excluded.area,
                status = excluded.status,
                priority = excluded.priority,
                deadline = excluded.deadline,
                estimated_hours = excluded.estimated_hours,
                planned_this_week = excluded.planned_this_week,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                completed_at = excluded.completed_at,
                tracks_job_links = excluded.tracks_job_links
            """,
            (
                card.id,
                position,
                card.title,
                card.description,
                card.area,
                card.status,
                card.priority,
                card.deadline,
                card.estimated_hours,
                card.planned_this_week,
                card.created_at,
                card.updated_at,
                card.completed_at,
                card.related_job_card_ids is not None,
            ),
        )

        for table in CHILD_TABLES:
            cur.execute(f"DELETE FROM {table} WHERE card_id = %s", (card.id,))

        cur.executemany(
            "INSERT INTO card_tags (card_id, position, tag) VALUES (%s,%s,%s)",
            [(card.id, i, tag) for i, tag in enumerate(card.tags)],
        )
        cur.executemany(
            "INSERT INTO subtasks (card_id, id, position, title, done) VALUES (%s,%s,%s,%s,%s)",
            [(card.id, s.id, i, s.title, s.done) for i, s in enumerate(card.subtasks)],
        )
        cur.executemany(
            "INSERT INTO learning_job_links (card_id, position, job_card_id) VALUES (%s,%s,%s)",
            [(card.id, i, j) for i, j in enumerate(card.related_job_card_ids or [])],
        )

        if card.job is None:
            cur.execute("DELETE FROM job_details WHERE card_id = %s", (card.id,))
        else:
            self._save_job(cur, card.id, card.job)

    @staticmethod
    def _save_job(cur: psycopg.Cursor[DictRow], card_id: str, job: JobDetails) -> None:
        columns = ", ".join(JOB_COLUMNS)
        placeholders = ", ".join("%s" for _ in JOB_COLUMNS)
        updates = ", ".join(f"{c} = excluded.{c}" for c in JOB_COLUMNS)
        values = [getattr(job, column) for column in JOB_COLUMNS]

        cur.execute(
            f"""INSERT INTO job_details (card_id, {columns})
                VALUES (%s, {placeholders})
                ON CONFLICT (card_id) DO UPDATE SET {updates}""",
            [card_id, *values],
        )
        cur.executemany(
            "INSERT INTO job_requirements (card_id, kind, position, text) VALUES (%s,%s,%s,%s)",
            [(card_id, "required", i, t) for i, t in enumerate(job.requirements)]
            + [(card_id, "nice", i, t) for i, t in enumerate(job.nice_to_have)],
        )
        cur.executemany(
            "INSERT INTO job_learning_links (card_id, position, learning_card_id)"
            " VALUES (%s,%s,%s)",
            [(card_id, i, learning) for i, learning in enumerate(job.related_learning_card_ids)],
        )

    def delete_card(self, card_id: str) -> bool:
        with self._cursor() as cur:
            cur.execute("DELETE FROM cards WHERE id = %s", (card_id,))
            return cur.rowcount > 0

    def _hydrate(self, cur: psycopg.Cursor[DictRow], row: DictRow) -> Card:
        card_id = row["id"]

        cur.execute("SELECT tag FROM card_tags WHERE card_id = %s ORDER BY position", (card_id,))
        tags = [r["tag"] for r in cur.fetchall()]

        cur.execute(
            "SELECT id, title, done FROM subtasks WHERE card_id = %s ORDER BY position",
            (card_id,),
        )
        subtasks = [Subtask(id=r["id"], title=r["title"], done=r["done"]) for r in cur.fetchall()]

        links = None
        if row["tracks_job_links"]:
            cur.execute(
                "SELECT job_card_id FROM learning_job_links WHERE card_id = %s ORDER BY position",
                (card_id,),
            )
            links = [r["job_card_id"] for r in cur.fetchall()]

        # Spelled out rather than built as a dict and splatted: the columns are
        # heterogeneous, and `Card(**data)` cannot be type-checked.
        return Card(
            id=card_id,
            title=row["title"],
            description=row["description"],
            area=row["area"],
            status=row["status"],
            priority=row["priority"],
            deadline=row["deadline"],
            estimated_hours=row["estimated_hours"],
            planned_this_week=row["planned_this_week"],
            tags=tags,
            subtasks=subtasks,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            job=self._hydrate_job(cur, card_id),
            related_job_card_ids=links,
        )

    @staticmethod
    def _hydrate_job(cur: psycopg.Cursor[DictRow], card_id: str) -> JobDetails | None:
        cur.execute("SELECT * FROM job_details WHERE card_id = %s", (card_id,))
        row = cur.fetchone()
        if row is None:
            return None

        cur.execute(
            "SELECT kind, text FROM job_requirements WHERE card_id = %s ORDER BY kind, position",
            (card_id,),
        )
        requirements: dict[str, list[str]] = {"required": [], "nice": []}
        for r in cur.fetchall():
            requirements[r["kind"]].append(r["text"])

        cur.execute(
            "SELECT learning_card_id FROM job_learning_links WHERE card_id = %s ORDER BY position",
            (card_id,),
        )
        linked = [r["learning_card_id"] for r in cur.fetchall()]

        return JobDetails(
            **{str(column): row[column] for column in JOB_COLUMNS},
            requirements=requirements["required"],
            nice_to_have=requirements["nice"],
            related_learning_card_ids=linked,
        )

    # ------------------------------------------------------------ preferences

    def get_preferences(self) -> Preferences:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM preferences WHERE id = 1")
            row = cur.fetchone()
        if row is None:
            return Preferences()
        return Preferences(
            display_name=row["display_name"],
            weekly_available_hours=row["weekly_available_hours"],
        )

    def save_preferences(self, preferences: Preferences) -> Preferences:
        with self._cursor() as cur:
            self._save_preferences(cur, preferences)
        return self.get_preferences()

    @staticmethod
    def _save_preferences(cur: psycopg.Cursor[DictRow], preferences: Preferences) -> None:
        cur.execute(
            """INSERT INTO preferences (id, display_name, weekly_available_hours)
               VALUES (1, %s, %s)
               ON CONFLICT (id) DO UPDATE SET
                   display_name = excluded.display_name,
                   weekly_available_hours = excluded.weekly_available_hours""",
            (preferences.display_name, preferences.weekly_available_hours),
        )

    # ------------------------------------------------------------------ users

    def get_user(self, user_id: str) -> User | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return self._hydrate_user(cur.fetchone())

    def get_user_by_email(self, email: str) -> User | None:
        with self._cursor() as cur:
            return self._hydrate_user(self._find_user_by_email(cur, email))

    def save_user(self, user: User) -> User:
        with self._cursor() as cur:
            self._save_user(cur, user)
        return self._reread(self.get_user(user.id), f"user {user.id}")

    @staticmethod
    def _find_user_by_email(cur: psycopg.Cursor[DictRow], email: str) -> DictRow | None:
        cur.execute("SELECT * FROM users WHERE LOWER(email) = %s", (email.strip().lower(),))
        return cur.fetchone()

    @staticmethod
    def _save_user(cur: psycopg.Cursor[DictRow], user: User) -> None:
        cur.execute(
            "SELECT id FROM users WHERE LOWER(email) = %s AND id <> %s",
            (user.email.strip().lower(), user.id),
        )
        if cur.fetchone() is not None:
            raise ValueError(f"another account already uses {user.email}")

        try:
            cur.execute(
                """INSERT INTO users (id, email, display_name, password_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                       email = excluded.email,
                       display_name = excluded.display_name,
                       password_hash = excluded.password_hash,
                       created_at = excluded.created_at""",
                (user.id, user.email, user.display_name, user.password_hash, user.created_at),
            )
        except psycopg.errors.UniqueViolation as clash:
            # The check above lost a race with another connection. The answer is
            # the same either way, so callers never have to know which happened.
            raise ValueError(f"another account already uses {user.email}") from clash

    @staticmethod
    def _hydrate_user(row: DictRow | None) -> User | None:
        if row is None:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )

    # ----------------------------------------------------------------- tokens

    def get_token(self, token: str) -> TokenSession | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tokens WHERE token = %s", (token,))
            row = cur.fetchone()
        if row is None:
            return None
        return TokenSession(
            token=row["token"], user_id=row["user_id"], expires_at=row["expires_at"]
        )

    def save_token(self, token: str, user_id: str, expires_at: datetime) -> TokenSession:
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO tokens (token, user_id, expires_at) VALUES (%s,%s,%s)
                   ON CONFLICT (token) DO UPDATE SET
                       user_id = excluded.user_id,
                       expires_at = excluded.expires_at""",
                (token, user_id, expires_at),
            )
        return self._reread(self.get_token(token), "token")

    def delete_token(self, token: str) -> bool:
        with self._cursor() as cur:
            cur.execute("DELETE FROM tokens WHERE token = %s", (token,))
            return cur.rowcount > 0

    def delete_tokens_for(self, user_id: str) -> int:
        with self._cursor() as cur:
            cur.execute("DELETE FROM tokens WHERE user_id = %s", (user_id,))
            return cur.rowcount

    # ---------------------------------------------------------------- seeding

    def seed(self) -> None:
        """Fill an empty database with the §31 fixtures. Does nothing otherwise.

        One transaction, behind an advisory lock. Two containers starting at
        once against one empty database would otherwise both find it empty and
        both fill it. The lock is transaction-scoped, so the commit or the
        rollback releases it and a process that dies holding it releases it too.
        """
        from app.auth import build_demo_user
        from app.seed import build_seed

        with self._cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (SEED_LOCK,))

            cur.execute("SELECT 1 FROM cards LIMIT 1")
            if cur.fetchone():
                return

            cards, preferences = build_seed()
            for card in cards:
                self._save_card(cur, card)
            self._save_preferences(cur, preferences)
            if self._find_user_by_email(cur, "researcher@example.com") is None:
                self._save_user(cur, build_demo_user())

    # ----------------------------------------------------------------- shared

    @staticmethod
    def _reread(value, what):
        """A row read back immediately after writing it.

        `None` here would mean the write silently did not happen, which is worth
        a loud failure rather than a confusing one further downstream.
        """
        if value is None:
            raise RuntimeError(f"{what} vanished immediately after being written")
        return value


def safe_dsn(dsn: str) -> str:
    """A DSN with the password taken out, for error messages.

    A connection string is the one piece of configuration that routinely carries
    a secret, and the messages it appears in are the ones that end up in a log
    or a screenshot.
    """
    scheme, separator, rest = dsn.partition("://")
    if not separator or "@" not in rest:
        return dsn

    credentials, _, host = rest.rpartition("@")
    user, has_password, _ = credentials.partition(":")
    return f"{scheme}://{user}:***@{host}" if has_password else dsn
