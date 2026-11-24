"""
Unit Tests for User Profile & SQLite Persistence (Stages 1-5 + Profile)
Tests GET/PUT /api/profile, user_key isolation, and SQLite persistence in backend/pusher_runs.db.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import db_get_profile, db_save_profile, get_db_connection


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestUserProfilePersistence:

    def test_get_profile_returns_default_profile(self, client):
        """Confirm GET /api/profile returns the default seeded profile from SQLite."""
        res = client.get("/api/profile")
        assert res.status_code == 200
        data = res.json()
        assert data["user_key"] == "default_test_user"
        assert "email" in data
        assert "full_name" in data
        assert "username" in data
        assert "default_ram_ceiling_mb" in data
        assert data["default_ram_ceiling_mb"] >= 50

    def test_put_profile_updates_and_persists(self, client):
        """Confirm PUT /api/profile updates attributes and returns updated profile."""
        payload = {
            "full_name": "Test Benchmark Lead",
            "username": "benchmark_pro",
            "role_title": "Staff Reliability Engineer",
            "organization": "Pusher Test Division",
            "github_username": "pusher-test-bot",
            "default_ram_ceiling_mb": 750,
            "bio_notes": "Automated verification test notes.",
        }
        res = client.put("/api/profile", json=payload)
        assert res.status_code == 200
        updated = res.json()
        assert updated["full_name"] == "Test Benchmark Lead"
        assert updated["username"] == "benchmark_pro"
        assert updated["role_title"] == "Staff Reliability Engineer"
        assert updated["organization"] == "Pusher Test Division"
        assert updated["github_username"] == "pusher-test-bot"
        assert updated["default_ram_ceiling_mb"] == 750
        assert updated["bio_notes"] == "Automated verification test notes."

    def test_subsequent_get_reflects_updated_profile(self, client):
        """Confirm subsequent GET /api/profile retrieves the newly persisted attributes from SQLite."""
        assert client.put("/api/profile", json={
            "full_name": "Test Benchmark Lead", "username": "benchmark_pro", "default_ram_ceiling_mb": 750,
        }).status_code == 200
        res = client.get("/api/profile")
        assert res.status_code == 200
        data = res.json()
        assert data["full_name"] == "Test Benchmark Lead"
        assert data["username"] == "benchmark_pro"
        assert data["default_ram_ceiling_mb"] == 750

    def test_explicit_account_key_cannot_override_the_session(self, client):
        response = client.put("/api/profile?user_key=other", headers={"X-User-Key": "other"},
                              json={"full_name": "Current operator"})
        assert response.status_code == 200
        assert response.json()["user_key"] == "default_test_user"
        assert db_get_profile("other") is None
        assert client.get("/api/profile").json()["full_name"] == "Current operator"

    def test_partial_update_preserves_omitted_fields_and_clears_explicit_text(self, client):
        initial = client.put("/api/profile", json={
            "full_name": "Before",
            "organization": "Fixture team",
            "bio_notes": "Remove this",
            "default_ram_ceiling_mb": 750,
        })
        assert initial.status_code == 200

        updated = client.put("/api/profile", json={"full_name": "After", "bio_notes": ""})
        assert updated.status_code == 200
        for profile in (updated.json(), client.get("/api/profile").json()):
            assert profile["full_name"] == "After"
            assert profile["organization"] == "Fixture team"
            assert profile["default_ram_ceiling_mb"] == 750
            assert profile["bio_notes"] == ""
            assert profile["email"] == initial.json()["email"]

    def test_ram_ceiling_bounds_validation(self, client):
        """Confirm RAM ceiling below 50 MB is rejected with 422 validation error."""
        res = client.put("/api/profile", json={"default_ram_ceiling_mb": 10})
        assert res.status_code == 422
