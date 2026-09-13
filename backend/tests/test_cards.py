"""The shared card model: create, read, update, delete. §10, §13, §14, §29."""

from tests.conftest import make_card, make_job, make_learning


class TestListCards:
    def test_empty_database_returns_an_empty_list(self, client):
        response = client.get("/api/cards")
        assert response.status_code == 200
        assert response.json() == []

    def test_seeded_database_returns_all_three_areas(self, seeded_client):
        cards = seeded_client.get("/api/cards").json()
        areas = {card["area"] for card in cards}
        assert areas == {"CURRENT_JOB", "JOB_SEARCH", "LEARNING"}
        assert len(cards) == 12

    def test_seed_links_are_two_way(self, seeded_client):
        cards = {c["id"]: c for c in seeded_client.get("/api/cards").json()}
        learning = cards["seed-system-design"]
        job = cards["seed-job-anthropic"]
        assert job["id"] in learning["relatedJobCardIds"]
        assert learning["id"] in job["job"]["relatedLearningCardIds"]


class TestCreateCard:
    def test_title_and_area_are_enough(self, client):
        """§13 — no wizard. Everything else is optional."""
        card = make_card(client, title="Finish rebuttal")

        assert card["title"] == "Finish rebuttal"
        assert card["area"] == "CURRENT_JOB"
        assert card["id"]
        assert card["createdAt"]
        assert card["updatedAt"]

    def test_defaults_are_filled_in(self, client):
        card = make_card(client)

        assert card["status"] == "BACKLOG"
        assert card["priority"] == "MEDIUM"
        assert card["description"] == ""
        assert card["deadline"] is None
        assert card["estimatedHours"] is None
        assert card["plannedThisWeek"] is False
        assert card["tags"] == []
        assert card["subtasks"] == []
        assert card["completedAt"] is None

    def test_each_area_gets_its_own_first_column(self, client):
        assert make_card(client, area="CURRENT_JOB")["status"] == "BACKLOG"
        assert make_card(client, area="JOB_SEARCH")["status"] == "INTERESTING"
        assert make_card(client, area="LEARNING")["status"] == "IDEAS"

    def test_a_status_can_be_chosen(self, client):
        assert make_card(client, status="IN_PROGRESS")["status"] == "IN_PROGRESS"

    def test_full_payload_round_trips(self, client):
        card = make_card(
            client,
            title="Run final experiment",
            description="The last ablation.",
            status="IN_PROGRESS",
            priority="HIGH",
            deadline="2026-11-30",
            estimatedHours=4,
            plannedThisWeek=True,
            tags=["research", "cluster"],
            subtasks=[{"title": "Queue the job"}, {"title": "Check the logs", "done": True}],
        )

        assert card["deadline"] == "2026-11-30"
        assert card["estimatedHours"] == 4
        assert card["plannedThisWeek"] is True
        assert card["tags"] == ["research", "cluster"]
        assert [s["title"] for s in card["subtasks"]] == ["Queue the job", "Check the logs"]
        assert [s["done"] for s in card["subtasks"]] == [False, True]
        assert all(s["id"] for s in card["subtasks"]), "subtasks need ids assigned"

    def test_an_appearing_card_is_in_the_list(self, client):
        card = make_card(client)
        assert card["id"] in [c["id"] for c in client.get("/api/cards").json()]

    def test_learning_cards_carry_a_link_list(self, client):
        assert make_learning(client)["relatedJobCardIds"] == []

    def test_non_job_cards_have_no_job_object(self, client):
        assert make_card(client).get("job") is None


class TestCreateCardValidation:
    """§29 — forgiving, but not silent."""

    def test_blank_title_is_rejected(self, client):
        assert client.post("/api/cards", json={"title": "   ", "area": "LEARNING"}).status_code == 422

    def test_missing_title_is_rejected(self, client):
        assert client.post("/api/cards", json={"area": "LEARNING"}).status_code == 422

    def test_overlong_title_is_rejected(self, client):
        response = client.post("/api/cards", json={"title": "x" * 201, "area": "LEARNING"})
        assert response.status_code == 422

    def test_a_200_character_title_is_allowed(self, client):
        response = client.post("/api/cards", json={"title": "x" * 200, "area": "LEARNING"})
        assert response.status_code == 201

    def test_unknown_area_is_rejected(self, client):
        assert client.post("/api/cards", json={"title": "x", "area": "HOLIDAY"}).status_code == 422

    def test_negative_estimate_is_rejected(self, client):
        response = client.post(
            "/api/cards", json={"title": "x", "area": "LEARNING", "estimatedHours": -1}
        )
        assert response.status_code == 422

    def test_absurd_estimate_is_rejected(self, client):
        response = client.post(
            "/api/cards", json={"title": "x", "area": "LEARNING", "estimatedHours": 500}
        )
        assert response.status_code == 422

    def test_zero_estimate_is_allowed(self, client):
        assert make_card(client, estimatedHours=0)["estimatedHours"] == 0

    def test_half_hour_estimate_is_allowed(self, client):
        assert make_card(client, estimatedHours=1.5)["estimatedHours"] == 1.5

    def test_a_status_from_another_board_is_rejected(self, client):
        """A learning card cannot sit in the Current Job board's WAITING column."""
        response = client.post(
            "/api/cards", json={"title": "x", "area": "LEARNING", "status": "WAITING"}
        )
        assert response.status_code == 422

    def test_the_error_carries_a_readable_message(self, client):
        response = client.post("/api/cards", json={"title": "", "area": "LEARNING"})
        assert response.status_code == 422
        assert response.json()["message"]


class TestGetCard:
    def test_returns_the_card(self, client):
        card = make_card(client, title="Review journal paper")
        fetched = client.get(f"/api/cards/{card['id']}")
        assert fetched.status_code == 200
        assert fetched.json() == card

    def test_unknown_id_is_404(self, client):
        response = client.get("/api/cards/nope")
        assert response.status_code == 404
        assert response.json()["message"]


class TestUpdateCard:
    def test_changes_only_what_is_sent(self, client):
        card = make_card(client, title="Original", description="Keep me", priority="HIGH")

        updated = client.patch(f"/api/cards/{card['id']}", json={"title": "Renamed"}).json()

        assert updated["title"] == "Renamed"
        assert updated["description"] == "Keep me"
        assert updated["priority"] == "HIGH"

    def test_moving_between_columns(self, client):
        """§14 — the drag-and-drop path."""
        card = make_card(client)
        updated = client.patch(f"/api/cards/{card['id']}", json={"status": "IN_PROGRESS"}).json()
        assert updated["status"] == "IN_PROGRESS"

    def test_planned_this_week_toggle(self, client):
        """§10.5 — what the weekly workload is built from."""
        card = make_card(client)
        on = client.patch(f"/api/cards/{card['id']}", json={"plannedThisWeek": True}).json()
        assert on["plannedThisWeek"] is True
        off = client.patch(f"/api/cards/{card['id']}", json={"plannedThisWeek": False}).json()
        assert off["plannedThisWeek"] is False

    def test_an_estimate_can_be_cleared(self, client):
        card = make_card(client, estimatedHours=3)
        updated = client.patch(f"/api/cards/{card['id']}", json={"estimatedHours": None}).json()
        assert updated["estimatedHours"] is None

    def test_a_deadline_can_be_cleared(self, client):
        card = make_card(client, deadline="2026-01-01")
        updated = client.patch(f"/api/cards/{card['id']}", json={"deadline": None}).json()
        assert updated["deadline"] is None

    def test_subtasks_can_be_replaced(self, client):
        card = make_card(client, subtasks=[{"title": "One"}])
        updated = client.patch(
            f"/api/cards/{card['id']}",
            json={"subtasks": [{"title": "One", "done": True}, {"title": "Two"}]},
        ).json()
        assert [s["title"] for s in updated["subtasks"]] == ["One", "Two"]
        assert updated["subtasks"][0]["done"] is True

    def test_updated_at_advances(self, client):
        card = make_card(client)
        updated = client.patch(f"/api/cards/{card['id']}", json={"title": "Changed"}).json()
        assert updated["updatedAt"] >= card["updatedAt"]
        assert updated["createdAt"] == card["createdAt"]

    def test_unknown_id_is_404(self, client):
        assert client.patch("/api/cards/nope", json={"title": "x"}).status_code == 404

    def test_a_status_from_another_board_is_rejected(self, client):
        card = make_card(client, area="LEARNING")
        response = client.patch(f"/api/cards/{card['id']}", json={"status": "WAITING"})
        assert response.status_code == 422

    def test_blank_title_is_rejected(self, client):
        card = make_card(client)
        assert client.patch(f"/api/cards/{card['id']}", json={"title": " "}).status_code == 422

    def test_an_empty_patch_is_harmless(self, client):
        card = make_card(client)
        response = client.patch(f"/api/cards/{card['id']}", json={})
        assert response.status_code == 200
        assert response.json()["title"] == card["title"]


class TestCompletion:
    """§12.1 — completedAt is the server's business, not the client's."""

    def test_entering_done_stamps_completed_at(self, client):
        card = make_card(client)
        done = client.patch(f"/api/cards/{card['id']}", json={"status": "DONE"}).json()
        assert done["completedAt"] is not None

    def test_leaving_done_clears_completed_at(self, client):
        card = make_card(client)
        client.patch(f"/api/cards/{card['id']}", json={"status": "DONE"})
        reopened = client.patch(f"/api/cards/{card['id']}", json={"status": "BACKLOG"}).json()
        assert reopened["completedAt"] is None

    def test_each_area_has_its_own_done_column(self, client):
        learning = make_card(client, area="LEARNING")
        done = client.patch(f"/api/cards/{learning['id']}", json={"status": "DONE"}).json()
        assert done["completedAt"] is not None

        job = make_job(client)
        offer = client.patch(f"/api/cards/{job['id']}", json={"status": "OFFER"}).json()
        assert offer["completedAt"] is not None

    def test_other_columns_do_not_stamp_it(self, client):
        card = make_card(client)
        moved = client.patch(f"/api/cards/{card['id']}", json={"status": "WAITING"}).json()
        assert moved["completedAt"] is None


class TestDeleteCard:
    def test_deletes(self, client):
        card = make_card(client)
        assert client.delete(f"/api/cards/{card['id']}").status_code == 204
        assert client.get(f"/api/cards/{card['id']}").status_code == 404

    def test_it_leaves_the_list(self, client):
        card = make_card(client)
        make_card(client, title="Survivor")
        client.delete(f"/api/cards/{card['id']}")
        remaining = client.get("/api/cards").json()
        assert [c["title"] for c in remaining] == ["Survivor"]

    def test_unknown_id_is_404(self, client):
        assert client.delete("/api/cards/nope").status_code == 404

    def test_deleting_a_job_unlinks_it_from_learning_cards(self, client):
        job = make_job(client)
        learning = make_learning(client)
        client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")

        client.delete(f"/api/cards/{job['id']}")

        refreshed = client.get(f"/api/cards/{learning['id']}").json()
        assert refreshed["relatedJobCardIds"] == []

    def test_deleting_a_learning_card_unlinks_it_from_jobs(self, client):
        job = make_job(client)
        learning = make_learning(client)
        client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")

        client.delete(f"/api/cards/{learning['id']}")

        refreshed = client.get(f"/api/cards/{job['id']}").json()
        assert refreshed["job"]["relatedLearningCardIds"] == []
