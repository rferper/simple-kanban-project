/**
 * Card helpers: validation (§29), formatting (§10.3), deadline reasoning.
 *
 * Pure functions only — no DOM, no storage. The board and the drawer both
 * lean on these so that "due soon" means the same thing in both places.
 */

import { PRIORITY, areaOf, isArchived, isDone } from "./types.js";

export const MAX_TITLE = 200;

/** Local midnight for a YYYY-MM-DD string, so comparisons never drift by a timezone. */
export function parseDate(value) {
  if (!value) return null;
  const [y, m, d] = String(value).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function todayKey(date = new Date()) {
  const d = new Date(date);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Whole days from today. Negative is overdue, 0 is today. */
export function daysUntil(value, now = new Date()) {
  const target = parseDate(value);
  if (!target) return null;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target - start) / 86400000);
}

/** The date a card is actually judged on: a job's interview beats its deadline. */
export function effectiveDate(card) {
  if (card.job?.interviewDate) return card.job.interviewDate;
  return card.deadline || card.job?.applicationDeadline || null;
}

export function deadlineState(card, now = new Date()) {
  const value = effectiveDate(card);
  const days = daysUntil(value, now);
  if (days === null) return { value: null, days: null, state: "none" };
  if (isDone(card) || isArchived(card)) return { value, days, state: "neutral" };
  if (days < 0) return { value, days, state: "overdue" };
  if (days === 0) return { value, days, state: "today" };
  if (days <= 2) return { value, days, state: "soon" };
  return { value, days, state: "upcoming" };
}

export function formatDate(value) {
  const date = parseDate(value);
  if (!date) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** "Overdue", "Today", "Tomorrow", "18 Sep" — the phrasing a card badge uses. */
export function formatDeadline(value, now = new Date()) {
  const days = daysUntil(value, now);
  if (days === null) return "";
  if (days < -1) return `${Math.abs(days)}d overdue`;
  if (days === -1) return "Yesterday";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days <= 6) return parseDate(value).toLocaleDateString(undefined, { weekday: "long" });
  return formatDate(value);
}

/** §10.3 — 0.5 becomes "30m", 1.5 becomes "1h 30m". */
export function formatHours(hours) {
  if (hours === null || hours === undefined || hours === "") return "";
  const n = Number(hours);
  if (!Number.isFinite(n) || n <= 0) return n === 0 ? "0h" : "";
  const whole = Math.floor(n);
  const minutes = Math.round((n - whole) * 60);
  if (whole === 0) return `${minutes}m`;
  if (minutes === 0) return `${whole}h`;
  return `${whole}h ${minutes}m`;
}

export function hasEstimate(card) {
  return typeof card.estimatedHours === "number" && Number.isFinite(card.estimatedHours);
}

/** §8.2 — a job card leads with company and role, everything else leads with its title. */
export function cardTitle(card) {
  if (card.job?.company) return card.job.company;
  return card.title;
}

export function cardSubtitle(card) {
  if (card.job?.company) return card.job.role || card.title;
  return "";
}

export function searchableText(card) {
  return [
    card.title,
    card.description,
    card.job?.company,
    card.job?.role,
    card.job?.location,
    ...(card.tags || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

/**
 * §29 — forgiving. Only title, area and status are required; a bad estimate is
 * reported against its own field rather than failing the whole save.
 */
export function validateCard(patch, { area, status } = {}) {
  const errors = {};
  const title = (patch.title ?? "").trim();

  if ("title" in patch) {
    if (!title) errors.title = "A title is required.";
    else if (title.length > MAX_TITLE) errors.title = `Keep it under ${MAX_TITLE} characters.`;
  }

  if ("estimatedHours" in patch) {
    const raw = patch.estimatedHours;
    if (raw !== null && raw !== undefined && raw !== "") {
      const n = Number(raw);
      if (!Number.isFinite(n)) errors.estimatedHours = "Use a number, like 1.5.";
      else if (n < 0) errors.estimatedHours = "Hours cannot be negative.";
      else if (n > 200) errors.estimatedHours = "That looks like a typo — 200h is the ceiling.";
    }
  }

  if ("deadline" in patch && patch.deadline && !parseDate(patch.deadline)) {
    errors.deadline = "Use a real date.";
  }

  const areaDef = area ? areaOf(area) : null;
  if (status && areaDef && !areaDef.statuses.includes(status)) {
    errors.status = "Unknown column for this board.";
  }

  return { ok: Object.keys(errors).length === 0, errors };
}

export function normaliseHours(raw) {
  if (raw === null || raw === undefined || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

export function parseTags(raw) {
  if (Array.isArray(raw)) return raw;
  return String(raw || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

/**
 * §5.2 — dashboard column ordering: overdue, then urgent, then due soon, then
 * in progress, then everything else still active.
 */
export function dashboardRank(card, now = new Date()) {
  const { state } = deadlineState(card, now);
  const areaDef = areaOf(card.area);
  if (state === "overdue") return 0;
  if (card.priority === PRIORITY.URGENT) return 1;
  if (state === "today" || state === "soon") return 2;
  if (card.status === areaDef.inProgressStatus) return 3;
  if (card.priority === PRIORITY.HIGH) return 4;
  return 5;
}

const PRIORITY_WEIGHT = { URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export function compareForDashboard(a, b, now = new Date()) {
  const rank = dashboardRank(a, now) - dashboardRank(b, now);
  if (rank !== 0) return rank;

  const da = daysUntil(effectiveDate(a), now);
  const db = daysUntil(effectiveDate(b), now);
  if (da !== null && db !== null && da !== db) return da - db;
  if (da !== null && db === null) return -1;
  if (da === null && db !== null) return 1;

  const pa = PRIORITY_WEIGHT[a.priority] ?? 9;
  const pb = PRIORITY_WEIGHT[b.priority] ?? 9;
  if (pa !== pb) return pa - pb;

  return String(a.createdAt).localeCompare(String(b.createdAt));
}

/** Cards that still want attention: not done, not archived. */
export function isActive(card) {
  return !isDone(card) && !isArchived(card);
}
