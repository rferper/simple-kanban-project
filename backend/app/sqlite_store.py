"""A real database behind the `Store` protocol — issue #19.

SQLite through the standard library's `sqlite3`. No ORM and no new dependency:
`AGENTS.md` says not to add one without asking, and this project has a habit of
reaching for the standard library first (scrypt rather than passlib, plain ES
modules rather than a framework). The schema is small enough that hand-written
SQL is clearer than the machinery to avoid it.

The schema is normalised rather than a JSON blob in a column, because
`_docs/specs.md` §24 describes real relations — a card's tags and subtasks, a
job's requirements, the job ↔ learning links — and a blob would make every one
of them invisible to the database.

**This class is interchangeable with `InMemoryStore` and stays that way.**
`tests/test_store.py` runs the same contract against both; a behaviour that
holds for the dict has to hold here.

One thing to know about the link tables: each card owns its own side of a job ↔
learning relationship, exactly as the in-memory store does. `app/service.py` is
what keeps the two ends in step, and moving that responsibility down here would
mean two places enforcing one rule.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.models import Card, JobDetails, Preferences, Subtask, TokenSession, User

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id                TEXT PRIMARY KEY,
    position          INTEGER NOT NULL,
    title             TEXT    NOT NULL,
    description       TEXT    NOT NULL DEFAULT '',
    area              TEXT    NOT NULL,
    status            TEXT    NOT NULL,
    priority          TEXT    NOT NULL,
    deadline          TEXT,
    estimated_hours   REAL,
    planned_this_week INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    completed_at      TEXT,
    -- Distinguishes a Learning card with no links (an empty list) from a card
    -- that cannot have any (null). The two are not the same thing.
    tracks_job_links  INTEGER NOT NULL DEFAULT 0
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
    done     INTEGER NOT NULL DEFAULT 0,
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
    application_deadline TEXT,
    interview_date       TEXT,
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
    weekly_available_hours REAL
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS tokens (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    expires_at TEXT NOT NULL
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


class SqliteStore:
    """The `Store` protocol, backed by a file on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # FastAPI runs sync endpoints on a threadpool, so the connection is
        # shared across threads and every operation takes the lock.
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._db.executescript(SCHEMA)
            row = self._db.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
                )
            elif row["version"] != SCHEMA_VERSION:
                # Nothing to migrate from yet. When there is, it branches here
                # rather than silently running against a schema it does not know.
                raise RuntimeError(
                    f"Database at {self.path} is schema version {row['version']}, "
                    f"this code expects {SCHEMA_VERSION}."
                )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------------ cards

    def list_cards(self) -> list[Card]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM cards ORDER BY position").fetchall()
            return [self._hydrate(row) for row in rows]

    def get_card(self, card_id: str) -> Card | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            return self._hydrate(row) if row else None

    def save_card(self, card: Card) -> Card:
        with self._lock:
            self._db.execute("BEGIN")
            try:
                existing = self._db.execute(
                    "SELECT position FROM cards WHERE id = ?", (card.id,)
                ).fetchone()

                if existing is None:
                    nxt = self._db.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 AS n FROM cards"
                    ).fetchone()["n"]
                    position = nxt
                else:
                    position = existing["position"]  # an update keeps its place

                self._db.execute(
                    """
                    INSERT INTO cards (
                        id, position, title, description, area, status, priority,
                        deadline, estimated_hours, planned_this_week,
                        created_at, updated_at, completed_at, tracks_job_links
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        _text(card.deadline),
                        card.estimated_hours,
                        int(card.planned_this_week),
                        _text(card.created_at),
                        _text(card.updated_at),
                        _text(card.completed_at),
                        int(card.related_job_card_ids is not None),
                    ),
                )

                # Child rows are replaced wholesale: a card's tags, subtasks and
                # links are the card's, not accumulated history.
                for table in (
                    "card_tags",
                    "subtasks",
                    "job_requirements",
                    "learning_job_links",
                    "job_learning_links",
                ):
                    self._db.execute(f"DELETE FROM {table} WHERE card_id = ?", (card.id,))

                self._db.executemany(
                    "INSERT INTO card_tags (card_id, position, tag) VALUES (?,?,?)",
                    [(card.id, i, tag) for i, tag in enumerate(card.tags)],
                )
                self._db.executemany(
                    "INSERT INTO subtasks (card_id, id, position, title, done) VALUES (?,?,?,?,?)",
                    [(card.id, s.id, i, s.title, int(s.done)) for i, s in enumerate(card.subtasks)],
                )
                self._db.executemany(
                    "INSERT INTO learning_job_links (card_id, position, job_card_id) VALUES (?,?,?)",
                    [(card.id, i, j) for i, j in enumerate(card.related_job_card_ids or [])],
                )

                if card.job is None:
                    self._db.execute("DELETE FROM job_details WHERE card_id = ?", (card.id,))
                else:
                    self._save_job(card.id, card.job)

                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

        return self._reread(self.get_card(card.id), card.id)

    def _reread(self, value, what: str):
        """A row read back immediately after writing it in the same connection.

        `None` here would mean the write silently did not happen, which is worth
        a loud failure rather than a confusing one further downstream.
        """
        if value is None:
            raise RuntimeError(f"{what} vanished immediately after being written")
        return value

    def _save_job(self, card_id: str, job: JobDetails) -> None:
        columns = ", ".join(JOB_COLUMNS)
        placeholders = ", ".join("?" for _ in JOB_COLUMNS)
        updates = ", ".join(f"{c} = excluded.{c}" for c in JOB_COLUMNS)
        values = [_text(getattr(job, column)) for column in JOB_COLUMNS]

        self._db.execute(
            f"""INSERT INTO job_details (card_id, {columns})
                VALUES (?, {placeholders})
                ON CONFLICT (card_id) DO UPDATE SET {updates}""",
            [card_id, *values],
        )
        self._db.executemany(
            "INSERT INTO job_requirements (card_id, kind, position, text) VALUES (?,?,?,?)",
            [(card_id, "required", i, t) for i, t in enumerate(job.requirements)]
            + [(card_id, "nice", i, t) for i, t in enumerate(job.nice_to_have)],
        )
        self._db.executemany(
            "INSERT INTO job_learning_links (card_id, position, learning_card_id) VALUES (?,?,?)",
            [(card_id, i, learning) for i, learning in enumerate(job.related_learning_card_ids)],
        )

    def delete_card(self, card_id: str) -> bool:
        with self._lock:
            cursor = self._db.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            return cursor.rowcount > 0

    def _hydrate(self, row: sqlite3.Row) -> Card:
        card_id = row["id"]

        tags = [
            r["tag"]
            for r in self._db.execute(
                "SELECT tag FROM card_tags WHERE card_id = ? ORDER BY position", (card_id,)
            )
        ]
        subtasks = [
            Subtask(id=r["id"], title=r["title"], done=bool(r["done"]))
            for r in self._db.execute(
                "SELECT id, title, done FROM subtasks WHERE card_id = ? ORDER BY position",
                (card_id,),
            )
        ]

        links = None
        if row["tracks_job_links"]:
            links = [
                r["job_card_id"]
                for r in self._db.execute(
                    "SELECT job_card_id FROM learning_job_links WHERE card_id = ? ORDER BY position",
                    (card_id,),
                )
            ]

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
            planned_this_week=bool(row["planned_this_week"]),
            tags=tags,
            subtasks=subtasks,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            job=self._hydrate_job(card_id),
            related_job_card_ids=links,
        )

    def _hydrate_job(self, card_id: str) -> JobDetails | None:
        row = self._db.execute("SELECT * FROM job_details WHERE card_id = ?", (card_id,)).fetchone()
        if row is None:
            return None

        requirements = {"required": [], "nice": []}
        for r in self._db.execute(
            "SELECT kind, text FROM job_requirements WHERE card_id = ? ORDER BY kind, position",
            (card_id,),
        ):
            requirements[r["kind"]].append(r["text"])

        linked = [
            r["learning_card_id"]
            for r in self._db.execute(
                "SELECT learning_card_id FROM job_learning_links WHERE card_id = ? ORDER BY position",
                (card_id,),
            )
        ]

        return JobDetails(
            **{str(column): row[column] for column in JOB_COLUMNS},
            requirements=requirements["required"],
            nice_to_have=requirements["nice"],
            related_learning_card_ids=linked,
        )

    # ------------------------------------------------------------ preferences

    def get_preferences(self) -> Preferences:
        with self._lock:
            row = self._db.execute("SELECT * FROM preferences WHERE id = 1").fetchone()
        if row is None:
            return Preferences()
        return Preferences(
            display_name=row["display_name"],
            weekly_available_hours=row["weekly_available_hours"],
        )

    def save_preferences(self, preferences: Preferences) -> Preferences:
        with self._lock:
            self._db.execute(
                """INSERT INTO preferences (id, display_name, weekly_available_hours)
                   VALUES (1, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET
                       display_name = excluded.display_name,
                       weekly_available_hours = excluded.weekly_available_hours""",
                (preferences.display_name, preferences.weekly_available_hours),
            )
        return self.get_preferences()

    # ------------------------------------------------------------------ users

    def get_user(self, user_id: str) -> User | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._hydrate_user(row)

    def get_user_by_email(self, email: str) -> User | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),)
            ).fetchone()
        return self._hydrate_user(row)

    def save_user(self, user: User) -> User:
        with self._lock:
            clash = self._db.execute(
                "SELECT id FROM users WHERE LOWER(email) = ? AND id <> ?",
                (user.email.strip().lower(), user.id),
            ).fetchone()
            if clash is not None:
                raise ValueError(f"another account already uses {user.email}")

            self._db.execute(
                """INSERT INTO users (id, email, display_name, password_hash, created_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT (id) DO UPDATE SET
                       email = excluded.email,
                       display_name = excluded.display_name,
                       password_hash = excluded.password_hash,
                       created_at = excluded.created_at""",
                (
                    user.id,
                    user.email,
                    user.display_name,
                    user.password_hash,
                    _text(user.created_at),
                ),
            )
        return self._reread(self.get_user(user.id), f"user {user.id}")

    @staticmethod
    def _hydrate_user(row: sqlite3.Row | None) -> User | None:
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
        with self._lock:
            row = self._db.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        if row is None:
            return None
        return TokenSession(
            token=row["token"], user_id=row["user_id"], expires_at=row["expires_at"]
        )

    def save_token(self, token: str, user_id: str, expires_at: datetime) -> TokenSession:
        with self._lock:
            self._db.execute(
                """INSERT INTO tokens (token, user_id, expires_at) VALUES (?,?,?)
                   ON CONFLICT (token) DO UPDATE SET
                       user_id = excluded.user_id,
                       expires_at = excluded.expires_at""",
                (token, user_id, _text(expires_at)),
            )
        return self._reread(self.get_token(token), "token")

    def delete_token(self, token: str) -> bool:
        with self._lock:
            return self._db.execute("DELETE FROM tokens WHERE token = ?", (token,)).rowcount > 0

    def delete_tokens_for(self, user_id: str) -> int:
        with self._lock:
            return self._db.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,)).rowcount

    # ----------------------------------------------------------------- seeding

    def seed(self) -> None:
        """Fill an empty database with the §31 fixtures. Does nothing otherwise."""
        from app.auth import build_demo_user
        from app.seed import build_seed

        with self._lock:
            if self._db.execute("SELECT 1 FROM cards LIMIT 1").fetchone():
                return

            cards, preferences = build_seed()
            for card in cards:
                self.save_card(card)
            self.save_preferences(preferences)
            if self.get_user_by_email("researcher@example.com") is None:
                self.save_user(build_demo_user())


def _text(value) -> str | None:
    """Dates and datetimes go in as ISO strings; Pydantic parses them back."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
