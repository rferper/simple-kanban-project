"""The rules.

Everything that is true of a card regardless of how it is stored or how it is
asked for lives here: which columns a board has, when `completedAt` is stamped,
and how the two ends of a job ↔ learning link are kept in step.

Routers translate HTTP; the store stores; this module decides.
"""

from __future__ import annotations

from app.domain import (
    Area,
    Status,
    default_status,
    done_status,
    new_id,
    now,
    status_belongs_to,
    status_names,
)
from app.errors import Conflict, Invalid, NotFound
from app.store import Store
from app.models import (
    Card,
    CardCreate,
    CardUpdate,
    JobDetails,
    JobDetailsInput,
    Preferences,
    PreferencesUpdate,
    Subtask,
    SubtaskInput,
)


def _require(store: Store, card_id: str) -> Card:
    card = store.get_card(card_id)
    if card is None:
        raise NotFound(f"No card with id {card_id}.")
    return card


def _check_status(area: Area, status: Status) -> None:
    if not status_belongs_to(area, status):
        raise Invalid(
            f"{status} is not a column on the {area} board. Use one of: {status_names(area)}."
        )


def _materialise(subtasks: list[SubtaskInput]) -> list[Subtask]:
    return [
        Subtask(id=item.id or new_id("st"), title=item.title, done=item.done) for item in subtasks
    ]


def _touch_completion(card: Card) -> None:
    """§12.1 — `completedAt` follows the done column, and is never client-set."""
    if card.status == done_status(card.area):
        if card.completed_at is None:
            card.completed_at = now()
    else:
        card.completed_at = None


# ----------------------------------------------------------------------- cards


def list_cards(store: Store) -> list[Card]:
    return store.list_cards()


def get_card(store: Store, card_id: str) -> Card:
    return _require(store, card_id)


def create_card(store: Store, payload: CardCreate) -> Card:
    area = payload.area
    status = payload.status or default_status(area)
    _check_status(area, status)

    if payload.job is not None and area != Area.JOB_SEARCH:
        raise Invalid("Only a Job Search card can carry application details.")

    if payload.related_job_card_ids and area != Area.LEARNING:
        raise Invalid("Only a Learning card can be linked to roles.")

    timestamp = now()
    card = Card(
        id=new_id("card"),
        title=payload.title,
        description=payload.description,
        area=area,
        status=status,
        priority=payload.priority,
        deadline=payload.deadline,
        estimated_hours=payload.estimated_hours,
        planned_this_week=payload.planned_this_week,
        tags=payload.tags,
        subtasks=_materialise(payload.subtasks),
        created_at=timestamp,
        updated_at=timestamp,
        completed_at=None,
    )

    if area == Area.JOB_SEARCH:
        card.job = _merge_job(JobDetails(), payload.job) if payload.job else JobDetails()
    if area == Area.LEARNING:
        card.related_job_card_ids = []

    _touch_completion(card)
    saved = store.save_card(card)

    # Links requested at creation go through the same bookkeeping as any other.
    for job_id in payload.related_job_card_ids or []:
        saved, _ = set_link(store, saved.id, job_id, connected=True)

    return saved


def update_card(store: Store, card_id: str, payload: CardUpdate) -> Card:
    card = _require(store, card_id)
    changes = payload.model_dump(exclude_unset=True, by_alias=False)

    if "status" in changes:
        _check_status(card.area, payload.status)
        card.status = payload.status

    for field in (
        "title",
        "description",
        "priority",
        "deadline",
        "estimated_hours",
        "planned_this_week",
        "tags",
    ):
        if field in changes:
            setattr(card, field, getattr(payload, field))

    if "subtasks" in changes:
        card.subtasks = _materialise(payload.subtasks or [])

    # A nested job patch is a convenience; on a non-job card it is simply not
    # applicable, and the dedicated endpoint is the one that complains.
    if "job" in changes and payload.job is not None and card.job is not None:
        card.job = _merge_job(card.job, payload.job)

    _touch_completion(card)
    card.updated_at = now()
    return store.save_card(card)


def delete_card(store: Store, card_id: str) -> None:
    card = _require(store, card_id)
    _forget_links(store, card)
    store.delete_card(card_id)


# ------------------------------------------------------------------ job details


def _merge_job(existing: JobDetails, patch: JobDetailsInput) -> JobDetails:
    """Field-by-field, so an update of one field does not blank the rest."""
    merged = existing.model_copy(deep=True)
    for field, value in patch.model_dump(exclude_unset=True, by_alias=False).items():
        setattr(merged, field, value)
    return merged


def update_job_details(store: Store, card_id: str, patch: JobDetailsInput) -> Card:
    card = _require(store, card_id)
    if card.job is None:
        raise Conflict(f"Card {card_id} is not a job card, so it has no application details.")

    card.job = _merge_job(card.job, patch)
    card.updated_at = now()
    return store.save_card(card)


# ------------------------------------------------------------------------ links


def _require_learning(store: Store, card_id: str) -> Card:
    card = _require(store, card_id)
    if card.area != Area.LEARNING:
        raise Conflict(f"Card {card_id} is not a Learning card.")
    return card


def _require_job(store: Store, card_id: str) -> Card:
    card = _require(store, card_id)
    if card.job is None:
        raise Conflict(f"Card {card_id} is not a job card.")
    return card


def set_link(
    store: Store, learning_id: str, job_id: str, *, connected: bool
) -> tuple[Card, Card]:
    """§9.3 — both ends move together or neither does. Idempotent either way."""
    learning = _require_learning(store, learning_id)
    job = _require_job(store, job_id)

    learning.related_job_card_ids = learning.related_job_card_ids or []
    job.job.related_learning_card_ids = job.job.related_learning_card_ids or []

    already = job_id in learning.related_job_card_ids
    if connected and not already:
        learning.related_job_card_ids.append(job_id)
    elif not connected and already:
        learning.related_job_card_ids.remove(job_id)

    linked_back = learning_id in job.job.related_learning_card_ids
    if connected and not linked_back:
        job.job.related_learning_card_ids.append(learning_id)
    elif not connected and linked_back:
        job.job.related_learning_card_ids.remove(learning_id)

    timestamp = now()
    learning.updated_at = timestamp
    job.updated_at = timestamp

    return store.save_card(learning), store.save_card(job)


def _forget_links(store: Store, card: Card) -> None:
    """Leave no card pointing at something that has just been deleted."""
    for job_id in card.related_job_card_ids or []:
        other = store.get_card(job_id)
        if other and other.job:
            other.job.related_learning_card_ids = [
                x for x in other.job.related_learning_card_ids if x != card.id
            ]
            store.save_card(other)

    if card.job:
        for learning_id in card.job.related_learning_card_ids:
            other = store.get_card(learning_id)
            if other and other.related_job_card_ids is not None:
                other.related_job_card_ids = [
                    x for x in other.related_job_card_ids if x != card.id
                ]
                store.save_card(other)


# ------------------------------------------------------------------ preferences


def get_preferences(store: Store) -> Preferences:
    return store.get_preferences()


def update_preferences(store: Store, patch: PreferencesUpdate) -> Preferences:
    preferences = store.get_preferences()
    for field, value in patch.model_dump(exclude_unset=True, by_alias=False).items():
        setattr(preferences, field, value)
    return store.save_preferences(preferences)
