/**
 * NextLane — entry point.
 *
 * Every backend call in the app goes through `src/api/client.js`, which talks
 * to the API in `backend/` over HTTP.
 */

import { startApp } from "./ui/app.js";
import { api } from "./api/client.js";
import { openAddJobDialog } from "./ui/job-import.js";
import { toastError } from "./ui/overlay.js";

startApp();

/* A shortcut worth having: "j" adds a job from anywhere. */
document.addEventListener("keydown", (event) => {
  if (event.key !== "j" || event.metaKey || event.ctrlKey || event.altKey) return;
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (!document.getElementById("modal").hidden || !document.getElementById("drawer").hidden) return;
  event.preventDefault();
  openAddJobDialog();
});

/** Console handle: `nextlane.api.cards.list()`, `nextlane.api.baseUrl`. */
window.nextlane = { api };

window.addEventListener("unhandledrejection", (event) => {
  console.error("[nextlane] unhandled rejection", event.reason);
  toastError(event.reason?.message || "Something went wrong.");
});
