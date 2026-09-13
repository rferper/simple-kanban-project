/**
 * Domain vocabulary — _docs/specs.md §28.
 *
 * Everything the rest of the app knows about areas, statuses, priorities and
 * outcomes comes from here. No other module hardcodes these strings.
 */

export const AREA = {
  CURRENT_JOB: "CURRENT_JOB",
  JOB_SEARCH: "JOB_SEARCH",
  LEARNING: "LEARNING",
};

export const PRIORITY = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
  URGENT: "URGENT",
};

export const FIT = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
  DREAM: "DREAM",
};

export const WORK_MODE = {
  ONSITE: "ONSITE",
  HYBRID: "HYBRID",
  REMOTE: "REMOTE",
  UNKNOWN: "UNKNOWN",
};

export const OUTCOME = {
  ACTIVE: "ACTIVE",
  REJECTED: "REJECTED",
  WITHDRAWN: "WITHDRAWN",
  ACCEPTED: "ACCEPTED",
  DECLINED: "DECLINED",
};

/** Per-area board definition: statuses in column order, identity, copy. §7, §8, §9, §16.3, §17 */
export const AREAS = {
  [AREA.CURRENT_JOB]: {
    id: AREA.CURRENT_JOB,
    name: "Current Job",
    icon: "🎓",
    route: "work",
    statuses: ["BACKLOG", "THIS_WEEK", "IN_PROGRESS", "WAITING", "DONE"],
    statusLabels: {
      BACKLOG: "Backlog",
      THIS_WEEK: "This Week",
      IN_PROGRESS: "In Progress",
      WAITING: "Waiting",
      DONE: "Done",
    },
    doneStatus: "DONE",
    inProgressStatus: "IN_PROGRESS",
    defaultStatus: "BACKLOG",
    empty: {
      title: "Nothing urgent here 🎓",
      hint: "Add the work that currently needs your attention.",
    },
    addLabel: "Add task",
  },

  [AREA.JOB_SEARCH]: {
    id: AREA.JOB_SEARCH,
    name: "Job Search",
    icon: "🚀",
    route: "jobs",
    statuses: ["INTERESTING", "PREPARING", "APPLIED", "INTERVIEW", "OFFER"],
    statusLabels: {
      INTERESTING: "Interesting",
      PREPARING: "Preparing",
      APPLIED: "Applied",
      INTERVIEW: "Interview",
      OFFER: "Offer",
    },
    doneStatus: "OFFER",
    inProgressStatus: "PREPARING",
    defaultStatus: "INTERESTING",
    empty: {
      title: "Your next opportunity starts here 🚀",
      hint: "Save an interesting role or paste a job advert.",
    },
    addLabel: "Add job",
  },

  [AREA.LEARNING]: {
    id: AREA.LEARNING,
    name: "Learning",
    icon: "🌱",
    route: "learning",
    statuses: ["IDEAS", "PLANNED", "LEARNING", "PRACTISING", "DONE"],
    statusLabels: {
      IDEAS: "Ideas",
      PLANNED: "Planned",
      LEARNING: "Learning",
      PRACTISING: "Practising",
      DONE: "Done",
    },
    doneStatus: "DONE",
    inProgressStatus: "LEARNING",
    defaultStatus: "IDEAS",
    empty: {
      title: "What would make the next application easier? 🌱",
      hint: "Add a skill, project, course, or practice goal.",
    },
    addLabel: "Add goal",
  },
};

export const AREA_ORDER = [AREA.CURRENT_JOB, AREA.JOB_SEARCH, AREA.LEARNING];

export const PRIORITY_LABELS = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  URGENT: "Urgent",
};

/** §11.1 — friendly wording, never presented as an objective score. */
export const FIT_LABELS = {
  LOW: "Possible fit",
  MEDIUM: "Good fit",
  HIGH: "Strong fit",
  DREAM: "Dream role",
};

export const WORK_MODE_LABELS = {
  ONSITE: "On-site",
  HYBRID: "Hybrid",
  REMOTE: "Remote",
  UNKNOWN: "Not stated",
};

/** §16.8 — neutral language. A rejection is never framed as failure. */
export const OUTCOME_LABELS = {
  ACTIVE: "Active",
  REJECTED: "Archived — not taken forward",
  WITHDRAWN: "Archived — withdrawn",
  ACCEPTED: "Offer accepted",
  DECLINED: "Offer declined",
};

export const ARCHIVED_OUTCOMES = [OUTCOME.REJECTED, OUTCOME.WITHDRAWN, OUTCOME.DECLINED];

export function areaOf(cardOrArea) {
  const id = typeof cardOrArea === "string" ? cardOrArea : cardOrArea?.area;
  return AREAS[id] || AREAS[AREA.CURRENT_JOB];
}

export function statusLabel(area, status) {
  return areaOf(area).statusLabels[status] || status;
}

export function isDone(card) {
  return card.status === areaOf(card.area).doneStatus;
}

export function isArchived(card) {
  return Boolean(card.job && ARCHIVED_OUTCOMES.includes(card.job.outcome));
}
