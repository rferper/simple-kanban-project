/**
 * Shell and router — _docs/specs.md §18, §19.
 *
 * Hash routing, so the whole thing runs from a static file server with no
 * rewrite rules. Routes match the spec's conceptual list: / , /work, /jobs,
 * /learning, /settings.
 */

import { h, mount } from "./dom.js";
import { renderDashboard } from "./dashboard.js";
import { renderBoard } from "./board.js";
import { renderSettings } from "./settings.js";
import { renderLogin } from "./login.js";
import { state, subscribe, boot, actions } from "../store.js";
import { AREA_ORDER, AREAS } from "../domain/types.js";

const ROUTES = {
  "": { title: "Dashboard", icon: "🏠", render: renderDashboard, area: null },
  work: { title: "Current Job", icon: AREAS.CURRENT_JOB.icon, render: () => renderBoard("CURRENT_JOB"), area: "CURRENT_JOB" },
  jobs: { title: "Job Search", icon: AREAS.JOB_SEARCH.icon, render: () => renderBoard("JOB_SEARCH"), area: "JOB_SEARCH" },
  learning: { title: "Learning", icon: AREAS.LEARNING.icon, render: () => renderBoard("LEARNING"), area: "LEARNING" },
  settings: { title: "Settings", icon: "⚙️", render: renderSettings, area: null },
};

function currentRoute() {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return ROUTES[raw] ? raw : "";
}

export function startApp() {
  renderNav();

  window.addEventListener("hashchange", () => {
    renderNav();
    render();
    document.getElementById("view").focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  });

  subscribe(() => {
    renderNav();
    render();
  });
  render();
  boot();
}

function renderNav() {
  const active = currentRoute();
  const nav = document.getElementById("nav");

  if (state.session.status !== "in") {
    mount(nav);
    return;
  }

  mount(
    nav,
    Object.entries(ROUTES).map(([key, route]) =>
      h(
        "a",
        {
          href: `#/${key}`,
          dataset: { area: route.area || "" },
          "aria-current": key === active ? "page" : null,
        },
        h("span", { "aria-hidden": "true" }, route.icon),
        route.title
      )
    ),
    h(
      "button",
      {
        class: "btn btn-sm btn-ghost nav-signout",
        title: state.session.user?.email || "",
        onClick: () => actions.signOut(),
      },
      "Sign out"
    )
  );
}

function render() {
  const view = document.getElementById("view");
  const route = ROUTES[currentRoute()];
  const signedIn = state.session.status === "in";

  document.title = currentRoute() && signedIn ? `${route.title} · NextLane` : "NextLane";
  document.getElementById("app").dataset.session = state.session.status;

  if (state.session.status === "out") {
    mount(view, renderLogin());
    return;
  }

  if (state.status === "loading" || state.session.status === "checking") {
    mount(view, renderLoading());
    return;
  }

  if (state.status === "error") {
    mount(view, renderLoadError());
    return;
  }

  mount(view, route.render());
}

/** §38 — skeletons, not a frozen screen. */
function renderLoading() {
  return h(
    "div",
    {},
    h("div", { class: "skeleton", style: { height: "28px", width: "220px", marginBottom: "24px" } }),
    h(
      "div",
      { class: "dash-top" },
      h("div", { class: "skeleton", style: { height: "190px" } }),
      h("div", { class: "skeleton", style: { height: "190px" } })
    ),
    h(
      "div",
      { class: "dash-columns", style: { marginTop: "24px" } },
      AREA_ORDER.map(() =>
        h(
          "div",
          {},
          h("div", { class: "skeleton skeleton-card" }),
          h("div", { class: "skeleton skeleton-card" }),
          h("div", { class: "skeleton skeleton-card" })
        )
      )
    )
  );
}

/** §37 — calm, specific, and it offers the way out. */
function renderLoadError() {
  return h(
    "div",
    { class: "panel", style: { maxWidth: "440px", margin: "48px auto", textAlign: "center" } },
    h("div", { class: "empty-emoji" }, "🌧️"),
    h("h2", { style: { fontSize: "17px" } }, "Couldn't load your board"),
    h("p", { class: "muted", style: { fontSize: "13.5px" } }, state.error),
    h("button", { class: "btn btn-primary", onClick: () => boot() }, "Try again")
  );
}
