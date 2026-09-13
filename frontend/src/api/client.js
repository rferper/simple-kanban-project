/**
 * ============================================================================
 *  THE ONLY PLACE THE APP TALKS TO A BACKEND
 * ============================================================================
 *
 * Every read and every write in NextLane goes through this module. No view, no
 * component and no domain function fetches anything on its own — if you find
 * yourself reaching for `fetch` anywhere else, add a method here instead.
 *
 * This now talks to the real API (`backend/`), over HTTP. The contract is
 * `openapi.yaml` at the repository root, and each method below names the call
 * it makes.
 *
 * ---------------------------------------------------------------------------
 *  Authentication
 * ---------------------------------------------------------------------------
 * Every endpoint requires a bearer token except `POST /api/auth/login`. The
 * token is held here and in `localStorage`, and attached to every request.
 *
 * When the API answers 401 — no token, a revoked one, or one that has expired
 * while the tab sat open — the token is dropped and everything registered with
 * `onUnauthorized()` is told, so the app can show the sign-in screen instead of
 * a wall of failed requests.
 *
 * ---------------------------------------------------------------------------
 *  Where the API lives
 * ---------------------------------------------------------------------------
 * `http://localhost:8001` by default, matching `openapi.yaml` and the backend
 * README. Override it before the app loads:
 *
 *     <script>window.NEXTLANE_API_BASE = "https://api.example.com";</script>
 */

import { areaOf } from "../domain/types.js";

const API_BASE = String(window.NEXTLANE_API_BASE || "http://localhost:8001").replace(/\/+$/, "");
const TOKEN_KEY = "nextlane.token";

/** What every failed call throws. `message` is safe to show a user (§37). */
export class ApiError extends Error {
  constructor(message, { cause, kind = "request", status = 0 } = {}) {
    super(message);
    this.name = "ApiError";
    this.cause = cause;
    this.kind = kind;
    this.status = status;
  }
}

const OFFLINE =
  "Can't reach the server. Is the API running on " + API_BASE + "?";
const SAVE_FAILED = "Couldn't save that change. Your card is still open — please try again.";
const LOAD_FAILED = "Couldn't load your board. Check your connection and try again.";

/* ------------------------------------------------------------------- token */

let token = readStoredToken();

function readStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null; // private mode, blocked storage — the session still works
  }
}

function setToken(value) {
  token = value || null;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Not being able to remember the token across reloads is survivable.
  }
}

export function hasToken() {
  return Boolean(token);
}

const unauthorizedListeners = new Set();

/** Called when the API rejects our token. The app uses this to show sign-in. */
export function onUnauthorized(fn) {
  unauthorizedListeners.add(fn);
  return () => unauthorizedListeners.delete(fn);
}

function forgetSession() {
  const had = Boolean(token);
  setToken(null);
  if (had) for (const fn of unauthorizedListeners) fn();
}

/* ----------------------------------------------------------------- request */

async function request(method, path, body, { failureMessage, anonymous = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token && !anonymous) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    // A network failure, a CORS rejection, or the server simply not running.
    console.error(`[api] ${method} ${path} could not be sent`, error);
    throw new ApiError(OFFLINE, { cause: error, kind: "network" });
  }

  const payload = await readBody(response);

  if (response.ok) return payload;

  if (response.status === 401) {
    forgetSession();
    throw new ApiError(payload?.message || "Please sign in again.", {
      kind: "unauthorized",
      status: 401,
    });
  }

  console.error(`[api] ${method} ${path} failed`, response.status, payload);
  throw new ApiError(payload?.message || failureMessage || "That didn't work. Try again.", {
    kind: payload?.kind || "request",
    status: response.status,
  });
}

async function readBody(response) {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null; // a proxy's HTML error page, say — the status still tells us
  }
}

/* --------------------------------------------------------------------- api */

export const api = {
  /* ----------------------------------------------------------------- auth */

  auth: {
    /** POST /api/auth/login — the one endpoint that needs no token. */
    async login(email, password) {
      const result = await request(
        "POST",
        "/api/auth/login",
        { email, password },
        { anonymous: true, failureMessage: "Couldn't sign you in. Try again." }
      );
      setToken(result.token);
      return result.user;
    },

    /** POST /api/auth/logout — revokes this token server-side, immediately. */
    async logout() {
      try {
        await request("POST", "/api/auth/logout");
      } catch (error) {
        // Already invalid server-side is a fine outcome for signing out.
        if (error.kind !== "unauthorized") console.error("[api] logout failed", error);
      } finally {
        setToken(null);
      }
    },

    /** GET /api/auth/me — also how the app checks a stored token still works. */
    me: () => request("GET", "/api/auth/me", undefined, { failureMessage: LOAD_FAILED }),

    hasToken,
    onUnauthorized,
  },

  /* ---------------------------------------------------------------- cards */

  cards: {
    /** GET /api/cards */
    list: () => request("GET", "/api/cards", undefined, { failureMessage: LOAD_FAILED }),

    /** GET /api/cards/:id */
    get: (id) => request("GET", `/api/cards/${encodeURIComponent(id)}`, undefined, {
      failureMessage: LOAD_FAILED,
    }),

    /** POST /api/cards */
    create: (draft) => request("POST", "/api/cards", draft, { failureMessage: SAVE_FAILED }),

    /** PATCH /api/cards/:id */
    update: (id, patch) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}`, patch, {
        failureMessage: SAVE_FAILED,
      }),

    /** PATCH /api/cards/:id — status only, the drag-and-drop path (§14). */
    move: (id, status) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}`, { status }, {
        failureMessage: SAVE_FAILED,
      }),

    /** PATCH /api/cards/:id — the weekly planning toggle (§10.5). */
    setPlannedThisWeek: (id, planned) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}`, { plannedThisWeek: planned }, {
        failureMessage: SAVE_FAILED,
      }),

    /** PATCH /api/cards/:id — move to the area's done column (§12.1). */
    complete: (id, area) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}`, {
        status: areaOf(area).doneStatus,
      }, { failureMessage: SAVE_FAILED }),

    /** DELETE /api/cards/:id — 204, no body. */
    remove: (id) =>
      request("DELETE", `/api/cards/${encodeURIComponent(id)}`, undefined, {
        failureMessage: "Couldn't delete that card. Try again.",
      }),
  },

  /* ----------------------------------------------------------------- jobs */

  jobs: {
    /** POST /api/cards — a job card is a card carrying a JobDetails record (§11, §24). */
    create: (draft) =>
      request(
        "POST",
        "/api/cards",
        { ...draft, area: "JOB_SEARCH", title: draft.title || jobTitle(draft.job) },
        { failureMessage: SAVE_FAILED }
      ),

    /** PATCH /api/cards/:id/job */
    update: (id, jobPatch) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}/job`, jobPatch, {
        failureMessage: SAVE_FAILED,
      }),

    /**
     * PATCH /api/cards/:id/job — the archive path (§8.1, §16.8).
     * Archiving is routine, so it is one call and no ceremony.
     */
    setOutcome: (id, outcome) =>
      request("PATCH", `/api/cards/${encodeURIComponent(id)}/job`, { outcome }, {
        failureMessage: SAVE_FAILED,
      }),
  },

  /* ---------------------------------------------------- job ↔ learning links */

  links: {
    /** PUT /api/learning/:learningId/jobs/:jobId (§9.3) — returns both cards. */
    connect: (learningId, jobId) =>
      request(
        "PUT",
        `/api/learning/${encodeURIComponent(learningId)}/jobs/${encodeURIComponent(jobId)}`,
        undefined,
        { failureMessage: "Couldn't link those cards. Try again." }
      ),

    /** DELETE /api/learning/:learningId/jobs/:jobId — returns both cards. */
    disconnect: (learningId, jobId) =>
      request(
        "DELETE",
        `/api/learning/${encodeURIComponent(learningId)}/jobs/${encodeURIComponent(jobId)}`,
        undefined,
        { failureMessage: "Couldn't unlink those cards. Try again." }
      ),
  },

  /* ---------------------------------------------------------- preferences */

  preferences: {
    /** GET /api/preferences (§20) */
    get: () => request("GET", "/api/preferences", undefined, { failureMessage: LOAD_FAILED }),

    /** PATCH /api/preferences */
    update: (patch) =>
      request("PATCH", "/api/preferences", patch, {
        failureMessage: "Couldn't save your settings. Try again.",
      }),
  },

  /* ------------------------------------------------------------------- AI */

  /**
   * Isolated on purpose (§27): if this endpoint is unavailable, every other
   * call above still works and the Kanban is fully usable.
   */
  ai: {
    /** POST /api/ai/extract-job-advert (§15.2) */
    extractJobAdvert: (advert) =>
      request("POST", "/api/ai/extract-job-advert", { advert }, {
        failureMessage:
          "I couldn't reliably extract this advert. You can retry or create the job manually.",
      }),
  },

  /** Where this app is pointed. Shown in Settings. */
  baseUrl: API_BASE,
};

function jobTitle(job) {
  if (!job) return "Untitled role";
  const parts = [job.company, job.role].filter(Boolean);
  return parts.length ? parts.join(" — ") : "Untitled role";
}
