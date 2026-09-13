/**
 * Adding a job — _docs/specs.md §15.
 *
 * Two doors: create manually, or paste an advert and let the extraction fill
 * the form in. The extracted result is *always* shown as an editable preview
 * before anything is saved (§15.3), and the pasted text is never thrown away
 * when extraction fails.
 */

import { h, field, select, focusFirst } from "./dom.js";
import { openModal, toastError, toastOk } from "./overlay.js";
import { actions } from "../store.js";
import { api } from "../api/client.js";
import { FIT_LABELS, WORK_MODE_LABELS } from "../domain/types.js";
import { openCardDrawer } from "./drawer.js";

export function openAddJobDialog() {
  openModal((rerender, close) =>
    h(
      "div",
      { dataset: { area: "JOB_SEARCH" } },
      h("h2", { class: "modal-title" }, "Add a job"),
      h("p", { class: "modal-sub" }, "Two ways in. Both end up as an editable card in Interesting."),

      h(
        "div",
        { class: "choice-grid" },
        h(
          "button",
          {
            class: "choice",
            type: "button",
            onClick: () => {
              close();
              openManualJobDialog();
            },
          },
          h("div", { class: "choice-emoji" }, "✍️"),
          h("div", { class: "choice-name" }, "Create manually"),
          h("div", { class: "choice-hint" }, "Company and role is enough to start.")
        ),
        h(
          "button",
          {
            class: "choice",
            type: "button",
            onClick: () => {
              close();
              openPasteAdvertDialog();
            },
          },
          h("div", { class: "choice-emoji" }, "✨"),
          h("div", { class: "choice-name" }, "Paste job advert"),
          h("div", { class: "choice-hint" }, "Pull out the details, then check them yourself.")
        )
      )
    )
  );
}

/* ------------------------------------------------------------ manual path */

export function openManualJobDialog(prefill = {}) {
  openModal((rerender, close) => {
    const form = h(
      "form",
      {
        dataset: { area: "JOB_SEARCH" },
        onSubmit: async (event) => {
          event.preventDefault();
          await saveJob(form, close);
        },
      },
      h("h2", { class: "modal-title" }, "New job"),
      h("p", { class: "modal-sub" }, "Everything except the identity of the role is optional."),
      jobFields(prefill),
      h(
        "div",
        { class: "modal-foot" },
        h("button", { class: "btn btn-ghost", type: "button", onClick: close }, "Cancel"),
        h("button", { class: "btn btn-primary", type: "submit" }, "Save job")
      )
    );
    return form;
  });
}

/* ------------------------------------------------------------- paste path */

export function openPasteAdvertDialog() {
  let advert = "";
  let stage = "input"; // input | working | preview | failed
  let result = null;
  let errorMessage = "";

  openModal((rerender, close) => {
    if (stage === "preview") return renderPreview();
    return renderInput();

    function renderInput() {
      const busy = stage === "working";

      const form = h(
        "form",
        {
          dataset: { area: "JOB_SEARCH" },
          onSubmit: async (event) => {
            event.preventDefault();
            const textarea = form.elements.advert;
            advert = textarea.value;

            stage = "working";
            errorMessage = "";
            rerender();

            try {
              result = await api.ai.extractJobAdvert(advert);
              stage = "preview";
            } catch (error) {
              // §15.3 — keep the advert, say something useful, offer both exits.
              stage = "failed";
              errorMessage = error.message;
            }
            rerender();
          },
        },

        h("h2", { class: "modal-title" }, "Paste a job advert"),
        h(
          "p",
          { class: "modal-sub" },
          "Paste the whole thing. You will see everything it found before anything is saved."
        ),

        stage === "failed" ? h("div", { class: "notice notice-warn" }, errorMessage) : null,

        h("textarea", {
          class: "textarea",
          name: "advert",
          style: { minHeight: "220px" },
          placeholder:
            "Company: …\nRole: …\n\nAbout the role\n…\n\nRequirements\n- …\n- …",
          value: advert,
          disabled: busy,
        }),

        h(
          "div",
          { class: "modal-foot" },
          h(
            "button",
            { class: "btn btn-ghost", type: "button", onClick: close, disabled: busy },
            "Cancel"
          ),
          h(
            "button",
            {
              class: "btn",
              type: "button",
              disabled: busy,
              onClick: () => {
                close();
                openManualJobDialog(advert ? { jobDescription: advert } : {});
              },
            },
            "Create manually instead"
          ),
          h(
            "button",
            { class: "btn btn-primary", type: "submit", disabled: busy },
            busy ? h("span", { class: "spinner" }) : null,
            busy ? "Reading…" : stage === "failed" ? "Try again" : "Generate job card"
          )
        )
      );

      if (busy) requestAnimationFrame(() => form.elements.advert.blur());
      return form;
    }

    function renderPreview() {
      const extracted = result.extracted;
      const prefill = {
        company: extracted.company,
        role: extracted.role,
        location: extracted.location,
        salaryText: extracted.salaryText,
        workMode: extracted.workMode,
        applicationDeadline: extracted.applicationDeadline || "",
        requirements: extracted.requirements,
        niceToHave: extracted.niceToHave,
        notes: extracted.summary,
        jobDescription: advert,
        tags: extracted.tags,
      };

      const form = h(
        "form",
        {
          dataset: { area: "JOB_SEARCH" },
          onSubmit: async (event) => {
            event.preventDefault();
            await saveJob(form, close, { tags: extracted.tags });
          },
        },

        h("h2", { class: "modal-title" }, "Check what I found"),
        h(
          "p",
          { class: "modal-sub" },
          "Nothing is saved yet. Fix anything that is wrong — extraction is a first draft, not a fact."
        ),

        result.missing.length
          ? h(
              "div",
              { class: "notice notice-warn" },
              `I couldn't find the ${result.missing.join(" or ")}. Fill ${
                result.missing.length > 1 ? "them" : "it"
              } in below.`
            )
          : null,

        extracted.tags.length
          ? h(
              "div",
              { class: "chips", style: { marginBottom: "12px" } },
              extracted.tags.map((tag) => h("span", { class: "badge badge-tag" }, tag))
            )
          : null,

        jobFields(prefill),

        h(
          "div",
          { class: "modal-foot" },
          h(
            "button",
            {
              class: "btn btn-ghost",
              type: "button",
              onClick: () => {
                stage = "input";
                rerender();
              },
            },
            "Back to the advert"
          ),
          h("button", { class: "btn btn-primary", type: "submit" }, "Save job card")
        )
      );

      requestAnimationFrame(() => focusFirst(form));
      return form;
    }
  });
}

/* ------------------------------------------------------------------ parts */

function jobFields(prefill = {}) {
  return h(
    "div",
    {},
    h(
      "div",
      { class: "field-row" },
      field("Company", h("input", { class: "input", name: "company", value: prefill.company || "", placeholder: "Anthropic" })),
      field("Role", h("input", { class: "input", name: "role", value: prefill.role || "", placeholder: "Research Engineer" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Location", h("input", { class: "input", name: "location", value: prefill.location || "" })),
      field("Work mode", select(Object.entries(WORK_MODE_LABELS), prefill.workMode || "UNKNOWN", { name: "workMode" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Salary", h("input", { class: "input", name: "salaryText", value: prefill.salaryText || "" })),
      field("Fit", select(Object.entries(FIT_LABELS), prefill.fit || "MEDIUM", { name: "fit" }))
    ),

    h(
      "div",
      { class: "field-row" },
      field("Apply by", h("input", { class: "input", type: "date", name: "applicationDeadline", value: prefill.applicationDeadline || "" })),
      field("Prep estimate (hours)", h("input", { class: "input", type: "number", step: "0.5", min: "0", name: "estimatedHours", value: prefill.estimatedHours ?? "", placeholder: "e.g. 2" }))
    ),

    field("Job URL", h("input", { class: "input", type: "url", name: "jobUrl", value: prefill.jobUrl || "", placeholder: "https://" })),

    field(
      "Requirements (one per line)",
      h("textarea", { class: "textarea", name: "requirements" }, (prefill.requirements || []).join("\n"))
    ),
    field(
      "Nice to have (one per line)",
      h("textarea", { class: "textarea", name: "niceToHave" }, (prefill.niceToHave || []).join("\n"))
    ),
    field("Notes", h("textarea", { class: "textarea", name: "notes" }, prefill.notes || "")),

    h("input", { type: "hidden", name: "jobDescription", value: prefill.jobDescription || "" })
  );
}

async function saveJob(form, close, { tags = [] } = {}) {
  const data = new FormData(form);
  const get = (name) => (data.get(name) ?? "").toString().trim();

  const company = get("company");
  const role = get("role");

  // §29 — one useful identifier is the real requirement.
  if (!company && !role) {
    toastError("Give the role a company or a title so you can find it again.");
    focusFirst(form);
    return;
  }

  const hours = get("estimatedHours");

  try {
    const card = await actions.createJob({
      title: [company, role].filter(Boolean).join(" — "),
      status: "INTERESTING",
      priority: "MEDIUM",
      estimatedHours: hours === "" ? null : Number(hours),
      tags,
      job: {
        company,
        role,
        jobUrl: get("jobUrl"),
        location: get("location"),
        workMode: get("workMode"),
        salaryText: get("salaryText"),
        fit: get("fit"),
        applicationDeadline: get("applicationDeadline") || null,
        requirements: splitLines(get("requirements")),
        niceToHave: splitLines(get("niceToHave")),
        notes: get("notes"),
        jobDescription: get("jobDescription"),
      },
    });

    close();
    toastOk(`${company || role} saved to Interesting`);
    openCardDrawer(card.id);
  } catch (error) {
    toastError(error.message);
  }
}

function splitLines(text) {
  return text
    .split("\n")
    .map((l) => l.replace(/^[-•*]\s*/, "").trim())
    .filter(Boolean);
}
