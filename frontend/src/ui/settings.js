/**
 * Settings — _docs/specs.md §20. Deliberately two fields.
 *
 * The second panel is the session: who you are signed in as, where the API is,
 * and the way out.
 */

import { h, field } from "./dom.js";
import { toastError, toastOk, confirmDialog } from "./overlay.js";
import { actions, state } from "../store.js";
import { api } from "../api/client.js";

export function renderSettings() {
  const { preferences } = state;

  const form = h(
    "form",
    {
      onSubmit: async (event) => {
        event.preventDefault();
        const data = new FormData(form);
        const rawHours = (data.get("weeklyAvailableHours") || "").toString().trim();
        const hours = rawHours === "" ? null : Number(rawHours);

        if (hours !== null && (!Number.isFinite(hours) || hours < 0 || hours > 168)) {
          toastError("Use a number of hours between 0 and 168.");
          return;
        }

        try {
          await actions.savePreferences({
            displayName: (data.get("displayName") || "").toString().trim(),
            weeklyAvailableHours: hours,
          });
          toastOk("Settings saved");
        } catch (error) {
          toastError(error.message);
        }
      },
    },

    field(
      "Available focused hours this week",
      h("input", {
        class: "input",
        type: "number",
        step: "0.5",
        min: "0",
        max: "168",
        name: "weeklyAvailableHours",
        value: preferences.weeklyAvailableHours ?? "",
        placeholder: "e.g. 18",
      }),
      {
        hint: "Optional. It is a capacity indicator, not a schedule — nothing is planned for you.",
      }
    ),

    field(
      "Display name",
      h("input", {
        class: "input",
        name: "displayName",
        value: preferences.displayName || "",
        placeholder: "Used in the greeting",
        maxlength: 60,
      })
    ),

    h("button", { class: "btn btn-primary", type: "submit" }, "Save settings")
  );

  return h(
    "div",
    {},
    h(
      "div",
      { class: "page-head" },
      h(
        "div",
        {},
        h("h1", { class: "page-title" }, "Settings"),
        h("div", { class: "page-sub" }, "Two things. That is the whole of it.")
      )
    ),

    h("section", { class: "panel", style: { maxWidth: "460px" } }, form),

    h(
      "section",
      { class: "panel", style: { maxWidth: "460px", marginTop: "16px" } },
      h("div", { class: "panel-title" }, "Account"),

      h(
        "dl",
        { class: "detail-grid" },
        h("dt", {}, "Signed in"),
        h("dd", {}, state.session.user?.email || "—"),
        h("dt", {}, "API"),
        h("dd", {}, h("code", {}, api.baseUrl))
      ),

      h(
        "p",
        { class: "muted", style: { fontSize: "12.5px", marginBottom: 0 } },
        "Your board lives on the server. Signing out revokes this device's token ",
        "immediately; other devices stay signed in."
      ),

      h(
        "button",
        {
          class: "btn",
          style: { marginTop: "12px" },
          onClick: () =>
            confirmDialog({
              title: "Sign out?",
              body: "You'll need your password to get back in.",
              confirmLabel: "Sign out",
              danger: false,
              onConfirm: async () => {
                try {
                  await actions.signOut();
                } catch (error) {
                  toastError(error.message);
                }
              },
            }),
        },
        "Sign out"
      )
    )
  );
}
