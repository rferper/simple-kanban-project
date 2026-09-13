# NextLane — Build Backlog

The product in `_docs/specs.md`, cut into tasks. Each one is small enough to
finish in a single session and written to be picked up by someone who has read
none of the others — the context you need is in the task, or in the spec section
it names.

Order matters up to task 11: the backend is built from the vocabulary outwards,
so each task has something real to stand on. From 12 the frontend tasks are
mostly independent of each other.

Read `_docs/process.md` before starting one, and `_docs/decisions.md` before
re-litigating anything it has already settled.

> **Status.** Tasks 1–20 are implemented — see `git log`. Tasks 1–18 describe how
> this repository was built and are recorded because the backlog is also the map
> of how the product got made. Anything still outstanding starts at 21.

---

## 1. Set up the project with a passing test

Goal: An empty project that installs, runs and proves it by passing one test.

Description: Create the repository skeleton with `uv` — `pyproject.toml`, a
pinned Python version, a `backend/` package and a `tests/` directory — and wire
up pytest so `uv run pytest` finds and runs it. Add a single trivial test that
asserts something true, so the first green run proves the toolchain rather than
the product. No application code, no dependencies beyond pytest and the web
framework the later tasks will need.

## 2. Define the domain vocabulary and card validation

Goal: The product's nouns exist in code, and an invalid card cannot be built.

Description: Encode the three areas, four priorities, per-board statuses, fit,
work mode and job outcome from `_docs/specs.md` §28 as enumerations in one
module, along with the column order for each board. Add the validation rules
from §29 — a title of 1–200 characters, a non-negative estimate, a status that
belongs to the card's own area — and test the awkward cases: a blank title, a
negative estimate, a Learning card sent to the Current Job board's column.

## 3. Build the in-memory store and the seed data

Goal: Somewhere to keep cards, behind a seam a real database can replace.

Description: Define a storage protocol covering cards and preferences, and one
in-memory implementation of it. Load it with the development fixtures from
`_docs/specs.md` §31 — a club of work mid-flight, including the awkward states:
a card with no estimate, a card with no deadline, an application already
archived. The store must copy objects in and out, so holding one cannot mutate
what is stored.

## 4. Add the card endpoints

Goal: Cards can be listed, read, created, changed and deleted over HTTP.

Description: Implement list, get, create, partial update and delete for cards,
with only title and area required on creation (§13) and everything else
defaulted. `completedAt` is the server's business: stamp it when a card enters
its area's done column and clear it when it leaves (§12.1). Every error answers
in one shape, `{"message", "kind"}`, with a message fit to show a person (§37).

## 5. Add job cards and their application details

Goal: A Job Search card carries the structured application record from §11.

Description: Give a card in the Job Search area an optional job object holding
company, role, location, salary, work mode, fit, dates, CV version, contact,
requirements and notes. Add an endpoint that updates those fields by merging
rather than replacing, so changing one field cannot blank the rest. Reject job
details on a card that is not a Job Search card.

## 6. Add the application archive

Goal: A rejected or withdrawn application leaves the board and keeps everything.

Description: Add the outcome values from `_docs/specs.md` §8.1 and make setting
one to rejected, withdrawn or declined take the application off the main board
without deleting anything it held — notes, stage and dates all survive, and the
move is reversible. Keep the language neutral throughout (§16.8): this is an
archive, never a failure.

## 7. Link learning cards to job cards

Goal: A learning card can say which roles it is preparing for.

Description: Implement the many-to-many relationship from §9.3 as endpoints that
connect and disconnect a learning card and a job card, keeping both ends in step
so neither can point at something the other does not. Make it idempotent in both
directions, and make deleting either card clean up the reference held by the
other.

## 8. Add the preferences endpoints

Goal: The two settings the product has can be read and written.

Description: Implement read and partial update for the weekly available hours
and the optional display name from `_docs/specs.md` §20. Available hours is
optional and nullable — unset is a different thing from zero, because the
capacity indicator in §5.4 says something different when it does not know your
capacity. Resist adding a third setting.

## 9. Add the job-advert extraction endpoint

Goal: Pasted advert text comes back as structured, editable job fields.

Description: Implement the extraction target in `_docs/specs.md` §15.2 —
company, role, location, salary, work mode, deadline, requirements, nice-to-have,
a summary and suggested tags. It returns a draft and persists nothing: the
editable preview in §15.3 is the whole point. Report what could not be found
rather than guessing, never score the candidate's fit, and keep the feature
isolated so the rest of the API is unaffected when it fails.

## 10. Add authentication with hashed passwords and bearer tokens

Goal: The API is closed by default, and login is the only way in.

Description: Hash passwords with a salted, memory-hard function and never store
or return the plaintext. Issue opaque bearer tokens on login, require one on
every other endpoint, and revoke immediately on logout. Make a wrong password
and an unknown email fail identically so the endpoint cannot be used to discover
which accounts exist, and seed one development account so a fresh clone can sign
in.

## 11. Write the OpenAPI contract and a test that guards it

Goal: The documented API and the running API cannot drift apart.

Description: Write `openapi.yaml` covering every path, method, request body,
response body and security requirement, including which endpoints are public.
Add a test that compares the file against the running application in both
directions, so an endpoint that is implemented but undocumented fails, and so
does one documented but missing. Cover the security posture too: an endpoint
added without a token requirement should fail the suite.

## 12. Build the frontend shell

Goal: A styled, navigable application shell with nothing in it yet.

Description: Create the page, the design tokens for the three area identities in
`_docs/specs.md` §16.3, the top navigation from §18 and client-side routing over
the conceptual routes in §19. Establish the visual language the rest of the
frontend inherits — warm off-white ground, rounded cards, generous spacing,
restrained animation — and make it work at laptop and phone width (§36).

## 13. Build the three Kanban boards with drag and drop

Goal: Each area has a full board whose cards can be dragged between columns.

Description: Render one board per area with the columns from §7.1, §8.1 and
§9.1, driven by the vocabulary rather than hardcoded per board. Dragging a card
moves it immediately and persists the new status (§14); a board only accepts its
own cards. Include the friendly empty states from §17, because a new user sees
those first.

## 14. Build the card detail drawer

Goal: Clicking a card opens everything it holds, and lets you change it.

Description: Implement the drawer from `_docs/specs.md` §12 — a drawer rather
than a modal, so the board stays visible. Show the base fields and, for a job
card, the application details from §12.2, with the controls people reach for
most live in place: status, priority, planned-this-week, subtasks. Deleting asks
first (§39); archiving does not, because archiving is routine.

## 15. Build quick add and the job import flow

Goal: Adding a task takes one field; adding a job takes a paste.

Description: Add an inline add control on every board where a title alone
creates a card, with no wizard (§13). For Job Search, offer the two doors from
§15.1 — create manually, or paste an advert — where the paste route shows an
editable preview of what was extracted before anything is saved. On failure keep
the pasted text, say something useful, and offer manual creation (§15.3).

## 16. Build the dashboard

Goal: One screen that answers "what should I work on today?"

Description: Build the three-column summary from §5.2 showing the most relevant
active cards per area, the weekly capacity indicator from §22 — planned against
available, broken down by area, with unestimated work counted separately rather
than silently as zero — and the Focus Today section from §23, using the
deterministic score and the area-diversity rule. Present the suggestions as
suggestions, never as a verdict.

## 17. Add filtering, search and settings

Goal: A busy board can be narrowed, and the two settings can be changed.

Description: Add the filters from `_docs/specs.md` §21 — priority, deadline,
tags, status, and company and fit on the Job Search board — plus a simple text
search. Build the settings page from §20 with its two fields, and make the
weekly available hours feed the dashboard capacity indicator. No query builders.

## 18. Sign in, and connect the frontend to the API

Goal: The frontend runs on the real backend, behind a sign-in screen.

Description: Route every call through the single API module, attaching the
bearer token to each request. Add the sign-in screen that stands in front of the
application until there is a session, keep the token across reloads, and handle
a rejected token in one place so an expired session is a single transition
rather than a wall of failed requests. Delete any mock the frontend was standing
on.

## 19. Replace the in-memory store with a real database

Goal: The board survives a restart.

Description: Write a second implementation of the storage protocol backed by a
real database, and swap it in at the one place the application resolves storage.
Nothing in the service layer or the routers should change — if either needs
editing, the seam is in the wrong place. Add migrations and a way to seed a
fresh database with the development fixtures.

## 20. Replace the advert parser with a real model call

Goal: Extraction reads adverts it was not written for.

Description: Swap the heuristic parser behind the extraction endpoint for a
model call, keeping the response shape and the editable-preview contract exactly
as they are, so nothing in the frontend changes. Handle the model being slow,
unavailable or returning something unusable, and keep the feature isolated: the
Kanban must stay fully usable with extraction switched off (§27).

---

# Open

## 21. Choose and wire up a linter and type checker

Goal: `make check` means something beyond the tests.

Description: Pick a linter and a type checker, configure them for both the
Python backend and the JavaScript frontend, and fix what they find on the
existing code. Add them to the task runners and to the pre-close checklist in
`_docs/process.md`, which currently names a step nobody can run.

## 22. Add continuous integration

Goal: The suite runs on every push, not just when someone remembers.

Description: Add a CI workflow that installs dependencies, runs the test suite
and reports the result on pull requests. It must run on Linux, which is the
reason the Makefile exists and the reason `.gitattributes` pins its line
endings. Make a failing suite block a merge.

## 23. Make the API root say what it is

Goal: Opening the API in a browser explains itself instead of 404ing.

Description: Add a small public endpoint at `/` returning the service name,
version and links to the interactive docs and the frontend. It has to be public,
or an unauthenticated visitor gets a 401 instead of help. Document it in
`openapi.yaml` and add it to the public set in the contract test, which is
deliberately a visible edit.
