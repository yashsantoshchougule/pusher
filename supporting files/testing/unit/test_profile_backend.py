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
        assert data["user_key"] == "default_user"
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
        res = client.get("/api/profile")
        assert res.status_code == 200
        data = res.json()
        assert data["full_name"] == "Test Benchmark Lead"
        assert data["username"] == "benchmark_pro"
        assert data["default_ram_ceiling_mb"] == 750

    def test_custom_user_key_isolation(self, client):
        """Confirm requests with distinct X-User-Key get independent profile state."""
        headers = {"X-User-Key": "usr_isolated_99"}
        # Initial GET creates or returns profile for usr_isolated_99
        res = client.get("/api/profile", headers=headers)
        assert res.status_code == 200
        assert res.json()["user_key"] == "usr_isolated_99"

        # Update profile for usr_isolated_99
        res_put = client.put(
            "/api/profile",
            headers=headers,
            json={"full_name": "Isolated Architect", "username": "isolated_99"}
        )
        assert res_put.status_code == 200
        assert res_put.json()["full_name"] == "Isolated Architect"

        # Ensure default_user profile remains untouched
        default_res = client.get("/api/profile")
        assert default_res.json()["user_key"] == "default_user"
        assert default_res.json()["full_name"] == "Test Benchmark Lead"

    def test_ram_ceiling_bounds_validation(self, client):
        """Confirm RAM ceiling below 50 MB is rejected with 422 validation error."""
        res = client.put("/api/profile", json={"default_ram_ceiling_mb": 10})
        assert res.status_code == 422
