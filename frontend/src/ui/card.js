/**
 * Card rendering. §8.2, §16.5 — a collapsed card carries title, area, priority,
 * deadline and effort, and nothing else. Secondary metadata stays subdued.
 */

import { h } from "./dom.js";
import {
  AREAS,
  FIT_LABELS,
  PRIORITY_LABELS,
  areaOf,
  isArchived,
  isDone,
  statusLabel,
} from "../domain/types.js";
import {
  cardSubtitle,
  cardTitle,
  deadlineState,
  formatDeadline,
  formatHours,
} from "../domain/cards.js";

/** Priority is shown as a badge only when it is worth the ink (§10.2, §16.5). */
function priorityBadge(card) {
  if (card.priority === "MEDIUM" || card.priority === "LOW") return null;
  return h(
    "span",
    { class: `badge badge-prio-${card.priority}` },
    card.priority === "URGENT" ? "Urgent" : "High"
  );
}

function deadlineBadge(card) {
  const { value, state } = deadlineState(card);
  if (!value) return null;

  const cls =
    state === "overdue" ? "badge badge-overdue" : state === "today" ? "badge badge-today" : "badge";

  const prefix = card.job?.interviewDate === value ? "Interview · " : "";
  return h("span", { class: cls }, `${prefix}${formatDeadline(value)}`);
}

function hoursBadge(card, { prefix = "" } = {}) {
  const label = formatHours(card.estimatedHours);
  if (!label) return null;
  return h("span", { class: "badge" }, `${prefix}${label}`);
}

/**
 * One board card.
 *
 * @param {object} card
 * @param {{onOpen: Function, draggable?: boolean, showArea?: boolean}} options
 */
export function renderCard(card, { onOpen, draggable = true, showArea = false } = {}) {
  const area = areaOf(card.area);
  const job = card.job;
  const done = isDone(card);
  const archived = isArchived(card);

  const el = h(
    "article",
    {
      class: `card${done ? " is-done" : ""}`,
      dataset: { area: card.area, cardId: card.id },
      draggable: draggable && !archived,
      tabindex: "0",
      role: "button",
      "aria-label": `${cardTitle(card)}${job ? `, ${cardSubtitle(card)}` : ""}`,
      onClick: () => onOpen(card),
      onKeydown: (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(card);
        }
      },
    },

    draggable && !archived && h("span", { class: "card-drag", title: "Drag to another column" }, "⠿"),

    h("div", { class: "card-title" }, cardTitle(card)),
    job && cardSubtitle(card) && h("div", { class: "card-sub" }, cardSubtitle(card)),

    h(
      "div",
      { class: "card-meta" },

      showArea && h("span", { class: "badge badge-area" }, `${area.icon} ${area.name}`),

      job && job.fit && job.fit !== "MEDIUM"
        ? h(
            "span",
            { class: "badge" },
            job.fit === "DREAM" ? `⭐ ${FIT_LABELS.DREAM}` : FIT_LABELS[job.fit]
          )
        : null,

      priorityBadge(card),
      deadlineBadge(card),
      hoursBadge(card, { prefix: job ? "Prep: " : "" }),

      job?.location && h("span", { class: "badge badge-tag" }, job.location),

      card.plannedThisWeek && !done ? h("span", { class: "badge" }, "📌 This week") : null,

      card.subtasks?.length
        ? h(
            "span",
            { class: "badge" },
            `${card.subtasks.filter((s) => s.done).length}/${card.subtasks.length}`
          )
        : null,

      archived && h("span", { class: "badge" }, "Archived")
    )
  );

  if (draggable && !archived) attachDrag(el, card);
  return el;
}

/**
 * A dashboard row: the same card, told to be quieter. §5.2 — this is the
 * prioritised summary, not the board.
 */
export function renderCompactCard(card, { onOpen }) {
  return renderCard(card, { onOpen, draggable: false });
}

/* ------------------------------------------------------------ drag & drop */

let dragging = null;

function attachDrag(el, card) {
  el.addEventListener("dragstart", (event) => {
    dragging = { id: card.id, area: card.area, from: card.status };
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", card.id);
    // The class lands after the drag image is taken, so the ghost looks normal.
    requestAnimationFrame(() => el.classList.add("is-dragging"));
  });

  el.addEventListener("dragend", () => {
    el.classList.remove("is-dragging");
    dragging = null;
    document
      .querySelectorAll(".column.is-drop-target")
      .forEach((c) => c.classList.remove("is-drop-target"));
  });
}

export function getDragging() {
  return dragging;
}

/**
 * Wire a column as a drop target. Only accepts cards from its own board, so a
 * job can never land in the Learning column.
 */
export function attachDropTarget(columnEl, { area, status, onDrop }) {
  const accepts = () => dragging && dragging.area === area && dragging.from !== status;

  columnEl.addEventListener("dragover", (event) => {
    if (!accepts()) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    columnEl.classList.add("is-drop-target");
  });

  columnEl.addEventListener("dragleave", (event) => {
    if (!columnEl.contains(event.relatedTarget)) columnEl.classList.remove("is-drop-target");
  });

  columnEl.addEventListener("drop", (event) => {
    columnEl.classList.remove("is-drop-target");
    if (!accepts()) return;
    event.preventDefault();
    const id = dragging.id;
    dragging = null;
    onDrop(id, status);
  });
}

/** §17 — empty states are part of the product, not a fallback. */
export function renderEmpty(area, { small = false } = {}) {
  const def = AREAS[area];
  if (small) return h("div", { class: "empty-sm" }, "Nothing here yet");

  return h(
    "div",
    { class: "empty" },
    h("span", { class: "empty-emoji" }, def.icon),
    h("div", { class: "empty-title" }, def.empty.title.replace(` ${def.icon}`, "")),
    h("div", { class: "empty-hint" }, def.empty.hint)
  );
}

export function statusChip(card) {
  return h("span", { class: "badge" }, statusLabel(card.area, card.status));
}

export function priorityLabel(card) {
  return PRIORITY_LABELS[card.priority] || card.priority;
}
