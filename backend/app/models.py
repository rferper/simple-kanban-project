"""Wire models.

Python stays snake_case; the wire stays camelCase, because that is the
vocabulary `frontend/src/api/client.js` already speaks. Pydantic's alias
generator bridges the two, and FastAPI serialises responses by alias.

`extra="forbid"` everywhere is deliberate: a typo'd field name should be a 422,
not a silently ignored write.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.domain import Area, Fit, Outcome, Priority, Status, WorkMode

TITLE_MAX = 200
HOURS_MAX = 200
NAME_MAX = 60
WEEK_HOURS_MAX = 168


class Wire(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        use_enum_values=True,
    )


def _clean_title(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("a title is required")
    if len(cleaned) > TITLE_MAX:
        raise ValueError(f"keep it under {TITLE_MAX} characters")
    return cleaned


# --------------------------------------------------------------------- subtasks


class Subtask(Wire):
    id: str
    title: str
    done: bool = False


class SubtaskInput(Wire):
    id: str | None = None
    title: str
    done: bool = False

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _clean_title(value)


# ------------------------------------------------------------------ job details


class JobDetails(Wire):
    """The structured application record on a JOB_SEARCH card (§11)."""

    company: str = ""
    role: str = ""
    job_url: str = ""
    location: str = ""
    salary_text: str = ""
    work_mode: WorkMode = WorkMode.UNKNOWN
    contact_name: str = ""
    contact_details: str = ""
    job_description: str = ""
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    application_deadline: date | None = None
    interview_date: date | None = None
    cv_version: str = ""
    fit: Fit = Fit.MEDIUM
    outcome: Outcome = Outcome.ACTIVE
    notes: str = ""
    #: Maintained by the link endpoints only — see JobDetailsInput.
    related_learning_card_ids: list[str] = Field(default_factory=list)


class JobDetailsInput(Wire):
    """Everything optional. `relatedLearningCardIds` is absent on purpose: links
    are owned by the link endpoints, so a job patch cannot forge one."""

    company: str | None = None
    role: str | None = None
    job_url: str | None = None
    location: str | None = None
    salary_text: str | None = None
    work_mode: WorkMode | None = None
    contact_name: str | None = None
    contact_details: str | None = None
    job_description: str | None = None
    requirements: list[str] | None = None
    nice_to_have: list[str] | None = None
    application_deadline: date | None = None
    interview_date: date | None = None
    cv_version: str | None = None
    fit: Fit | None = None
    outcome: Outcome | None = None
    notes: str | None = None


# ------------------------------------------------------------------------ cards


class Card(Wire):
    id: str
    title: str
    description: str = ""
    area: Area
    status: Status
    priority: Priority = Priority.MEDIUM
    deadline: date | None = None
    estimated_hours: float | None = None
    planned_this_week: bool = False
    tags: list[str] = Field(default_factory=list)
    subtasks: list[Subtask] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    #: JOB_SEARCH cards only.
    job: JobDetails | None = None
    #: LEARNING cards only.
    related_job_card_ids: list[str] | None = None


class CardCreate(Wire):
    title: str
    area: Area
    description: str = ""
    status: Status | None = None
    priority: Priority = Priority.MEDIUM
    deadline: date | None = None
    estimated_hours: Annotated[float, Field(ge=0, le=HOURS_MAX)] | None = None
    planned_this_week: bool = False
    tags: list[str] = Field(default_factory=list)
    subtasks: list[SubtaskInput] = Field(default_factory=list)
    job: JobDetailsInput | None = None
    related_job_card_ids: list[str] | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _clean_title(value)


class CardUpdate(Wire):
    title: str | None = None
    description: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    deadline: date | None = None
    estimated_hours: Annotated[float, Field(ge=0, le=HOURS_MAX)] | None = None
    planned_this_week: bool | None = None
    tags: list[str] | None = None
    subtasks: list[SubtaskInput] | None = None
    job: JobDetailsInput | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)


# ------------------------------------------------------------------ preferences


class Preferences(Wire):
    display_name: str = ""
    weekly_available_hours: float | None = None


class PreferencesUpdate(Wire):
    display_name: Annotated[str, Field(max_length=NAME_MAX)] | None = None
    weekly_available_hours: Annotated[float, Field(ge=0, le=WEEK_HOURS_MAX)] | None = None


# --------------------------------------------------------------------------- AI


class ExtractionRequest(Wire):
    advert: str


class ExtractedJob(Wire):
    """Note what is *not* here: fit. §15.2 — suitability is never scored."""

    company: str = ""
    role: str = ""
    location: str = ""
    salary_text: str = ""
    work_mode: WorkMode = WorkMode.UNKNOWN
    application_deadline: date | None = None
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


class ExtractionResult(Wire):
    extracted: ExtractedJob
    missing: list[str] = Field(default_factory=list)
    confidence: str = "good"


# --------------------------------------------------------------------- auth
#
# `User` and `TokenSession` are internal: they are what the store holds, and
# they never leave the process. What a client sees is `UserPublic` and
# `LoginResponse`. A password hash has no business on the wire.


class User(Wire):
    id: str
    email: str
    display_name: str = ""
    password_hash: str
    created_at: datetime


class TokenSession(Wire):
    token: str
    user_id: str
    expires_at: datetime


class UserPublic(Wire):
    id: str
    email: str
    display_name: str = ""


class LoginRequest(Wire):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or "@" not in cleaned:
            raise ValueError("enter the email address you signed up with")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        if not value:
            raise ValueError("a password is required")
        return value


class LoginResponse(Wire):
    token: str
    expires_at: datetime
    user: UserPublic


class Error(Wire):
    message: str
    kind: str | None = None
