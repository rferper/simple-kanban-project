"""The loop the product is for: put work on a board, and move it.

§13 — the title is the only required field and there is no wizard, so the whole
add-a-card journey is one input and Enter. §14 — moving a card changes its
status. These run through the drawer rather than dragging: a drag is one of two
ways to do it (§14 keeps both), and it is the one a keyboard user never takes.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def column(page: Page, status: str):
    return page.locator(f"section.column[data-status='{status}']")


def card_named(page: Page, title: str):
    return page.locator("article.card").filter(has_text=title)


def add_a_card(page: Page, title: str, *, status: str = "BACKLOG") -> None:
    """The §13 journey: open the quick-add, type a title, submit."""
    page.click(f"[data-quick-add='{status}'] .add-trigger")
    page.fill(f"[data-quick-add='{status}'] input[name=title]", title)
    page.press(f"[data-quick-add='{status}'] input[name=title]", "Enter")
    expect(card_named(page, title)).to_be_visible()


class TestGettingToABoard:
    def test_the_nav_reaches_current_job(self, signed_in: Page):
        signed_in.click("#nav a[href='#/work']")
        expect(signed_in.locator("h1.page-title")).to_contain_text("Current Job")

    def test_the_nav_reaches_job_search(self, signed_in: Page):
        signed_in.click("#nav a[href='#/jobs']")
        expect(signed_in.locator("h1.page-title")).to_contain_text("Job Search")

    def test_the_nav_reaches_learning(self, signed_in: Page):
        signed_in.click("#nav a[href='#/learning']")
        expect(signed_in.locator("h1.page-title")).to_contain_text("Learning")

    def test_a_board_has_the_columns_the_spec_names(self, signed_in: Page):
        """§7.1. The columns are the vocabulary of the product, not decoration."""
        signed_in.click("#nav a[href='#/work']")
        # `all_inner_texts` does not wait for anything, so wait for the board
        # first — otherwise this reads an empty list off the dashboard and the
        # failure blames the column names.
        expect(signed_in.locator(".column").first).to_be_visible()

        # `text_content`, not `inner_text`: the stylesheet upper-cases these, and
        # what is being checked is the product's vocabulary, not its typography.
        names = signed_in.locator(".column .column-name").all_text_contents()
        assert names == ["Backlog", "This Week", "In Progress", "Waiting", "Done"]


class TestAddingACard:
    def test_a_new_card_appears_on_the_board(self, signed_in: Page, unique: str):
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, f"Write the rebuttal {unique}")

        expect(column(signed_in, "BACKLOG")).to_contain_text(f"Write the rebuttal {unique}")

    def test_the_column_count_follows(self, signed_in: Page, unique: str):
        signed_in.click("#nav a[href='#/work']")
        before = int(column(signed_in, "BACKLOG").locator(".badge-count").inner_text())

        add_a_card(signed_in, f"Another task {unique}")

        expect(column(signed_in, "BACKLOG").locator(".badge-count")).to_have_text(str(before + 1))

    def test_two_in_a_row_is_two_titles_and_nothing_else(self, signed_in: Page, unique: str):
        """§13 — no wizard. Emptying your head onto the board should not mean a
        dialog per thought.

        Note what this does *not* claim: the quick-add collapses back to its
        button after each card, because the board re-renders on the new state.
        `renderQuickAdd` refocuses the input, which that re-render then throws
        away — harmless, and not a promise §13 makes.
        """
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, f"First {unique}")
        add_a_card(signed_in, f"Second {unique}")

        expect(column(signed_in, "BACKLOG")).to_contain_text(f"First {unique}")
        expect(column(signed_in, "BACKLOG")).to_contain_text(f"Second {unique}")
        # `#modal` is always in index.html; what "no wizard" means is that it
        # never opened.
        expect(signed_in.locator("#modal")).to_be_hidden()


class TestMovingACard:
    def test_the_drawer_opens_on_a_card(self, signed_in: Page, unique: str):
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, f"Open me {unique}")

        card_named(signed_in, f"Open me {unique}").click()
        expect(signed_in.locator("#drawer")).to_be_visible()
        expect(signed_in.locator("#drawer")).to_contain_text(f"Open me {unique}")

    def test_changing_the_status_moves_it(self, signed_in: Page, unique: str):
        title = f"Move me {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        card_named(signed_in, title).click()
        drawer = signed_in.locator("#drawer")
        drawer.locator(".field").filter(has_text="Status").locator("select").select_option(
            "IN_PROGRESS"
        )
        drawer.locator("[aria-label='Close']").click()

        expect(column(signed_in, "IN_PROGRESS")).to_contain_text(title)
        expect(column(signed_in, "BACKLOG")).not_to_contain_text(title)

    def test_a_card_can_be_marked_done(self, signed_in: Page, unique: str):
        """The done column is the one the dashboard stops counting against you."""
        title = f"Finish me {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        card_named(signed_in, title).click()
        drawer = signed_in.locator("#drawer")
        drawer.locator(".field").filter(has_text="Status").locator("select").select_option("DONE")
        drawer.locator("[aria-label='Close']").click()

        expect(column(signed_in, "DONE")).to_contain_text(title)
        expect(card_named(signed_in, title)).to_have_class("card is-done")


class TestOnAPhone:
    """§ — "a responsive web Kanban". The three areas on a phone is the case the
    layout is actually for: this is an app for someone job-hunting on a train."""

    def test_the_board_is_usable_at_phone_width(self, signed_in: Page, unique: str):
        signed_in.set_viewport_size({"width": 390, "height": 844})
        signed_in.click("#nav a[href='#/work']")

        expect(signed_in.locator("h1.page-title")).to_be_visible()
        expect(signed_in.locator(".column").first).to_be_visible()

    def test_nothing_overflows_sideways(self, signed_in: Page):
        """A horizontal scrollbar on the page — as opposed to inside the board —
        is the usual sign a layout has given up at this width."""
        signed_in.set_viewport_size({"width": 390, "height": 844})
        signed_in.click("#nav a[href='#/work']")
        expect(signed_in.locator(".column").first).to_be_visible()

        overflow = signed_in.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, f"the page scrolls {overflow}px sideways at 390px wide"
