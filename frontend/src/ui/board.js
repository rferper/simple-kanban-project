/**
 * A full Kanban board — _docs/specs.md §6–§9, §13, §14, §21.
 *
 * One board per area. Columns come from the area definition, so adding a status
 * is a one-line change in `domain/types.js` rather than a change here.
 */

import { h, select, debounce } from "./dom.js";
import { renderCard, renderEmpty, attachDropTarget } from "./card.js";
import { openCardDrawer } from "./drawer.js";
import { openAddJobDialog } from "./job-import.js";
import { toast, toastError } from "./overlay.js";
import { actions, state } from "../store.js";
import { AREAS, PRIORITY_LABELS, FIT_LABELS, isArchived, isDone } from "../domain/types.js";
import { daysUntil, effectiveDate, searchableText, compareForDashboard } from "../domain/cards.js";

export function renderBoard(areaId) {
  const area = AREAS[areaId];
  const isJobs = areaId === "JOB_SEARCH";

  const all = state.cards.filter((c) => c.area === areaId);
  const onBoard = all.filter((c) => !isArchived(c));
  const archived = all.filter(isArchived);
  const visible = applyFilters(onBoard, state.filters, areaId);

  return h(
    "div",
    { dataset: { area: areaId } },

    h(
      "div",
      { class: "page-head" },
      h(
        "div",
        {},
        h("h1", { class: "page-title" }, `${area.icon} ${area.name}`),
        h(
          "div",
          { class: "page-sub" },
          `${onBoard.length} on the board${archived.length ? ` · ${archived.length} archived` : ""}`
        )
      ),
      h(
        "div",
        { class: "page-actions" },
        isJobs
          ? h("button", { class: "btn btn-primary", onClick: openAddJobDialog }, "＋ Add job")
          : h(
              "button",
              {
                class: "btn btn-primary",
                onClick: () => focusQuickAdd(area.defaultStatus),
              },
              `＋ ${area.addLabel}`
            ),
        isJobs && archived.length
          ? h(
              "button",
              {
                class: "btn",
                onClick: () => actions.setShowArchive(!state.showArchive),
              },
              state.showArchive ? "Hide archive" : `Archive (${archived.length})`
            )
          : null
      )
    ),

    renderFilters(areaId, onBoard),

    all.length === 0
      ? h("div", { class: "panel" }, renderEmpty(areaId))
      : h(
          "div",
          { class: "board" },
          area.statuses.map((status) => renderColumn(area, status, visible))
        ),

    isJobs && state.showArchive ? renderArchive(archived) : null,

    visible.length === 0 && all.length > 0
      ? h(
          "p",
          { class: "muted", style: { textAlign: "center", marginTop: "16px" } },
          "Nothing matches these filters."
        )
      : null
  );
}

function renderColumn(area, status, cards) {
  const inColumn = cards
    .filter((c) => c.status === status)
    .sort((a, b) => compareForDashboard(a, b));

  const column = h(
    "section",
    { class: "column", dataset: { area: area.id, status } },

    h(
      "div",
      { class: "column-head" },
      h("h2", { class: "column-name" }, area.statusLabels[status]),
      h("span", { class: "badge badge-count" }, String(inColumn.length))
    ),

    h(
      "div",
      { class: "column-list" },
      inColumn.length
        ? inColumn.map((card) => renderCard(card, { onOpen: (c) => openCardDrawer(c.id) }))
        : h("div", { class: "empty-sm" }, "—")
    ),

    renderQuickAdd(area, status)
  );

  // §14 — drop changes status, optimistically, and says so.
  attachDropTarget(column, {
    area: area.id,
    status,
    onDrop: async (cardId, newStatus) => {
      try {
        const card = await actions.moveCard(cardId, newStatus);
        if (card && isDone(card)) toast("Nice — one less thing to carry.");
      } catch (error) {
        toastError(error.message);
      }
    },
  });

  return column;
}

/** §13 — title is the only required field, and no wizard. */
function renderQuickAdd(area, status) {
  if (area.id === "JOB_SEARCH") {
    if (status !== area.defaultStatus) return null;
    return h(
      "button",
      { class: "add-trigger", onClick: openAddJobDialog },
      "＋ Add job"
    );
  }

  const wrap = h("div", { dataset: { quickAdd: status } });

  const trigger = h(
    "button",
    {
      class: "add-trigger",
      onClick: () => {
        wrap.replaceChildren(form);
        form.elements.title.focus();
      },
    },
    "＋ Add card"
  );

  const form = h(
    "form",
    {
      class: "quick-add",
      onSubmit: async (event) => {
        event.preventDefault();
        const input = form.elements.title;
        const title = input.value.trim();
        if (!title) return;

        input.value = "";
        try {
          await actions.createCard({ title, area: area.id, status });
          input.focus();
        } catch (error) {
          input.value = title;
          toastError(error.message);
        }
      },
    },
    h("input", {
      class: "input",
      name: "title",
      maxlength: 200,
      placeholder: "What needs doing?",
      onBlur: () => {
        if (!form.elements.title.value.trim()) wrap.replaceChildren(trigger);
      },
    }),
    h("button", { class: "btn btn-sm btn-primary", type: "submit" }, "Add")
  );

  wrap.replaceChildren(trigger);
  return wrap;
}

function focusQuickAdd(status) {
  const wrap = document.querySelector(`[data-quick-add="${status}"] .add-trigger`);
  if (wrap) wrap.click();
}

/* ---------------------------------------------------------------- filters */

function renderFilters(areaId, cards) {
  const { filters } = state;
  const isJobs = areaId === "JOB_SEARCH";

  const tags = [...new Set(cards.flatMap((c) => c.tags || []))].sort();
  const companies = isJobs
    ? [...new Set(cards.map((c) => c.job?.company).filter(Boolean))].sort()
    : [];

  const active =
    filters.query || filters.priority || filters.tag || filters.due || filters.fit || filters.company;

  return h(
    "div",
    { class: "filters" },
    h("span", { class: "filters-label" }, "Filter"),

    h("input", {
      class: "input",
      type: "search",
      placeholder: "Search…",
      value: filters.query,
      oninput: debounce((event) => actions.setFilters({ query: event.target.value }), 180),
    }),

    select([["", "Any priority"], ...Object.entries(PRIORITY_LABELS)], filters.priority, {
      onChange: (e) => actions.setFilters({ priority: e.target.value }),
    }),

    select(
      [
        ["", "Any deadline"],
        ["overdue", "Overdue"],
        ["today", "Due today"],
        ["week", "Next 7 days"],
        ["none", "No deadline"],
      ],
      filters.due,
      { onChange: (e) => actions.setFilters({ due: e.target.value }) }
    ),

    tags.length
      ? select([["", "Any tag"], ...tags.map((t) => [t, t])], filters.tag, {
          onChange: (e) => actions.setFilters({ tag: e.target.value }),
        })
      : null,

    isJobs
      ? select([["", "Any fit"], ...Object.entries(FIT_LABELS)], filters.fit, {
          onChange: (e) => actions.setFilters({ fit: e.target.value }),
        })
      : null,

    isJobs && companies.length
      ? select([["", "Any company"], ...companies.map((c) => [c, c])], filters.company, {
          onChange: (e) => actions.setFilters({ company: e.target.value }),
        })
      : null,

    active
      ? h("button", { class: "btn btn-sm btn-ghost", onClick: () => actions.clearFilters() }, "Clear")
      : null
  );
}

function applyFilters(cards, filters, areaId) {
  return cards.filter((card) => {
    if (filters.query && !searchableText(card).includes(filters.query.toLowerCase())) return false;
    if (filters.priority && card.priority !== filters.priority) return false;
    if (filters.tag && !(card.tags || []).includes(filters.tag)) return false;

    if (areaId === "JOB_SEARCH") {
      if (filters.fit && card.job?.fit !== filters.fit) return false;
      if (filters.company && card.job?.company !== filters.company) return false;
    }

    if (filters.due) {
      const days = daysUntil(effectiveDate(card));
      if (filters.due === "none" && days !== null) return false;
      if (filters.due === "overdue" && !(days !== null && days < 0)) return false;
      if (filters.due === "today" && days !== 0) return false;
      if (filters.due === "week" && !(days !== null && days >= 0 && days <= 7)) return false;
    }

    return true;
  });
}

/* ---------------------------------------------------------------- archive */

/** §8.1 — archived applications leave the board but keep everything. */
function renderArchive(cards) {
  return h(
    "section",
    { class: "panel", style: { marginTop: "24px" } },
    h("div", { class: "panel-title" }, "Archive"),
    h(
      "p",
      { class: "muted", style: { marginTop: 0, fontSize: "13px" } },
      "Applications that are no longer active. Everything they held is still here — keep notes for future applications."
    ),
    h(
      "div",
      { class: "dash-col-list", style: { marginTop: "12px" } },
      cards.length
        ? cards.map((card) => renderCard(card, { onOpen: (c) => openCardDrawer(c.id), draggable: false }))
        : h("div", { class: "empty-sm" }, "Nothing archived.")
    )
  );
}
