"""Job cards and their application details. §8, §11, §16.8."""

from tests.conftest import make_card, make_job


class TestCreatingJobCards:
    def test_a_job_search_card_always_has_job_details(self, client):
        card = make_card(client, area="JOB_SEARCH", title="Something")
        assert card["job"] is not None

    def test_job_details_default_sensibly(self, client):
        job = make_card(client, area="JOB_SEARCH", title="Something")["job"]

        assert job["company"] == ""
        assert job["role"] == ""
        assert job["workMode"] == "UNKNOWN"
        assert job["fit"] == "MEDIUM"
        assert job["outcome"] == "ACTIVE"
        assert job["requirements"] == []
        assert job["niceToHave"] == []
        assert job["applicationDeadline"] is None
        assert job["interviewDate"] is None
        assert job["relatedLearningCardIds"] == []

    def test_job_details_round_trip(self, client):
        card = make_job(
            client,
            company="Anthropic",
            role="Research Engineer",
            location="London",
            workMode="HYBRID",
            salaryText="Competitive",
            fit="DREAM",
            applicationDeadline="2026-11-30",
            interviewDate="2026-12-05",
            requirements=["Strong Python", "Published research"],
            niceToHave=["Interpretability"],
            cvVersion="cv-research-v3.pdf",
            contactName="Priya",
            contactDetails="priya@example.com",
            notes="Second round is a deep dive.",
            jobUrl="https://example.com/role",
        )
        job = card["job"]

        assert job["company"] == "Anthropic"
        assert job["role"] == "Research Engineer"
        assert job["workMode"] == "HYBRID"
        assert job["fit"] == "DREAM"
        assert job["applicationDeadline"] == "2026-11-30"
        assert job["interviewDate"] == "2026-12-05"
        assert job["requirements"] == ["Strong Python", "Published research"]
        assert job["cvVersion"] == "cv-research-v3.pdf"

    def test_job_cards_start_in_interesting(self, client):
        """§15.1 — where an imported advert lands."""
        assert make_job(client)["status"] == "INTERESTING"

    def test_job_details_on_a_non_job_card_are_rejected(self, client):
        response = client.post(
            "/api/cards",
            json={"title": "x", "area": "LEARNING", "job": {"company": "Anthropic"}},
        )
        assert response.status_code == 422

    def test_unknown_fit_is_rejected(self, client):
        response = client.post(
            "/api/cards", json={"title": "x", "area": "JOB_SEARCH", "job": {"fit": "PERFECT"}}
        )
        assert response.status_code == 422


class TestUpdatingJobDetails:
    def test_merges_rather_than_replaces(self, client):
        card = make_job(client, company="Anthropic", role="Research Engineer", location="London")

        updated = client.patch(f"/api/cards/{card['id']}/job", json={"location": "Remote"}).json()

        assert updated["job"]["location"] == "Remote"
        assert updated["job"]["company"] == "Anthropic"
        assert updated["job"]["role"] == "Research Engineer"

    def test_advancing_the_application_stage(self, client):
        """§30.5 — Preparing to Applied is a card update, not a job update."""
        card = make_job(client)
        moved = client.patch(f"/api/cards/{card['id']}", json={"status": "APPLIED"}).json()
        assert moved["status"] == "APPLIED"

    def test_an_interview_date_can_be_set_and_cleared(self, client):
        card = make_job(client)
        with_date = client.patch(
            f"/api/cards/{card['id']}/job", json={"interviewDate": "2026-09-18"}
        ).json()
        assert with_date["job"]["interviewDate"] == "2026-09-18"

        cleared = client.patch(f"/api/cards/{card['id']}/job", json={"interviewDate": None}).json()
        assert cleared["job"]["interviewDate"] is None

    def test_updated_at_advances(self, client):
        card = make_job(client)
        updated = client.patch(f"/api/cards/{card['id']}/job", json={"notes": "hi"}).json()
        assert updated["updatedAt"] >= card["updatedAt"]

    def test_links_cannot_be_written_directly(self, client):
        """The link endpoints own both ends; a job patch must not forge one."""
        card = make_job(client)
        response = client.patch(
            f"/api/cards/{card['id']}/job", json={"relatedLearningCardIds": ["made-up"]}
        )
        assert response.status_code == 422

    def test_a_non_job_card_is_409(self, client):
        card = make_card(client, area="LEARNING")
        response = client.patch(f"/api/cards/{card['id']}/job", json={"company": "x"})
        assert response.status_code == 409
        assert response.json()["message"]

    def test_unknown_id_is_404(self, client):
        assert client.patch("/api/cards/nope/job", json={"company": "x"}).status_code == 404


class TestArchiving:
    """§8.1, §16.8 — archiving is routine, reversible, and keeps everything."""

    def test_archiving_sets_the_outcome(self, client):
        card = make_job(client)
        archived = client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "REJECTED"}).json()
        assert archived["job"]["outcome"] == "REJECTED"

    def test_archiving_keeps_the_notes_and_the_stage(self, client):
        card = make_job(client, notes="Reuse this cover letter.")
        client.patch(f"/api/cards/{card['id']}", json={"status": "APPLIED"})

        archived = client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "REJECTED"}).json()

        assert archived["job"]["notes"] == "Reuse this cover letter."
        assert archived["status"] == "APPLIED"

    def test_an_archived_job_is_still_in_the_list(self, client):
        card = make_job(client)
        client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "WITHDRAWN"})
        assert card["id"] in [c["id"] for c in client.get("/api/cards").json()]

    def test_restoring_to_the_board(self, client):
        card = make_job(client)
        client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "REJECTED"})
        restored = client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "ACTIVE"}).json()
        assert restored["job"]["outcome"] == "ACTIVE"

    def test_every_outcome_in_the_vocabulary_is_accepted(self, client):
        card = make_job(client)
        for outcome in ["ACTIVE", "REJECTED", "WITHDRAWN", "ACCEPTED", "DECLINED"]:
            response = client.patch(f"/api/cards/{card['id']}/job", json={"outcome": outcome})
            assert response.status_code == 200, outcome

    def test_unknown_outcome_is_rejected(self, client):
        card = make_job(client)
        response = client.patch(f"/api/cards/{card['id']}/job", json={"outcome": "FAILED"})
        assert response.status_code == 422
