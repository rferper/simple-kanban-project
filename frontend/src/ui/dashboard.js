/**
 * The unified dashboard — _docs/specs.md §5.
 *
 * One screen that answers "what should I work on today?": a capacity line, three
 * deterministic focus suggestions, and the most relevant active cards from each
 * of the three areas. Not a board — a prioritised summary.
 */

import { h } from "./dom.js";
import { renderCard, renderEmpty } from "./card.js";
import { openCardDrawer } from "./drawer.js";
import { state } from "../store.js";
import { AREAS, AREA_ORDER } from "../domain/types.js";
import { compareForDashboard, formatHours, isActive } from "../domain/cards.js";
import { calculateWorkload, workloadSummary, unestimatedNote, workloadSegments } from "../domain/workload.js";
import { focusToday, focusReason } from "../domain/focus.js";

const COLUMN_LIMIT = 6;

export function renderDashboard() {
  const cards = state.cards;
  const workload = calculateWorkload(cards, state.preferences.weeklyAvailableHours);

  return h(
    "div",
    {},
    h("h1", { class: "greeting" }, greeting(state.preferences.displayName)),

    h(
      "div",
      { class: "dash-top" },
      renderWorkload(workload),
      renderFocus(cards)
    ),

    h(
      "div",
      { class: "dash-columns" },
      AREA_ORDER.map((areaId) => renderColumn(areaId, cards))
    )
  );
}

function greeting(name) {
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return name ? `${part}, ${name} 👋` : `${part} 👋`;
}

/* --------------------------------------------------------------- workload */

function renderWorkload(workload) {
  const summary = workloadSummary(workload);
  const note = unestimatedNote(workload);
  const segments = workloadSegments(workload);

  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-title" }, "This week"),

    h(
      "div",
      { class: "workload-headline" },
      h("span", { class: "workload-big" }, `${formatNumber(workload.plannedHours)}h`),
      h(
        "span",
        { class: "workload-of" },
        workload.availableHours === null
          ? "planned"
          : `planned / ${formatNumber(workload.availableHours)}h available`
      )
    ),

    h("div", { class: `workload-note is-${summary.tone}` }, summary.text),

    h(
      "div",
      { class: "workload-bar", role: "img", "aria-label": summary.text },
      segments.map((seg) =>
        h("div", {
          class: "workload-seg",
          dataset: { seg: seg.area },
          style: { width: `${Math.min(seg.percent, 100)}%` },
          title: `${seg.area === "OVER" ? "Over capacity" : AREAS[seg.area].name}: ${formatNumber(seg.hours)}h`,
        })
      )
    ),

    h(
      "div",
      { class: "workload-legend" },
      AREA_ORDER.map((areaId) => {
        const area = AREAS[areaId];
        const bucket = workload.byArea[areaId];
        return h(
          "div",
          { class: "workload-row" },
          h("span", {
            class: "swatch",
            style: { background: `var(--${swatchVar(areaId)})` },
          }),
          h("span", { class: "label" }, `${area.icon} ${area.name}`),
          h(
            "span",
            { class: "value" },
            bucket.hours ? `${formatNumber(bucket.hours)}h` : "—",
            bucket.unestimated ? h("span", { class: "muted" }, ` +${bucket.unestimated}`) : null
          )
        );
      })
    ),

    note ? h("div", { class: "workload-unestimated" }, note) : null,

    workload.plannedCount === 0
      ? h(
          "div",
          { class: "workload-unestimated" },
          "Mark cards as “planned this week” to see them here."
        )
      : null
  );
}

function swatchVar(areaId) {
  return {
    CURRENT_JOB: "job-current",
    JOB_SEARCH: "job-search",
    LEARNING: "learning",
  }[areaId];
}

/* ------------------------------------------------------------ focus today */

function renderFocus(cards) {
  const picks = focusToday(cards);

  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-title" }, "Focus today"),

    picks.length
      ? h(
          "div",
          { class: "focus-list" },
          picks.map((entry, index) => {
            const card = entry.card;
            const area = AREAS[card.area];
            return h(
              "button",
              {
                class: "focus-item",
                dataset: { area: card.area },
                type: "button",
                onClick: () => openCardDrawer(card.id),
              },
              h("span", { class: "focus-rank" }, String(index + 1)),
              h(
                "span",
                { class: "focus-body" },
                h("span", { class: "focus-title" }, card.job?.company
                  ? `${card.job.company} — ${card.job.role}`
                  : card.title),
                h("span", { class: "focus-meta" }, `${area.icon} ${area.name} · ${focusReason(entry)}`)
              ),
              h("span", { class: "focus-hours" }, formatHours(card.estimatedHours) || "")
            );
          })
        )
      : h(
          "p",
          { class: "muted", style: { margin: 0, fontSize: "13.5px" } },
          "Nothing is pressing. Add a deadline or a priority and suggestions will appear here."
        ),

    picks.length
      ? h(
          "p",
          { class: "focus-caveat" },
          "Suggestions, not a verdict — ranked by deadline, priority and what you have already started."
        )
      : null
  );
}

/* -------------------------------------------------------------- columns */

function renderColumn(areaId, cards) {
  const area = AREAS[areaId];

  const relevant = cards
    .filter((c) => c.area === areaId && isActive(c))
    .sort((a, b) => compareForDashboard(a, b))
    .slice(0, COLUMN_LIMIT);

  const total = cards.filter((c) => c.area === areaId && isActive(c)).length;

  return h(
    "section",
    { class: "dash-col", dataset: { area: areaId } },

    h(
      "div",
      { class: "dash-col-head" },
      h("h2", { class: "dash-col-title" }, `${area.icon} ${area.name}`),
      total ? h("span", { class: "badge badge-count" }, String(total)) : null
    ),

    h(
      "div",
      { class: "dash-col-list" },
      relevant.length
        ? relevant.map((card) =>
            renderCard(card, { onOpen: (c) => openCardDrawer(c.id), draggable: false })
          )
        : renderEmpty(areaId)
    ),

    h(
      "a",
      {
        class: "btn btn-sm",
        href: `#/${area.route}`,
        style: { alignSelf: "flex-start", textDecoration: "none" },
      },
      total > relevant.length ? `View full board (${total})` : "View full board"
    )
  );
}

function formatNumber(n) {
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10);
}
