"""The storage contract, run against every implementation of it.

Issue #19 swaps the in-memory store for a real database. The point of the `Store`
protocol is that nothing above it can tell the difference, so these tests are
written once and parametrised over every implementation. A behaviour that holds
for the dict must hold for SQLite and for Postgres, or the seam is a fiction.

Anything specific to durability — surviving a restart — is at the bottom, since
the in-memory store cannot and is not meant to.

**Postgres needs a server, so those runs skip unless you point them at one:**

    NEXTLANE_TEST_POSTGRES=postgresql://postgres:nextlane@localhost/nextlane_test

Point it at a throwaway database. Every test empties the NextLane tables before
it runs. CI sets it, against a `postgres:16-alpine` service container, so the
contract is checked against all three implementations on every push.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.auth import build_demo_user
from app.models import Card, JobDetails, Preferences, Subtask
from app.sqlite_store import SqliteStore
from app.store import InMemoryStore
from tests.conftest import POSTGRES_DSN


@pytest.fixture(params=["memory", "sqlite", "postgres"])
def store(request, tmp_path):
    """Every test in this module runs once per implementation."""
    if request.param == "memory":
        return InMemoryStore()
    if request.param == "sqlite":
        return SqliteStore(tmp_path / "nextlane.sqlite3")
    return request.getfixturevalue("empty_postgres")


def now():
    return datetime.now(UTC)


def a_card(**overrides) -> Card:
    values = dict(
        id="card-1",
        title="Finish the rebuttal",
        description="",
        area="CURRENT_JOB",
        status="BACKLOG",
        priority="MEDIUM",
        deadline=None,
        estimated_hours=None,
        planned_this_week=False,
        tags=[],
        subtasks=[],
        created_at=now(),
        updated_at=now(),
        completed_at=None,
    )
    values.update(overrides)
    return Card(**values)


def a_job_card(**overrides) -> Card:
    values = dict(
        id="card-job",
        area="JOB_SEARCH",
        status="INTERESTING",
        title="Anthropic — Research Engineer",
        job=JobDetails(company="Anthropic", role="Research Engineer"),
    )
    values.update(overrides)
    return a_card(**values)


def a_learning_card(**overrides) -> Card:
    values = dict(
        id="card-learning",
        area="LEARNING",
        status="IDEAS",
        title="System design",
        related_job_card_ids=[],
    )
    values.update(overrides)
    return a_card(**values)


class TestCards:
    def test_an_empty_store_has_no_cards(self, store):
        assert store.list_cards() == []

    def test_a_saved_card_can_be_read_back(self, store):
        store.save_card(a_card(title="Review the paper"))
        assert store.get_card("card-1").title == "Review the paper"

    def test_an_unknown_card_is_none(self, store):
        assert store.get_card("nope") is None

    def test_saving_twice_updates_rather_than_duplicates(self, store):
        store.save_card(a_card(title="First"))
        store.save_card(a_card(title="Second"))
        assert len(store.list_cards()) == 1
        assert store.get_card("card-1").title == "Second"

    def test_cards_come_back_in_insertion_order(self, store):
        for i in range(5):
            store.save_card(a_card(id=f"card-{i}", title=f"Task {i}"))
        assert [c.id for c in store.list_cards()] == [f"card-{i}" for i in range(5)]

    def test_order_survives_an_update(self, store):
        for i in range(3):
            store.save_card(a_card(id=f"card-{i}"))
        store.save_card(a_card(id="card-0", title="Edited"))
        assert [c.id for c in store.list_cards()] == ["card-0", "card-1", "card-2"]

    def test_deleting(self, store):
        store.save_card(a_card())
        assert store.delete_card("card-1") is True
        assert store.get_card("card-1") is None

    def test_deleting_something_absent_says_so(self, store):
        assert store.delete_card("nope") is False

    def test_what_comes_out_is_a_copy(self, store):
        """Holding a card must not let you edit what is stored."""
        store.save_card(a_card(title="Original"))
        fetched = store.get_card("card-1")
        fetched.title = "Tampered"
        assert store.get_card("card-1").title == "Original"

    def test_what_goes_in_is_a_copy(self, store):
        card = a_card(title="Original")
        store.save_card(card)
        card.title = "Tampered"
        assert store.get_card("card-1").title == "Original"


class TestCardFidelity:
    """Every field has to survive the round trip, not just the easy ones."""

    def test_scalars(self, store):
        store.save_card(
            a_card(
                description="Two lines\nof description",
                priority="URGENT",
                status="IN_PROGRESS",
                deadline="2026-11-30",
                estimated_hours=1.5,
                planned_this_week=True,
            )
        )
        card = store.get_card("card-1")

        assert card.description == "Two lines\nof description"
        assert card.priority == "URGENT"
        assert card.status == "IN_PROGRESS"
        assert str(card.deadline) == "2026-11-30"
        assert card.estimated_hours == 1.5
        assert card.planned_this_week is True

    def test_null_scalars_stay_null(self, store):
        store.save_card(a_card(deadline=None, estimated_hours=None, completed_at=None))
        card = store.get_card("card-1")
        assert card.deadline is None
        assert card.estimated_hours is None
        assert card.completed_at is None

    def test_zero_is_not_null(self, store):
        """§22 — an unestimated card and a zero-hour card mean different things."""
        store.save_card(a_card(estimated_hours=0))
        assert store.get_card("card-1").estimated_hours == 0

    def test_timestamps(self, store):
        created = now() - timedelta(days=3)
        completed = now()
        store.save_card(a_card(created_at=created, updated_at=created, completed_at=completed))
        card = store.get_card("card-1")

        assert abs((card.created_at - created).total_seconds()) < 1
        assert abs((card.completed_at - completed).total_seconds()) < 1

    def test_tags_keep_their_order(self, store):
        store.save_card(a_card(tags=["research", "AI safety", "paper"]))
        assert store.get_card("card-1").tags == ["research", "AI safety", "paper"]

    def test_tags_can_be_emptied(self, store):
        store.save_card(a_card(tags=["one", "two"]))
        store.save_card(a_card(tags=[]))
        assert store.get_card("card-1").tags == []

    def test_subtasks_keep_their_order_and_state(self, store):
        store.save_card(
            a_card(
                subtasks=[
                    Subtask(id="st-1", title="First", done=True),
                    Subtask(id="st-2", title="Second", done=False),
                    Subtask(id="st-3", title="Third", done=False),
                ]
            )
        )
        subtasks = store.get_card("card-1").subtasks

        assert [s.id for s in subtasks] == ["st-1", "st-2", "st-3"]
        assert [s.title for s in subtasks] == ["First", "Second", "Third"]
        assert [s.done for s in subtasks] == [True, False, False]

    def test_subtasks_can_be_replaced_wholesale(self, store):
        store.save_card(a_card(subtasks=[Subtask(id="st-1", title="Old", done=True)]))
        store.save_card(a_card(subtasks=[Subtask(id="st-9", title="New", done=False)]))
        subtasks = store.get_card("card-1").subtasks
        assert len(subtasks) == 1
        assert subtasks[0].id == "st-9"

    def test_a_non_job_card_has_no_job(self, store):
        store.save_card(a_card())
        assert store.get_card("card-1").job is None

    def test_job_details(self, store):
        store.save_card(
            a_job_card(
                job=JobDetails(
                    company="Anthropic",
                    role="Research Engineer",
                    job_url="https://example.com/role",
                    location="London",
                    salary_text="Competitive",
                    work_mode="HYBRID",
                    contact_name="Priya",
                    contact_details="priya@example.com",
                    job_description="The whole advert.",
                    requirements=["Strong Python", "Published research"],
                    nice_to_have=["Interpretability"],
                    application_deadline="2026-11-30",
                    interview_date="2026-12-05",
                    cv_version="cv-v3.pdf",
                    fit="DREAM",
                    outcome="ACTIVE",
                    notes="Second round is a deep dive.",
                )
            )
        )
        job = store.get_card("card-job").job

        assert job.company == "Anthropic"
        assert job.work_mode == "HYBRID"
        assert job.fit == "DREAM"
        assert job.requirements == ["Strong Python", "Published research"]
        assert job.nice_to_have == ["Interpretability"]
        assert str(job.application_deadline) == "2026-11-30"
        assert str(job.interview_date) == "2026-12-05"
        assert job.notes == "Second round is a deep dive."

    def test_job_defaults(self, store):
        store.save_card(a_job_card(job=JobDetails()))
        job = store.get_card("card-job").job
        assert job.company == ""
        assert job.work_mode == "UNKNOWN"
        assert job.fit == "MEDIUM"
        assert job.outcome == "ACTIVE"
        assert job.requirements == []

    def test_a_learning_card_keeps_its_link_list(self, store):
        store.save_card(a_learning_card(related_job_card_ids=[]))
        assert store.get_card("card-learning").related_job_card_ids == []


class TestLinks:
    """§9.3 — the many-to-many both ends of the app rely on."""

    def test_links_survive_the_round_trip(self, store):
        store.save_card(a_job_card(id="job-a"))
        store.save_card(a_job_card(id="job-b"))
        store.save_card(a_learning_card(related_job_card_ids=["job-a", "job-b"]))

        assert store.get_card("card-learning").related_job_card_ids == ["job-a", "job-b"]

    def test_the_job_side_survives_too(self, store):
        job = a_job_card()
        job.job.related_learning_card_ids = ["card-learning"]
        store.save_card(job)

        assert store.get_card("card-job").job.related_learning_card_ids == ["card-learning"]

    def test_links_can_be_removed(self, store):
        store.save_card(a_job_card(id="job-a"))
        store.save_card(a_learning_card(related_job_card_ids=["job-a"]))
        store.save_card(a_learning_card(related_job_card_ids=[]))

        assert store.get_card("card-learning").related_job_card_ids == []


class TestPreferences:
    def test_the_default(self, store):
        preferences = store.get_preferences()
        assert preferences.display_name == ""
        assert preferences.weekly_available_hours is None

    def test_saving_and_reading_back(self, store):
        store.save_preferences(Preferences(display_name="Raquel", weekly_available_hours=18))
        preferences = store.get_preferences()
        assert preferences.display_name == "Raquel"
        assert preferences.weekly_available_hours == 18

    def test_hours_can_be_cleared(self, store):
        store.save_preferences(Preferences(weekly_available_hours=18))
        store.save_preferences(Preferences(weekly_available_hours=None))
        assert store.get_preferences().weekly_available_hours is None

    def test_half_hours_survive(self, store):
        store.save_preferences(Preferences(weekly_available_hours=17.5))
        assert store.get_preferences().weekly_available_hours == 17.5

    def test_there_is_only_ever_one_row(self, store):
        store.save_preferences(Preferences(display_name="First"))
        store.save_preferences(Preferences(display_name="Second"))
        assert store.get_preferences().display_name == "Second"


class TestUsers:
    def test_saving_and_reading_back(self, store):
        user = build_demo_user()
        store.save_user(user)
        assert store.get_user(user.id).email == user.email

    def test_the_hash_survives_exactly(self, store):
        """A single altered byte and nobody can sign in again."""
        user = build_demo_user()
        store.save_user(user)
        assert store.get_user(user.id).password_hash == user.password_hash

    def test_lookup_by_email_is_case_insensitive(self, store):
        user = build_demo_user()
        store.save_user(user)
        assert store.get_user_by_email(user.email.upper()).id == user.id

    def test_an_unknown_user_is_none(self, store):
        assert store.get_user("nope") is None
        assert store.get_user_by_email("nobody@example.com") is None

    def test_saving_twice_updates(self, store):
        user = build_demo_user()
        store.save_user(user)
        store.save_user(user.model_copy(update={"display_name": "Changed"}))
        assert store.get_user(user.id).display_name == "Changed"

    def test_two_accounts_cannot_share_an_email(self, store):
        """SQLite enforces this with a unique index. The dict did not, until the
        API suite was run against both and the two disagreed."""
        first = build_demo_user()
        store.save_user(first)

        with pytest.raises(ValueError):
            store.save_user(first.model_copy(update={"id": "user-second"}))

    def test_the_check_is_case_insensitive(self, store):
        first = build_demo_user()
        store.save_user(first)

        with pytest.raises(ValueError):
            store.save_user(
                first.model_copy(update={"id": "user-second", "email": first.email.upper()})
            )

    def test_changing_your_own_email_is_not_a_clash(self, store):
        user = build_demo_user()
        store.save_user(user)
        store.save_user(user.model_copy(update={"email": "moved@example.com"}))
        assert store.get_user(user.id).email == "moved@example.com"


class TestTokens:
    def test_saving_and_reading_back(self, store):
        user = build_demo_user()
        store.save_user(user)
        expires = now() + timedelta(days=14)
        store.save_token("tok-1", user.id, expires)

        session = store.get_token("tok-1")
        assert session.user_id == user.id
        assert abs((session.expires_at - expires).total_seconds()) < 1

    def test_an_unknown_token_is_none(self, store):
        assert store.get_token("nope") is None

    def test_deleting_a_token(self, store):
        user = build_demo_user()
        store.save_user(user)
        store.save_token("tok-1", user.id, now() + timedelta(days=1))

        assert store.delete_token("tok-1") is True
        assert store.get_token("tok-1") is None

    def test_deleting_an_absent_token_says_so(self, store):
        assert store.delete_token("nope") is False

    def test_deleting_every_token_for_a_user(self, store):
        user = build_demo_user()
        store.save_user(user)
        for i in range(3):
            store.save_token(f"tok-{i}", user.id, now() + timedelta(days=1))

        assert store.delete_tokens_for(user.id) == 3
        assert store.get_token("tok-0") is None

    def test_one_user_s_tokens_are_not_another_s(self, store):
        first = build_demo_user()
        second = first.model_copy(update={"id": "user-second", "email": "other@example.com"})
        store.save_user(first)
        store.save_user(second)
        store.save_token("tok-first", first.id, now() + timedelta(days=1))
        store.save_token("tok-second", second.id, now() + timedelta(days=1))

        store.delete_tokens_for(first.id)

        assert store.get_token("tok-first") is None
        assert store.get_token("tok-second") is not None


class TestSeeding:
    def test_a_seeded_store_has_the_fixtures(self, store):
        store.seed()
        cards = store.list_cards()

        assert len(cards) == 12
        assert {c.area for c in cards} == {"CURRENT_JOB", "JOB_SEARCH", "LEARNING"}
        assert store.get_preferences().weekly_available_hours == 18
        assert store.get_user_by_email("researcher@example.com") is not None

    def test_seeding_twice_does_not_duplicate(self, store):
        store.seed()
        store.seed()
        assert len(store.list_cards()) == 12

    def test_the_seeded_links_are_two_way(self, store):
        store.seed()
        learning = store.get_card("seed-system-design")
        job = store.get_card("seed-job-anthropic")

        assert job.id in learning.related_job_card_ids
        assert learning.id in job.job.related_learning_card_ids


class TestDurability:
    """The whole point of issue #19, and the one thing the dict cannot do."""

    def test_cards_survive_reopening_the_database(self, tmp_path):
        path = tmp_path / "nextlane.sqlite3"

        first = SqliteStore(path)
        first.save_card(a_card(title="Written before the restart", tags=["one"]))
        first.close()

        second = SqliteStore(path)
        card = second.get_card("card-1")
        assert card.title == "Written before the restart"
        assert card.tags == ["one"]

    def test_a_whole_seeded_board_survives(self, tmp_path):
        path = tmp_path / "nextlane.sqlite3"

        first = SqliteStore(path)
        first.seed()
        first.close()

        second = SqliteStore(path)
        assert len(second.list_cards()) == 12
        assert second.get_card("seed-job-anthropic").job.company == "Anthropic"
        assert second.get_card("seed-system-design").related_job_card_ids

    def test_a_session_survives_a_restart(self, tmp_path):
        """Otherwise every deploy signs everybody out."""
        path = tmp_path / "nextlane.sqlite3"
        user = build_demo_user()

        first = SqliteStore(path)
        first.save_user(user)
        first.save_token("tok-1", user.id, now() + timedelta(days=7))
        first.close()

        second = SqliteStore(path)
        assert second.get_token("tok-1").user_id == user.id
        assert second.get_user(user.id).password_hash == user.password_hash

    def test_the_file_is_actually_created(self, tmp_path):
        path = tmp_path / "nextlane.sqlite3"
        SqliteStore(path).save_card(a_card())
        assert path.exists() and path.stat().st_size > 0

    def test_a_fresh_database_is_empty_not_broken(self, tmp_path):
        store = SqliteStore(tmp_path / "brand-new.sqlite3")
        assert store.list_cards() == []
        assert store.get_preferences().display_name == ""


class TestPostgresDurability:
    """The same promise as SQLite's, against a server rather than a file.

    A new `PostgresStore` here stands in for a restarted container: a different
    process, a different pool, the same database.
    """

    def reconnect(self, request):
        from app.postgres_store import PostgresStore

        store = PostgresStore(POSTGRES_DSN)
        request.addfinalizer(store.close)
        return store

    def test_cards_survive_reconnecting(self, request, empty_postgres):
        empty_postgres.save_card(a_card(title="Written before the restart", tags=["one"]))

        card = self.reconnect(request).get_card("card-1")
        assert card.title == "Written before the restart"
        assert card.tags == ["one"]

    def test_a_whole_seeded_board_survives(self, request, empty_postgres):
        empty_postgres.seed()

        second = self.reconnect(request)
        assert len(second.list_cards()) == 12
        assert second.get_card("seed-job-anthropic").job.company == "Anthropic"
        assert second.get_card("seed-system-design").related_job_card_ids

    def test_a_session_survives_a_restart(self, request, empty_postgres):
        """Otherwise every deploy signs everybody out."""
        user = build_demo_user()
        empty_postgres.save_user(user)
        empty_postgres.save_token("tok-1", user.id, now() + timedelta(days=7))

        second = self.reconnect(request)
        assert second.get_token("tok-1").user_id == user.id
        assert second.get_user(user.id).password_hash == user.password_hash

    def test_a_fresh_database_is_empty_not_broken(self, empty_postgres):
        assert empty_postgres.list_cards() == []
        assert empty_postgres.get_preferences().display_name == ""

    def test_seeding_twice_from_two_connections_does_not_duplicate(self, request, empty_postgres):
        """Two containers starting at once against one empty database (§the
        advisory lock in postgres_store.seed)."""
        empty_postgres.seed()
        self.reconnect(request).seed()

        assert len(empty_postgres.list_cards()) == 12

    def test_timestamps_come_back_as_they_went_in(self, request, empty_postgres):
        """TIMESTAMPTZ, and every connection pinned to UTC, so this cannot drift
        with the server's own timezone."""
        stamp = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        empty_postgres.save_card(a_card(created_at=stamp, updated_at=stamp))

        assert self.reconnect(request).get_card("card-1").created_at == stamp
