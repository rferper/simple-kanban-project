"""Getting in, and staying in.

Every endpoint but login needs a token, so this is the whole app until there is
one (§10). What only a browser can check: that the form works, that a refusal
reads like the product rather than a stack trace, and that a session survives a
reload — which is the difference between a usable app and one that logs you out
every time you press F5.
"""

from __future__ import annotations

from conftest import DEMO_EMAIL, DEMO_PASSWORD, sign_in_through_the_form
from playwright.sync_api import Page, expect


class TestTheGate:
    def test_the_sign_in_page_is_what_you_get(self, page: Page, base_url: str):
        page.goto("/")
        expect(page.locator("form.signin")).to_be_visible()

    def test_the_board_is_not_behind_it(self, page: Page, base_url: str):
        """Not merely hidden — the nav is not rendered at all until there is a
        session, so there is nothing to click your way into."""
        page.goto("/")
        expect(page.locator("#nav a")).to_have_count(0)
        expect(page.locator(".board")).to_have_count(0)

    def test_a_deep_link_does_not_get_you_in(self, page: Page, base_url: str):
        """Routing is hash-based, so the URL is guessable. §10 is not."""
        page.goto("/#/jobs")
        expect(page.locator("form.signin")).to_be_visible()
        expect(page.locator(".board")).to_have_count(0)


class TestARefusal:
    def test_a_wrong_password_says_so_and_stays_put(self, page: Page, base_url: str):
        page.goto("/")
        page.fill("form.signin input[name=email]", DEMO_EMAIL)
        page.fill("form.signin input[name=password]", "not the password")
        page.click("button.signin-submit")

        expect(page.locator("form.signin .notice-warn")).to_be_visible()
        expect(page.locator("form.signin")).to_be_visible()

    def test_the_message_is_for_a_person(self, page: Page, base_url: str):
        """§37 — what the API says is written to be shown verbatim, so a status
        code or a schema dump reaching the screen is the failure."""
        page.goto("/")
        page.fill("form.signin input[name=email]", DEMO_EMAIL)
        page.fill("form.signin input[name=password]", "not the password")
        page.click("button.signin-submit")

        message = page.locator("form.signin .notice-warn").inner_text().strip()
        assert message, "a refusal with no message is a dead end"
        assert "401" not in message, "a status code is not an explanation"
        assert not {"{", "[", "<"} & set(message), (
            f"that looks like a dump, not a sentence: {message}"
        )
        assert message.endswith("."), f"not written as a sentence: {message}"

    def test_an_unknown_email_looks_the_same(self, page: Page, base_url: str):
        """Otherwise this endpoint becomes a way to discover who has an account."""
        page.goto("/")
        page.fill("form.signin input[name=email]", "nobody@example.com")
        page.fill("form.signin input[name=password]", DEMO_PASSWORD)
        page.click("button.signin-submit")

        expect(page.locator("form.signin .notice-warn")).to_be_visible()


class TestGettingIn:
    def test_the_demo_account_reaches_the_board(self, page: Page, base_url: str):
        sign_in_through_the_form(page)
        expect(page.locator("form.signin")).to_have_count(0)
        expect(page.locator(".greeting")).to_be_visible()

    def test_all_three_areas_are_offered(self, signed_in: Page):
        """Current Job, Job Search, Learning — the product is the three of them
        together, so a nav missing one is a broken product, not a broken link."""
        nav = signed_in.locator("#nav")
        expect(nav.get_by_text("Current Job")).to_be_visible()
        expect(nav.get_by_text("Job Search")).to_be_visible()
        expect(nav.get_by_text("Learning")).to_be_visible()

    def test_the_session_survives_a_reload(self, signed_in: Page):
        """The token lives in localStorage for exactly this reason."""
        signed_in.reload()
        expect(signed_in.locator(".greeting")).to_be_visible()
        expect(signed_in.locator("form.signin")).to_have_count(0)


class TestGettingOut:
    def test_signing_out_returns_you_to_the_form(self, signed_in: Page):
        signed_in.click(".nav-signout")
        expect(signed_in.locator("form.signin")).to_be_visible()

    def test_and_a_reload_does_not_bring_you_back(self, signed_in: Page):
        """Logging out has to mean something — the token is revoked server-side,
        not merely forgotten by this tab."""
        signed_in.click(".nav-signout")
        expect(signed_in.locator("form.signin")).to_be_visible()

        signed_in.reload()
        expect(signed_in.locator("form.signin")).to_be_visible()
