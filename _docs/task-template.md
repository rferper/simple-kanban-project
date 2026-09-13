# Task template

The shape a new issue takes.

---

## Goal

One or two sentences on what should be true when this is done.

## Acceptance criteria

- [ ] A statement you can check by looking at the result
- [ ] One line per case, including the awkward ones — the empty board, the
      card with no deadline, the AI call that fails, the week with no
      available hours set
- [ ] At least one that names a test: what must fail before, and pass after
- [ ] For anything visual, one that names what it must look like at laptop
      width and at phone width

## Out of scope

- Something a reader might reasonably assume is included, and is not
- Where it went instead, if it went somewhere (#12)

## Constraints

- Files this should stay inside
- Libraries it may not add, patterns it must follow
- Decisions in `_docs/decisions.md` it must respect
- Spec sections it must not contradict

## Context

Enough for someone who has read no other issue: which spec sections apply,
which parts of the product already exist, which document to read first.

---

## Writing them

- **Title is imperative and specific.** "Add the weekly workload bar", not
  "Dashboard work".
- **One sitting.** If it cannot be finished and closed in one go, it is two
  issues.
- **Standalone.** Assume the reader has read no other issue. Repeat the context
  they need rather than pointing at issue #6.
- **Cite the spec by number.** "Implements `_docs/specs.md` §22" is worth more
  than a paragraph re-describing it, and it cannot drift.
- **Acceptance criteria are observable.** "Workload is calculated correctly" is
  not checkable. "Planning 12 hours against 10 available shows the bar in its
  over-capacity state" is.
- **Name the awkward cases in the criteria**, because those are the ones that
  get skipped: the empty state, the duplicate submission, the archived job, the
  AI response that comes back missing half its fields.
