/**
 * Sign in.
 *
 * Every endpoint but login needs a token, so this is the whole app until there
 * is one. Kept in the product's voice rather than looking like a bolted-on
 * security gate — it is the first thing anyone sees.
 */

import { h, field } from "./dom.js";
import { actions } from "../store.js";
import { api } from "../api/client.js";

export function renderLogin() {
  let busy = false;
  let error = "";

  const wrap = h("div", { class: "signin-wrap" });

  function render() {
    const form = h(
      "form",
      {
        class: "signin",
        dataset: { area: "CURRENT_JOB" },
        onSubmit: async (event) => {
          event.preventDefault();
          if (busy) return;

          const email = form.elements.email.value.trim();
          const password = form.elements.password.value;

          if (!email || !password) {
            error = "Enter your email and password.";
            render();
            return;
          }

          busy = true;
          error = "";
          render();

          try {
            await actions.signIn(email, password);
            // The shell re-renders on the session change; nothing to do here.
          } catch (failure) {
            busy = false;
            error = failure.message;
            render();
          }
        },
      },

      h("div", { class: "signin-brand" }, h("span", { "aria-hidden": "true" }, "🛣️"), "NextLane"),

      h(
        "p",
        { class: "signin-tagline" },
        "Your current job, your job search, and the learning that connects them — in one place."
      ),

      error ? h("div", { class: "notice notice-warn" }, error) : null,

      field(
        "Email",
        h("input", {
          class: "input",
          type: "email",
          name: "email",
          autocomplete: "username",
          placeholder: "you@university.edu",
          disabled: busy,
          required: true,
        })
      ),

      field(
        "Password",
        h("input", {
          class: "input",
          type: "password",
          name: "password",
          autocomplete: "current-password",
          disabled: busy,
          required: true,
        })
      ),

      h(
        "button",
        { class: "btn btn-primary signin-submit", type: "submit", disabled: busy },
        busy ? h("span", { class: "spinner" }) : null,
        busy ? "Signing in…" : "Sign in"
      ),

      h(
        "p",
        { class: "signin-foot" },
        "Development account: ",
        h("code", {}, "researcher@example.com"),
        " / ",
        h("code", {}, "nextlane"),
        h("br"),
        h("span", { class: "muted" }, `API: ${api.baseUrl}`)
      )
    );

    wrap.replaceChildren(form);
    const first = form.elements.email;
    if (!busy && first) requestAnimationFrame(() => first.focus());
  }

  render();
  return wrap;
}
