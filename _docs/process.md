# Process

## One issue at a time

The backlog is `_docs/tasks.md`, mirrored to GitHub issues #1–#23, where the
issue number is the task number. Pick one, finish it, close it. Do not open a
second until the first is closed or explicitly parked.

Issues #1–#18 describe how the repository was built and are already implemented;
they are kept because the backlog is also the map of how the product was made.
The work that is actually outstanding starts at #19.

## Before starting

- Read the whole issue, including the context section. Each issue is written to
  be picked up without having read the others.
- Read `_docs/decisions.md`. If the issue appears to contradict something settled
  there, the decision wins — say so on the issue rather than quietly doing it
  your own way.
- Read the spec sections the issue cites. `_docs/specs.md` is the product; the
  issue is only the slice of it being built now.

## While working

- Stay inside the task. Anything worth doing that the issue does not cover
  becomes a new issue, not a larger diff.
- Commit regularly, in commits small enough that each one leaves the suite green.
- Put the issue number in the commit message (`#7`) so the history is traceable
  back to the reason.

## Before closing

Walk the acceptance criteria clause by clause, then check:

- `make check` passes: lint, types and the whole test suite
- The app still starts and the dashboard still renders
- Route changes are reflected in the spec's route list, `_docs/specs.md` §19, in
  the same commit
- Any judgment call the issue did not settle is written into `_docs/decisions.md`

The last two matter most. A route that exists only in the code, or a decision
that exists only in someone's head, is how the next task starts by guessing.

## Branches

One branch per issue, named `<number>-<slug>` — `7-card-model`, `4-dashboard-shell`.
Work merges into `main`.

## When the spec is unclear

`_docs/specs.md` is detailed, but it is a product specification and it leaves
implementation questions open. When you hit one:

1. Check `_docs/decisions.md` — it may already be answered.
2. If not, pick the option that keeps the product simple and says so on the issue.
3. Record it in `_docs/decisions.md` with the reasoning, so the next person
   inherits an answer instead of the same fork.

Do not expand scope to resolve an ambiguity. The spec's non-goals list, §33, is
binding: no calendar, no time tracking, no multi-user, no notifications, no
generic productivity features — regardless of how convenient they would be.

The product test in §45 settles most arguments: does this make it easier for an
academic to balance their current job, job search, and preparation for an
industry pivot? If no, it is not in the MVP.

## Roles

- PM - grooms a task before anyone implements it, follows _docs/_team/pm.md
- Engineer - implements one groomed task, follows _docs/_team/software-engineer.md
- QA - checks the result against the acceptance criteria, follows _docs/_team/qa-engineer.md

## Orchestrator

The main session is the orchestrator. It launches the PM, the engineer
and QA as subagents. It does not groom, implement or test itself.

## Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. Orchestrator cuts the branch, `<number>-<slug>`, from an up-to-date `main`
4. Engineer implements it on that branch
5. QA verifies it on that branch
6. On FAIL, back to step 4 with the QA comment as input
7. On PASS, the orchestrator merges the branch into `main`, pushes, and
   closes the issue
8. Repeat until the backlog is empty

## Rules

- Do not skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- Only the orchestrator merges and pushes. The engineer commits to the branch
  and stops there, so that what QA reads is exactly what it verified
- The orchestrator closes the issue only after QA outputs PASS
