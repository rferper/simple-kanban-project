/**
 * Card detail drawer — _docs/specs.md §12.
 *
 * A drawer rather than a modal, so the board stays visible behind it. It opens
 * read-only with the controls people reach for most (status, priority, planned
 * this week, subtasks) live in place, and switches to a full form on Edit.
 */

import { h, field, select, focusFirst } from "./dom.js";
import { openDrawer, toast, toastError, toastOk, confirmDialog } from "./overlay.js";
import { actions, cardById, jobCards, learningCards, subscribe } from "../store.js";
import {
  AREAS,
  FIT_LABELS,
  OUTCOME,
  OUTCOME_LABELS,
  PRIORITY_LABELS,
  WORK_MODE_LABELS,
  areaOf,
  isArchived,
  isDone,
} from "../domain/types.js";
import {
  cardSubtitle,
  cardTitle,
  formatDate,
  formatDeadline,
  formatHours,
  normaliseHours,
  parseTags,
  validateCard,
} from "../domain/cards.js";

export function openCardDrawer(cardOrId) {
  const id = typeof cardOrId === "string" ? cardOrId : cardOrId.id;

  let editing = false;
  let errors = {};
  let draft = null;

  const handle = openDrawer((rerender, close) => {
    const card = cardById(id);
    if (!card) {
      close();
      return h("div");
    }
    return editing
      ? renderForm(card, { draft, errors, onCancel, onSave, close })
      : renderDetail(card, { onEdit, close, rerender });

    function onEdit() {
      editing = true;
      draft = toDraft(card);
      errors = {};
      rerender();
      focusFirst(document.getElementById("drawer"));
    }

    function onCancel() {
      editing = false;
      errors = {};
      rerender();
    }

    async function onSave(values) {
      const check = validateCard(values, { area: card.area, status: values.status });
      if (!check.ok) {
        errors = check.errors;
        draft = values;
        rerender();
        return;
      }

      try {
        const { job, ...base } = values;
        await actions.updateCard(card.id, {
          ...base,
          estimatedHours: normaliseHours(base.estimatedHours),
          tags: parseTags(base.tags),
        });
        if (job) await actions.updateJob(card.id, job);
        editing = false;
        errors = {};
        toastOk("Saved");
        rerender();
      } catch (error) {
        toastError(error.message);
      }
    }
  });

  // Keep the drawer in step with the board behind it, but never yank a form
  // out from under someone mid-edit.
  const unsubscribe = subscribe(() => {
    if (!editing) handle.rerender();
  });

  const originalClose = handle.close;
  handle.close = () => {
    unsubscribe();
    originalClose();
  };

  return handle;
}

/* ---------------------------------------------------------------- reading */

function renderDetail(card, { onEdit, close, rerender }) {
  const area = areaOf(card.area);
  const job = card.job;
  const done = isDone(card);
  const archived = isArchived(card);

  return h(
    "div",
    { dataset: { area: card.area } },

    h(
      "header",
      { class: "drawer-head" },
      h(
        "div",
        { class: "drawer-head-body" },
        h("span", { class: "badge badge-area" }, `${area.icon} ${area.name}`),
        h("h2", { style: { fontSize: "18px", marginTop: "6px" } }, cardTitle(card)),
        cardSubtitle(card) && h("div", { class: "muted", style: { fontWeight: 600 } }, cardSubtitle(card))
      ),
      h("button", { class: "btn-icon", onClick: close, "aria-label": "Close" }, "✕")
    ),

    h(
      "div",
      { class: "drawer-body" },

      archived &&
        h("div", { class: "notice notice-info" }, OUTCOME_LABELS[job.outcome]),

      /* ---- live controls ---- */
      h(
        "section",
        { class: "drawer-section" },
        h(
          "div",
          { class: "field-row" },
          field(
            "Status",
            select(
              area.statuses.map((s) => [s, area.statusLabels[s]]),
              card.status,
              {
                onChange: async (event) => {
                  try {
                    await actions.moveCard(card.id, event.target.value);
                  } catch (error) {
                    toastError(error.message);
                  }
                },
              }
            )
          ),
          field(
            "Priority",
            select(
              Object.entries(PRIORITY_LABELS),
              card.priority,
              {
                onChange: async (event) => {
                  try {
                    await actions.updateCard(card.id, { priority: event.target.value });
                  } catch (error) {
                    toastError(error.message);
                  }
                },
              }
            )
          )
        ),

        h(
          "label",
          { class: "check" },
          h("input", {
            type: "checkbox",
            checked: card.plannedThisWeek,
            onChange: async (event) => {
              try {
                await actions.setPlannedThisWeek(card.id, event.target.checked);
              } catch (error) {
                toastError(error.message);
              }
            },
          }),
          "Planned this week",
          h("span", { class: "muted", style: { fontWeight: 500 } }, "— counts toward your workload")
        )
      ),

      /* ---- base details ---- */
      h(
        "section",
        { class: "drawer-section" },
        card.description
          ? h("p", { style: { margin: "0 0 12px", whiteSpace: "pre-wrap" } }, card.description)
          : h("p", { class: "muted", style: { margin: "0 0 12px" } }, "No description yet."),

        h(
          "dl",
          { class: "detail-grid" },
          row("Deadline", card.deadline ? `${formatDate(card.deadline)} · ${formatDeadline(card.deadline)}` : "—"),
          row("Estimate", formatHours(card.estimatedHours) || "Not estimated"),
          row("Created", formatDate(card.createdAt.slice(0, 10))),
          card.completedAt && row("Completed", formatDate(card.completedAt.slice(0, 10)))
        ),

        card.tags?.length
          ? h(
              "div",
              { class: "chips", style: { marginTop: "12px" } },
              card.tags.map((tag) => h("span", { class: "badge badge-tag" }, tag))
            )
          : null
      ),

      /* ---- job specifics (§12.2) ---- */
      job && renderJobSection(card, job),

      /* ---- subtasks ---- */
      renderSubtasks(card, rerender),

      /* ---- links (§9.3) ---- */
      card.area === "LEARNING" ? renderLearningLinks(card) : null,

      /* ---- actions (§12.1, §39) ---- */
      h(
        "div",
        { class: "drawer-foot" },
        h("button", { class: "btn btn-primary", onClick: onEdit }, "Edit"),

        !done &&
          !archived &&
          h(
            "button",
            {
              class: "btn",
              onClick: async () => {
                try {
                  await actions.completeCard(card.id, card.area);
                  toast("Nice — one less thing to carry.");
                } catch (error) {
                  toastError(error.message);
                }
              },
            },
            "✓ Mark complete"
          ),

        job && !archived
          ? h(
              "button",
              {
                class: "btn",
                onClick: () => openArchiveDialog(card),
              },
              "Archive application"
            )
          : null,

        job && archived
          ? h(
              "button",
              {
                class: "btn",
                onClick: async () => {
                  try {
                    await actions.setOutcome(card.id, OUTCOME.ACTIVE);
                    toastOk("Back on the board");
                  } catch (error) {
                    toastError(error.message);
                  }
                },
              },
              "Restore to board"
            )
          : null,

        h(
          "button",
          {
            class: "btn btn-danger",
            onClick: () =>
              confirmDialog({
                title: "Delete card?",
                body: "This cannot be undone.",
                confirmLabel: "Delete",
                onConfirm: async () => {
                  try {
                    await actions.deleteCard(card.id);
                    close();
                    toastOk("Card deleted");
                  } catch (error) {
                    toastError(error.message);
                  }
                },
              }),
          },
          "Delete"
        )
      )
    )
  );
}

function row(label, value) {
  if (!value) return null;
  return [h("dt", {}, label), h("dd", {}, value)];
}

function renderJobSection(card, job) {
  const learning = learningCards();
  const linked = (job.relatedLearningCardIds || [])
    .map((id) => learning.find((c) => c.id === id))
    .filter(Boolean);

  const unlinked = learning.filter((c) => !(job.relatedLearningCardIds || []).includes(c.id));

  return h(
    "section",
    { class: "drawer-section" },
    h("div", { class: "panel-title" }, "Application"),

    h(
      "dl",
      { class: "detail-grid" },
      row("Company", job.company || "—"),
      row("Role", job.role || "—"),
      row("Location", job.location || "—"),
      row("Work mode", WORK_MODE_LABELS[job.workMode] || "—"),
      row("Salary", job.salaryText || "—"),
      row("Fit", FIT_LABELS[job.fit] || "—"),
      row("Applied by", job.applicationDeadline ? formatDate(job.applicationDeadline) : "—"),
      row("Interview", job.interviewDate ? formatDate(job.interviewDate) : "—"),
      row("CV version", job.cvVersion || "—"),
      row("Contact", [job.contactName, job.contactDetails].filter(Boolean).join(" · ") || "—"),
      row("Outcome", OUTCOME_LABELS[job.outcome] || "—")
    ),

    job.jobUrl
      ? h(
          "p",
          { style: { marginTop: "12px" } },
          h(
            "a",
            { href: job.jobUrl, target: "_blank", rel: "noreferrer noopener" },
            "Open the advert ↗"
          )
        )
      : null,

    job.requirements?.length
      ? h(
          "div",
          { style: { marginTop: "14px" } },
          h("div", { class: "panel-title" }, "Requirements"),
          h("ul", { style: { margin: 0, paddingLeft: "18px", fontSize: "13.5px" } },
            job.requirements.map((r) => h("li", {}, r)))
        )
      : null,

    job.niceToHave?.length
      ? h(
          "div",
          { style: { marginTop: "14px" } },
          h("div", { class: "panel-title" }, "Nice to have"),
          h("ul", { style: { margin: 0, paddingLeft: "18px", fontSize: "13.5px" } },
            job.niceToHave.map((r) => h("li", {}, r)))
        )
      : null,

    job.jobDescription
      ? h(
          "details",
          { style: { marginTop: "14px" } },
          h("summary", { style: { cursor: "pointer", fontWeight: 700, fontSize: "13.5px" } },
            "The advert"),
          h("p", { style: { whiteSpace: "pre-wrap", fontSize: "13px", color: "var(--ink-2)" } },
            job.jobDescription)
        )
      : null,

    job.notes
      ? h(
          "div",
          { style: { marginTop: "14px" } },
          h("div", { class: "panel-title" }, "Notes"),
          h("p", { style: { margin: 0, whiteSpace: "pre-wrap", fontSize: "13.5px" } }, job.notes)
        )
      : null,

    /* Learning linked to this job (§9.3) */
    h(
      "div",
      { style: { marginTop: "16px" } },
      h("div", { class: "panel-title" }, "Preparing with"),
      linked.length
        ? h(
            "div",
            { class: "link-list" },
            linked.map((c) =>
              h(
                "div",
                { class: "link-row" },
                h("span", {}, AREAS.LEARNING.icon),
                h("span", { class: "link-name" }, c.title),
                h(
                  "button",
                  {
                    class: "btn-icon",
                    title: "Unlink",
                    onClick: async () => {
                      try {
                        await actions.unlinkLearningFromJob(c.id, card.id);
                      } catch (error) {
                        toastError(error.message);
                      }
                    },
                  },
                  "✕"
                )
              )
            )
          )
        : h("p", { class: "muted", style: { margin: 0, fontSize: "13px" } },
            "No learning linked to this role yet."),

      unlinked.length
        ? h(
            "div",
            { class: "row", style: { marginTop: "8px" } },
            select(
              [["", "Link a learning goal…"], ...unlinked.map((c) => [c.id, c.title])],
              "",
              {
                onChange: async (event) => {
                  const learningId = event.target.value;
                  if (!learningId) return;
                  try {
                    await actions.linkLearningToJob(learningId, card.id);
                    toastOk("Linked");
                  } catch (error) {
                    toastError(error.message);
                  }
                },
              }
            )
          )
        : null
    )
  );
}

function renderSubtasks(card, rerender) {
  const done = card.subtasks.filter((s) => s.done).length;

  return h(
    "section",
    { class: "drawer-section" },
    h(
      "div",
      { class: "row-between" },
      h("div", { class: "panel-title", style: { marginBottom: 0 } }, "Subtasks"),
      card.subtasks.length ? h("span", { class: "badge" }, `${done}/${card.subtasks.length}`) : null
    ),

    h(
      "div",
      { class: "subtasks", style: { marginTop: "8px" } },
      card.subtasks.map((subtask) =>
        h(
          "div",
          { class: `subtask${subtask.done ? " is-done" : ""}` },
          h("input", {
            type: "checkbox",
            id: `st-${subtask.id}`,
            checked: subtask.done,
            onChange: async () => {
              try {
                await actions.toggleSubtask(card.id, subtask.id);
              } catch (error) {
                toastError(error.message);
              }
            },
          }),
          h("label", { for: `st-${subtask.id}` }, subtask.title),
          h(
            "button",
            {
              class: "btn-icon",
              title: "Remove",
              onClick: async () => {
                try {
                  await actions.removeSubtask(card.id, subtask.id);
                } catch (error) {
                  toastError(error.message);
                }
              },
            },
            "✕"
          )
        )
      )
    ),

    h(
      "form",
      {
        class: "quick-add",
        style: { marginTop: "8px" },
        onSubmit: async (event) => {
          event.preventDefault();
          const input = event.target.elements.subtask;
          const title = input.value.trim();
          if (!title) return;
          input.value = "";
          try {
            await actions.addSubtask(card.id, title);
          } catch (error) {
            toastError(error.message);
          }
        },
      },
      h("input", { class: "input", name: "subtask", placeholder: "Add a subtask…", maxlength: 200 }),
      h("button", { class: "btn btn-sm", type: "submit" }, "Add")
    )
  );
}

function renderLearningLinks(card) {
  const jobs = jobCards().filter((c) => !isArchived(c));
  const linkedIds = card.relatedJobCardIds || [];
  const linked = linkedIds.map((id) => jobs.find((c) => c.id === id)).filter(Boolean);
  const unlinked = jobs.filter((c) => !linkedIds.includes(c.id));

  return h(
    "section",
    { class: "drawer-section" },
    h("div", { class: "panel-title" }, "Relevant for"),

    linked.length
      ? h(
          "div",
          { class: "link-list" },
          linked.map((job) =>
            h(
              "div",
              { class: "link-row" },
              h("span", {}, AREAS.JOB_SEARCH.icon),
              h("span", { class: "link-name" }, `${job.job.company} — ${job.job.role}`),
              h(
                "button",
                {
                  class: "btn-icon",
                  title: "Unlink",
                  onClick: async () => {
                    try {
                      await actions.unlinkLearningFromJob(card.id, job.id);
                    } catch (error) {
                      toastError(error.message);
                    }
                  },
                },
                "✕"
              )
            )
          )
        )
      : h(
          "p",
          { class: "muted", style: { margin: 0, fontSize: "13px" } },
          "Not linked to a role yet. Linking keeps this board honest about why the work matters."
        ),

    unlinked.length
      ? h(
          "div",
          { style: { marginTop: "8px" } },
          select([["", "Link to a role…"], ...unlinked.map((j) => [j.id, `${j.job.company} — ${j.job.role}`])],
            "",
            {
              onChange: async (event) => {
                const jobId = event.target.value;
                if (!jobId) return;
                try {
                  await actions.linkLearningToJob(card.id, jobId);
                  toastOk("Linked");
                } catch (error) {
                  toastError(error.message);
                }
              },
            })
        )
      : null
  );
}

/* ---------------------------------------------------------------- editing */

function toDraft(card) {
  return {
    title: card.title,
    description: card.description || "",
    deadline: card.deadline || "",
    estimatedHours: card.estimatedHours ?? "",
    priority: card.priority,
    status: card.status,
    plannedThisWeek: card.plannedThisWeek,
    tags: (card.tags || []).join(", "),
    job: card.job ? { ...card.job } : null,
  };
}

function renderForm(card, { draft, errors, onCancel, onSave, close }) {
  const area = areaOf(card.area);
  const values = draft || toDraft(card);
  const job = values.job;

  const form = h(
    "form",
    {
      dataset: { area: card.area },
      onSubmit: (event) => {
        event.preventDefault();
        onSave(collect(form, Boolean(job)));
      },
    },

    h(
      "header",
      { class: "drawer-head" },
      h(
        "div",
        { class: "drawer-head-body" },
        h("span", { class: "badge badge-area" }, `${area.icon} ${area.name}`),
        h("h2", { style: { fontSize: "18px", marginTop: "6px" } }, "Edit card")
      ),
      h("button", { class: "btn-icon", type: "button", onClick: close, "aria-label": "Close" }, "✕")
    ),

    h(
      "div",
      { class: "drawer-body" },

      field(
        "Title",
        h("input", {
          class: `input${errors.title ? " is-invalid" : ""}`,
          name: "title",
          value: values.title,
          maxlength: 200,
          required: true,
        }),
        { error: errors.title }
      ),

      field(
        "Description",
        h("textarea", { class: "textarea", name: "description" }, values.description)
      ),

      h(
        "div",
        { class: "field-row" },
        field(
          "Status",
          select(area.statuses.map((s) => [s, area.statusLabels[s]]), values.status, {
            name: "status",
          })
        ),
        field(
          "Priority",
          select(Object.entries(PRIORITY_LABELS), values.priority, { name: "priority" })
        )
      ),

      h(
        "div",
        { class: "field-row" },
        field("Deadline", h("input", { class: "input", type: "date", name: "deadline", value: values.deadline })),
        field(
          "Estimate (hours)",
          h("input", {
            class: `input${errors.estimatedHours ? " is-invalid" : ""}`,
            type: "number",
            step: "0.5",
            min: "0",
            name: "estimatedHours",
            value: values.estimatedHours,
            placeholder: "e.g. 1.5",
          }),
          { error: errors.estimatedHours }
        )
      ),

      field(
        "Tags",
        h("input", {
          class: "input",
          name: "tags",
          value: values.tags,
          placeholder: "comma, separated",
        })
      ),

      h(
        "label",
        { class: "check" },
        h("input", { type: "checkbox", name: "plannedThisWeek", checked: values.plannedThisWeek }),
        "Planned this week"
      ),

      job && renderJobFields(job),

      h(
        "div",
        { class: "drawer-foot" },
        h("button", { class: "btn btn-primary", type: "submit" }, "Save changes"),
        h("button", { class: "btn btn-ghost", type: "button", onClick: onCancel }, "Cancel")
      )
    )
  );

  return form;
}

function renderJobFields(job) {
  return h(
    "section",
    { class: "drawer-section" },
    h("div", { class: "panel-title" }, "Application details"),

    h(
      "div",
      { class: "field-row" },
      field("Company", h("input", { class: "input", name: "job.company", value: job.company })),
      field("Role", h("input", { class: "input", name: "job.role", value: job.role }))
    ),

    field("Job URL", h("input", { class: "input", type: "url", name: "job.jobUrl", value: job.jobUrl, placeholder: "https://" })),

    h(
      "div",
      { class: "field-row" },
      field("Location", h("input", { class: "input", name: "job.location", value: job.location })),
      field("Work mode", select(Object.entries(WORK_MODE_LABELS), job.workMode, { name: "job.workMode" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Salary", h("input", { class: "input", name: "job.salaryText", value: job.salaryText })),
      field("Fit", select(Object.entries(FIT_LABELS), job.fit, { name: "job.fit" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Apply by", h("input", { class: "input", type: "date", name: "job.applicationDeadline", value: job.applicationDeadline || "" })),
      field("Interview", h("input", { class: "input", type: "date", name: "job.interviewDate", value: job.interviewDate || "" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("CV version", h("input", { class: "input", name: "job.cvVersion", value: job.cvVersion })),
      field("Outcome", select(Object.entries(OUTCOME_LABELS), job.outcome, { name: "job.outcome" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Contact name", h("input", { class: "input", name: "job.contactName", value: job.contactName })),
      field("Contact details", h("input", { class: "input", name: "job.contactDetails", value: job.contactDetails }))
    ),

    field(
      "Requirements (one per line)",
      h("textarea", { class: "textarea", name: "job.requirements" }, (job.requirements || []).join("\n"))
    ),
    field(
      "Nice to have (one per line)",
      h("textarea", { class: "textarea", name: "job.niceToHave" }, (job.niceToHave || []).join("\n"))
    ),
    field("Notes", h("textarea", { class: "textarea", name: "job.notes" }, job.notes || "")),
    field(
      "The advert",
      h("textarea", { class: "textarea", name: "job.jobDescription" }, job.jobDescription || "")
    )
  );
}

function collect(form, hasJob) {
  const data = new FormData(form);
  const get = (name) => (data.get(name) ?? "").toString();

  const values = {
    title: get("title"),
    description: get("description"),
    status: get("status"),
    priority: get("priority"),
    deadline: get("deadline") || null,
    estimatedHours: get("estimatedHours"),
    tags: get("tags"),
    plannedThisWeek: data.get("plannedThisWeek") === "on",
  };

  if (hasJob) {
    values.job = {
      company: get("job.company"),
      role: get("job.role"),
      jobUrl: get("job.jobUrl"),
      location: get("job.location"),
      workMode: get("job.workMode"),
      salaryText: get("job.salaryText"),
      fit: get("job.fit"),
      applicationDeadline: get("job.applicationDeadline") || null,
      interviewDate: get("job.interviewDate") || null,
      cvVersion: get("job.cvVersion"),
      outcome: get("job.outcome"),
      contactName: get("job.contactName"),
      contactDetails: get("job.contactDetails"),
      requirements: splitLines(get("job.requirements")),
      niceToHave: splitLines(get("job.niceToHave")),
      notes: get("job.notes"),
      jobDescription: get("job.jobDescription"),
    };
  }

  return values;
}

function splitLines(text) {
  return text
    .split("\n")
    .map((l) => l.replace(/^[-•*]\s*/, "").trim())
    .filter(Boolean);
}

/** §16.8 — archiving is routine and neutrally worded. */
function openArchiveDialog(card) {
  confirmDialog({
    title: "Archive this application?",
    body: "It moves off the board and keeps all its notes. Keep notes for future applications.",
    confirmLabel: "Archive",
    danger: false,
    onConfirm: async () => {
      try {
        await actions.setOutcome(card.id, OUTCOME.REJECTED);
        toast("Application archived");
      } catch (error) {
        toastError(error.message);
      }
    },
  });
}
