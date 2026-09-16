"""Fixtures for the browser tests.

`stack` is session-scoped: one `docker compose up --build` for the whole run,
because building the image per test would make these unusable.

`signed_in` is the fixture most tests want — a page on the dashboard, with the
demo account's session already in `localStorage`. Signing in is itself a journey
worth testing, so `test_signing_in.py` does it through the form instead.

Every test gets a fresh browser context (pytest-playwright's default), so no
test inherits another's session or storage. The *database* is shared across the
session, which is why nothing here asserts an absolute card count — tests add
cards with unique titles and look for their own.
"""

from __future__ import annotations

import shutil
import uuid

import pytest
from compose import Stack
from playwright.sync_api import Page, expect

DEMO_EMAIL = "researcher@example.com"
DEMO_PASSWORD = "nextlane"

#: The app is a local dev stack on a laptop, not a network away. Long enough to
#: absorb a cold start, short enough that a hang fails rather than hangs.
expect.set_options(timeout=15_000)


@pytest.fixture(scope="session")
def stack():
    if not shutil.which("docker"):
        pytest.skip("docker is not on PATH")

    running = Stack()
    running.down(volumes=True)  # a leftover from a failed run is not a fixture
    running.up(build=True)
    yield running
    running.down(volumes=True)


@pytest.fixture(scope="session")
def base_url(stack: Stack) -> str:
    """pytest-playwright uses this for `page.goto("/")`."""
    return stack.base_url


@pytest.fixture
def unique() -> str:
    """A title no other test will have written, since they share a database."""
    return uuid.uuid4().hex[:8]


def sign_in_through_the_form(page: Page) -> None:
    page.goto("/")
    page.fill("form.signin input[name=email]", DEMO_EMAIL)
    page.fill("form.signin input[name=password]", DEMO_PASSWORD)
    page.click("button.signin-submit")
    expect(page.locator("#nav a[href='#/work']")).to_be_visible()


@pytest.fixture
def signed_in(page: Page, base_url: str) -> Page:
    """A page on the dashboard, signed in.

    Through the form rather than by writing a token into `localStorage`: the
    token's shape is the app's business, and a test that forged one would keep
    passing after the app stopped accepting real ones.
    """
    sign_in_through_the_form(page)
    return page
