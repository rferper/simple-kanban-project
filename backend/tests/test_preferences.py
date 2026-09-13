"""Preferences. §20 — two fields, and no more."""


class TestReadingPreferences:
    def test_defaults_on_an_empty_database(self, client):
        response = client.get("/api/preferences")
        assert response.status_code == 200
        assert response.json() == {"displayName": "", "weeklyAvailableHours": None}

    def test_the_seed_sets_available_hours(self, seeded_client):
        assert seeded_client.get("/api/preferences").json()["weeklyAvailableHours"] == 18


class TestUpdatingPreferences:
    def test_setting_available_hours(self, client):
        updated = client.patch("/api/preferences", json={"weeklyAvailableHours": 18}).json()
        assert updated["weeklyAvailableHours"] == 18

    def test_setting_a_display_name(self, client):
        assert (
            client.patch("/api/preferences", json={"displayName": "Raquel"}).json()["displayName"]
            == "Raquel"
        )

    def test_a_partial_update_leaves_the_other_field_alone(self, client):
        client.patch("/api/preferences", json={"displayName": "Raquel", "weeklyAvailableHours": 20})
        updated = client.patch("/api/preferences", json={"weeklyAvailableHours": 12}).json()
        assert updated["displayName"] == "Raquel"
        assert updated["weeklyAvailableHours"] == 12

    def test_available_hours_can_be_cleared(self, client):
        """§5.4 — the capacity line is optional, and 'unset' is not the same as zero."""
        client.patch("/api/preferences", json={"weeklyAvailableHours": 18})
        cleared = client.patch("/api/preferences", json={"weeklyAvailableHours": None}).json()
        assert cleared["weeklyAvailableHours"] is None

    def test_half_hours_are_allowed(self, client):
        assert (
            client.patch("/api/preferences", json={"weeklyAvailableHours": 17.5}).json()[
                "weeklyAvailableHours"
            ]
            == 17.5
        )

    def test_the_change_is_persisted(self, client):
        client.patch("/api/preferences", json={"displayName": "Raquel"})
        assert client.get("/api/preferences").json()["displayName"] == "Raquel"


class TestPreferencesValidation:
    def test_negative_hours_are_rejected(self, client):
        assert (
            client.patch("/api/preferences", json={"weeklyAvailableHours": -1}).status_code == 422
        )

    def test_more_hours_than_a_week_holds_are_rejected(self, client):
        assert (
            client.patch("/api/preferences", json={"weeklyAvailableHours": 200}).status_code == 422
        )

    def test_zero_hours_is_allowed(self, client):
        assert (
            client.patch("/api/preferences", json={"weeklyAvailableHours": 0}).json()[
                "weeklyAvailableHours"
            ]
            == 0
        )

    def test_an_overlong_display_name_is_rejected(self, client):
        assert client.patch("/api/preferences", json={"displayName": "x" * 61}).status_code == 422

    def test_an_empty_patch_is_harmless(self, client):
        assert client.patch("/api/preferences", json={}).status_code == 200
