"""Development fixtures — _docs/specs.md §31.

The same club of work the frontend seeds itself with, so the two can be compared
side by side. Dates are relative to whenever the process starts, which keeps
something overdue, something due today and an interview next week.

The awkward states are deliberate: a card with no estimate, a card with no
deadline, and an application that has already been archived.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.models import Card, JobDetails, Preferences, Subtask

ANTHROPIC = "seed-job-anthropic"
DEEPMIND = "seed-job-deepmind"
SYSTEM_DESIGN = "seed-system-design"
LEETCODE = "seed-leetcode"


def _day(offset: int) -> date:
    return date.today() + timedelta(days=offset)


def _stamp(offset_days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=offset_days)


def _next_weekday(target: int) -> date:
    """Next Monday(0)…Sunday(6), at least one day out."""
    today = date.today()
    delta = (target - today.weekday()) % 7
    return today + timedelta(days=delta or 7)


def build_seed() -> tuple[list[Card], Preferences]:
    cards = [
        # ---------------------------------------------------- Current Job
        Card(
            id="seed-slides",
            title="Finish conference slides",
            description=(
                "Forty minutes, ten slides. The results section is the only part "
                "that still needs work."
            ),
            area="CURRENT_JOB",
            status="THIS_WEEK",
            priority="HIGH",
            deadline=_next_weekday(4),
            estimated_hours=3,
            planned_this_week=True,
            tags=["conference", "teaching"],
            subtasks=[
                Subtask(id="st-1", title="Redraw the main figure", done=True),
                Subtask(id="st-2", title="Cut the related-work slides to two", done=False),
                Subtask(id="st-3", title="Practice run", done=False),
            ],
            created_at=_stamp(-9),
            updated_at=_stamp(-2),
        ),
        Card(
            id="seed-review",
            title="Review journal paper",
            description="Second reminder from the editor arrived on Monday.",
            area="CURRENT_JOB",
            status="BACKLOG",
            priority="MEDIUM",
            deadline=_day(-1),
            estimated_hours=2,
            planned_this_week=True,
            tags=["review", "service"],
            created_at=_stamp(-14),
            updated_at=_stamp(-14),
        ),
        Card(
            id="seed-experiment",
            title="Run final experiment",
            description="The last ablation for the rebuttal. Cluster job is queued.",
            area="CURRENT_JOB",
            status="IN_PROGRESS",
            priority="HIGH",
            estimated_hours=4,
            planned_this_week=True,
            tags=["research"],
            created_at=_stamp(-5),
            updated_at=_stamp(-1),
        ),
        Card(
            id="seed-supervision",
            title="Read Marta's draft chapter",
            area="CURRENT_JOB",
            status="WAITING",
            priority="LOW",
            tags=["supervision"],
            created_at=_stamp(-3),
            updated_at=_stamp(-3),
        ),
        # ----------------------------------------------------- Job Search
        Card(
            id=ANTHROPIC,
            title="Anthropic — Research Engineer",
            area="JOB_SEARCH",
            status="INTERVIEW",
            priority="URGENT",
            estimated_hours=3,
            planned_this_week=True,
            tags=["interview", "AI safety"],
            subtasks=[
                Subtask(id="st-a1", title="Re-read the interpretability papers", done=False),
                Subtask(id="st-a2", title="Prepare two research stories", done=False),
            ],
            created_at=_stamp(-21),
            updated_at=_stamp(-2),
            job=JobDetails(
                company="Anthropic",
                role="Research Engineer",
                job_url="https://example.com/anthropic/research-engineer",
                location="London",
                salary_text="Competitive",
                work_mode="HYBRID",
                contact_name="Priya (recruiter)",
                contact_details="priya@example.com",
                requirements=[
                    "Strong Python",
                    "Published research in ML",
                    "Comfortable with large-scale training infrastructure",
                ],
                nice_to_have=["Interpretability experience", "Open-source contributions"],
                interview_date=_next_weekday(1),
                cv_version="cv-research-v3.pdf",
                fit="DREAM",
                notes="Second round is a technical deep-dive on my own work.",
                related_learning_card_ids=[SYSTEM_DESIGN, LEETCODE],
            ),
        ),
        Card(
            id=DEEPMIND,
            title="DeepMind — Research Scientist",
            area="JOB_SEARCH",
            status="PREPARING",
            priority="HIGH",
            estimated_hours=2,
            planned_this_week=True,
            tags=["application"],
            subtasks=[Subtask(id="st-d1", title="Tailor the research statement", done=False)],
            created_at=_stamp(-11),
            updated_at=_stamp(-4),
            job=JobDetails(
                company="DeepMind",
                role="Research Scientist",
                location="London",
                work_mode="ONSITE",
                requirements=["PhD in a quantitative field", "First-author publications"],
                nice_to_have=["RL experience"],
                application_deadline=_day(6),
                cv_version="cv-research-v3.pdf",
                fit="HIGH",
                related_learning_card_ids=[SYSTEM_DESIGN],
            ),
        ),
        Card(
            id="seed-job-startup",
            title="AI Startup — ML Engineer",
            area="JOB_SEARCH",
            status="INTERESTING",
            priority="MEDIUM",
            created_at=_stamp(-2),
            updated_at=_stamp(-2),
            job=JobDetails(
                company="AI Startup",
                role="ML Engineer",
                location="Remote (EU)",
                salary_text="€75k–€95k",
                work_mode="REMOTE",
                requirements=["Python", "Some production ML"],
                fit="MEDIUM",
                notes="Small team, would mean more engineering than research.",
            ),
        ),
        Card(
            id="seed-job-archived",
            title="Big Corp — Data Scientist",
            area="JOB_SEARCH",
            status="APPLIED",
            priority="LOW",
            created_at=_stamp(-40),
            updated_at=_stamp(-8),
            job=JobDetails(
                company="Big Corp",
                role="Data Scientist",
                location="Manchester",
                work_mode="HYBRID",
                cv_version="cv-industry-v1.pdf",
                fit="LOW",
                outcome="REJECTED",
                notes=("Wanted five years of industry experience. Worth reusing the cover letter."),
            ),
        ),
        # ------------------------------------------------------- Learning
        Card(
            id=SYSTEM_DESIGN,
            title="System design",
            description="Working through the course, one module per week.",
            area="LEARNING",
            status="LEARNING",
            priority="HIGH",
            estimated_hours=3,
            planned_this_week=True,
            tags=["course", "interview"],
            subtasks=[
                Subtask(id="st-s1", title="Caching module", done=True),
                Subtask(id="st-s2", title="Sharding module", done=False),
            ],
            created_at=_stamp(-18),
            updated_at=_stamp(-1),
            related_job_card_ids=[ANTHROPIC, DEEPMIND],
        ),
        Card(
            id=LEETCODE,
            title="LeetCode arrays",
            area="LEARNING",
            status="PRACTISING",
            priority="MEDIUM",
            estimated_hours=1,
            planned_this_week=True,
            tags=["coding"],
            created_at=_stamp(-7),
            updated_at=_stamp(-1),
            related_job_card_ids=[ANTHROPIC],
        ),
        Card(
            id="seed-portfolio",
            title="Portfolio project",
            description="Ship one thing a reviewer can open in thirty seconds.",
            area="LEARNING",
            status="PLANNED",
            priority="MEDIUM",
            estimated_hours=4,
            tags=["portfolio"],
            created_at=_stamp(-6),
            updated_at=_stamp(-6),
            related_job_card_ids=[],
        ),
        Card(
            id="seed-docker",
            title="Learn Docker properly",
            area="LEARNING",
            status="IDEAS",
            priority="LOW",
            tags=["skill"],
            created_at=_stamp(-4),
            updated_at=_stamp(-4),
            related_job_card_ids=[],
        ),
    ]

    return cards, Preferences(display_name="", weekly_available_hours=18)
