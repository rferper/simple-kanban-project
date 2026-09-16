# e2e — the app, in a browser

Playwright drives a real Chromium against the stack in
[`../docker-compose.yaml`](../docker-compose.yaml): the image the `Dockerfile`
builds, serving the frontend, talking to Postgres. Nothing is mocked and nothing
is called directly — every one of these clicks a button.

```sh
make test-e2e
```

That installs Chromium if it is missing (once, about 150MB), builds the image,
brings the stack up, runs the tests, and takes it down again.

## What is here, and why these

Each file is a journey a person actually takes, and each one fails for a reason
no other test in this repository can fail for.

| File | The journey |
| --- | --- |
| `test_signing_in.py` | The gate: the form, a refusal that reads like the product, a session that survives a reload, and a sign-out that means it |
| `test_the_board.py` | The loop: reach a board, add a card with just a title, open it, move it, finish it — and do all of that at phone width |
| `test_it_persists.py` | Is it still there? After a reload, in a different browser session, and after the app restarts |
| `test_the_dashboard.py` | The question the product exists to answer: what should I work on today, why that, and does it know what my week holds |

## Where the line is

Three suites overlap here and each has a job:

* **`backend/tests/`** — the API and the store contract, in-process, in
  milliseconds. Business rules live here: which statuses a Learning card may
  hold, what `completedAt` does, how links stay two-way.
* **`backend/tests/test_compose.py`** — the container seams. The image builds,
  the app finds Postgres, the published port is the same database. HTTP and SQL,
  no browser.
* **`e2e/`** — what a person sees. If a test here does not need a rendered page,
  it belongs in one of the other two.

So nothing below asserts a row in Postgres, and nothing below re-tests a
validation rule. `test_it_persists.py` is the clearest case of the split: it
proves a card is still on the board after a restart, and says nothing at all
about where it was kept.

## Things worth knowing before you add one

**The database is shared for the whole run.** One `docker compose up` per
session, so tests see each other's cards. Use the `unique` fixture in titles and
assert on your own card — never on an absolute count.

**Each test gets a fresh browser context**, so sessions and `localStorage` never
leak between them. `signed_in` gives you a page already on the dashboard.

**Signing in goes through the form**, even in the fixture. Writing a token
straight into `localStorage` would be faster and would keep passing after the
app stopped accepting real ones.

**This stack is not the development one.** Its own compose project
(`nextlane-e2e`), its own ports (18100 and 15532), its own volume — the teardown
deletes that volume, so `compose.py` checks the project name before it does.
`make compose-up` and `make test-integration` use different ones again, and all
three can run at once.

**Wait with `expect`, not with reads.** `all_text_contents()` and friends do not
wait for anything, so assert something is visible first — a locator that resolves
to nothing returns an empty list, and the failure then blames the wrong thing.

**`inner_text()` is what CSS rendered; `text_content()` is what the DOM says.**
The column headings are upper-cased by the stylesheet, so checking the product's
vocabulary means reading the second one.
