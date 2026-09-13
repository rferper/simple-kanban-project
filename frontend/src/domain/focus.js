/**
 * Focus Today — _docs/specs.md §23.
 *
 * Deterministic, no AI, and deliberately explainable: every card can say which
 * clauses gave it its score. The spec's diversity rule is applied afterwards,
 * as a nudge rather than a constraint.
 */

import { PRIORITY, areaOf } from "./types.js";
import { daysUntil, effectiveDate, isActive } from "./cards.js";

export const SCORE = {
  OVERDUE: 100,
  DUE_TODAY: 80,
  DUE_WITHIN_2_DAYS: 60,
  URGENT_PRIORITY: 50,
  HIGH_PRIORITY: 30,
  MEDIUM_PRIORITY: 15,
  IN_PROGRESS: 20,
  PLANNED_THIS_WEEK: 10,
};

/** How close a runner-up has to be before area diversity is allowed to reorder it. */
const DIVERSITY_TOLERANCE = 25;

export function scoreCard(card, now = new Date()) {
  const reasons = [];
  let score = 0;

  const days = daysUntil(effectiveDate(card), now);
  if (days !== null) {
    if (days < 0) {
      score += SCORE.OVERDUE;
      reasons.push("overdue");
    } else if (days === 0) {
      score += SCORE.DUE_TODAY;
      reasons.push("due today");
    } else if (days <= 2) {
      score += SCORE.DUE_WITHIN_2_DAYS;
      reasons.push("due within 2 days");
    }
  }

  if (card.priority === PRIORITY.URGENT) {
    score += SCORE.URGENT_PRIORITY;
    reasons.push("urgent");
  } else if (card.priority === PRIORITY.HIGH) {
    score += SCORE.HIGH_PRIORITY;
    reasons.push("high priority");
  } else if (card.priority === PRIORITY.MEDIUM) {
    score += SCORE.MEDIUM_PRIORITY;
  }

  if (card.status === areaOf(card.area).inProgressStatus) {
    score += SCORE.IN_PROGRESS;
    reasons.push("in progress");
  }

  if (card.plannedThisWeek) {
    score += SCORE.PLANNED_THIS_WEEK;
    reasons.push("planned this week");
  }

  return { score, reasons };
}

const PRIORITY_WEIGHT = { URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

/**
 * Rank, then walk the list picking a different area for slots 2 and 3 when a
 * comparable card exists. "Comparable" is within DIVERSITY_TOLERANCE points —
 * the spec asks for simple, not optimal.
 */
export function focusToday(cards, { limit = 3, now = new Date() } = {}) {
  const ranked = cards
    .filter(isActive)
    .map((card) => ({ card, ...scoreCard(card, now) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => compare(a, b, now));

  const picked = [];
  const pool = [...ranked];
  const usedAreas = new Set();

  while (picked.length < limit && pool.length) {
    let index = 0;

    if (picked.length > 0) {
      const best = pool[0];
      const fresh = pool.findIndex(
        (entry) =>
          !usedAreas.has(entry.card.area) && best.score - entry.score <= DIVERSITY_TOLERANCE
      );
      if (fresh > 0) index = fresh;
    }

    const [chosen] = pool.splice(index, 1);
    usedAreas.add(chosen.card.area);
    picked.push(chosen);
  }

  return picked;
}

function compare(a, b, now) {
  if (b.score !== a.score) return b.score - a.score;

  const da = daysUntil(effectiveDate(a.card), now);
  const db = daysUntil(effectiveDate(b.card), now);
  if (da !== null && db !== null && da !== db) return da - db;
  if (da !== null && db === null) return -1;
  if (da === null && db !== null) return 1;

  const pa = PRIORITY_WEIGHT[a.card.priority] ?? 9;
  const pb = PRIORITY_WEIGHT[b.card.priority] ?? 9;
  if (pa !== pb) return pa - pb;

  return String(a.card.createdAt).localeCompare(String(b.card.createdAt));
}

/** A short "why this card" line for the dashboard. Never claims optimality. */
export function focusReason(entry) {
  if (!entry.reasons.length) return areaOf(entry.card.area).name;
  return entry.reasons.slice(0, 2).join(" · ");
}
