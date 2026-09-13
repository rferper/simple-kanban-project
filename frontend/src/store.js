/**
 * Application state.
 *
 * One object, one subscriber list, and a set of actions that are the only
 * things allowed to call the API client. Views read `state` and re-render when
 * told; they never mutate it.
 *
 * Writes are optimistic where the user expects instant feedback — dragging a
 * card, ticking a subtask — and roll back with a visible message if the call
 * fails (§14, §37).
 */

import { api } from "./api/client.js";

const listeners = new Set();

export const state = {
  status: "loading", // loading | ready | error
  error: null,
  /** Every endpoint but login needs a token, so the shell renders off this. */
  session: { status: "checking", user: null }, // checking | in | out
  cards: [],
  preferences: { displayName: "", weeklyAvailableHours: null },
  /** §21 — per-board filters, kept out of the URL to stay simple. */
  filters: { query: "", priority: "", tag: "", status: "", fit: "", company: "", due: "" },
  showArchive: false,
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  for (const fn of listeners) fn(state);
}

function set(patch) {
  Object.assign(state, patch);
  notify();
}

/* ---------------------------------------------------------------- reading */

export function cardById(id) {
  return state.cards.find((c) => c.id === id) || null;
}

export function cardsInArea(area) {
  return state.cards.filter((c) => c.area === area);
}

export function jobCards() {
  return state.cards.filter((c) => c.area === "JOB_SEARCH");
}

export function learningCards() {
  return state.cards.filter((c) => c.area === "LEARNING");
}

/* ---------------------------------------------------------------- loading */

export async function load() {
  set({ status: "loading", error: null });
  try {
    const [cards, preferences] = await Promise.all([api.cards.list(), api.preferences.get()]);
    set({ cards, preferences, status: "ready", error: null });
  } catch (error) {
    // A rejected token is not a broken board — it is a sign-in screen.
    if (error.kind === "unauthorized") signedOut();
    else set({ status: "error", error: error.message });
  }
}

/**
 * Decide what to show on start-up: the board if the stored token still works,
 * the sign-in screen if there isn't one or the API rejects it.
 */
export async function boot() {
  if (!api.auth.hasToken()) {
    signedOut();
    return;
  }

  set({ session: { status: "checking", user: null }, status: "loading" });

  try {
    const user = await api.auth.me();
    set({ session: { status: "in", user } });
    await load();
  } catch (error) {
    if (error.kind === "unauthorized") signedOut();
    else set({ status: "error", error: error.message });
  }
}

function signedOut() {
  set({
    session: { status: "out", user: null },
    status: "ready",
    error: null,
    cards: [],
    preferences: { displayName: "", weeklyAvailableHours: null },
  });
}

// The API drops the token the moment it is rejected — a revoked session, or one
// that expired while the tab sat open. Follow it here rather than letting every
// in-flight call fail separately.
api.auth.onUnauthorized(() => {
  if (state.session.status !== "out") signedOut();
});

function replace(card) {
  const index = state.cards.findIndex((c) => c.id === card.id);
  if (index === -1) state.cards.push(card);
  else state.cards[index] = card;
}

function replaceMany(cards) {
  for (const card of [].concat(cards)) replace(card);
}

/* ---------------------------------------------------------------- actions */

export const actions = {
  async createCard(draft) {
    const card = await api.cards.create(draft);
    state.cards.push(card);
    notify();
    return card;
  },

  async createJob(draft) {
    const card = await api.jobs.create(draft);
    state.cards.push(card);
    notify();
    return card;
  },

  async updateCard(id, patch) {
    const card = await api.cards.update(id, patch);
    replace(card);
    notify();
    return card;
  },

  async updateJob(id, jobPatch) {
    const card = await api.jobs.update(id, jobPatch);
    replace(card);
    notify();
    return card;
  },

  /**
   * §14 — the board must move under the user's hand, not after a round trip.
   * Apply locally, then persist; put it back if the write fails.
   */
  async moveCard(id, status) {
    const card = cardById(id);
    if (!card || card.status === status) return card;

    const previous = card.status;
    card.status = status;
    notify();

    try {
      const saved = await api.cards.move(id, status);
      replace(saved);
      notify();
      return saved;
    } catch (error) {
      card.status = previous;
      notify();
      throw error;
    }
  },

  async setPlannedThisWeek(id, planned) {
    const card = cardById(id);
    if (!card) return null;

    const previous = card.plannedThisWeek;
    card.plannedThisWeek = planned;
    notify();

    try {
      const saved = await api.cards.setPlannedThisWeek(id, planned);
      replace(saved);
      notify();
      return saved;
    } catch (error) {
      card.plannedThisWeek = previous;
      notify();
      throw error;
    }
  },

  async toggleSubtask(id, subtaskId) {
    const card = cardById(id);
    if (!card) return null;

    const subtasks = card.subtasks.map((s) => (s.id === subtaskId ? { ...s, done: !s.done } : s));
    const previous = card.subtasks;
    card.subtasks = subtasks;
    notify();

    try {
      const saved = await api.cards.update(id, { subtasks });
      replace(saved);
      notify();
      return saved;
    } catch (error) {
      card.subtasks = previous;
      notify();
      throw error;
    }
  },

  async addSubtask(id, title) {
    const card = cardById(id);
    if (!card) return null;
    const subtasks = [
      ...card.subtasks,
      { id: `st-${Date.now().toString(36)}`, title: title.trim(), done: false },
    ];
    return actions.updateCard(id, { subtasks });
  },

  async removeSubtask(id, subtaskId) {
    const card = cardById(id);
    if (!card) return null;
    return actions.updateCard(id, { subtasks: card.subtasks.filter((s) => s.id !== subtaskId) });
  },

  async completeCard(id, area) {
    const card = await api.cards.complete(id, area);
    replace(card);
    notify();
    return card;
  },

  async deleteCard(id) {
    await api.cards.remove(id);
    state.cards = state.cards.filter((c) => c.id !== id);
    notify();
  },

  async setOutcome(id, outcome) {
    const card = await api.jobs.setOutcome(id, outcome);
    replace(card);
    notify();
    return card;
  },

  async linkLearningToJob(learningId, jobId) {
    replaceMany(await api.links.connect(learningId, jobId));
    notify();
  },

  async unlinkLearningFromJob(learningId, jobId) {
    replaceMany(await api.links.disconnect(learningId, jobId));
    notify();
  },

  async savePreferences(patch) {
    const preferences = await api.preferences.update(patch);
    set({ preferences });
    return preferences;
  },

  setFilters(patch) {
    Object.assign(state.filters, patch);
    notify();
  },

  clearFilters() {
    state.filters = { query: "", priority: "", tag: "", status: "", fit: "", company: "", due: "" };
    notify();
  },

  setShowArchive(show) {
    set({ showArchive: show });
  },

  async signIn(email, password) {
    const user = await api.auth.login(email, password);
    set({ session: { status: "in", user } });
    await load();
    return user;
  },

  async signOut() {
    await api.auth.logout();
    signedOut();
  },
};
