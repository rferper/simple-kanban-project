/**
 * Weekly capacity indicator — _docs/specs.md §22.
 *
 * Deliberately transparent: sum the estimates of everything flagged for this
 * week, break it down by area, and count what has no estimate rather than
 * quietly treating it as zero.
 */

import { AREA_ORDER } from "./types.js";
import { hasEstimate, isActive } from "./cards.js";

export function calculateWorkload(cards, availableHours) {
  const planned = cards.filter((c) => c.plannedThisWeek && isActive(c));

  const byArea = {};
  for (const area of AREA_ORDER) byArea[area] = { hours: 0, cards: 0, unestimated: 0 };

  let total = 0;
  let unestimated = 0;

  for (const card of planned) {
    const bucket = byArea[card.area];
    if (!bucket) continue;
    bucket.cards += 1;
    if (hasEstimate(card)) {
      bucket.hours += card.estimatedHours;
      total += card.estimatedHours;
    } else {
      bucket.unestimated += 1;
      unestimated += 1;
    }
  }

  const available =
    typeof availableHours === "number" && Number.isFinite(availableHours) && availableHours > 0
      ? availableHours
      : null;

  const difference = available === null ? null : available - total;

  return {
    plannedHours: round(total),
    availableHours: available,
    difference: difference === null ? null : round(difference),
    isOverCapacity: difference !== null && difference < 0,
    unestimatedCount: unestimated,
    plannedCount: planned.length,
    byArea: Object.fromEntries(
      Object.entries(byArea).map(([k, v]) => [k, { ...v, hours: round(v.hours) }])
    ),
  };
}

/**
 * The sentence under the numbers. §5.4 gives the two shapes; the third is the
 * honest answer when the user has not told us their capacity.
 */
export function workloadSummary(workload) {
  const { plannedHours, availableHours, difference, isOverCapacity } = workload;

  if (availableHours === null) {
    return {
      tone: "idle",
      text: plannedHours
        ? "Set your available hours in Settings to see whether this fits."
        : "Nothing planned for this week yet.",
    };
  }

  if (isOverCapacity) {
    return { tone: "over", text: `${formatDelta(-difference)} over capacity` };
  }

  if (difference === 0) return { tone: "ok", text: "Exactly full — no slack left." };

  return { tone: "ok", text: `${formatDelta(difference)} still available` };
}

/** §22 — never hide the unestimated work behind a clean total. */
export function unestimatedNote(workload) {
  const n = workload.unestimatedCount;
  if (!n) return "";
  return `+ ${n} unestimated ${n === 1 ? "task" : "tasks"} not counted above`;
}

/** Bar segment widths. Over capacity, the excess gets its own hatched segment. */
export function workloadSegments(workload) {
  const { byArea, plannedHours, availableHours } = workload;
  const scale = Math.max(availableHours || 0, plannedHours, 0.0001);

  const segments = AREA_ORDER.map((area) => ({
    area,
    hours: byArea[area]?.hours || 0,
    percent: ((byArea[area]?.hours || 0) / scale) * 100,
  }));

  if (workload.isOverCapacity) {
    // Re-scale so the bar fills exactly, with the overflow marked.
    const overflow = plannedHours - availableHours;
    segments.push({ area: "OVER", hours: round(overflow), percent: (overflow / scale) * 100 });
  }

  return segments.filter((s) => s.percent > 0);
}

function round(n) {
  return Math.round(n * 100) / 100;
}

function formatDelta(hours) {
  const n = round(Math.abs(hours));
  return Number.isInteger(n) ? `${n}h` : `${n}h`;
}
