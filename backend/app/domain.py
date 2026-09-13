"""The product's vocabulary and the rules that go with it.

This mirrors `_docs/specs.md` §28 and `frontend/src/domain/types.js`. When a
status or an area changes, it changes here and nowhere else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum


class Area(StrEnum):
    CURRENT_JOB = "CURRENT_JOB"
    JOB_SEARCH = "JOB_SEARCH"
    LEARNING = "LEARNING"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Fit(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    DREAM = "DREAM"


class WorkMode(StrEnum):
    ONSITE = "ONSITE"
    HYBRID = "HYBRID"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"


class Outcome(StrEnum):
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class Status(StrEnum):
    # Current Job (§7.1)
    BACKLOG = "BACKLOG"
    THIS_WEEK = "THIS_WEEK"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    # Job Search (§8.1)
    INTERESTING = "INTERESTING"
    PREPARING = "PREPARING"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    # Learning (§9.1)
    IDEAS = "IDEAS"
    PLANNED = "PLANNED"
    LEARNING = "LEARNING"
    PRACTISING = "PRACTISING"
    # Shared by Current Job and Learning
    DONE = "DONE"


#: Column order per board. The first is where a new card lands; the last is done.
AREA_STATUSES: dict[Area, tuple[Status, ...]] = {
    Area.CURRENT_JOB: (
        Status.BACKLOG,
        Status.THIS_WEEK,
        Status.IN_PROGRESS,
        Status.WAITING,
        Status.DONE,
    ),
    Area.JOB_SEARCH: (
        Status.INTERESTING,
        Status.PREPARING,
        Status.APPLIED,
        Status.INTERVIEW,
        Status.OFFER,
    ),
    Area.LEARNING: (
        Status.IDEAS,
        Status.PLANNED,
        Status.LEARNING,
        Status.PRACTISING,
        Status.DONE,
    ),
}

#: Outcomes that take an application off the board but keep everything (§8.1).
ARCHIVED_OUTCOMES = frozenset({Outcome.REJECTED, Outcome.WITHDRAWN, Outcome.DECLINED})


# These take `Area | str` and `Status | str` because the wire models are
# configured with `use_enum_values=True` and so carry plain strings. A StrEnum
# member hashes and compares equal to its value, so both work - the signatures
# just admit it rather than relying on the reader to know.


def default_status(area: Area | str) -> Status:
    return AREA_STATUSES[Area(area)][0]


def done_status(area: Area | str) -> Status:
    return AREA_STATUSES[Area(area)][-1]


def status_belongs_to(area: Area | str, status: Status | str) -> bool:
    return status in AREA_STATUSES[Area(area)]


def status_names(area: Area | str) -> str:
    return ", ".join(AREA_STATUSES[Area(area)])


def now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
