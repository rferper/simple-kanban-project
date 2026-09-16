"""Work that is saved stays saved.

This is the journey that went wrong in practice, which is why it gets its own
file. The symptom was a board that looked like it never saved anything; the
cause was two databases, one of them always the wrong one (`_docs/decisions.md`
#26). Nothing below asserts anything about Postgres — that is
`backend/tests/test_compose.py`'s job. These ask the only question a user asks:
is it still there?

Three horizons, and they fail for different reasons:

* **a reload** — the write never reached the server, or the client cached a
  stale board;
* **a new browser context** — it was in this tab's memory and nowhere else;
* **an app restart** — it was in the process, not the database. This is what a
  deploy does, and the one that a SQLite file inside a container would survive
  and a container with no volume would not.
"""

from __future__ import annotations

from conftest import sign_in_through_the_form
from playwright.sync_api import Browser, Page, expect
from test_the_board import add_a_card, card_named


class TestACardSurvives:
    def test_a_reload(self, signed_in: Page, unique: str):
        title = f"Written before the reload {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        signed_in.reload()
        signed_in.click("#nav a[href='#/work']")
        expect(card_named(signed_in, title)).to_be_visible()

    def test_a_different_browser_session(self, signed_in: Page, browser: Browser, base_url: str):
        """A second context is a second browser as far as storage goes: nothing
        of the first one's memory comes with it."""
        title = "Written in the first session"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        second = browser.new_context(base_url=base_url)
        try:
            page = second.new_page()
            sign_in_through_the_form(page)
            page.click("#nav a[href='#/work']")
            expect(card_named(page, title)).to_be_visible()
        finally:
            second.close()

    def test_restarting_the_app(self, signed_in: Page, stack, unique: str):
        """What a deploy looks like from the outside. The card is in the
        database or it is nowhere."""
        title = f"Written before the deploy {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        stack.restart_the_app()

        signed_in.reload()
        signed_in.click("#nav a[href='#/work']")
        expect(card_named(signed_in, title)).to_be_visible()


class TestTheRestOfTheCardSurvives:
    """A title round-tripping is not much of a promise on its own."""

    def test_a_move_is_not_forgotten(self, signed_in: Page, unique: str):
        title = f"Moved then reloaded {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        card_named(signed_in, title).click()
        drawer = signed_in.locator("#drawer")
        drawer.locator(".field").filter(has_text="Status").locator("select").select_option(
            "WAITING"
        )
        drawer.locator("[aria-label='Close']").click()

        signed_in.reload()
        signed_in.click("#nav a[href='#/work']")
        expect(signed_in.locator("section.column[data-status='WAITING']")).to_contain_text(title)

    def test_a_priority_is_not_forgotten(self, signed_in: Page, unique: str):
        title = f"Urgent then reloaded {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        card_named(signed_in, title).click()
        drawer = signed_in.locator("#drawer")
        drawer.locator(".field").filter(has_text="Priority").locator("select").select_option(
            "URGENT"
        )
        drawer.locator("[aria-label='Close']").click()

        signed_in.reload()
        signed_in.click("#nav a[href='#/work']")
        expect(card_named(signed_in, title)).to_contain_text("Urgent")


class TestTheSessionSurvives:
    def test_a_restart_does_not_sign_everybody_out(self, signed_in: Page, stack):
        """Tokens are held server-side, so an app that kept them in memory would
        log every user out on every deploy."""
        stack.restart_the_app()

        signed_in.reload()
        expect(signed_in.locator(".greeting")).to_be_visible()
        expect(signed_in.locator("form.signin")).to_have_count(0)
