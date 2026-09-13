"""Job-advert extraction — §15.

A heuristic parser standing in for a model call: labels first ("Company: …"),
then headed bullet sections, then a few keyword sweeps. It is honest about what
it could not find, which is the whole point of the preview step in §15.3 — the
user fixes the gaps before anything is saved.

Isolated on purpose (§27). If this module is unavailable, every other endpoint
still works and the Kanban remains fully usable.

Replacing it with a real model call means replacing `extract` and nothing else.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from app.errors import AiUnreadable
from app.models import ExtractedJob, ExtractionResult

MIN_LENGTH = 40

ROLE_WORDS = re.compile(
    r"(engineer|scientist|researcher|developer|analyst|manager|lead|architect"
    r"|specialist|consultant|designer|director|intern|postdoc|fellow)",
    re.I,
)

LABEL = re.compile(r"^([A-Za-z][A-Za-z /'-]{2,28})\s*[:—–-]\s*(.+)$")

BULLET = re.compile(r"^(?:[-•*·–—]|\d+[.)])\s*(.+)$")

REQUIREMENT_HEADING = re.compile(
    r"^(requirements|what you.?ll need|about you|essential|you have|qualifications)\b", re.I
)
NICE_HEADING = re.compile(
    r"^(nice[ -]to[ -]have|bonus|preferred|desirable|it would help|plus(es)?)\b", re.I
)

TAG_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpython\b", re.I), "python"),
    (re.compile(r"\b(pytorch|tensorflow|jax)\b", re.I), "deep learning"),
    (re.compile(r"\b(llm|large language model|genai|transformer)", re.I), "LLM"),
    (re.compile(r"\b(nlp|natural language)", re.I), "NLP"),
    (re.compile(r"\b(research|publication|paper)", re.I), "research"),
    (re.compile(r"\b(ai safety|alignment|interpretability)", re.I), "AI safety"),
    (re.compile(r"\b(mlops|kubernetes|docker|aws|gcp|azure)", re.I), "infrastructure"),
    (re.compile(r"\b(phd|doctorate|postdoc)", re.I), "phd-friendly"),
    (re.compile(r"\b(sql|data warehouse|analytics)", re.I), "data"),
)


def extract(advert: str) -> ExtractionResult:
    text = (advert or "").strip()

    if len(text) < MIN_LENGTH:
        raise AiUnreadable(
            "There isn't enough text here to read reliably. "
            "Paste the full advert, or create the job manually."
        )

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    paragraphs = _paragraphs(text)
    labels = _labels(lines)

    extracted = ExtractedJob(
        company=labels.get("company") or labels.get("employer") or _company(lines, text),
        role=labels.get("role") or labels.get("position") or labels.get("job title") or _role(lines),
        location=labels.get("location") or _location(text),
        salary_text=labels.get("salary") or labels.get("compensation") or _salary(text),
        work_mode=_work_mode(text),
        application_deadline=_date(
            labels.get("deadline") or labels.get("closing date") or _deadline(text)
        ),
        requirements=_section(lines, REQUIREMENT_HEADING),
        nice_to_have=_section(lines, NICE_HEADING),
        summary=_summary(paragraphs),
        tags=_tags(text),
    )

    missing = [name for name in ("company", "role") if not getattr(extracted, name)]

    return ExtractionResult(
        extracted=extracted,
        missing=missing,
        confidence="good" if not missing else "partial",
    )


# ------------------------------------------------------------------ heuristics


def _paragraphs(text: str) -> list[str]:
    """Adverts arrive hard-wrapped. Rejoin the lines before judging length."""
    blocks = re.split(r"\n\s*\n", text)
    return [" ".join(part.split()) for part in blocks if part.strip()]


def _labels(lines: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines:
        match = LABEL.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if value and len(value) < 160 and key not in found:
            found[key] = value
    return found


def _company(lines: list[str], text: str) -> str:
    patterns = (
        r"\bat\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})\s+(?:we|you|is|are)\b",
        r"^([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})\s+is\s+(?:hiring|looking|seeking|recruiting)",
        r"\bjoin\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.M)
        if match:
            return _clean(match.group(1))

    first = lines[0] if lines else ""
    if first and len(first) <= 48 and not _looks_like_role(first) and first[:1].isupper():
        return _clean(first)
    return ""


def _looks_like_role(line: str) -> bool:
    return bool(ROLE_WORDS.search(line)) and len(line) <= 80


def _role(lines: list[str]) -> str:
    for line in lines[:6]:
        if _looks_like_role(line):
            return _clean(re.sub(r"^(job title|role|position)\s*[:—–-]\s*", "", line, flags=re.I))
    return ""


def _location(text: str) -> str:
    match = re.search(
        r"\b(?:based in|located in|office in)\s+([A-Z][\w'-]*(?:[ ,]+[A-Z][\w'-]*){0,2})", text
    )
    if match:
        return _clean(match.group(1))
    if re.search(r"\bfully remote\b", text, re.I):
        return "Remote"
    return ""


def _salary(text: str) -> str:
    match = re.search(
        r"(?:[£$€]\s?\d[\d,.]*\s?[kK]?(?:\s?[–—-]\s?[£$€]?\s?\d[\d,.]*\s?[kK]?)?)"
        r"|(?:\d{2,3},\d{3}\s?(?:-|to)\s?\d{2,3},\d{3})",
        text,
    )
    return _clean(match.group(0)) if match else ""


def _work_mode(text: str) -> str:
    if re.search(r"\bhybrid\b", text, re.I):
        return "HYBRID"
    if re.search(r"\b(fully remote|remote[- ]first|work from home|100% remote|remote)\b", text, re.I):
        return "REMOTE"
    if re.search(r"\b(on[- ]site|in[- ]office|onsite)\b", text, re.I):
        return "ONSITE"
    return "UNKNOWN"


def _deadline(text: str) -> str:
    match = re.search(
        r"(?:deadline|closes?|closing|apply by|applications? close)[^\n]*?"
        r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
        text,
        re.I,
    )
    return match.group(1) if match else ""


def _section(lines: list[str], heading: re.Pattern[str]) -> list[str]:
    """The bullets under a heading, stopping at the next heading."""
    start = next(
        (i for i, line in enumerate(lines) if heading.match(line.rstrip(":•-–— "))),
        None,
    )
    if start is None:
        return []

    items: list[str] = []
    for line in lines[start + 1 :]:
        bullet = BULLET.match(line)
        if bullet:
            items.append(_clean(bullet.group(1)))
            continue
        if items:
            break
        if re.match(r"^[A-Z][\w ’'-]{2,40}:?$", line):
            break
        if len(line) < 120:
            items.append(_clean(line))
        else:
            break

    return [item for item in items if item][:10]


def _summary(paragraphs: list[str]) -> str:
    for paragraph in paragraphs:
        if len(paragraph) <= 60:
            continue
        if BULLET.match(paragraph):
            continue
        if LABEL.match(paragraph):
            continue
        return paragraph if len(paragraph) <= 260 else paragraph[:257].rstrip() + "…"
    return ""


def _tags(text: str) -> list[str]:
    tags: list[str] = []
    for pattern, tag in TAG_HINTS:
        if pattern.search(text) and tag not in tags:
            tags.append(tag)
    return tags[:5]


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()

    dmy = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", text)
    if dmy:
        day, month, year = dmy.groups()
        year = f"20{year}" if len(year) == 2 else year
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None

    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().rstrip(".,;:")
