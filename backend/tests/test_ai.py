"""Job-advert extraction. §15 — a draft for the user to check, never a saved card."""

import pytest

ADVERT = """Nimbus Labs

Senior Research Engineer

Nimbus Labs is hiring a Senior Research Engineer to work on large scale language
model evaluation, joining a team of twelve researchers building open tooling for
the whole field.

Location: Berlin
Salary: EUR 90,000 - 120,000
This is a hybrid role, three days in the office.
Deadline: 30/11/2026

Requirements
- Strong Python and PyTorch
- Published research in NLP or ML
- Experience with distributed training

Nice to have
- Interpretability experience
- Open-source contributions
"""


@pytest.fixture
def extraction(client):
    response = client.post("/api/ai/extract-job-advert", json={"advert": ADVERT})
    assert response.status_code == 200, response.text
    return response.json()


class TestExtraction:
    def test_company_and_role(self, extraction):
        assert extraction["extracted"]["company"] == "Nimbus Labs"
        assert extraction["extracted"]["role"] == "Senior Research Engineer"

    def test_location_and_work_mode(self, extraction):
        assert extraction["extracted"]["location"] == "Berlin"
        assert extraction["extracted"]["workMode"] == "HYBRID"

    def test_salary_is_kept_as_written(self, extraction):
        """§11 — salaryText, not a parsed number. Adverts phrase it a hundred ways."""
        assert "90,000" in extraction["extracted"]["salaryText"]

    def test_deadline_is_normalised_to_a_date(self, extraction):
        assert extraction["extracted"]["applicationDeadline"] == "2026-11-30"

    def test_requirements_are_split_into_a_list(self, extraction):
        requirements = extraction["extracted"]["requirements"]
        assert len(requirements) == 3
        assert requirements[0] == "Strong Python and PyTorch"

    def test_nice_to_have_is_separate_from_requirements(self, extraction):
        assert len(extraction["extracted"]["niceToHave"]) == 2
        assert "Interpretability experience" in extraction["extracted"]["niceToHave"]

    def test_a_summary_is_offered(self, extraction):
        assert len(extraction["extracted"]["summary"]) > 40

    def test_tags_are_suggested(self, extraction):
        assert extraction["extracted"]["tags"]

    def test_nothing_is_missing_from_a_full_advert(self, extraction):
        assert extraction["missing"] == []
        assert extraction["confidence"] == "good"

    def test_fit_is_never_scored_automatically(self, extraction):
        """§15.2 — the app must not pretend to judge suitability."""
        assert "fit" not in extraction["extracted"]


class TestExtractionIsADraft:
    def test_nothing_is_persisted(self, client):
        """§15.3 — the preview step exists precisely so nothing is saved yet."""
        client.post("/api/ai/extract-job-advert", json={"advert": ADVERT})
        assert client.get("/api/cards").json() == []

    def test_a_partial_advert_says_what_is_missing(self, client):
        response = client.post(
            "/api/ai/extract-job-advert",
            json={
                "advert": (
                    "We are looking for someone to help with data work. "
                    "It is a varied position with a lot of independence and "
                    "plenty of room to grow into the role over time."
                )
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "role" in body["missing"] or "company" in body["missing"]
        assert body["confidence"] == "partial"


class TestExtractionFailure:
    def test_too_short_to_read_is_422(self, client):
        response = client.post("/api/ai/extract-job-advert", json={"advert": "too short"})
        assert response.status_code == 422

    def test_the_failure_message_is_shown_to_a_person(self, client):
        """§37 — never a generic 'something went wrong' when we know better."""
        response = client.post("/api/ai/extract-job-advert", json={"advert": "x"})
        message = response.json()["message"]
        assert message
        assert "something went wrong" not in message.lower()

    def test_an_empty_advert_is_rejected(self, client):
        assert client.post("/api/ai/extract-job-advert", json={"advert": ""}).status_code == 422

    def test_a_missing_advert_field_is_rejected(self, client):
        assert client.post("/api/ai/extract-job-advert", json={}).status_code == 422

    def test_the_rest_of_the_api_is_unaffected(self, client):
        """§27 — AI is isolated. If it fails, the Kanban still works."""
        client.post("/api/ai/extract-job-advert", json={"advert": "x"})
        assert client.get("/api/cards").status_code == 200
        assert client.post("/api/cards", json={"title": "Still fine", "area": "LEARNING"}).status_code == 201
