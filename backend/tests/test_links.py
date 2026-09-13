"""Job ↔ learning links. §9.3 — the relationship that keeps the Learning board honest."""

from tests.conftest import make_card, make_job, make_learning


class TestLinking:
    def test_linking_updates_both_ends(self, client):
        job = make_job(client)
        learning = make_learning(client)

        response = client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")
        assert response.status_code == 200

        returned_learning, returned_job = response.json()
        assert returned_learning["id"] == learning["id"]
        assert returned_job["id"] == job["id"]
        assert job["id"] in returned_learning["relatedJobCardIds"]
        assert learning["id"] in returned_job["job"]["relatedLearningCardIds"]

    def test_the_link_is_persisted(self, client):
        job = make_job(client)
        learning = make_learning(client)
        client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")

        assert job["id"] in client.get(f"/api/cards/{learning['id']}").json()["relatedJobCardIds"]
        assert (
            learning["id"]
            in client.get(f"/api/cards/{job['id']}").json()["job"]["relatedLearningCardIds"]
        )

    def test_linking_twice_does_not_duplicate(self, client):
        job = make_job(client)
        learning = make_learning(client)

        client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")
        second = client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")

        assert second.status_code == 200
        assert second.json()[0]["relatedJobCardIds"] == [job["id"]]

    def test_one_learning_card_can_serve_several_roles(self, client):
        """§9.3 — 'System design' is relevant for Anthropic and DeepMind both."""
        anthropic = make_job(client, company="Anthropic")
        deepmind = make_job(client, company="DeepMind")
        learning = make_learning(client)

        client.put(f"/api/learning/{learning['id']}/jobs/{anthropic['id']}")
        client.put(f"/api/learning/{learning['id']}/jobs/{deepmind['id']}")

        refreshed = client.get(f"/api/cards/{learning['id']}").json()
        assert set(refreshed["relatedJobCardIds"]) == {anthropic["id"], deepmind["id"]}

    def test_one_role_can_have_several_learning_cards(self, client):
        job = make_job(client)
        design = make_learning(client, "System design")
        leetcode = make_learning(client, "LeetCode arrays")

        client.put(f"/api/learning/{design['id']}/jobs/{job['id']}")
        client.put(f"/api/learning/{leetcode['id']}/jobs/{job['id']}")

        refreshed = client.get(f"/api/cards/{job['id']}").json()
        assert set(refreshed["job"]["relatedLearningCardIds"]) == {design["id"], leetcode["id"]}


class TestUnlinking:
    def test_unlinking_clears_both_ends(self, client):
        job = make_job(client)
        learning = make_learning(client)
        client.put(f"/api/learning/{learning['id']}/jobs/{job['id']}")

        response = client.delete(f"/api/learning/{learning['id']}/jobs/{job['id']}")
        assert response.status_code == 200

        returned_learning, returned_job = response.json()
        assert returned_learning["relatedJobCardIds"] == []
        assert returned_job["job"]["relatedLearningCardIds"] == []

    def test_unlinking_what_was_never_linked_is_fine(self, client):
        job = make_job(client)
        learning = make_learning(client)
        assert client.delete(f"/api/learning/{learning['id']}/jobs/{job['id']}").status_code == 200

    def test_unlinking_leaves_other_links_alone(self, client):
        anthropic = make_job(client, company="Anthropic")
        deepmind = make_job(client, company="DeepMind")
        learning = make_learning(client)
        client.put(f"/api/learning/{learning['id']}/jobs/{anthropic['id']}")
        client.put(f"/api/learning/{learning['id']}/jobs/{deepmind['id']}")

        client.delete(f"/api/learning/{learning['id']}/jobs/{anthropic['id']}")

        refreshed = client.get(f"/api/cards/{learning['id']}").json()
        assert refreshed["relatedJobCardIds"] == [deepmind["id"]]


class TestLinkValidation:
    def test_unknown_learning_card_is_404(self, client):
        job = make_job(client)
        assert client.put(f"/api/learning/nope/jobs/{job['id']}").status_code == 404

    def test_unknown_job_card_is_404(self, client):
        learning = make_learning(client)
        assert client.put(f"/api/learning/{learning['id']}/jobs/nope").status_code == 404

    def test_the_learning_side_must_be_a_learning_card(self, client):
        job = make_job(client)
        task = make_card(client, area="CURRENT_JOB")
        response = client.put(f"/api/learning/{task['id']}/jobs/{job['id']}")
        assert response.status_code == 409
        assert response.json()["message"]

    def test_the_job_side_must_be_a_job_card(self, client):
        learning = make_learning(client)
        task = make_card(client, area="CURRENT_JOB")
        response = client.put(f"/api/learning/{learning['id']}/jobs/{task['id']}")
        assert response.status_code == 409

    def test_a_card_cannot_be_linked_to_itself(self, client):
        learning = make_learning(client)
        response = client.put(f"/api/learning/{learning['id']}/jobs/{learning['id']}")
        assert response.status_code == 409
