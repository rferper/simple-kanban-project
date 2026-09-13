/**
 * Toasts, the detail drawer and modals — the three things that live outside the
 * view and survive a re-render. §12, §16.7, §37, §39.
 */

import { h, mount, focusFirst } from "./dom.js";

const toasts = () => document.getElementById("toasts");
const drawerEl = () => document.getElementById("drawer");
const scrimEl = () => document.getElementById("scrim");
const modalEl = () => document.getElementById("modal");
const modalScrimEl = () => document.getElementById("modal-scrim");

/* ------------------------------------------------------------------ toast */

export function toast(message, { tone = "", duration = 2800 } = {}) {
  const el = h("div", { class: `toast ${tone ? `toast-${tone}` : ""}` }, message);
  toasts().append(el);

  setTimeout(() => {
    el.classList.add("is-out");
    setTimeout(() => el.remove(), 220);
  }, duration);

  return el;
}

export const toastError = (message) => toast(message, { tone: "error", duration: 4200 });
export const toastOk = (message) => toast(message, { tone: "ok" });

/* ----------------------------------------------------------------- drawer */

let closeDrawerFn = null;

export function openDrawer(render) {
  const drawer = drawerEl();
  const scrim = scrimEl();

  const rerender = () => mount(drawer, render(rerender, closeDrawer));
  rerender();

  drawer.hidden = false;
  scrim.hidden = false;
  drawer.dataset.open = "true";
  scrim.onclick = closeDrawer;
  focusFirst(drawer);

  closeDrawerFn = closeDrawer;
  return { rerender, close: closeDrawer };

  function closeDrawer() {
    drawer.hidden = true;
    scrim.hidden = true;
    delete drawer.dataset.open;
    mount(drawer);
    closeDrawerFn = null;
  }
}

export function isDrawerOpen() {
  return Boolean(closeDrawerFn);
}

export function closeDrawer() {
  if (closeDrawerFn) closeDrawerFn();
}

/* ------------------------------------------------------------------ modal */

let closeModalFn = null;

export function openModal(render, { narrow = false, dismissible = true } = {}) {
  const modal = modalEl();
  const scrim = modalScrimEl();

  const rerender = () => mount(modal, render(rerender, close));
  rerender();

  modal.className = `modal${narrow ? " is-narrow" : ""}`;
  modal.hidden = false;
  scrim.hidden = false;
  scrim.onclick = dismissible ? close : null;
  focusFirst(modal);

  closeModalFn = close;
  return { rerender, close };

  function close() {
    modal.hidden = true;
    scrim.hidden = true;
    mount(modal);
    closeModalFn = null;
  }
}

export function closeModal() {
  if (closeModalFn) closeModalFn();
}

export function isModalOpen() {
  return Boolean(closeModalFn);
}

/**
 * §39 — deleting asks; archiving a job does not, because archiving is routine
 * and the wording should not imply failure.
 */
export function confirmDialog({
  title,
  body,
  confirmLabel = "Delete",
  danger = true,
  onConfirm,
}) {
  return openModal(
    (_rerender, close) =>
      h(
        "div",
        {},
        h("h2", { class: "modal-title" }, title),
        body && h("p", { class: "modal-sub" }, body),
        h(
          "div",
          { class: "modal-foot" },
          h("button", { class: "btn btn-ghost", onClick: close }, "Cancel"),
          h(
            "button",
            {
              class: `btn ${danger ? "btn-danger" : "btn-primary"}`,
              onClick: async () => {
                close();
                await onConfirm();
              },
            },
            confirmLabel
          )
        )
      ),
    { narrow: true }
  );
}

/* Escape closes the topmost layer. */
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (isModalOpen()) closeModal();
  else if (isDrawerOpen()) closeDrawer();
});
