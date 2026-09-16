"""The dashboard answers the question the product exists to answer.

From `_docs/specs.md`: one dashboard over three areas, answering *what should I
work on today to maximise my chances of moving without neglecting my current
job?* §23 is the focus ranking that answers it and §22 is the workload that
keeps the answer honest about capacity.

The ranking and the arithmetic themselves are pure functions with their own
tests in `frontend/src/domain/`. What these check is that the answer reaches the
screen: a dashboard that computes a perfect focus list and renders an empty
panel is a broken product and a passing unit test.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from test_the_board import add_a_card, card_named


def unestimated(page: Page) -> int:
    """How many planned-but-unestimated tasks the week panel is owning up to."""
    page.click("#nav a[href='#/']")
    expect(panel(page, "This week")).to_be_visible()

    note = panel(page, "This week").locator(".workload-unestimated")
    if note.count() == 0:
        return 0

    found = re.search(r"\+\s*(\d+)\s+unestimated", note.first.inner_text())
    return int(found.group(1)) if found else 0


def panel(page: Page, title: str):
    """The panel with exactly this title.

    `filter(has_text=...)` is a case-insensitive substring over the whole
    panel, and both "Focus today" (in its caveat) and the settings page say
    "this week" somewhere. Matching the title exactly is the only way to mean
    one panel.
    """
    return page.locator(f".panel:has(.panel-title:text-is('{title}'))")


class TestItAnswersTheQuestion:
    def test_the_dashboard_is_the_front_door(self, signed_in: Page):
        expect(signed_in.locator(".greeting")).to_be_visible()

    def test_it_suggests_what_to_work_on(self, signed_in: Page):
        """§23. The panel exists and has picks in it — an empty one on a seeded
        board would mean the ranking never ran."""
        focus = panel(signed_in, "Focus today")
        expect(focus).to_be_visible()
        expect(focus.locator(".focus-item").first).to_be_visible()

    def test_each_suggestion_says_why_it_is_there(self, signed_in: Page):
        """§23 again, and the part that matters: a ranked list nobody trusts is
        a list nobody uses, so every pick carries its reason."""
        first = signed_in.locator(".focus-item").first
        expect(first.locator(".focus-title")).not_to_be_empty()
        expect(first.locator(".focus-meta")).not_to_be_empty()

    def test_all_three_areas_are_on_it(self, signed_in: Page):
        """The point of the dashboard is that the three are one view (§5)."""
        columns = signed_in.locator(".dash-col")
        expect(columns).to_have_count(3)
        expect(signed_in.locator(".dash-columns")).to_contain_text("Current Job")
        expect(signed_in.locator(".dash-columns")).to_contain_text("Job Search")
        expect(signed_in.locator(".dash-columns")).to_contain_text("Learning")


class TestTheWeek:
    def test_there_is_a_this_week_panel(self, signed_in: Page):
        """§22 — capacity, so that "what should I do today" is answerable
        against a real week rather than an infinite one."""
        expect(panel(signed_in, "This week")).to_be_visible()

    def test_planning_a_card_reaches_it(self, signed_in: Page, unique: str):
        """The whole §22 loop through the UI: mark a card for this week on one
        page, and the dashboard's workload has heard about it.

        The card is counted by the unestimated note rather than the hours,
        because a quick-added card has no estimate — and §22 is explicit that
        unestimated work is never hidden behind a clean total.
        """
        before = unestimated(signed_in)

        title = f"Planned this week {unique}"
        signed_in.click("#nav a[href='#/work']")
        add_a_card(signed_in, title)

        card_named(signed_in, title).click()
        drawer = signed_in.locator("#drawer")
        drawer.locator("label.check input[type=checkbox]").check()
        drawer.locator("[aria-label='Close']").click()

        signed_in.click("#nav a[href='#/']")
        expect(panel(signed_in, "This week")).to_be_visible()
        assert unestimated(signed_in) == before + 1


class TestSettingsFeedTheDashboard:
    def test_the_greeting_uses_the_display_name(self, signed_in: Page, unique: str):
        """Two settings is the whole of it (§26), and this is one of them
        actually doing something."""
        name = f"Rae {unique}"
        signed_in.click("#nav a[href='#/settings']")
        signed_in.fill("input[name=displayName]", name)
        signed_in.click("button[type=submit]")

        signed_in.click("#nav a[href='#/']")
        expect(signed_in.locator(".greeting")).to_contain_text(name)

    def test_available_hours_reach_the_week(self, signed_in: Page):
        """§22 — the capacity the workload is measured against."""
        signed_in.click("#nav a[href='#/settings']")
        signed_in.fill("input[name=weeklyAvailableHours]", "21")
        signed_in.click("button[type=submit]")

        signed_in.click("#nav a[href='#/']")
        expect(panel(signed_in, "This week")).to_contain_text("21")
